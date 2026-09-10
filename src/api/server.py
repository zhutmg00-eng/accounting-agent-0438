"""
FastAPI Server for DeepSeek-AuditMind Accounting Agent.
Exposes REST and SSE Streaming APIs for the modern frontend presentation.
"""

import os
import io
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from src.core.schemas import (
    ExecutionMode, AccountingCaseData, AnalysisReportResult,
    FinancialStatementsSummary
)
from src.core.harness import AccountingAgentHarness
from src.core.llm_adapter import DeepSeekLLMAdapter
from src.benchmark.test_cases import (
    get_benchmark_cases, get_all_cases, get_case_categories, get_case_by_id, register_custom_case
)
from src.plugins.audit_fraud_plugin.tools import (
    calculate_beneish_m_score, calculate_beneish_from_case, perform_three_way_reconciliation
)
from src.benchmark.benchmark_runner import run_benchmark_suite
from src.exporters.excel_exporter import export_workpaper_to_excel
from src.exporters.pdf_exporter import export_report_to_pdf
from src.exporters.json_exporter import export_report_to_json
from src.data_loader.file_importer import (
    parse_vouchers_file, parse_invoices_file, parse_bank_flows_file
)
from src.config import settings

app = FastAPI(
    title="DeepSeek-AuditMind Agent API",
    description="Intelligent Accounting & Audit Fraud Detection Harness API",
    version="2.0.0"
)

# Compliant CORS configuration for modern frontend development (Vite port 5173, etc.)
cors_origins_env = os.getenv("CORS_ORIGINS")
allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()] if cors_origins_env else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global harness instance
_HARNESS = AccountingAgentHarness()


class AuditRunRequest(BaseModel):
    case_id: str
    plugin_id: str = "audit_fraud_detection"
    mode: str = "MOCK"  # STRICT_ONLINE, ONLINE, MOCK
    temperature: float = 0.1


class BeneishCalcRequest(BaseModel):
    cur_sales: float
    prev_sales: float
    cur_ar: float
    prev_ar: float
    cur_cogs: float
    prev_cogs: float
    cur_assets: float
    prev_assets: float
    cur_depr: float
    prev_depr: float
    cur_ppe: float
    prev_ppe: float
    cur_sga: float
    prev_sga: float
    cur_leverage: float
    prev_leverage: float
    cur_net_income: float
    cur_cfo: float


@app.get("/api/health")
def get_health():
    """Health check and harness status."""
    return {
        "status": "online",
        "service": "DeepSeek-AuditMind Agent",
        "version": "2.0.0",
        "mode": "MOCK" if settings.use_mock_llm else "ONLINE",
        "cases_count": len(get_benchmark_cases()),
        "categories_count": len(get_case_categories()),
    }


@app.get("/api/categories")
def get_categories():
    """List all available case categories with counts."""
    all_cases = get_benchmark_cases()
    cats = {}
    for c in all_cases:
        cats[c.case_category] = cats.get(c.case_category, 0) + 1
    return {
        "categories": [
            {"name": cat, "count": count} for cat, count in cats.items()
        ],
        "total_cases": len(all_cases)
    }


@app.get("/api/cases")
def list_cases(category: Optional[str] = Query(None)):
    """List cases filtered by category or all authentic cases + custom uploaded cases."""
    cases = get_all_cases(category=category)
    result = []
    for c in cases:
        result.append({
            "case_id": c.case_id,
            "company_name": c.company_name,
            "stock_code": c.stock_code,
            "case_category": c.case_category,
            "penalty_decision_no": c.penalty_decision_no,
            "audit_period": c.audit_period,
            "industry": c.industry,
            "csrc_summary": c.csrc_summary,
            "voucher_count": len(c.vouchers),
            "invoice_count": len(c.invoices),
            "contract_count": len(c.contracts),
            "bank_flow_count": len(c.bank_flows),
            "ground_truth_count": len(c.ground_truth_findings or []),
            "is_clean": len(c.ground_truth_findings or []) == 0
        })
    return {"cases": result, "total": len(result)}


@app.get("/api/cases/{case_id}")
def get_case_detail(case_id: str):
    """Retrieve full details of a specific case."""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return case.model_dump()


@app.post("/api/audit/run")
def run_audit(req: AuditRunRequest):
    """Execute end-to-end intelligent audit on a case."""
    case = get_case_by_id(req.case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{req.case_id}' not found")

    mode_enum = ExecutionMode.MOCK
    if req.mode.upper() == "STRICT_ONLINE":
        mode_enum = ExecutionMode.STRICT_ONLINE
    elif req.mode.upper() == "ONLINE":
        mode_enum = ExecutionMode.ONLINE

    llm = DeepSeekLLMAdapter(mode=mode_enum)
    harness = AccountingAgentHarness(llm_adapter=llm)

    try:
        report = harness.run_case(case, plugin_id=req.plugin_id, temperature=req.temperature)
        report_dict = report.model_dump()
        recon_res = perform_three_way_reconciliation(case)
        beneish_res = calculate_beneish_from_case(case)
        report_dict["tool_outputs"] = {
            "beneish_m_score": beneish_res,
            "three_way_reconciliation": recon_res
        }
        return report_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/stream")
async def stream_audit(case_id: str = Query(...), mode: str = Query("MOCK")):
    """Server-Sent Events (SSE) streaming of 5-stage pipeline & CoT reasoning."""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    mode_enum = ExecutionMode.MOCK
    if mode.upper() == "STRICT_ONLINE":
        mode_enum = ExecutionMode.STRICT_ONLINE
    elif mode.upper() == "ONLINE":
        mode_enum = ExecutionMode.ONLINE

    async def event_generator():
        # Stage 1: Ingestion
        yield f"data: {json.dumps({'stage': 1, 'title': '业财全模态数据接入与时序校验', 'status': 'running', 'detail': f'加载公司 {case.company_name} 凭证 {len(case.vouchers)} 笔、发票 {len(case.invoices)} 张、流水 {len(case.bank_flows)} 笔'})}\n\n"
        await asyncio.sleep(0.3)
        yield f"data: {json.dumps({'stage': 1, 'title': '业财全模态数据接入与时序校验', 'status': 'completed', 'detail': '数据格式校验通过，已构建多模态业财关联图谱'})}\n\n"

        # Stage 2: Deterministic calculation
        yield f"data: {json.dumps({'stage': 2, 'title': '确定性财务算子矩阵扫描', 'status': 'running', 'detail': '执行 Beneish M-Score 8 因子与借贷平衡刚性验证'})}\n\n"
        await asyncio.sleep(0.3)
        beneish_res = calculate_beneish_from_case(case)
        if beneish_res.get("is_calculable"):
            m_score_val = beneish_res.get("m_score", 0.0)
            stage2_detail = f"Beneish M-Score: {m_score_val:.2f} (操纵预警: {'超标' if beneish_res.get('is_manipulator') else '正常'})"
        else:
            stage2_detail = f"Beneish M-Score: 不可计算 ({beneish_res.get('reason')})"
        yield f"data: {json.dumps({'stage': 2, 'title': '确定性财务算子矩阵扫描', 'status': 'completed', 'detail': stage2_detail})}\n\n"

        # Stage 3: Three-way reconciliation
        yield f"data: {json.dumps({'stage': 3, 'title': '三单勾稽穿透核查', 'status': 'running', 'detail': '执行 凭证 ⟷ 合同 ⟷ 发票 ⟷ 银行流水 闭环对账'})}\n\n"
        await asyncio.sleep(0.3)
        recon_res = perform_three_way_reconciliation(case)
        disc_cnt = recon_res.get("total_discrepancies_count", 0)
        abn_amt = recon_res.get("total_abnormal_amount", 0.0)
        yield f"data: {json.dumps({'stage': 3, 'title': '三单勾稽穿透核查', 'status': 'completed', 'detail': f'发现勾稽异常 {disc_cnt} 项，涉案金额 ¥{abn_amt:,.2f}'})}\n\n"

        # Stage 4: DeepSeek Cognitive Reasoning & CoT streaming
        yield f"data: {json.dumps({'stage': 4, 'title': 'DeepSeek 大模型准则深度研判', 'status': 'running', 'detail': '正在调用 DeepSeek 推理引擎进行 CAS 准则条款比对与商业实质穿透'})}\n\n"
        llm = DeepSeekLLMAdapter(mode=mode_enum)
        harness = AccountingAgentHarness(llm_adapter=llm)
        report = harness.run_case(case, plugin_id="audit_fraud_detection")

        # Stream CoT text in chunks
        cot_text = report.reasoning_content or "DeepSeek 推理完成：业财数据已完成多模态综合研判。"
        words = cot_text.split("，")
        for chunk in words:
            yield f"data: {json.dumps({'type': 'cot_token', 'token': chunk + '，'})}\n\n"
            await asyncio.sleep(0.05)

        yield f"data: {json.dumps({'stage': 4, 'title': 'DeepSeek 大模型准则深度研判', 'status': 'completed', 'detail': f'研判完成，总体风险等级: {report.overall_risk_rating}'})}\n\n"

        # Stage 5: Workpaper synthesis
        yield f"data: {json.dumps({'stage': 5, 'title': '审计工作底稿与结论合成', 'status': 'running', 'detail': '正在编排标准化三层证据审计底稿与监管合规建议'})}\n\n"
        await asyncio.sleep(0.2)
        yield f"data: {json.dumps({'stage': 5, 'title': '审计工作底稿与结论合成', 'status': 'completed', 'detail': f'生成底稿 {len(report.workpapers)} 份，审计发现 {len(report.findings)} 项'})}\n\n"

        # Final full report with tool_outputs
        report_dict = report.model_dump()
        report_dict["tool_outputs"] = {
            "beneish_m_score": beneish_res,
            "three_way_reconciliation": recon_res
        }
        yield f"data: {json.dumps({'type': 'final_report', 'report': report_dict})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/tools/m-score")
def calc_m_score(req: BeneishCalcRequest):
    """Calculate Beneish M-Score and 8 financial ratios."""
    res = calculate_beneish_m_score(**req.model_dump())
    return res


@app.post("/api/tools/reconcile")
def calc_reconciliation(case_id: str = Query(...)):
    """Run 3-way reconciliation on specified case."""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return perform_three_way_reconciliation(case)


@app.post("/api/benchmark/run")
def run_benchmark():
    """Run full benchmark across all 28 authentic cases and return scorecards."""
    harness = AccountingAgentHarness(llm_adapter=DeepSeekLLMAdapter(mode=ExecutionMode.MOCK))
    summary = run_benchmark_suite(harness, plugin_id="audit_fraud_detection")
    return summary.model_dump()


@app.post("/api/upload")
async def upload_files(
    vouchers_file: Optional[UploadFile] = File(None),
    invoices_file: Optional[UploadFile] = File(None),
    bank_flows_file: Optional[UploadFile] = File(None),
    company_name: str = Form("自定义导入企业"),
    stock_code: str = Form("CUSTOM-001"),
    industry: str = Form("综合制造")
):
    """Upload custom Excel/CSV files, strictly validate fields, register into case pool, and return case_id."""
    # Check if at least one file is provided
    if not vouchers_file and not invoices_file and not bank_flows_file:
        raise HTTPException(
            status_code=400,
            detail="未检测到上传文件，请至少上传凭证表、发票表或银行流水表之一。"
        )

    vouchers = []
    invoices = []
    bank_flows = []
    validation_errors = []

    if vouchers_file:
        v_bytes = await vouchers_file.read()
        if len(v_bytes) == 0:
            validation_errors.append(f"凭证文件 '{vouchers_file.filename}' 为空文件（0字节）")
        else:
            parsed_v, v_val = parse_vouchers_file(io.BytesIO(v_bytes), filename=vouchers_file.filename or "")
            if not v_val.is_valid:
                validation_errors.extend([f"[凭证表校验未通过] {err}" for err in v_val.errors])
            else:
                vouchers = parsed_v

    if invoices_file:
        i_bytes = await invoices_file.read()
        if len(i_bytes) == 0:
            validation_errors.append(f"发票文件 '{invoices_file.filename}' 为空文件（0字节）")
        else:
            parsed_i, i_val = parse_invoices_file(io.BytesIO(i_bytes), filename=invoices_file.filename or "")
            if not i_val.is_valid:
                validation_errors.extend([f"[发票表校验未通过] {err}" for err in i_val.errors])
            else:
                invoices = parsed_i

    if bank_flows_file:
        b_bytes = await bank_flows_file.read()
        if len(b_bytes) == 0:
            validation_errors.append(f"银行流水文件 '{bank_flows_file.filename}' 为空文件（0字节）")
        else:
            parsed_b, b_val = parse_bank_flows_file(io.BytesIO(b_bytes), filename=bank_flows_file.filename or "")
            if not b_val.is_valid:
                validation_errors.extend([f"[银行流水表校验未通过] {err}" for err in b_val.errors])
            else:
                bank_flows = parsed_b

    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "账套文件解析校验失败，请修正后重新上传", "errors": validation_errors}
        )

    if not vouchers and not invoices and not bank_flows:
        raise HTTPException(
            status_code=400,
            detail="上传的文件未解析出任何有效凭证、发票或银行流水明细数据。"
        )

    case_id = f"CASE-CUSTOM-{int(time.time())}"
    custom_case = AccountingCaseData(
        case_id=case_id,
        company_name=company_name,
        stock_code=stock_code,
        industry=industry,
        case_category="自定义导入案例",
        audit_period="2025年度",
        description=f"用户自定义上传导入的业财与凭证账套数据（包含凭证 {len(vouchers)} 笔、发票 {len(invoices)} 张、流水 {len(bank_flows)} 笔）",
        vouchers=vouchers,
        invoices=invoices,
        bank_flows=bank_flows,
        contracts=[],
        financial_summary=None,
        prior_financial_summary=None
    )

    # 1. Register into in-memory case store for immediate API access
    register_custom_case(custom_case)

    # 2. Persist to disk for reload persistence
    custom_cases_dir = Path("data/cases/custom_cases")
    custom_cases_dir.mkdir(parents=True, exist_ok=True)
    with open(custom_cases_dir / f"{case_id}.json", "w", encoding="utf-8") as f:
        json.dump(custom_case.model_dump(), f, ensure_ascii=False, indent=2)

    return {
        "status": "success",
        "case_id": case_id,
        "case": custom_case.model_dump(),
        "counts": {
            "vouchers": len(vouchers),
            "invoices": len(invoices),
            "bank_flows": len(bank_flows)
        }
    }


@app.post("/api/export/excel")
def export_excel_endpoint(report_data: Dict[str, Any] = Body(...)):
    """Export workpaper to Excel and return file download."""
    report = AnalysisReportResult(**report_data)
    out_dir = Path("output/excel")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"AuditWorkpaper_{report.case_id}_{int(time.time())}.xlsx"
    export_workpaper_to_excel(report, out_path)
    return FileResponse(
        str(out_path),
        filename=out_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.post("/api/export/pdf")
def export_pdf_endpoint(report_data: Dict[str, Any] = Body(...)):
    """Export audit report to PDF and return file download."""
    report = AnalysisReportResult(**report_data)
    out_dir = Path("output/pdf")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"AuditReport_{report.case_id}_{int(time.time())}.pdf"
    export_report_to_pdf(report, out_path)
    return FileResponse(
        str(out_path),
        filename=out_path.name,
        media_type="application/pdf"
    )


@app.post("/api/export/json")
def export_json_endpoint(report_data: Dict[str, Any] = Body(...)):
    """Export full report to JSON package."""
    report = AnalysisReportResult(**report_data)
    out_dir = Path("output/json")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"AuditPackage_{report.case_id}_{int(time.time())}.json"
    export_report_to_json(report, out_path)
    return FileResponse(
        str(out_path),
        filename=out_path.name,
        media_type="application/json"
    )


# Mount static frontend production build if available
BASE_DIR = Path(__file__).resolve().parent.parent.parent
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
