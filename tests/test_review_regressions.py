"""Issue #8: exercise real public paths with isolated storage and model stubs."""
import asyncio
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.benchmark import test_cases
from src.core.harness import AccountingAgentHarness
from src.core.llm_adapter import DeepSeekAPIError
from src.core.schemas import (
    AccountingCaseData, AnalysisReportResult, FinancialStatementsSummary,
    GroundTruthRiskItem, RiskFinding, RiskLevel,
)
from src.plugins.audit_fraud_plugin.tools import calculate_beneish_from_case


def case(**kwargs):
    return AccountingCaseData(case_id="TEST", company_name="测试企业", description="", **kwargs)


def finding(title="风险甲", level=RiskLevel.HIGH, amount=100):
    return RiskFinding(finding_id="F1", title=title, risk_level=level,
                       accounting_standard="CAS 14", impact_amount=amount,
                       suspected_mechanism="", suggested_procedure="核实")


def report(findings=None):
    return AnalysisReportResult(case_id="TEST", company_name="测试企业",
                                plugin_name="audit", overall_risk_rating=RiskLevel.HIGH,
                                findings=findings or [], executive_summary="测试")


def evaluate(monkeypatch, expected, predicted):
    harness = AccountingAgentHarness()
    monkeypatch.setattr(harness, "run_case", lambda *a, **kw: report(predicted))
    return harness.evaluate_case(case(ground_truth_findings=expected))


def test_partial_financial_statements_are_not_estimated():
    summary = FinancialStatementsSummary(period="2025", revenue=1000, cost_of_sales=600,
        gross_margin=0.4, net_profit=100, accounts_receivable=100, inventory=100,
        total_assets=2000, operating_cash_flow=80)
    result = calculate_beneish_from_case(case(financial_summary=summary, prior_financial_summary=summary))
    assert result["is_calculable"] is False
    assert result["m_score"] is None
    assert len(result["missing_fields"]) == 8


def test_single_prediction_cannot_match_two_truths(monkeypatch):
    expected = [GroundTruthRiskItem(finding_type=t, expected_amount=100) for t in ("风险甲", "风险乙")]
    score = evaluate(monkeypatch, expected, [finding("风险甲与风险乙")])
    assert 0 <= score.precision <= 1
    assert 0 <= score.f1_score <= 1
    assert score.recall <= 0.5


def test_extra_and_low_risk_predictions_count_as_false_positives(monkeypatch):
    expected = [GroundTruthRiskItem(finding_type="风险甲", expected_amount=100)]
    score = evaluate(monkeypatch, expected, [finding(), finding("风险乙", RiskLevel.LOW)])
    assert score.false_positive_count == 1
    assert score.precision == 0.5
    clean = evaluate(monkeypatch, [], [finding(level=RiskLevel.LOW)])
    assert clean.false_positive_count == 1
    assert not clean.passed


def test_risk_level_mismatch_fails_case(monkeypatch):
    expected = [GroundTruthRiskItem(finding_type="风险甲", expected_risk_level=RiskLevel.HIGH)]
    score = evaluate(monkeypatch, expected, [finding(level=RiskLevel.LOW)])
    assert score.risk_level_accuracy_rate == 0.0
    assert not score.passed


@pytest.fixture
def isolated_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(server.settings, "data_dir", tmp_path / "cases")
    monkeypatch.setattr(test_cases, "_DYNAMIC_CASES_STORE", {})
    monkeypatch.chdir(tmp_path)
    return TestClient(server.app)


def upload(client, name="企业"):
    csv = b"transaction_id,transaction_time,counterparty_name,amount\nBK1,2025-01-01 10:00,Vendor,100\n"
    return client.post("/api/upload", data={"company_name": name},
                       files={"bank_flows_file": ("bank.csv", csv, "text/csv")})


def test_upload_ids_are_unique_and_survive_changed_cwd(isolated_cases, monkeypatch, tmp_path):
    monkeypatch.setattr(time, "time", lambda: 1234567890)
    first = upload(isolated_cases, "甲").json()["case_id"]
    second = upload(isolated_cases, "乙").json()["case_id"]
    assert first != second
    assert len(list((server.settings.data_dir / "custom_cases").glob("*.json"))) == 2
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    test_cases._DYNAMIC_CASES_STORE.clear()
    test_cases._load_custom_cases_from_disk(server.settings.data_dir)
    assert isolated_cases.get(f"/api/cases/{first}").json()["company_name"] == "甲"
    assert isolated_cases.get(f"/api/cases/{second}").json()["company_name"] == "乙"


def test_storage_failure_does_not_publish_case(isolated_cases, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(Path, "mkdir", fail)
    response = upload(isolated_cases)
    assert response.status_code == 500
    assert test_cases._DYNAMIC_CASES_STORE == {}


def test_stream_reports_model_failure_without_success(monkeypatch):
    def fail(*args, **kwargs):
        raise DeepSeekAPIError("upstream unavailable")
    monkeypatch.setattr(AccountingAgentHarness, "run_case", fail)
    response = TestClient(server.app).get("/api/audit/stream?case_id=REAL_CSRC_001&mode=STRICT_ONLINE")
    events = [json.loads(line[6:]) for line in response.text.splitlines()
              if line.startswith("data: ") and line != "data: [DONE]"]
    assert any(e.get("type") == "error" and e.get("code") == "MODEL_UNAVAILABLE" for e in events)
    assert not any(e.get("type") == "final_report" for e in events)


def test_slow_model_does_not_block_event_loop(monkeypatch):
    entered = threading.Event()
    released = threading.Event()
    timed_out = []
    def slow(*args, **kwargs):
        entered.set()
        if not released.wait(1):
            timed_out.append(True)
        return report()
    monkeypatch.setattr(AccountingAgentHarness, "run_case", slow)

    async def exercise():
        response = await server.stream_audit("REAL_CSRC_001", "MOCK")
        async def consume():
            async for _ in response.body_iterator:
                pass
        task = asyncio.create_task(consume())
        while not entered.is_set():
            await asyncio.sleep(0.01)
        released.set()
        await task
    asyncio.run(exercise())
    assert not timed_out, "Synchronous model call blocked the event loop"
