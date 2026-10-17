"""v2.4：职业判断类算子、金额按口径反算、自洽性投票与中间档定级。"""
import json

from src.core.harness import AccountingAgentHarness
from src.core.schemas import (
    AccountingCaseData, AccountingVoucher, BusinessContract, InvoiceItem, JournalEntryLine, RiskFinding, RiskLevel,
)
from src.plugins.audit_fraud_plugin.judgment import run_judgment_procedures
from src.plugins.audit_fraud_plugin.plugin import calibrate_model_findings, recompute_amount
from src.plugins.audit_fraud_plugin.substantive import compute_materiality, run_substantive_procedures


def _v(vid, d, lines, doc=None, att=1):
    return AccountingVoucher(voucher_id=vid, voucher_date=d, associated_doc_id=doc, attachments_count=att,
                             entries=[JournalEntryLine(account_code=c, account_name=n, debit=dr, credit=cr) for c, n, dr, cr in lines])


def _case(vouchers, invoices=(), contracts=()):
    return AccountingCaseData(case_id="T-J", company_name="测试公司", description="", audit_period="2024年度",
                              vouchers=list(vouchers), invoices=list(invoices), contracts=list(contracts))


SALES = _v("VS-001", "2024-03-01", [("1122", "应收账款-甲", 113_000_000, 0), ("6001", "主营业务收入", 0, 100_000_000),
                                ("2221", "应交税费-销项", 0, 13_000_000)])


def test_service_fee_parked_in_prepayment_is_flagged():
    inv = InvoiceItem(invoice_no="INV-9", invoice_date="2024-11-30", buyer_name="测试公司", seller_name="丙推广公司",
                        amount_without_tax=2_000_000, tax_amount=120_000, total_amount=2_120_000, goods_or_service="市场推广服务费")
    v = _v("P1", "2024-11-30", [("1123", "预付账款-丙推广公司", 2_000_000, 0), ("2221", "应交税费-进项", 120_000, 0),
                                ("1002", "银行存款", 0, 2_120_000)], doc="INV-9")
    j = run_judgment_procedures(_case([SALES, v], invoices=[inv]))
    items = j["expense_completeness"]["items"]
    assert items and items[0]["voucher_id"] == "P1" and items[0]["amount"] == 2_000_000


def test_year_end_impairment_reversal_and_payable_writeoff():
    r = _v("R1", "2024-12-28", [("1231", "坏账准备", 900_000, 0), ("6702", "信用减值损失", 0, 900_000)])
    w = _v("W1", "2024-12-30", [("2202", "应付账款-丁公司", 700_000, 0), ("6301", "营业外收入", 0, 700_000)], att=0)
    j = run_judgment_procedures(_case([SALES, r, w]))
    assert j["impairment"]["items"][0]["amount"] == 900_000
    wo = j["liability_writeoff"]["items"][0]
    assert wo["amount"] == 700_000 and wo["weak_support"] and wo["year_end"]


def test_normal_accruals_do_not_trigger_judgment_operators():
    acc = _v("A1", "2024-12-31", [("6602", "管理费用-职工薪酬", 5_000_000, 0), ("2211", "应付职工薪酬", 0, 5_000_000)])
    ad = _v("A2", "2024-10-08", [("6601", "销售费用-广告费", 3_000_000, 0), ("1002", "银行存款", 0, 3_000_000)])
    j = run_judgment_procedures(_case([SALES, acc, ad]))
    assert all(not b["items"] for b in j.values())


def test_recompute_amount_from_declared_basis():
    s2 = _v("S2", "2024-12-20", [("1122", "应收账款-乙", 56_500_000, 0), ("6001", "主营业务收入", 0, 50_000_000),
                                 ("2221", "应交税费-销项", 0, 6_500_000)])
    case = _case([SALES, s2])
    f = RiskFinding(finding_id="RF-1", title="t", risk_level=RiskLevel.HIGH, accounting_standard="", suspected_mechanism="",
                    suggested_procedure="", impact_amount=169_500_000.0,  # 模型误用了价税合计
                    amount_basis={"vouchers": ["VS-001", "S2"], "account_code": "6001", "side": "credit"})
    recompute_amount(f, case)
    assert f.impact_amount == 150_000_000 and f.model_reported_amount == 169_500_000.0


def test_middle_tier_requires_basis_materiality_and_consensus():
    case = _case([SALES, _v("VX-001", "2024-06-01", [("6601", "销售费用", 2_000_000, 0), ("1002", "银行存款", 0, 2_000_000)])])
    tr = {"substantive": run_substantive_procedures(case)}
    pm = compute_materiality(case)["performance_materiality"]

    def mk(support):
        f = RiskFinding(finding_id="RF-1", title="凭证[VX-001] 费用归属期", risk_level=RiskLevel.HIGH, accounting_standard="",
                        suspected_mechanism="", suggested_procedure="", impact_amount=2_000_000.0, vote_support=support,
                        amount_basis={"vouchers": ["VX-001"], "account_code": "6601", "side": "debit"})
        recompute_amount(f, case)
        return f
    assert 2_000_000 >= pm
    a, b = mk("2/3"), mk("1/3")
    calibrate_model_findings([a, b], case, tr)
    assert a.risk_level == RiskLevel.MEDIUM   # 锚定 + 可复算 + 达到重要性 + 多数一致
    assert b.risk_level == RiskLevel.LOW      # 只有一次采样提出


class _Resp:
    def __init__(self, payload):
        self.content = json.dumps(payload, ensure_ascii=False)
        self._p = payload
        self.prompt_tokens, self.completion_tokens = 10, 5

    def json(self):
        return self._p

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens


class _FakeLLM:
    use_mock = False
    model_name = "fake"

    def __init__(self, payloads):
        self.payloads, self.i = payloads, 0

    def chat_completion(self, **kw):
        p = self.payloads[self.i % len(self.payloads)]
        self.i += 1
        return _Resp(p)


def test_self_consistency_clusters_by_cited_documents():
    case = _case([SALES, _v("VX-001", "2024-06-01", [("6601", "销售费用", 1, 0), ("1002", "银行存款", 0, 1)])])
    f_s1 = {"title": "凭证 VS-001 收入", "risk_level": "HIGH", "evidences": [{"source_ref": "VS-001", "detail": ""}]}
    f_x1 = {"title": "凭证 VX-001 费用", "risk_level": "MEDIUM", "evidences": [{"source_ref": "VX-001", "detail": ""}]}
    payloads = [{"risk_findings": [f_s1, f_x1]}, {"risk_findings": [f_s1]}, {"risk_findings": [dict(f_s1, risk_level="MEDIUM")]}]
    h = AccountingAgentHarness.__new__(AccountingAgentHarness)
    h.llm = _FakeLLM(payloads)
    _, raw, info = h._sample_and_vote([{"role": "user", "content": "x"}], 3, 0.1, None, case)
    sup = {f["title"]: (f["_vote_support"], f["risk_level"]) for f in raw["risk_findings"]}
    assert sup["凭证 VS-001 收入"] == ("3/3", "HIGH")
    assert sup["凭证 VX-001 费用"][0] == "1/3"
    assert info["samples_ok"] == 3 and info["consensus"] == 1
