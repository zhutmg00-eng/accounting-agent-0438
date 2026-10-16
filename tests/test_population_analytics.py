"""Population analytics, grounding guard, outbound privacy gate and native tool calling."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.server import app, DEMO_CASE_ID
from src.core.harness import AccountingAgentHarness, execute_audit_tool, AUDIT_TOOL_SCHEMAS
from src.core.llm_adapter import DeepSeekLLMAdapter, redact_outbound
from src.core.schemas import (
    AccountingCaseData, AccountingVoucher, JournalEntryLine, BankFlowRecord, ExecutionMode,
    RiskFinding, RiskLevel, EvidenceItem,
)
from src.plugins.audit_fraud_plugin.analytics import (
    journal_entry_testing, detect_fund_round_trips, benford_first_digit_test,
)
from src.plugins.audit_fraud_plugin.plugin import ground_findings
from src.plugins.audit_fraud_plugin.tools import calculate_beneish_m_score
from src.benchmark.test_cases import get_case_by_id

client = TestClient(app)


@pytest.fixture(scope="module")
def demo_case():
    resp = client.post("/api/demo/population")
    assert resp.status_code == 200, resp.text
    case = get_case_by_id(DEMO_CASE_ID)
    assert case is not None
    return case


def _voucher(vid, d, amt, preparer="甲", checker="乙", attach=1, doc=None, summary="销售"):
    return AccountingVoucher(
        voucher_id=vid, voucher_date=d, preparer=preparer, checker=checker, attachments_count=attach,
        associated_doc_id=doc,
        entries=[JournalEntryLine(account_code="1002", account_name="银行存款", debit=amt, summary=summary),
                 JournalEntryLine(account_code="6001", account_name="主营业务收入", credit=amt, summary=summary)],
    )


def test_je_testing_recovers_injected_anomalies(demo_case):
    res = journal_entry_testing(demo_case, top_n=100)
    assert res["applicable"] and res["coverage_rate"] == 1.0
    assert res["population"] == len(demo_case.vouchers) > 500
    hits = res["rule_hits"]
    # 注入：12 张周末/节假日（另有 2 张期末收入也落在周末）、8 张职责分离缺失、6 张无附件、5 张 JE07、4 张虚构单据
    assert hits["JE01"] >= 12
    assert hits["JE04"] == 8
    assert hits["JE05"] == 6
    assert hits["JE07"] == 5
    assert hits["JE10"] == 4
    assert res["high_risk_count"] >= 5


def test_missing_checker_info_is_not_a_control_failure():
    case = AccountingCaseData(case_id="T", company_name="T", description="t",
                              vouchers=[_voucher("V1", "2025-03-04", 1234.5, checker=None)])
    assert journal_entry_testing(case)["rule_hits"]["JE04"] == 0
    case.vouchers[0].checker = ""
    assert journal_entry_testing(case)["rule_hits"]["JE04"] == 1


def test_fund_round_trips_detected_in_demo(demo_case):
    res = detect_fund_round_trips(demo_case)
    pairs = {(l["out_id"], l["in_id"]) for l in res["loops"]}
    assert {("BKRT01A", "BKRT01B"), ("BKRT02A", "BKRT02B"), ("BKRT03A", "BKRT03B")} <= pairs


def test_round_trip_requires_amount_and_window():
    def flow(tid, t, party, amt):
        return BankFlowRecord(transaction_id=tid, transaction_time=t, counterparty_name=party,
                              counterparty_account="1", amount=amt, balance_after=0)
    case = AccountingCaseData(case_id="T", company_name="T", description="t", bank_flows=[
        flow("A", "2025-01-01 10:00", "甲公司", -1_000_000), flow("B", "2025-03-01 10:00", "甲公司", 1_000_000),
        flow("C", "2025-05-01 10:00", "乙公司", -1_000_000), flow("D", "2025-05-03 10:00", "乙公司", 500_000),
    ])
    assert detect_fund_round_trips(case)["loop_count"] == 0


def test_benford_refuses_small_samples_and_conforms_on_demo(demo_case):
    small = get_case_by_id("REAL_CSRC_001")
    assert benford_first_digit_test(small)["applicable"] is False
    res = benford_first_digit_test(demo_case)
    assert res["applicable"] and res["sample_size"] >= 1000
    assert res["conforms"] is True


def test_beneish_aqi_uses_current_assets_or_neutral():
    base = dict(cur_sales=100, prev_sales=100, cur_ar=10, prev_ar=10, cur_cogs=60, prev_cogs=60,
                cur_assets=200, prev_assets=200, cur_depr=5, prev_depr=5, cur_ppe=50, prev_ppe=50,
                cur_sga=10, prev_sga=10, cur_leverage=0.5, prev_leverage=0.5, cur_net_income=10, cur_cfo=10)
    neutral = calculate_beneish_m_score(**base)
    assert neutral["aqi_neutralized"] is True and neutral["variables"]["AQI (资产质量指数)"] == 1.0
    full = calculate_beneish_m_score(**base, cur_ca=60, prev_ca=100)
    # AQI = [1-(60+50)/200] / [1-(100+50)/200] = 0.45 / 0.25 = 1.8
    assert full["aqi_neutralized"] is False
    assert full["variables"]["AQI (资产质量指数)"] == pytest.approx(1.8)


def test_annual_report_inputs_vs_reconstructed_inputs():
    # 康美：两期数据摘自 2018 年年报原始发布版，AQI 用真实流动资产计算
    km = execute_audit_tool(get_case_by_id("REAL_CSRC_001"), "calculate_beneish_m_score", {})
    assert km["input_quality"] == "reported" and km["aqi_neutralized"] is False and km["caveats"] == []
    fs = get_case_by_id("REAL_CSRC_001").financial_summary
    assert fs.provenance == "reported_original" and fs.source_url.startswith("http://static.cninfo.com.cn/")
    assert fs.revenue == pytest.approx(19_356_233_375.88)
    # 瑞幸：无 A 股年报，仍为结构化重构，必须显式披露
    lk = execute_audit_tool(get_case_by_id("REAL_CSRC_009"), "calculate_beneish_m_score", {})
    assert lk["input_quality"] == "reconstructed" and any("估算" in c for c in lk["caveats"])


def test_grounding_guard_flags_ungrounded_and_unverifiable_amounts():
    case = get_case_by_id("REAL_CSRC_001")
    from src.plugins.audit_fraud_plugin.tools import perform_three_way_reconciliation
    recon = perform_three_way_reconciliation(case)
    good = RiskFinding(finding_id="RF-1", title="虚增货币资金", risk_level=RiskLevel.HIGH, accounting_standard="CAS 22",
                       impact_amount=123.0, suspected_mechanism="x", suggested_procedure="函证",
                       evidences=[EvidenceItem(evidence_type="凭证", source_ref="凭证[KM-2018-BK01]", detail="")])
    ghost = RiskFinding(finding_id="RF-2", title="虚构收入", risk_level=RiskLevel.HIGH, accounting_standard="CAS 14",
                        impact_amount=5.0, suspected_mechanism="x", suggested_procedure="函证",
                        evidences=[EvidenceItem(evidence_type="凭证", source_ref="凭证[NOT-EXIST-999]", detail="")])
    summary = ground_findings([good, ghost], case, recon)
    assert good.grounded and "KM-2018-BK01" in good.cited_refs
    assert good.impact_amount == 123.0  # 守卫从不改写模型数字，只标记
    assert "未能" in good.verification_note and "金额待复核" in good.human_verification_flag
    assert ghost.grounded is False and "人工复核" in ghost.human_verification_flag
    assert summary == {**summary, "grounded": 1, "ungrounded": 1, "amount_unverified": 2}
    # 引用单据上的分录金额（收入 206.44 亿）可以复核
    good.impact_amount = 20_644_000_000.0
    ground_findings([good], case, recon)
    assert "可在源单据" in good.verification_note


def test_mock_report_carries_analytics_and_verification():
    report = AccountingAgentHarness(llm_adapter=DeepSeekLLMAdapter(mode=ExecutionMode.MOCK)).run_case(
        get_case_by_id("REAL_CSRC_001"))
    assert report.analytics["journal_entry_testing"]["applicable"]
    assert report.verification["ungrounded"] == 0
    assert report.privacy_audit["outbound"] is False


def test_redact_outbound_masks_identifiers_not_amounts():
    safe, stats = redact_outbound([{"role": "user", "content":
        "账号6222021234567890123 金额29944000000.00 代码91440500231131361X 手机13812345678"}])
    text = safe[0]["content"]
    assert "6222021234567890123" not in text and "29944000000.00" in text
    assert "91440500231131361X" not in text and "13812345678" not in text
    assert stats["total"] == 3


def test_native_function_calling_loop(monkeypatch):
    """The model, not a keyword list, chooses the operator; results are fed back as tool messages."""
    calls = {"n": 0, "payloads": []}

    class Resp:
        status_code = 200

        def __init__(self, body):
            self._b = body
            self.text = json.dumps(body)

        def json(self):
            return self._b

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["payloads"].append(json)
        calls["n"] += 1
        if calls["n"] == 1:
            return Resp({"choices": [{"message": {"content": "", "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "detect_fund_round_trips", "arguments": "{\"window_days\": 30}"}}]}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        assert json["messages"][-1]["role"] == "tool"
        return Resp({"choices": [{"message": {"content": "未发现资金往返。"}}],
                     "usage": {"prompt_tokens": 20, "completion_tokens": 8}})

    import src.core.llm_adapter as la
    monkeypatch.setattr(la.requests, "post", fake_post)
    llm = DeepSeekLLMAdapter(mode=ExecutionMode.STRICT_ONLINE, api_key="k")
    harness = AccountingAgentHarness(llm_adapter=llm)
    out = harness.run_agent_turn(get_case_by_id("REAL_CSRC_001"), [{"role": "user", "content": "查一下体外循环"}])
    assert out["tool_routing"] == "model_function_calling"
    assert [c["tool_name"] for c in out["tool_calls"]] == ["detect_fund_round_trips"]
    assert out["tool_calls"][0]["decided_by"] == "model"
    assert calls["payloads"][0]["tools"] == AUDIT_TOOL_SCHEMAS
    assert out["content"] == "未发现资金往返。"


def test_analytics_endpoint():
    assert client.post("/api/demo/population").status_code == 200
    resp = client.get(f"/api/analytics/{DEMO_CASE_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fund_round_trips"]["loop_count"] >= 3
