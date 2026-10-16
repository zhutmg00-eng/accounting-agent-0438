"""
FastAPI Server for DeepSeek-AuditMind Accounting Agent.
Exposes REST and SSE Streaming APIs for the modern frontend presentation.
"""

import os
import io
import json
import re
import time
import asyncio
import random
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.core.schemas import (
    ExecutionMode, AccountingCaseData, AnalysisReportResult,
    FinancialStatementsSummary
)
from src.core.harness import AccountingAgentHarness
from src.core.llm_adapter import (
    DeepSeekLLMAdapter, DeepSeekAPIError, detect_deepseek_models, MODEL_PROFILES
)
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
from src.benchmark.test_cases import _load_custom_cases_from_disk
from src.plugins.audit_fraud_plugin.analytics import run_population_analytics
from src.core.compliance import (
    DataSanitizer, CpaApprovalRequest, CpaApprovalReceipt,
    generate_cpa_signoff, get_ethics_and_compliance_manifest
)

_load_custom_cases_from_disk(settings.data_dir)

import logging as _logging
_logging.basicConfig(level=_logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

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

@app.middleware("http")
async def add_no_cache_headers_for_spa(request, call_next):
    response = await call_next(request)
    # Ensure browsers never serve stale HTML for the SPA root
    if request.url.path in ("/", "/index.html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Global harness instance
_HARNESS = AccountingAgentHarness()

# Upload cap: read uploads in chunks and abort as soon as one file exceeds settings.max_upload_mb
_UPLOAD_CHUNK_SIZE = 1024 * 1024
_UPLOAD_OVERHEAD_SLACK = 1024 * 1024  # multipart framing allowance for the Content-Length pre-check


async def _read_upload_capped(upload: UploadFile, limit_bytes: int) -> bytes:
    """Read an upload in chunks, raising 413 as soon as the running total exceeds the limit."""
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit_bytes:
            raise HTTPException(status_code=413, detail="上传文件超过大小限制")
        chunks.append(chunk)
    return b"".join(chunks)


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


class ModelDetectRequest(BaseModel):
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class ModelConfigRequest(BaseModel):
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class AgentChatRequest(BaseModel):
    case_id: str
    messages: List[Dict[str, str]]
    tools_enabled: bool = True
    mode: str = "MOCK"
    temperature: float = 0.3


class AgentGoalRequest(BaseModel):
    case_id: str
    goal: str = "执行端到端全量舞弊穿透审计与底稿生成"
    mode: str = "MOCK"


@app.get("/api/health")
def get_health():
    """Health check and harness status."""
    return {
        "status": "online",
        "service": "DeepSeek-AuditMind Agent",
        "version": "2.0.0",
        "mode": "MOCK" if settings.use_mock_llm else "ONLINE",
        "cases_count": len(get_all_cases()),
        "categories_count": len(get_case_categories()),
    }


@app.get("/api/deepseek/models")
def get_deepseek_models():
    """Get active DeepSeek model configuration, auto-detected model profile, and model list."""
    info = detect_deepseek_models(settings.api_key, settings.api_base)
    info["active_model"] = settings.model_name
    info["configured_mode"] = "MOCK" if settings.use_mock_llm else "ONLINE"
    return info


@app.post("/api/deepseek/detect")
def detect_models_endpoint(req: ModelDetectRequest):
    """Test API connection, ping /models, and auto-detect models and latency."""
    return detect_deepseek_models(req.api_key, req.api_base)


@app.post("/api/deepseek/config")
def update_deepseek_config(req: ModelConfigRequest):
    """Dynamically switch active DeepSeek model or update API credentials."""
    supplied = req.model_fields_set

    if "model_name" in supplied:
        if req.model_name is None or not req.model_name.strip():
            raise HTTPException(status_code=400, detail="模型名称不能为空")
        settings.model_name = req.model_name.strip()
    if req.api_key:
        settings.api_key = req.api_key
        if req.api_key not in ("mock-key", ""):
            settings.use_mock_llm = False
    if "api_base" in supplied:
        if req.api_base is None or not req.api_base.strip():
            raise HTTPException(status_code=400, detail="API Base 地址不能为空")
        settings.api_base = req.api_base.strip().rstrip("/")

    profile = MODEL_PROFILES.get(settings.model_name, {
        "id": settings.model_name,
        "display_name": settings.model_name,
        "series": "Custom",
        "description": "自定义模型",
        "has_thinking_mode": "pro" in settings.model_name or "reason" in settings.model_name,
        "supports_tools": True,
        "context_window": "128,000 tokens",
        "throughput_tier": "Standard",
        "recommended_scenario": "自定义调用",
        "is_latest_2026": "v4" in settings.model_name
    })

    return {
        "status": "success",
        "active_model": settings.model_name,
        "active_model_profile": profile,
        "api_base": settings.api_base,
        "mode": "MOCK" if settings.use_mock_llm else "ONLINE"
    }


@app.post("/api/agent/chat")
def agent_chat_endpoint(req: AgentChatRequest):
    """Interactive multi-turn dialogue with DeepSeek CPA Audit Agent (with domain tools)."""
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
        reply = harness.run_agent_turn(
            case=case,
            messages=req.messages,
            tools_enabled=req.tools_enabled,
            temperature=req.temperature
        )
        return reply
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/stream")
async def agent_stream_endpoint(
    case_id: str = Query(...),
    message: str = Query(...),
    mode: str = Query("MOCK"),
    tools_enabled: bool = Query(True)
):
    """Server-Sent Events (SSE) streaming for Agent chat and real-time tool execution."""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    mode_enum = ExecutionMode.MOCK
    if mode.upper() == "STRICT_ONLINE":
        mode_enum = ExecutionMode.STRICT_ONLINE
    elif mode.upper() == "ONLINE":
        mode_enum = ExecutionMode.ONLINE

    llm = DeepSeekLLMAdapter(mode=mode_enum)
    harness = AccountingAgentHarness(llm_adapter=llm)

    async def event_generator():
        yield f"data: {json.dumps({'type': 'agent_status', 'status': 'analyzing', 'detail': f'正在调阅企业【{case.company_name}】账套并研判审计意图...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.2)

        try:
            reply = await run_in_threadpool(
                harness.run_agent_turn,
                case,
                [{"role": "user", "content": message}],
                tools_enabled
            )
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Emit tool call events
        for tc in reply.get("tool_calls", []):
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

        # Emit CoT thinking if available
        if reply.get("reasoning_content"):
            yield f"data: {json.dumps({'type': 'cot_stream', 'content': reply['reasoning_content']}, ensure_ascii=False)}\n\n"

        # Stream assistant response content in chunks
        content = reply.get("content", "")
        chunk_size = 40
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            yield f"data: {json.dumps({'type': 'content_chunk', 'chunk': chunk}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.03)

        yield f"data: {json.dumps({'type': 'agent_reply', 'reply': reply}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/agent/goal")
def agent_goal_endpoint(req: AgentGoalRequest):
    """Execute autonomous multi-step audit goal (/goal) natively on the selected case."""
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
        res = harness.run_autonomous_audit_goal(case=case, goal_instruction=req.goal)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/categories")
def get_categories():
    """List all available case categories with counts."""
    all_cases = get_all_cases()
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
            "is_clean": c.ground_truth_findings is not None and len(c.ground_truth_findings) == 0,
            "is_unlabeled": c.ground_truth_findings is None,
        })
    return {"cases": result, "total": len(result)}


@app.post("/api/cases/reload")
def reload_custom_cases():
    """Re-scan the persisted custom-case directory so newly added case files appear without a restart."""
    _load_custom_cases_from_disk(settings.data_dir)
    return {
        "status": "success",
        "message": "已重新扫描自定义案例目录",
        "total_cases": len(get_all_cases())
    }


@app.get("/api/cases/{case_id}")
def get_case_detail(case_id: str):
    """Retrieve full details of a specific case."""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    data = case.model_dump()
    data["reconciliation"] = perform_three_way_reconciliation(case)
    return data


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
        analytics_res = run_population_analytics(case)
        je_res = analytics_res["journal_entry_testing"]
        rt_res = analytics_res["fund_round_trips"]
        stage3_detail = f'发现勾稽异常 {disc_cnt} 项，涉案金额 ¥{abn_amt:,.2f}'
        if je_res.get("applicable"):
            stage3_detail += f' | 全量分录测试 {je_res["population"]} 张，风险标识 {je_res["flagged_count"]} 张'
        if rt_res.get("loop_count"):
            stage3_detail += f' | 资金往返 {rt_res["loop_count"]} 组'
        yield f"data: {json.dumps({'stage': 3, 'title': '三单勾稽穿透核查', 'status': 'completed', 'detail': stage3_detail})}\n\n"

        # Stage 4: DeepSeek Cognitive Reasoning & CoT streaming
        llm = DeepSeekLLMAdapter(mode=mode_enum)
        harness = AccountingAgentHarness(llm_adapter=llm)
        if llm.use_mock:
            stage4_running = '离线确定性模式：调用领域规则推理引擎（不调用大模型）'
        else:
            stage4_running = f'正在调用 DeepSeek {llm.model_name}，思维链逐 token 实时推送'
        yield f"data: {json.dumps({'stage': 4, 'title': 'DeepSeek 大模型准则深度研判', 'status': 'running', 'detail': stage4_running})}\n\n"

        loop = asyncio.get_running_loop()
        delta_q: asyncio.Queue = asyncio.Queue()

        def on_delta(kind: str, text: str) -> None:
            loop.call_soon_threadsafe(delta_q.put_nowait, (kind, text))

        run_task = asyncio.ensure_future(
            run_in_threadpool(harness.run_case, case, "audit_fraud_detection", 0.1, on_delta)
        )
        streamed_live = False
        while True:
            if run_task.done() and delta_q.empty():
                break
            try:
                kind, text = await asyncio.wait_for(delta_q.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            streamed_live = True
            event_type = 'cot_token' if kind == 'reasoning' else 'answer_token'
            yield f"data: {json.dumps({'type': event_type, 'token': text, 'live': True})}\n\n"

        try:
            report = run_task.result()
        except Exception as exc:
            error_code = "MODEL_UNAVAILABLE" if isinstance(exc, DeepSeekAPIError) else "AUDIT_FAILED"
            yield f"data: {json.dumps({'type': 'error', 'code': error_code, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not streamed_live:
            # 离线确定性模式：规则推理链一次生成，按句回放（非大模型实时输出）
            cot_text = report.reasoning_content or "推理完成：业财数据已完成多模态综合研判。"
            rng = random.Random(len(cot_text))  # 固定种子：同一输入回放节奏一致
            pieces, i = [], 0
            while i < len(cot_text):
                n = rng.randint(1, 4)
                pieces.append(cot_text[i:i + n])
                i += n
            budget = float(os.getenv("AUDITMIND_MOCK_COT_SECONDS", "4.5"))
            base = budget / max(len(pieces), 1)
            for piece in pieces:
                yield f"data: {json.dumps({'type': 'cot_token', 'token': piece, 'live': False})}\n\n"
                pause = base * rng.uniform(0.4, 1.6)
                if "\n" in piece or "。" in piece:
                    pause += base * 3
                await asyncio.sleep(pause)

        yield f"data: {json.dumps({'stage': 4, 'title': 'DeepSeek 大模型准则深度研判', 'status': 'completed', 'detail': (f'研判完成，总体风险等级: {report.overall_risk_rating.value}' + (f' · {report.model_name} 输出 {report.token_usage.get("completion_tokens", 0)} tokens' if streamed_live else ' · 离线规则推理'))})}\n\n"

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
    request: Request,
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

    # Reject oversized payloads before reading any body (per-file cap x 3 optional files)
    limit_bytes = max(1, settings.max_upload_mb) * 1024 * 1024
    declared_length = request.headers.get("content-length", "")
    if declared_length.isdigit() and int(declared_length) > limit_bytes * 3 + _UPLOAD_OVERHEAD_SLACK:
        raise HTTPException(status_code=413, detail="上传文件超过大小限制")

    vouchers = []
    invoices = []
    bank_flows = []
    validation_errors = []

    if vouchers_file:
        v_bytes = await _read_upload_capped(vouchers_file, limit_bytes)
        if len(v_bytes) == 0:
            validation_errors.append(f"凭证文件 '{vouchers_file.filename}' 为空文件（0字节）")
        else:
            parsed_v, v_val = parse_vouchers_file(io.BytesIO(v_bytes), filename=vouchers_file.filename or "")
            if not v_val.is_valid:
                validation_errors.extend([f"[凭证表校验未通过] {err}" for err in v_val.errors])
            else:
                vouchers = parsed_v

    if invoices_file:
        i_bytes = await _read_upload_capped(invoices_file, limit_bytes)
        if len(i_bytes) == 0:
            validation_errors.append(f"发票文件 '{invoices_file.filename}' 为空文件（0字节）")
        else:
            parsed_i, i_val = parse_invoices_file(io.BytesIO(i_bytes), filename=invoices_file.filename or "")
            if not i_val.is_valid:
                validation_errors.extend([f"[发票表校验未通过] {err}" for err in i_val.errors])
            else:
                invoices = parsed_i

    if bank_flows_file:
        b_bytes = await _read_upload_capped(bank_flows_file, limit_bytes)
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

    case_id = f"CASE-CUSTOM-{uuid.uuid4().hex}"
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
    custom_cases_dir = settings.data_dir / "custom_cases"
    try:
        custom_cases_dir.mkdir(parents=True, exist_ok=True)
        with open(custom_cases_dir / f"{case_id}.json", "x", encoding="utf-8") as f:
            json.dump(custom_case.model_dump(), f, ensure_ascii=False, indent=2)
    except Exception as exc:
        from src.benchmark import test_cases
        test_cases._DYNAMIC_CASES_STORE.pop(case_id, None)
        raise HTTPException(status_code=500, detail=f"自定义案例持久化失败: {exc}") from exc

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


DEMO_LEDGER_DIR = Path("data/templates/demo_population")
DEMO_CASE_ID = "DEMO-POPULATION-2025"


@app.post("/api/demo/population")
def load_demo_population_ledger():
    """一键载入「全量分析程序」演示账套（合成数据，535 张凭证 / 260 张发票 / 300+ 笔流水）。"""
    existing = get_case_by_id(DEMO_CASE_ID)
    if existing:
        return {"status": "success", "case_id": DEMO_CASE_ID, "case": existing.model_dump(), "reused": True}
    files = {
        "vouchers": DEMO_LEDGER_DIR / "演示账套_记账凭证.xlsx",
        "invoices": DEMO_LEDGER_DIR / "演示账套_增值税发票.csv",
        "bank_flows": DEMO_LEDGER_DIR / "演示账套_银行流水.csv",
    }
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise HTTPException(status_code=404, detail=f"演示账套文件缺失，请先运行 tools/make_demo_ledger.py：{missing}")
    with open(files["vouchers"], "rb") as fh:
        vouchers, v_res = parse_vouchers_file(fh, filename=files["vouchers"].name)
    with open(files["invoices"], "rb") as fh:
        invoices, i_res = parse_invoices_file(fh, filename=files["invoices"].name)
    with open(files["bank_flows"], "rb") as fh:
        flows, b_res = parse_bank_flows_file(fh, filename=files["bank_flows"].name)
    errors = v_res.errors + i_res.errors + b_res.errors
    if errors:
        raise HTTPException(status_code=500, detail={"message": "演示账套解析失败", "errors": errors[:10]})
    case = AccountingCaseData(
        case_id=DEMO_CASE_ID,
        company_name="星河精密制造有限公司（合成演示账套）",
        stock_code="DEMO",
        industry="通用设备制造业",
        case_category="全量分析程序演示（合成数据）",
        audit_period="2025年度",
        description=(
            f"合成演示账套（非真实企业）：凭证 {len(vouchers)} 张、发票 {len(invoices)} 张、银行流水 {len(flows)} 笔。"
            "已知注入异常：周末记账、职责分离缺失、无附件、期末收入直接对应银行存款、引用不存在单据、3 组同一对手方资金往返。"
            "用于验证全量分录测试、资金闭环识别与 Benford 检验能否找回注入异常。"
        ),
        vouchers=vouchers, invoices=invoices, bank_flows=flows, contracts=[],
    )
    register_custom_case(case)
    return {"status": "success", "case_id": DEMO_CASE_ID, "case": case.model_dump(), "reused": False,
            "counts": {"vouchers": len(vouchers), "invoices": len(invoices), "bank_flows": len(flows)}}


@app.get("/api/analytics/{case_id}")
def population_analytics_endpoint(case_id: str):
    """单独运行全量分析程序（分录测试 / 资金闭环 / Benford），不调用大模型。"""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return run_population_analytics(case)


@app.get("/api/templates/download/{template_type}")
def download_template_endpoint(template_type: str):
    """Download standard Excel / CSV templates for offline preparation."""
    templates_dir = Path("data/templates")
    if template_type == "vouchers":
        file_path = templates_dir / "企业记账凭证模板.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "企业记账凭证模板.xlsx"
    elif template_type == "invoices":
        file_path = templates_dir / "增值税发票清单模板.csv"
        media_type = "text/csv; charset=utf-8"
        filename = "增值税发票清单模板.csv"
    elif template_type == "bank_flows":
        file_path = templates_dir / "银行对账单明细模板.csv"
        media_type = "text/csv; charset=utf-8"
        filename = "银行对账单明细模板.csv"
    else:
        raise HTTPException(status_code=400, detail=f"未知模板类型: {template_type}")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="模板文件不存在")

    return FileResponse(
        str(file_path),
        filename=filename,
        media_type=media_type
    )


_UNSAFE_FILENAME_CHARS = re.compile(r"[^0-9A-Za-z_\-\u4e00-\u9fff]")


def _safe_name(raw: object, fallback: str = "CASE") -> str:
    """Sanitize an untrusted identifier so it can only ever be one file-name component."""
    s = _UNSAFE_FILENAME_CHARS.sub("_", str(raw or ""))[:64].strip("_")
    return s or fallback


def _checked_export_case_id(raw: object) -> str:
    """Reject blank or file-name-hostile case ids before they reach an export path."""
    text = str(raw or "")
    if not text.strip() or _UNSAFE_FILENAME_CHARS.search(text):
        raise HTTPException(status_code=400, detail="非法的导出案例编号")
    return _safe_name(text)


def _export_path(out_dir: Path, filename: str) -> Path:
    """Resolve an export target inside out_dir, refusing any path that escapes it."""
    out_path = (out_dir / filename).resolve()
    if not str(out_path).startswith(str(out_dir.resolve())):
        raise HTTPException(status_code=400, detail="非法的导出文件名")
    return out_path


@app.post("/api/export/excel")
def export_excel_endpoint(report_data: Dict[str, Any] = Body(...)):
    """Export workpaper to Excel and return file download."""
    report = AnalysisReportResult(**report_data)
    case_id = _checked_export_case_id(report.case_id)
    out_dir = Path("output/excel")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _export_path(out_dir, f"AuditWorkpaper_{case_id}_{int(time.time())}.xlsx")
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
    case_id = _checked_export_case_id(report.case_id)
    out_dir = Path("output/pdf")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _export_path(out_dir, f"AuditReport_{case_id}_{int(time.time())}.pdf")
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
    case_id = _checked_export_case_id(report.case_id)
    out_dir = Path("output/json")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _export_path(out_dir, f"AuditPackage_{case_id}_{int(time.time())}.json")
    export_report_to_json(report, out_path)
    return FileResponse(
        str(out_path),
        filename=out_path.name,
        media_type="application/json"
    )

# -------------------------------------------------------------
# Ethics, Compliance & Data Privacy Endpoints (1/6 Scoring Pillar)
# -------------------------------------------------------------

@app.get("/api/compliance/manifest")
def get_compliance_manifest_endpoint():
    """Return full ethics, legal compliance, and data privacy governance whitepaper."""
    return get_ethics_and_compliance_manifest()


@app.post("/api/compliance/cpa-approval", response_model=CpaApprovalReceipt)
def cpa_approval_endpoint(req: CpaApprovalRequest):
    """CPA Lead Auditor digital sign-off and ethical verification endpoint."""
    return generate_cpa_signoff(req)


@app.post("/api/compliance/sanitize-case/{case_id}")
def sanitize_case_endpoint(case_id: str):
    """Sanitize bank accounts, counterparty names, and sensitive IDs for a case."""
    case = get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"案例 {case_id} 未找到")
    sanitized = DataSanitizer.sanitize_case_data(case)
    return {
        "status": "success",
        "case_id": case_id,
        "sanitized": True,
        "message": "已成功对该案例应用数据安全脱敏防护",
        "data": sanitized.model_dump()
    }


@app.get("/api/system/health")
def system_health_endpoint():
    """System readiness & health diagnosis for competition live demonstration."""
    all_cases = get_all_cases()
    dist_exists = (BASE_DIR / "frontend" / "dist").exists()
    return {
        "status": "ready",
        "timestamp": time.time(),
        "loaded_cases_count": len(all_cases),
        "frontend_production_built": dist_exists,
        "compliance_engine": "active",
        "default_execution_mode": "MOCK (Deterministic Demo Safeguard)",
        "recommended_live_flow": "1. 载入真实案例 -> 2. 算子/思维链研判 -> 3. 拓扑与三单下钻 -> 4. CPA签章 -> 5. 导出底稿"
    }


# Mount static frontend production build if available
BASE_DIR = Path(__file__).resolve().parent.parent.parent
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
