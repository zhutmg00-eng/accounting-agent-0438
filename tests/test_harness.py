"""
Unit & Integration Tests for DeepSeek Accounting Agent Harness.
"""

import pytest
from pathlib import Path
from src.core.cordis_kernel import Context, SessionLogger
from src.core.harness import AccountingAgentHarness
from src.benchmark.test_cases import get_benchmark_cases
from src.benchmark.benchmark_runner import run_benchmark_suite
from src.plugins.audit_fraud_plugin.tools import calculate_beneish_m_score, perform_three_way_reconciliation
from src.exporters.excel_exporter import export_workpaper_to_excel
from src.exporters.pdf_exporter import export_report_to_pdf
from src.exporters.json_exporter import export_report_to_json
from src.config import settings


def test_cordis_kernel_lifecycle():
    """Test Cordis microkernel context, dependency injection, and event bus."""
    ctx = Context()
    ctx.provide("version", "1.0.0")
    assert ctx.get("version") == "1.0.0"

    received_events = []
    ctx.on("custom.event", lambda data: received_events.append(data))
    ctx.emit("custom.event", {"status": "ok"})
    assert len(received_events) == 1
    assert received_events[0]["status"] == "ok"

    session = ctx.create_session("session-001")
    session.emit("step", {"action": "parse"})
    traces = session.session_logger.get_traces()
    assert len(traces) >= 1


def test_beneish_m_score_calculation():
    """Test Beneish M-Score calculation on standard values."""
    res = calculate_beneish_m_score(
        cur_sales=120000000.0, prev_sales=80000000.0,
        cur_ar=65000000.0, prev_ar=30000000.0,
        cur_cogs=70000000.0, prev_cogs=48000000.0,
        cur_assets=220000000.0, prev_assets=160000000.0,
        cur_depr=10000000.0, prev_depr=8000000.0,
        cur_ppe=80000000.0, prev_ppe=60000000.0,
        cur_sga=14000000.0, prev_sga=9000000.0,
        cur_leverage=0.55, prev_leverage=0.40,
        cur_net_income=18000000.0, cur_cfo=-5000000.0
    )
    assert "m_score" in res
    assert isinstance(res["m_score"], float)
    assert res["is_manipulator"] is True


def test_three_way_reconciliation():
    """Test 3-way matching on sample fraud case."""
    cases = get_benchmark_cases()
    fraud_case = cases[0]
    recon = perform_three_way_reconciliation(fraud_case)
    
    assert recon["reconciliation_clean"] is False
    assert recon["total_discrepancies_count"] > 0
    assert recon["total_abnormal_amount"] > 0


def test_end_to_end_harness_execution():
    """Test full agent pipeline execution."""
    harness = AccountingAgentHarness()
    cases = get_benchmark_cases()
    case = cases[0]

    report = harness.run_case(case, plugin_id="audit_fraud_detection")
    
    assert report.case_id == case.case_id
    assert report.company_name == case.company_name
    assert len(report.findings) > 0
    assert len(report.workpapers) > 0
    assert report.execution_time_seconds >= 0.0
    assert report.token_usage.get("total", 0) > 0


def test_benchmark_suite():
    """Test full benchmark suite evaluation and scoring."""
    harness = AccountingAgentHarness()
    summary = run_benchmark_suite(harness, plugin_id="audit_fraud_detection")

    assert summary.total_cases >= 25
    assert summary.passed_cases >= 25
    assert summary.mean_f1_score >= 0.85
    assert summary.schema_valid_rate == 1.0
    assert summary.math_accuracy_rate == 1.0


def test_exporters(tmp_path: Path):
    """Test Excel, PDF, and JSON exporters."""
    harness = AccountingAgentHarness()
    cases = get_benchmark_cases()
    report = harness.run_case(cases[0], plugin_id="audit_fraud_detection")

    excel_file = tmp_path / "test_wp.xlsx"
    pdf_file = tmp_path / "test_rep.pdf"
    json_file = tmp_path / "test_data.json"

    export_workpaper_to_excel(report, excel_file)
    export_report_to_pdf(report, pdf_file)
    export_report_to_json(report, json_file)

    assert excel_file.exists() and excel_file.stat().st_size > 0
    assert pdf_file.exists() and pdf_file.stat().st_size > 0
    assert json_file.exists() and json_file.stat().st_size > 0
