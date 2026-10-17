"""
专项实质性程序算子（确定性、零模型调用）。

补齐资本市场高发舞弊形态的确定性识别，并给出审计重要性水平：

* ``compute_materiality``           CSA 1221：整体重要性 / 实际执行的重要性 / 明显微小错报临界值
* ``reconcile_book_to_bank``        CSA 1312：银行存款日记账 ↔ 银行对账单双向核对（有账无流 / 有流无账），受限资金线索
* ``detect_back_to_back_trades``    CAS 14：短窗口内同品类购销、毛利极低、货权不移库 → 无商业实质 / 总额法存疑
* ``verify_cutoff_and_cost``        CAS 14：控制权转移时点（终验/吊装/排期/结算类合同提前确认、期后开票或施工支出）与收入成本配比
* ``detect_third_party_and_prepay`` CSA 1141 / CAS 36：第三方代付回款、大额预付长期挂账或付给关联方
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.core.schemas import AccountingCaseData, AccountingVoucher

REVENUE_PREFIXES = ("6001", "6051")
COST_PREFIXES = ("6401", "6402")
CASH_PREFIXES = ("1001", "1002", "1012")
BILL_PREFIXES = ("1121",)
INVENTORY_PREFIXES = ("1401", "1402", "1403", "1404", "1405", "1406", "1408", "1411")
GOODS_SHIPPED_PREFIXES = ("1406",)
PREPAY_PREFIXES = ("1123",)
OTHER_RECEIVABLE_PREFIXES = ("1221",)
AR_PREFIXES = ("1122",)
FIXED_ASSET_PREFIXES = ("1601", "1604", "1605")


def _starts(code: str, prefixes: Iterable[str]) -> bool:
    code = (code or "").strip()
    return any(code.startswith(p) for p in prefixes)


def _is_account(e, prefixes: Iterable[str], names: Iterable[str] = ()) -> bool:
    return _starts(e.account_code, prefixes) or any(n in (e.account_name or "") for n in names)


def _d(s: str) -> Optional[date]:
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def revenue_net(v: AccountingVoucher) -> float:
    """凭证中主营/其他业务收入贷方净额（不含税）。"""
    return round(sum(e.credit - e.debit for e in v.entries
                     if _is_account(e, REVENUE_PREFIXES, ("主营业务收入", "其他业务收入"))), 2)


def side_amount(v: AccountingVoucher, prefixes: Iterable[str], side: str = "debit",
                names: Iterable[str] = ()) -> float:
    vals = [getattr(e, side) for e in v.entries if _is_account(e, prefixes, names)]
    return round(sum(vals), 2)


def voucher_total(v: AccountingVoucher) -> float:
    return max(sum(e.debit for e in v.entries), sum(e.credit for e in v.entries))


def primary_voucher_family(v: AccountingVoucher) -> str:
    """按分录科目识别凭证的核心业务归属族，避免把虚增存款、虚构票据与虚构收入混加。"""
    cash_dr = side_amount(v, CASH_PREFIXES, "debit", ("银行存款", "其他货币资金"))
    bill_dr = side_amount(v, BILL_PREFIXES, "debit", ("应收票据",))
    rev_cr = revenue_net(v)
    has_tax = any((e.account_code or "").startswith("2221") or "销项" in (e.account_name or "") for e in v.entries)
    other_cr = side_amount(v, OTHER_RECEIVABLE_PREFIXES + PREPAY_PREFIXES, "credit", ("其他应收", "预付"))
    if cash_dr > 0 and (rev_cr <= 0 or (other_cr > 0 and not has_tax)):
        return "cash_in"
    if bill_dr > 0 and rev_cr <= 0:
        return "bills"
    if rev_cr > 0:
        return "revenue"
    if side_amount(v, FIXED_ASSET_PREFIXES, "debit", ("固定资产", "在建工程")) > 0:
        return "fixed_assets"
    if side_amount(v, INVENTORY_PREFIXES, "debit", ("存货", "库存商品", "原材料", "发出商品", "跌价准备")) > 0:
        return "inventory"
    if side_amount(v, PREPAY_PREFIXES + OTHER_RECEIVABLE_PREFIXES, "debit", ("预付", "其他应收")) > 0:
        return "prepay"
    if side_amount(v, COST_PREFIXES, "debit", ("主营业务成本",)) > 0 or side_amount(v, COST_PREFIXES, "credit", ("主营业务成本",)) > 0:
        return "cost"
    return "voucher"


def component_amount(v: AccountingVoucher, family: str) -> Tuple[float, str]:
    """按舞弊形态取对应科目的发生额，而不是盲目取整张凭证的借方合计。"""
    if family == "voucher":
        return round(voucher_total(v), 2), "凭证借贷发生额合计"
    if family == "revenue":
        cash_dr = side_amount(v, CASH_PREFIXES, "debit", ("银行存款", "其他货币资金"))
        other_cr = side_amount(v, OTHER_RECEIVABLE_PREFIXES + PREPAY_PREFIXES, "credit", ("其他应收", "预付"))
        has_tax = any((e.account_code or "").startswith("2221") or "销项" in (e.account_name or "") for e in v.entries)
        if cash_dr > 0 and other_cr > 0 and not has_tax:
            return cash_dr, "货币资金借方（复合虚增总额）"
        r = revenue_net(v)
        if r:
            return r, "主营/其他业务收入贷方（不含税）"
    if family == "bills":
        a = side_amount(v, BILL_PREFIXES, "debit", ("应收票据",))
        if a:
            return a, "应收票据借方"
    if family == "inventory":
        a = side_amount(v, INVENTORY_PREFIXES, "debit", ("存货", "库存商品", "原材料", "发出商品", "跌价准备"))
        if a:
            return a, "存货类科目借方"
    if family == "fixed_assets":
        a = side_amount(v, FIXED_ASSET_PREFIXES, "debit", ("固定资产", "在建工程"))
        if a:
            return a, "固定资产/在建工程借方"
    if family == "cash_in":
        a = side_amount(v, CASH_PREFIXES, "debit", ("银行存款", "其他货币资金"))
        if a:
            return a, "货币资金借方"
    if family == "prepay":
        a = side_amount(v, PREPAY_PREFIXES + OTHER_RECEIVABLE_PREFIXES, "debit", ("预付", "其他应收"))
        if a:
            return a, "预付/其他应收借方"
    if family == "cost":
        a = side_amount(v, COST_PREFIXES, "debit", ("主营业务成本",)) or side_amount(v, COST_PREFIXES, "credit", ("主营业务成本",))
        if a:
            return a, "营业成本发生额"
    r = revenue_net(v)
    if r:
        return r, "主营/其他业务收入贷方（不含税）"
    m = max([e.debit for e in v.entries] + [e.credit for e in v.entries] + [0.0])
    return round(m, 2), "凭证单行最大发生额"


def period_end(case: AccountingCaseData) -> Optional[date]:
    m = re.findall(r"(20\d{2}|19\d{2})", case.audit_period or "")
    if m:
        yr = int(m[-1])
        m_month = re.search(r"1-(\d{1,2})月", case.audit_period or "")
        if m_month:
            mo = int(m_month.group(1))
            if mo in (3, 6, 9, 12):
                day = 31 if mo in (3, 12) else 30
                return date(yr, mo, day)
        return date(yr, 12, 31)
    ds = [_d(v.voucher_date) for v in case.vouchers]
    ds = [x for x in ds if x]
    return date(max(ds).year, 12, 31) if ds else None


def _sub_name(account_name: str) -> str:
    """科目名称里的明细（如 应收账款-甲公司 → 甲公司）。"""
    for sep in ("-", "—", "－", "/", "：", ":"):
        if sep in (account_name or ""):
            return account_name.split(sep, 1)[1].strip()
    return ""


def _same_party(a: str, b: str) -> bool:
    a = re.sub(r"(股份|有限|责任|公司|集团|\(.*?\)|（.*?）)", "", a or "")
    b = re.sub(r"(股份|有限|责任|公司|集团|\(.*?\)|（.*?）)", "", b or "")
    if not a or not b:
        return True
    if a in b or b in a:
        return True
    if any(a[i:i + 4] in b for i in range(max(len(a) - 3, 0))):
        return True
    # 支持 4 字简称匹配全称（如 "恒通租赁" 匹配 "湖南恒通工程机械租赁"）
    if len(a) == 4 and len(b) >= 6 and a[:2] in b and a[-2:] in b:
        return True
    if len(b) == 4 and len(a) >= 6 and b[:2] in a and b[-2:] in a:
        return True
    return False


def _contracts_by_id(case):
    return {c.contract_id: c for c in case.contracts}


def _invoices_by_id(case):
    return {i.invoice_no: i for i in case.invoices}


def _flows_by_id(case):
    return {b.transaction_id: b for b in case.bank_flows}


def _flow_date(b) -> Optional[date]:
    return _d(b.transaction_time)


# --------------------------------------------------------------------------- materiality
def compute_materiality(case: AccountingCaseData) -> Dict[str, Any]:
    """CSA 1221：重要性水平。"""
    fs = case.financial_summary
    base, basis = 0.0, ""
    if fs and getattr(fs, "revenue", 0) and fs.revenue > 0:
        base, basis = float(fs.revenue), f"{fs.period or '本期'}营业收入（财务报表）"
    else:
        base = sum(max(revenue_net(v), 0.0) for v in case.vouchers)
        basis = "账套内主营/其他业务收入贷方合计（无报表数据）"
    if base <= 0:
        base = sum(voucher_total(v) for v in case.vouchers)
        basis = "账套凭证发生额合计（无收入数据，替代基准）"
    overall = round(base * 0.005, 2)
    pm = round(overall * 0.75, 2)
    trivial = round(overall * 0.05, 2)
    return {
        "benchmark": basis,
        "benchmark_amount": round(base, 2),
        "rate": 0.005,
        "overall_materiality": overall,
        "performance_materiality": pm,
        "clearly_trivial_threshold": trivial,
        "standard": "CSA 1221 计划和执行审计工作时的重要性",
    }


# --------------------------------------------------------------------------- 1. book vs bank
def reconcile_book_to_bank(case: AccountingCaseData, day_window: int = 5,
                           min_amount: Optional[float] = None) -> Dict[str, Any]:
    """银行存款日记账 ↔ 银行对账单双向核对（CSA 1312 函证前的账实核对）。"""
    if not case.bank_flows:
        return {"applicable": False, "reason": "未提供银行对账单流水", "book_without_bank": [], "restricted_cash_signals": []}
    mat = compute_materiality(case)
    floor = min_amount if min_amount is not None else max(mat["clearly_trivial_threshold"], 100_000.0)
    flows = list(case.bank_flows)
    used = set()
    book_without_bank = []
    fmap = _flows_by_id(case)
    for v in case.vouchers:
        dr = side_amount(v, ("1002",), "debit", ("银行存款",))
        cr = side_amount(v, ("1002",), "credit", ("银行存款",))
        for amt, sign in ((dr, 1), (cr, -1)):
            if amt < floor:
                continue
            vd = _d(v.voucher_date)
            match = None
            if v.associated_doc_id in fmap and abs(abs(fmap[v.associated_doc_id].amount) - amt) <= max(amt * 0.001, 1.0):
                match = fmap[v.associated_doc_id]
            if match is None:
                for b in flows:
                    if b.transaction_id in used or (b.amount > 0) != (sign > 0):
                        continue
                    bd = _flow_date(b)
                    if abs(abs(b.amount) - amt) <= max(amt * 0.001, 1.0) and (not vd or not bd or abs((bd - vd).days) <= day_window):
                        match = b
                        break
            if match is not None:
                used.add(match.transaction_id)
            else:
                book_without_bank.append({
                    "voucher_id": v.voucher_id, "date": v.voucher_date, "amount": amt,
                    "direction": "收款" if sign > 0 else "付款",
                    "doc": v.associated_doc_id,
                    "summary": "；".join({e.summary for e in v.entries if e.summary})[:60],
                    "amount_basis": "银行存款借方" if sign > 0 else "银行存款贷方",
                })
    restricted = []
    kw = ("质押", "担保", "冻结", "存单", "归集", "保证金", "联动")
    for c in case.contracts:
        text = f"{c.payment_terms} {c.delivery_condition}"
        if any(k in text for k in kw):
            restricted.append({"source": "合同", "id": c.contract_id, "party": c.customer_or_vendor,
                               "amount": c.total_amount, "detail": text[:80], "related_party": c.is_related_party})
    for b in case.bank_flows:
        if any(k in (b.remark or "") for k in kw) and abs(b.amount) >= floor:
            restricted.append({"source": "流水", "id": b.transaction_id, "party": b.counterparty_name,
                               "amount": abs(b.amount), "detail": b.remark, "related_party": False})
    return {
        "applicable": True,
        "method": f"逐张核对 ≥{floor:,.0f} 元的银行存款发生额与对账单（金额 ±0.1%、日期 ±{day_window} 天，或凭证直接引用流水号）",
        "threshold": floor,
        "book_without_bank": book_without_bank,
        "book_without_bank_amount": round(sum(x["amount"] for x in book_without_bank if x["direction"] == "收款"), 2),
        "restricted_cash_signals": restricted,
        "caveat": "仅当对账单覆盖全部银行账户时，“有账无流”才构成账实不符；否则应向银行函证或获取全部账户清单",
    }


# --------------------------------------------------------------------------- 2. back-to-back
_NO_MOVE_TERMS = ("货权转移", "仓单", "不实际移库", "不移库", "自提", "港内", "转货权", "过户", "背靠背", "直发", "不承担运输及仓储")


def _voucher_party(v: AccountingVoucher, contracts, invoices) -> str:
    if v.associated_doc_id in contracts:
        return contracts[v.associated_doc_id].customer_or_vendor
    if v.associated_doc_id in invoices:
        inv = invoices[v.associated_doc_id]
        return inv.buyer_name if revenue_net(v) else inv.seller_name
    for e in v.entries:
        n = _sub_name(e.account_name)
        if n:
            return n
    return ""


def _voucher_goods(v: AccountingVoucher, contracts, invoices) -> str:
    if v.associated_doc_id in invoices:
        return invoices[v.associated_doc_id].goods_or_service or ""
    text = " ".join(f"{e.account_name} {e.summary}" for e in v.entries)
    return text


def detect_back_to_back_trades(case: AccountingCaseData, window_days: int = 7,
                               max_margin: float = 0.05) -> Dict[str, Any]:
    """短窗口内购销配对且毛利极低 / 合同约定货权不移库 → 无商业实质或应按净额法。"""
    contracts, invoices = _contracts_by_id(case), _invoices_by_id(case)
    sales, purchases = [], []
    for v in case.vouchers:
        r = revenue_net(v)
        if r > 0:
            sales.append((v, r))
        p = side_amount(v, INVENTORY_PREFIXES, "debit", ("库存商品", "原材料", "存货"))
        if p > 0 and not r:
            purchases.append((v, p))
    pairs, used_p, paired_sales = [], set(), set()
    for s, r in sales:
        sd = _d(s.voucher_date)
        s_party = _voucher_party(s, contracts, invoices)
        s_terms = contracts.get(s.associated_doc_id).delivery_condition if s.associated_doc_id in contracts else ""
        if not s_terms and s_party:
            mc = next((c for c in case.contracts if _same_party(c.customer_or_vendor, s_party)), None)
            if mc:
                s_terms = mc.delivery_condition
        best = None
        for p, cost in purchases:
            if p.voucher_id in used_p:
                continue
            pd = _d(p.voucher_date)
            if sd and pd and abs((sd - pd).days) > window_days:
                continue
            margin = (r - cost) / r if r else 1.0
            if not (-0.02 <= margin <= max_margin):
                continue
            p_party = _voucher_party(p, contracts, invoices)
            if p_party and s_party and _same_party(p_party, s_party) and p_party == s_party:
                continue
            best = (p, cost, margin, p_party)
            break
        if best:
            p, cost, margin, p_party = best
            used_p.add(p.voucher_id)
            paired_sales.add(s.voucher_id)
            p_terms = contracts.get(p.associated_doc_id).delivery_condition if p.associated_doc_id in contracts else ""
            if not p_terms and p_party:
                mc_p = next((c for c in case.contracts if _same_party(c.customer_or_vendor, p_party)), None)
                if mc_p:
                    p_terms = mc_p.delivery_condition
            no_move = any(t in f"{s_terms} {p_terms}" for t in _NO_MOVE_TERMS)
            pairs.append({
                "sale_voucher": s.voucher_id, "purchase_voucher": p.voucher_id,
                "sale_date": s.voucher_date, "purchase_date": p.voucher_date,
                "customer": s_party, "supplier": p_party,
                "revenue": r, "cost": cost, "gross_margin": round(margin, 4),
                "no_physical_transfer_terms": no_move,
                "terms": (s_terms or p_terms)[:60],
                "amount_basis": "主营/其他业务收入贷方（不含税）",
            })

    for s, r in sales:
        if s.voucher_id in paired_sales:
            continue
        cost = side_amount(s, COST_PREFIXES, "debit", ("主营业务成本",))
        if cost <= 0:
            continue
        margin = (r - cost) / r if r else 1.0
        if not (-0.02 <= margin <= max_margin):
            continue
        s_party = _voucher_party(s, contracts, invoices)
        c_obj = contracts.get(s.associated_doc_id) or next(
            (c for c in case.contracts if s_party and _same_party(c.customer_or_vendor, s_party)), None
        )
        all_terms = " ".join(f"{c.payment_terms} {c.delivery_condition}" for c in case.contracts)
        s_terms = f"{c_obj.payment_terms} {c_obj.delivery_condition}" if c_obj else all_terms
        if any(t in s_terms for t in _NO_MOVE_TERMS):
            prepay_v = next(
                (v for v in case.vouchers if v.voucher_id != s.voucher_id and side_amount(v, PREPAY_PREFIXES, "debit", ("预付",)) > 0),
                s,
            )
            pairs.append({
                "sale_voucher": s.voucher_id, "purchase_voucher": prepay_v.voucher_id,
                "sale_date": s.voucher_date, "purchase_date": prepay_v.voucher_date,
                "customer": s_party, "supplier": _voucher_party(prepay_v, contracts, invoices),
                "revenue": r, "cost": cost, "gross_margin": round(margin, 4),
                "no_physical_transfer_terms": True,
                "terms": s_terms[:60],
                "amount_basis": "主营/其他业务收入贷方（不含税）",
            })

    strong = [p for p in pairs if p["no_physical_transfer_terms"]]
    return {
        "applicable": bool(sales and (purchases or pairs)),
        "method": f"收入凭证与 {window_days} 天内的存货采购/结转成本配对，毛利率 −2%～{max_margin:.0%}，并检查合同是否约定货权转移不移库/自提/仓单转移/直发",
        "pairs": pairs,
        "strong_pairs": len(strong),
        "revenue_in_pairs": round(sum(p["revenue"] for p in pairs), 2),
    }


# --------------------------------------------------------------------------- 3. cutoff & cost
_FINAL_ACCEPTANCE = (
    "终验", "最终验收", "最终客户验收", "安装调试完成", "竣工验收", "整体验收", "审计定案",
    "吊装确认", "签署吊装", "排期确认单", "按实际使用量", "结算单价结算", "上线领用",
)
_EARLY_EVIDENCE = ("到货", "签收", "发货", "初验", "出库", "进度", "暂估", "框架合同", "借出")
_POST_WORK = ("安装", "调试", "施工", "分包", "实施", "劳务", "工程款")
_CONTRACT_INVALID_REV = ("解除", "终止", "审定结算", "结算审定", "停止履行")


def verify_cutoff_and_cost(case: AccountingCaseData, year_end_days: int = 45) -> Dict[str, Any]:
    pe = period_end(case)
    contracts, invoices = _contracts_by_id(case), _invoices_by_id(case)
    cutoff, cost_gaps = [], []

    post_flows = []
    if pe:
        for b in case.bank_flows:
            bd = _flow_date(b)
            if bd and pe < bd <= pe + timedelta(days=120) and b.amount < 0 and any(k in (b.remark or "") for k in _POST_WORK):
                post_flows.append(b)

    def contract_of(v):
        if v.associated_doc_id in contracts:
            return contracts[v.associated_doc_id]
        if v.associated_doc_id in invoices:
            buyer = invoices[v.associated_doc_id].buyer_name
            cands = [c for c in case.contracts if _same_party(c.customer_or_vendor, buyer) and c.customer_or_vendor]
            if len(cands) == 1:
                return cands[0]
        vtxt = " ".join(f"{e.account_name} {e.summary}" for e in v.entries)
        for c in case.contracts:
            if c.customer_or_vendor and _same_party(c.customer_or_vendor, vtxt):
                return c
            for tok in re.findall(r"[\u4e00-\u9fa5]{2,5}", c.customer_or_vendor or ""):
                if len(tok) >= 2 and tok not in ("股份", "有限", "责任", "公司", "集团", "科技", "发展", "国际", "贸易") and tok in vtxt:
                    return c
        return None

    inflow_parties = [b.counterparty_name for b in case.bank_flows if b.amount > 0]

    for v in case.vouchers:
        r = revenue_net(v)
        if r <= 0:
            continue
        vd = _d(v.voucher_date)
        c = contract_of(v)
        inv = invoices.get(v.associated_doc_id or "")
        text = " ".join(e.summary for e in v.entries) + " " + (v.associated_doc_id or "")
        near_end = bool(pe and vd and (pe - vd).days <= year_end_days and vd <= pe)

        if c and any(k in f"{c.payment_terms} {c.delivery_condition}" for k in _CONTRACT_INVALID_REV):
            cutoff.append({
                "voucher_id": v.voucher_id, "date": v.voucher_date, "contract_id": c.contract_id,
                "customer": c.customer_or_vendor, "revenue": r,
                "contract_condition": f"{c.payment_terms}；{c.delivery_condition}"[:60],
                "recognition_evidence": "合同已解除或已出具审定结算价，不应继续确认收入",
                "post_period_work_payments": [],
                "risk": "HIGH",
                "amount_basis": "主营/其他业务收入贷方（不含税）",
            })
            continue

        if any(k in text for k in ("框架合同", "借出明细", "暂估")) and (
            not inv or (c and ("排期确认单" in c.delivery_condition or "结算单" in c.delivery_condition))
        ):
            cust = c.customer_or_vendor if c else _voucher_party(v, contracts, invoices)
            has_collection = any(cust and _same_party(cust, p) for p in inflow_parties)
            if not has_collection:
                cutoff.append({
                    "voucher_id": v.voucher_id, "date": v.voucher_date,
                    "contract_id": c.contract_id if c else (v.associated_doc_id or "无合同"),
                    "customer": cust, "revenue": r,
                    "contract_condition": (c.delivery_condition if c else "需经排期确认单或结算单确认")[:60],
                    "recognition_evidence": "框架合同/借出暂估入账，无结算确认及回款支撑",
                    "post_period_work_payments": [],
                    "risk": "HIGH",
                    "amount_basis": "主营/其他业务收入贷方（不含税）",
                })
                continue

        if not c:
            continue
        requires_final = any(k in c.delivery_condition for k in _FINAL_ACCEPTANCE)
        early = [k for k in _EARLY_EVIDENCE if k in text]
        related_post = [b for b in post_flows
                        if any(tok and tok in (b.remark or "") + (b.counterparty_name or "")
                               for tok in _project_tokens(c, v))] or (post_flows if near_end and requires_final else [])
        requires_milestone_pay = any(k in (c.payment_terms or "") for k in ("到货付", "预付", "生效付"))
        has_cust_inflow = any(c.customer_or_vendor and _same_party(c.customer_or_vendor, p) for p in inflow_parties)
        year_end_rush = bool(pe and vd and 0 <= (pe - vd).days <= 5 and requires_milestone_pay and not has_cust_inflow and inflow_parties)
        consignment_unsettled = bool(
            near_end and any(k in f"{c.payment_terms} {c.delivery_condition}" for k in ("上线领用", "领用结算", "寄售"))
            and not has_cust_inflow
        )

        if requires_final and (early or related_post or year_end_rush or consignment_unsettled) and near_end:
            cutoff.append({
                "voucher_id": v.voucher_id, "date": v.voucher_date, "contract_id": c.contract_id,
                "customer": c.customer_or_vendor, "revenue": r,
                "contract_condition": c.delivery_condition[:60],
                "recognition_evidence": "、".join(early) or ("年末突击确认且无合同约定之到货/阶段回款" if year_end_rush else "未见终验/结算文件"),
                "post_period_work_payments": [
                    {"transaction_id": b.transaction_id, "time": b.transaction_time, "amount": b.amount, "remark": b.remark}
                    for b in related_post[:5]],
                "risk": "HIGH" if (related_post or year_end_rush or consignment_unsettled) else "MEDIUM",
                "amount_basis": "主营/其他业务收入贷方（不含税）",
            })

    shipped = defaultdict(float)
    cost_by_doc = defaultdict(float)
    rev_by_doc = defaultdict(float)
    vouchers_by_doc = defaultdict(list)
    for v in case.vouchers:
        key = v.associated_doc_id or ""
        for e in v.entries:
            if _is_account(e, GOODS_SHIPPED_PREFIXES, ("发出商品",)):
                k = key or _sub_name(e.account_name)
                shipped[k] += e.debit - e.credit
                vouchers_by_doc[k].append(v.voucher_id)
            if _is_account(e, COST_PREFIXES, ("主营业务成本",)):
                cost_by_doc[key] += e.debit - e.credit
        rv = revenue_net(v)
        if rv and key:
            rev_by_doc[key] += rv
            vouchers_by_doc[key].append(v.voucher_id)
    for key, bal in shipped.items():
        if bal > 1.0 and rev_by_doc.get(key, 0) > 0 and cost_by_doc.get(key, 0) < bal * 0.5:
            cost_gaps.append({
                "doc": key, "revenue": round(rev_by_doc[key], 2), "goods_shipped_balance": round(bal, 2),
                "cost_carried": round(cost_by_doc.get(key, 0.0), 2),
                "vouchers": sorted(set(vouchers_by_doc[key])),
                "amount_basis": "发出商品借方余额（应结转未结转的成本）",
            })
    return {
        "applicable": bool(case.vouchers),
        "period_end": pe.isoformat() if pe else None,
        "method": "合同约定终验/吊装/排期/领用结算才转移控制权而期末提前确认收入；合同已解除或已审定结算仍确认收入；已确认收入合同的发出商品未结转成本",
        "cutoff_items": cutoff,
        "cutoff_revenue": round(sum(x["revenue"] for x in cutoff), 2),
        "cost_gaps": cost_gaps,
        "cost_gap_amount": round(sum(x["goods_shipped_balance"] - x["cost_carried"] for x in cost_gaps), 2),
    }


def _project_tokens(c, v) -> List[str]:
    toks = []
    for src in (c.customer_or_vendor or "", " ".join(e.summary for e in v.entries)):
        for m in re.findall(r"[\u4e00-\u9fa5]{2,4}(?:项目|县|市|区|风电场)", src):
            toks.append(m.replace("项目", "").replace("风电场", ""))
    return [t for t in toks if len(t) >= 2]


# --------------------------------------------------------------------------- 4. third-party & prepay
def detect_third_party_and_prepay(case: AccountingCaseData) -> Dict[str, Any]:
    contracts, fmap = _contracts_by_id(case), _flows_by_id(case)
    mat = compute_materiality(case)
    third, prepay = [], []
    used_flows = set()
    for v in case.vouchers:
        ar_cr = [e for e in v.entries if _is_account(e, AR_PREFIXES, ("应收账款",)) and e.credit > 0]
        cash_dr = side_amount(v, CASH_PREFIXES, "debit", ("银行存款",))
        if not ar_cr or cash_dr <= 0:
            continue
        vd = _d(v.voucher_date)
        for line in ar_cr:
            customer = _sub_name(line.account_name) or ""
            if not customer:
                m_cust = re.search(r"收到(.*?)(?:分期款|预收款|结算款|货款|款|结算)", line.summary or "")
                if m_cust:
                    customer = m_cust.group(1).strip()
            amt = line.credit
            flow = fmap.get(v.associated_doc_id) if len(ar_cr) == 1 else None
            if flow is None:
                for b in case.bank_flows:
                    if b.transaction_id in used_flows:
                        continue
                    bd = _flow_date(b)
                    if b.amount > 0 and abs(b.amount - amt) <= max(amt * 0.001, 1.0) and (not vd or not bd or abs((bd - vd).days) <= 3):
                        flow = b
                        break
            if flow is None:
                continue
            used_flows.add(flow.transaction_id)
            on_behalf = ("代" in (flow.remark or "") and "付" in (flow.remark or "")) or ("第三方代付" in (line.summary or ""))
            if on_behalf or (customer and not _same_party(customer, flow.counterparty_name)):
                third.append({
                    "voucher_id": v.voucher_id, "transaction_id": flow.transaction_id, "date": v.voucher_date,
                    "customer_on_books": customer or "账面应收客户", "actual_payer": flow.counterparty_name,
                    "amount": round(amt, 2), "remark": flow.remark, "amount_basis": "应收账款贷方（对应银行收款）",
                })
    debits = defaultdict(list)
    credits = defaultdict(float)
    for v in case.vouchers:
        has_cost_reversal = any(_is_account(e, COST_PREFIXES + ("6601", "6602"), ("主营业务成本", "销售费用", "管理费用")) and e.credit > 0 for e in v.entries)
        if has_cost_reversal:
            continue
        inv_doc = _invoices_by_id(case).get(v.associated_doc_id or "")
        if inv_doc and any(k in (inv_doc.goods_or_service or "") for k in ("服务", "推广", "咨询", "广告")):
            continue
        for e in v.entries:
            if _is_account(e, PREPAY_PREFIXES, ("预付",)):
                party = _sub_name(e.account_name) or (contracts[v.associated_doc_id].customer_or_vendor
                                                       if v.associated_doc_id in contracts else "")
                if not party:
                    m_p = re.search(r"(?:预付|支付)(.*?)(?:款|保证金|原料|采购|收购)", e.summary or "")
                    if m_p:
                        party = m_p.group(1).strip()
                if e.debit:
                    debits[party].append((v, e.debit))
                if e.credit:
                    has_bill_return = any(_is_account(x, BILL_PREFIXES, ("应收票据",)) and x.debit > 0 and "退回预付" in (x.summary or "") for x in v.entries)
                    if not has_bill_return:
                        credits[party] += e.credit
    related_names = {c.customer_or_vendor for c in case.contracts if c.is_related_party}
    for party, items in debits.items():
        paid = sum(a for _, a in items)
        settled = credits.get(party, 0.0)
        outstanding = paid - settled
        if outstanding < max(mat["performance_materiality"], 1.0):
            continue
        first_date = min((_d(v.voucher_date) for v, _ in items if _d(v.voucher_date)), default=None)
        is_related = any(party and _same_party(party, r) for r in related_names)
        has_invoice = any(
            party and _same_party(party, i.seller_name)
            and (not first_date or not _d(i.invoice_date) or _d(i.invoice_date) >= first_date)
            for i in case.invoices
        )
        if is_related or not has_invoice:
            prepay.append({
                "party": party or "未注明", "vouchers": [v.voucher_id for v, _ in items],
                "paid": round(paid, 2), "settled": round(settled, 2), "outstanding": round(outstanding, 2),
                "related_party": is_related, "has_supplier_invoice": has_invoice,
                "risk": "HIGH" if (is_related or outstanding >= mat["overall_materiality"]) else "MEDIUM",
                "amount_basis": "预付账款借方余额（期内未结转部分）",
            })
    return {
        "applicable": bool(case.vouchers),
        "method": "冲减应收的收款，其银行流水付款方与账面客户不一致或附言为代付；预付账款期末未结转余额超过实际执行的重要性，且付给关联方或预付后无对应进项发票",
        "third_party_receipts": third,
        "third_party_amount": round(sum(x["amount"] for x in third), 2),
        "prepayments": prepay,
        "prepay_outstanding": round(sum(x["outstanding"] for x in prepay), 2),
    }


def run_substantive_procedures(case: AccountingCaseData) -> Dict[str, Any]:
    from src.plugins.audit_fraud_plugin.judgment import run_judgment_procedures
    mat = compute_materiality(case)
    return {
        "materiality": mat,
        "judgment": run_judgment_procedures(case, mat),
        "book_to_bank": reconcile_book_to_bank(case),
        "back_to_back": detect_back_to_back_trades(case),
        "cutoff_and_cost": verify_cutoff_and_cost(case),
        "third_party_and_prepay": detect_third_party_and_prepay(case),
    }
