"""
Population-level audit analytics (全量分析程序).

Three deterministic procedures that run over *every* record in the engagement
data rather than a sample, in the spirit of CSA 1141 第三十二条 / ISA 240.32(a)
journal-entry testing and the full-population approach now standard in
firm audit platforms:

1. ``journal_entry_testing``   — 会计分录测试：周末/节假日记账、期末窗口、
   整数金额、职责分离、无附件、收入借方冲减、异常摘要等风险标识打分。
2. ``detect_fund_round_trips`` — 资金闭环识别：同一（或关联）对手方在窗口期内
   先流出后流入、金额相近的资金往返（体外循环 / 过桥）。
3. ``benford_first_digit_test`` — Benford 首位数字检验（Nigrini MAD 判定），
   样本不足时明确返回「不适用」，不硬算。

Every function is pure: same input, same output, no model calls.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.schemas import AccountingCaseData, AccountingVoucher, BankFlowRecord

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# 法定节假日与调休：优先使用 chinesecalendar（依据国务院办公厅历年放假通知，覆盖 2004 年起）；
# 若运行环境未安装 chinesecalendar，内置 2023–2026 年国办法定节假日与调休上班日兜底表。
try:
    import chinese_calendar as _cc
except Exception:  # pragma: no cover - dependency missing
    _cc = None

_FALLBACK_HOLIDAYS = set(
    # 2023
    [date(2023, 1, 1), date(2023, 1, 2)]
    + [date(2023, 1, 21) + timedelta(days=i) for i in range(7)]
    + [date(2023, 4, 5)]
    + [date(2023, 4, 29) + timedelta(days=i) for i in range(5)]
    + [date(2023, 6, 22) + timedelta(days=i) for i in range(3)]
    + [date(2023, 9, 29) + timedelta(days=i) for i in range(8)]
    # 2024
    + [date(2024, 1, 1)]
    + [date(2024, 2, 10) + timedelta(days=i) for i in range(8)]
    + [date(2024, 4, 4) + timedelta(days=i) for i in range(3)]
    + [date(2024, 5, 1) + timedelta(days=i) for i in range(5)]
    + [date(2024, 6, 10)]
    + [date(2024, 9, 15) + timedelta(days=i) for i in range(3)]
    + [date(2024, 10, 1) + timedelta(days=i) for i in range(7)]
    # 2025
    + [date(2025, 1, 1)]
    + [date(2025, 1, 28) + timedelta(days=i) for i in range(8)]
    + [date(2025, 4, 4) + timedelta(days=i) for i in range(3)]
    + [date(2025, 5, 1) + timedelta(days=i) for i in range(5)]
    + [date(2025, 5, 31) + timedelta(days=i) for i in range(3)]
    + [date(2025, 10, 1) + timedelta(days=i) for i in range(8)]
)
_FALLBACK_MAKEUP_WORKDAYS = {
    # 2023
    date(2023, 1, 28), date(2023, 1, 29), date(2023, 4, 23), date(2023, 5, 6),
    date(2023, 6, 25), date(2023, 10, 7), date(2023, 10, 8),
    # 2024
    date(2024, 2, 4), date(2024, 2, 18), date(2024, 4, 7), date(2024, 4, 28),
    date(2024, 5, 11), date(2024, 9, 14), date(2024, 9, 29), date(2024, 10, 12),
    # 2025
    date(2025, 1, 26), date(2025, 2, 8), date(2025, 4, 27), date(2025, 9, 28), date(2025, 10, 11),
}

_SUSPICIOUS_SUMMARY_WORDS = (
    "调整", "冲销", "冲回", "补记", "更正", "暂估", "过桥", "代垫", "往来", "借款", "拆借",
    "划拨", "归集", "存单", "虚", "倒签", "红字", "无合同", "领导指示", "按要求",
)

_REVENUE_CODES = ("6001", "6051")
_REVENUE_NAMES = ("主营业务收入", "其他业务收入", "营业收入")
_CASH_CODES = ("1001", "1002", "1012")


def _to_date(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    s = str(text).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _is_offday(d: date) -> bool:
    """非工作日：法定节假日或周末（调休上班日除外）。超出日历覆盖年份时按内置国办表与周末判断。"""
    if _cc is not None:
        try:
            return not _cc.is_workday(d)
        except NotImplementedError:
            pass
    if d in _FALLBACK_MAKEUP_WORKDAYS:
        return False
    if d in _FALLBACK_HOLIDAYS:
        return True
    return d.weekday() >= 5


def _is_holiday(d: date) -> bool:  # backwards-compatible name
    return _is_offday(d)


def _voucher_amount(v: AccountingVoucher) -> float:
    return max(sum(e.debit for e in v.entries), sum(e.credit for e in v.entries))


def _is_round(amount: float) -> bool:
    """整数金额：≥10 万且为 10 万的整数倍（舞弊分录常见的人为取整特征）。"""
    return amount >= 100_000 and abs(amount % 100_000) < 0.005


def _is_revenue_line(code: str, name: str) -> bool:
    return str(code).startswith(_REVENUE_CODES) or any(k in (name or "") for k in _REVENUE_NAMES)


def _period_end(case: AccountingCaseData, vouchers: List[AccountingVoucher]) -> Optional[date]:
    """取账套内最晚记账日所在月份的月末，作为截止测试的期末基准。"""
    dates = [d for d in (_to_date(v.voucher_date) for v in vouchers) if d]
    if not dates:
        return None
    last = max(dates)
    nxt = date(last.year + (last.month == 12), (last.month % 12) + 1, 1)
    return nxt - timedelta(days=1)


def is_routine_closing_accrual(v: AccountingVoucher) -> bool:
    """判断是否为法定结账日（季末/年末最后一日）的常规成本费用计提或结转分录。

    依据《企业会计准则》权责发生制与《会计基础工作规范》，企业必须在会计期间最后一日（如 12-31、06-30）
    确认当期应计薪酬、折旧、质保金、市场支持费及成本结转，即便该日恰逢周末。
    此类分录满足：
    1. 不涉及货币资金（1001/1002/1012）与营业收入（6001/6051）；
    2. 借方全部为成本费用类科目（5001/5101/6401/6601/6602/6701/6702），贷方全部为应付/应计/备抵/存货结转类科目
       （2211/1602/1702/2801/2241/2202/1231/1405）；
    3. 不含冲回、转销等反向操纵方向。
    """
    d = _to_date(v.voucher_date)
    if not d or (d.month, d.day) not in ((3, 31), (6, 30), (9, 30), (12, 31)):
        return False
    if not v.entries:
        return False
    dr_codes = ("5001", "5101", "6401", "6402", "6601", "6602", "6603", "6701", "6702")
    cr_codes = ("2211", "1602", "1702", "2801", "2241", "2202", "1231", "1405")
    for e in v.entries:
        c = str(e.account_code or "").strip()
        if c.startswith(_CASH_CODES) or _is_revenue_line(c, e.account_name):
            return False
        if e.debit > 0 and not any(c.startswith(p) for p in dr_codes):
            return False
        if e.credit > 0 and not any(c.startswith(p) for p in cr_codes):
            return False
    return True


# ---------------------------------------------------------------------------
# 1. Journal entry testing
# ---------------------------------------------------------------------------

JE_RULES = {
    "JE01": ("非工作日记账（周末/法定节假日，已剔除调休上班日）", 2, "CSA 1141 第三十二条：识别非正常时间记录的分录"),
    "JE02": ("期末截止窗口（期末前后 5 日）大额分录", 2, "CSA 1141 / CSA 1311 截止测试"),
    "JE03": ("整数金额（10 万元整倍数）", 1, "CSA 1141 应用指南：以整数结尾的分录"),
    "JE04": ("职责分离缺失（制单=复核 或 无复核人）", 3, "CSA 1211 内部控制：不相容职务分离"),
    "JE05": ("无原始凭证附件", 2, "《会计基础工作规范》第五十一条：记账凭证应附原始凭证"),
    "JE06": ("收入科目借方发生（冲减/转出收入）", 2, "CAS 14：收入冲回需有退货或折让依据"),
    "JE07": ("收入直接对应货币资金且无业务单据", 3, "CAS 14 五步法：控制权转移证据缺失"),
    "JE08": ("摘要含敏感/调整类词汇", 1, "CSA 1141 应用指南：摘要异常或无说明的分录"),
    "JE09": ("借贷不平衡", 3, "《会计法》复式记账基本要求"),
    "JE10": ("引用单据在合同/发票/流水库中不存在", 3, "CSA 1301 审计证据：原始凭证真实性"),
}


def journal_entry_testing(case: AccountingCaseData, top_n: int = 20) -> Dict[str, Any]:
    vouchers = list(case.vouchers)
    population = len(vouchers)
    if population == 0:
        return {
            "applicable": False,
            "reason": "账套中没有记账凭证，无法执行全量分录测试",
            "population": 0, "flagged_count": 0, "coverage_rate": 0.0,
            "rule_hits": {}, "rules": {k: v[0] for k, v in JE_RULES.items()}, "flagged": [],
        }

    period_end = _period_end(case, vouchers)
    known_docs = ({c.contract_id for c in case.contracts} | {i.invoice_no for i in case.invoices}
                  | {b.transaction_id for b in case.bank_flows})
    registries_present = bool(known_docs)
    amounts = [_voucher_amount(v) for v in vouchers]
    big_threshold = sorted(amounts)[int(len(amounts) * 0.8)] if len(amounts) >= 5 else 0.0

    flagged: List[Dict[str, Any]] = []
    rule_hits: Counter = Counter()

    for v, amt in zip(vouchers, amounts):
        hits: List[str] = []
        d = _to_date(v.voucher_date)
        if d and _is_offday(d):
            hits.append("JE01")
        if d and period_end and abs((period_end - d).days) <= 5 and amt >= max(big_threshold, 100_000):
            hits.append("JE02")
        if _is_round(amt):
            hits.append("JE03")
        # None = 源数据没有复核人信息，不做判断（缺信息≠缺控制）
        if v.checker is not None:
            checker = v.checker.strip()
            if not checker or checker == (v.preparer or "").strip():
                hits.append("JE04")
        if (v.attachments_count or 0) <= 0:
            hits.append("JE05")
        rev_debit = any(_is_revenue_line(e.account_code, e.account_name) and e.debit > 0 for e in v.entries)
        if rev_debit:
            hits.append("JE06")
        rev_credit = any(_is_revenue_line(e.account_code, e.account_name) and e.credit > 0 for e in v.entries)
        cash_debit = any(str(e.account_code).startswith(_CASH_CODES) and e.debit > 0 for e in v.entries)
        if rev_credit and cash_debit and not v.associated_doc_id:
            hits.append("JE07")
        text = " ".join(e.summary or "" for e in v.entries)
        if any(w in text for w in _SUSPICIOUS_SUMMARY_WORDS):
            hits.append("JE08")
        if abs(sum(e.debit for e in v.entries) - sum(e.credit for e in v.entries)) > 0.01:
            hits.append("JE09")

        if registries_present and v.associated_doc_id and v.associated_doc_id not in known_docs:
            hits.append("JE10")

        if not hits:
            continue
        rule_hits.update(hits)
        score = sum(JE_RULES[h][1] for h in hits)
        # 季末/年末法定结账日（如 12-31 恰逢周日）的常规正向费用计提/成本结转分录，若无内控与单据缺失，
        # 不重复叠加 JE01 与 JE02 的日历权重，避免正常期末结账被直接推入 ≥5 分高风险。
        if "JE01" in hits and "JE02" in hits and is_routine_closing_accrual(v):
            if not (set(hits) & {"JE04", "JE05", "JE06", "JE07", "JE09", "JE10"}):
                score = max(score - 2, 1)
        flagged.append({
            "voucher_id": v.voucher_id,
            "date": v.voucher_date,
            "amount": round(amt, 2),
            "score": score,
            "rules": hits,
            "rule_names": [JE_RULES[h][0] for h in hits],
            "summary": (v.entries[0].summary if v.entries else "")[:40],
            "source_file": v.source_file or "",
            "row_index": v.row_index,
        })

    flagged.sort(key=lambda x: (-x["score"], -x["amount"]))
    high = [f for f in flagged if f["score"] >= 5]
    return {
        "applicable": True,
        "population": population,
        "population_amount": round(sum(amounts), 2),
        "coverage_rate": 1.0,
        "period_end": period_end.isoformat() if period_end else None,
        "flagged_count": len(flagged),
        "high_risk_count": len(high),
        "flagged_amount": round(sum(f["amount"] for f in flagged), 2),
        "rule_hits": {k: rule_hits.get(k, 0) for k in JE_RULES},
        "rules": {k: v[0] for k, v in JE_RULES.items()},
        "rule_basis": {k: v[2] for k, v in JE_RULES.items()},
        "flagged": flagged[:top_n],
        "method": "全量凭证逐张套用 10 条风险标识规则，按权重累计风险分（≥5 分为高风险分录），供注册会计师确定细节测试样本。",
    }


# ---------------------------------------------------------------------------
# 2. Fund round-trip detection
# ---------------------------------------------------------------------------

def _norm_party(name: str) -> str:
    n = (name or "").strip()
    for suffix in ("股份有限公司", "有限责任公司", "有限公司", "集团", "公司"):
        n = n.replace(suffix, "")
    return n


def detect_fund_round_trips(
    case: AccountingCaseData,
    window_days: int = 30,
    amount_tolerance: float = 0.10,
    min_amount: float = 100_000.0,
) -> Dict[str, Any]:
    flows = [f for f in case.bank_flows if abs(f.amount) >= min_amount]
    related = {_norm_party(c.customer_or_vendor) for c in case.contracts if c.is_related_party}

    def ts(f: BankFlowRecord) -> Optional[datetime]:
        s = (f.transaction_time or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        d = _to_date(s)
        return datetime(d.year, d.month, d.day) if d else None

    outs = [f for f in flows if f.amount < 0]
    ins = [f for f in flows if f.amount > 0]
    loops: List[Dict[str, Any]] = []
    used_in = set()
    for o in outs:
        to, po = ts(o), _norm_party(o.counterparty_name)
        if not to:
            continue
        for i in ins:
            if i.transaction_id in used_in:
                continue
            ti, pi = ts(i), _norm_party(i.counterparty_name)
            if not ti or not (timedelta(0) <= ti - to <= timedelta(days=window_days)):
                continue
            same_party = po and po == pi
            both_related = po in related and pi in related
            if not (same_party or both_related):
                continue
            ratio = abs(i.amount) / max(abs(o.amount), 1e-6)
            if abs(ratio - 1.0) > amount_tolerance:
                continue
            used_in.add(i.transaction_id)
            loops.append({
                "out_id": o.transaction_id, "in_id": i.transaction_id,
                "out_party": o.counterparty_name, "in_party": i.counterparty_name,
                "out_amount": round(abs(o.amount), 2), "in_amount": round(abs(i.amount), 2),
                "days": (ti - to).days,
                "pattern": "同一对手方资金往返" if same_party else "关联方之间资金接力",
            })
            break

    by_party: Dict[str, Dict[str, float]] = defaultdict(lambda: {"in": 0.0, "out": 0.0, "n": 0})
    for f in flows:
        k = f.counterparty_name or "（未知对手方）"
        by_party[k]["in" if f.amount > 0 else "out"] += abs(f.amount)
        by_party[k]["n"] += 1
    two_way = [
        {"party": k, "inflow": round(v["in"], 2), "outflow": round(v["out"], 2), "count": int(v["n"]),
         "is_related": _norm_party(k) in related}
        for k, v in by_party.items() if v["in"] > 0 and v["out"] > 0
    ]
    two_way.sort(key=lambda x: -(x["inflow"] + x["outflow"]))

    return {
        "applicable": len(case.bank_flows) > 0,
        "population": len(case.bank_flows),
        "screened": len(flows),
        "loops": loops,
        "loop_count": len(loops),
        "loop_amount": round(sum(l["out_amount"] for l in loops), 2),
        "two_way_counterparties": two_way[:10],
        "params": {"window_days": window_days, "amount_tolerance": amount_tolerance, "min_amount": min_amount},
        "method": f"对 ≥{min_amount:,.0f} 元的全部流水，配对 {window_days} 天内同一或关联对手方『先流出、后流入、金额偏差 ≤{amount_tolerance:.0%}』的资金往返。",
    }


# ---------------------------------------------------------------------------
# 3. Benford first-digit test
# ---------------------------------------------------------------------------

BENFORD_EXPECTED = {d: math.log10(1 + 1 / d) for d in range(1, 10)}
_MAD_BANDS = [(0.006, "高度符合"), (0.012, "可接受符合"), (0.015, "边缘符合"), (float("inf"), "不符合")]


def _first_digit(x: float) -> Optional[int]:
    x = abs(x)
    if x < 10:
        return None
    while x >= 10:
        x /= 10
    return int(x)


def benford_first_digit_test(case: AccountingCaseData, min_sample: int = 50) -> Dict[str, Any]:
    amounts: List[float] = []
    for v in case.vouchers:
        for e in v.entries:
            amt = e.debit or e.credit
            if amt:
                amounts.append(amt)
    amounts.extend(abs(f.amount) for f in case.bank_flows if f.amount)
    digits = [d for d in (_first_digit(a) for a in amounts) if d]
    n = len(digits)
    if n < min_sample:
        return {
            "applicable": False,
            "sample_size": n,
            "min_sample": min_sample,
            "reason": f"有效金额样本 {n} 个，少于 {min_sample} 个，Benford 检验不具统计意义，已如实标记为不适用。",
        }
    counts = Counter(digits)
    observed = {d: counts.get(d, 0) / n for d in range(1, 10)}
    mad = sum(abs(observed[d] - BENFORD_EXPECTED[d]) for d in range(1, 10)) / 9
    chi2 = sum(((counts.get(d, 0) - n * BENFORD_EXPECTED[d]) ** 2) / (n * BENFORD_EXPECTED[d]) for d in range(1, 10))
    verdict = next(label for bound, label in _MAD_BANDS if mad <= bound)
    z_scores = {}
    for d in range(1, 10):
        p = BENFORD_EXPECTED[d]
        z = (abs(observed[d] - p) - 1 / (2 * n)) / math.sqrt(p * (1 - p) / n)
        z_scores[d] = round(max(z, 0.0), 3)
    spikes = [d for d, z in z_scores.items() if z > 1.96]
    return {
        "applicable": True,
        "sample_size": n,
        "observed": {str(d): round(observed[d], 4) for d in range(1, 10)},
        "expected": {str(d): round(BENFORD_EXPECTED[d], 4) for d in range(1, 10)},
        "mad": round(mad, 5),
        "chi_square": round(chi2, 3),
        "chi_square_critical_95": 15.507,
        "verdict": verdict,
        "conforms": verdict != "不符合",
        "spike_digits": spikes,
        "z_scores": {str(k): v for k, v in z_scores.items()},
        "method": "Nigrini 首位数字检验：MAD ≤0.006 高度符合 / ≤0.012 可接受 / ≤0.015 边缘 / 以上不符合；z>1.96 的数字为显著偏离。",
    }


def run_population_analytics(case: AccountingCaseData) -> Dict[str, Any]:
    return {
        "journal_entry_testing": journal_entry_testing(case),
        "fund_round_trips": detect_fund_round_trips(case),
        "benford": benford_first_digit_test(case),
    }
