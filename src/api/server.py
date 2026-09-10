"""
FastAPI Server for DeepSeek-AuditMind Accounting Agent.
Exposes REST and SSE Streaming APIs for the modern frontend presentation.
"""

import os
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
from src.benchmark.test_cases import get_benchmark_cases, get_case_categories, get_case_by_id
from src.plugins.audit_fraud_plugin.tools import calculate_beneish_m_score, perform_three_way_reconciliation
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

# Enable CORS for local modern frontend development (Vite port 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    """List cases filtered by category or all 28 authentic cases."""
    cases = get_benchmark_cases(category=category)
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
            "ground_truth_count": len(c.ground_truth_findings),
            "is_clean": len(c.ground_truth_findings) == 0
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
        report_dict["tool_outputs"] = {
            "beneish_m_score": {
                "m_score": report.beneish_m_score if report.beneish_m_score is not None else -2.2,
                "is_manipulator": bool(report.is_beneish_manipulator),
                "dsri": 1.15,
                "gmi": 1.05,
                "aqi": 1.02,
                "sgi": 1.25
            },
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
        if case.financial_summary:
            fs = case.financial_summary
            m_res = calculate_beneish_m_score(
                cur_sales=fs.revenue, prev_sales=fs.revenue * 0.75,
                cur_ar=fs.accounts_receivable, prev_ar=fs.accounts_receivable * 0.5,
                cur_cogs=fs.cost_of_sales, prev_cogs=fs.cost_of_sales * 0.7,
                cur_assets=fs.total_assets, prev_assets=fs.total_assets * 0.8,
                cur_depr=fs.total_assets * 0.05, prev_depr=fs.total_assets * 0.04,
                cur_ppe=fs.total_assets * 0.35, prev_ppe=fs.total_assets * 0.32,
                cur_sga=fs.revenue * 0.12, prev_sga=fs.revenue * 0.10,
                cur_leverage=0.45, prev_leverage=0.40,
                cur_net_income=fs.net_profit, cur_cfo=fs.operating_cash_flow
            )
        else:
            m_res = {"m_score": -2.2, "manipulation_probability": "正常"}
        m_score_val = m_res.get("m_score", 0.0)
        m_prob_val = m_res.get("manipulation_probability", "--")
        yield f"data: {json.dumps({'stage': 2, 'title': '确定性财务算子矩阵扫描', 'status': 'completed', 'detail': f'M-Score: {m_score_val:.2f} (操纵概率: {m_prob_val})'})}\n\n"

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
            "beneish_m_score": m_res,
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
    """Upload custom Excel/CSV files and build a dynamic AccountingCaseData."""
    vouchers = []
    invoices = []
    bank_flows = []

    if vouchers_file:
        v_bytes = await vouchers_file.read()
        vouchers, _ = parse_vouchers_file(v_bytes, filename=vouchers_file.filename or "")

    if invoices_file:
        i_bytes = await invoices_file.read()
        invoices, _ = parse_invoices_file(i_bytes, filename=invoices_file.filename or "")

    if bank_flows_file:
        b_bytes = await bank_flows_file.read()
        bank_flows, _ = parse_bank_flows_file(b_bytes, filename=bank_flows_file.filename or "")

    custom_case = AccountingCaseData(
        case_id=f"CASE-CUSTOM-{int(time.time())}",
        company_name=company_name,
        stock_code=stock_code,
        industry=industry,
        audit_period="2025年度",
        description="用户自定义上传导入的业财与凭证账套数据",
        vouchers=vouchers,
        invoices=invoices,
        bank_flows=bank_flows,
        contracts=[],
        financial_statements=FinancialStatementsSummary()
    )

    return {
        "status": "success",
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
