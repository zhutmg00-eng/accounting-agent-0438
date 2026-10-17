"""
拟定审计调整分录（AJE）与审定前后报表冲击。

只为**确定性程序已锚定到具体凭证**的发现项编制调整分录，并且每笔分录借贷平衡：
* 收入真实性/截止类：冲回涉案凭证中的收入、销项税与对应往来（或货币资金）；
  若同一凭证结转了成本，一并冲回成本与存货；
* 发出商品未结转成本：借 主营业务成本 / 贷 发出商品；
* 有账无流（虚增货币资金收款）：借 应收账款/其他应收款 / 贷 银行存款（冲回虚假收款）；
* 预付款被关联方占用：借 其他应收款-关联方资金占用 / 贷 预付账款（重分类）；
* 职业判断类（v2.4/v2.5）：冲回违规冲减成本/费用、冲回无依据应付核销、冲回减值转回、冲回违规追偿款挂账。

调整分录是"拟定"的：必须经注册会计师与管理层沟通、取得证据后才可入账。
审定后指标只重算营业收入、营业成本、利润总额（未考虑所得税与减值），并如实标注。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.schemas import AccountingCaseData, RiskFinding, RiskLevel
from src.plugins.audit_fraud_plugin.substantive import (
    AR_PREFIXES, CASH_PREFIXES, COST_PREFIXES, INVENTORY_PREFIXES, REVENUE_PREFIXES, _is_account,
)

REVENUE_TITLE_HINTS = ("业务单据", "收入", "终验", "截止", "背靠背", "购销配对", "三单", "关联销售")
JUDGMENT_REVERSE_HINTS = ("冲减成本", "冲回已计提", "无依据核销应付", "负债核销", "追偿款挂账", "冲回减值")


def _line(code: str, name: str, dr: float = 0.0, cr: float = 0.0, note: str = "") -> Dict[str, Any]:
    return {"account_code": code, "account_name": name, "debit": round(dr, 2), "credit": round(cr, 2), "note": note}


def _reverse_revenue_voucher(v) -> List[Dict[str, Any]]:
    lines = []
    for e in v.entries:
        rev = _is_account(e, REVENUE_PREFIXES, ("主营业务收入", "其他业务收入"))
        tax = "销项" in (e.account_name or "") or (e.account_code or "").startswith("2221")
        cost = _is_account(e, COST_PREFIXES, ("主营业务成本",))
        inv = _is_account(e, INVENTORY_PREFIXES, ("库存商品", "发出商品", "存货"))
        ar = _is_account(e, AR_PREFIXES + CASH_PREFIXES + ("1121", "2203", "1221"), ("应收", "银行存款", "合同资产", "预收", "其他应收"))
        if rev or tax or cost or inv or ar:
            lines.append(_line(e.account_code, e.account_name, dr=e.credit, cr=e.debit, note=f"冲回 {v.voucher_id}"))
    return lines


def _reverse_full_voucher(v) -> List[Dict[str, Any]]:
    return [_line(e.account_code, e.account_name, dr=e.credit, cr=e.debit, note=f"冲回 {v.voucher_id}") for e in v.entries if (e.debit or e.credit)]


def _balanced(lines) -> bool:
    return abs(sum(l["debit"] for l in lines) - sum(l["credit"] for l in lines)) <= 0.01


def build_adjustments(case: AccountingCaseData, findings: List[RiskFinding],
                      tool_results: Dict[str, Any]) -> Dict[str, Any]:
    vouchers = {v.voucher_id: v for v in case.vouchers}
    sp = tool_results.get("substantive") or {}
    entries: List[Dict[str, Any]] = []
    covered = set()

    def push(source: RiskFinding, desc: str, lines: List[Dict[str, Any]]):
        lines = sorted(lines, key=lambda l: 0 if l["debit"] else 1)
        if lines and _balanced(lines):
            entries.append({"aje_id": f"AJE-{len(entries) + 1:02d}", "finding_id": source.finding_id,
                            "description": desc, "lines": lines})

    for f in findings:
        if f.risk_level not in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            continue
        cited = [r for r in (f.cited_refs or []) if r in vouchers]
        if not cited:
            continue
        title = f.title or ""
        if "发出商品未结转" in title:
            amt = f.impact_amount
            push(f, "补提少结转的营业成本", [
                _line("6401", "主营业务成本", dr=amt, note="补结转"),
                _line("1406", "发出商品", cr=amt, note="补结转")])
            continue
        if "有账无流" in title or "银行回单/存款单据" in title:
            for vid in cited:
                v = vouchers[vid]
                if vid in covered:
                    continue
                cash = sum(e.debit for e in v.entries if _is_account(e, ("1002", "1012"), ("银行存款", "其他货币资金")))
                if cash <= 0:
                    continue
                push(f, f"冲回无银行流水或真实回单支持的收款 {vid}", _reverse_full_voucher(v))
                covered.add(vid)
            continue
        if "预付" in title and "关联方" in title:
            amt = f.impact_amount
            push(f, "将关联方以预付款名义占用的资金重分类", [
                _line("1221", "其他应收款-关联方资金占用", dr=amt, note="重分类"),
                _line("1123", "预付账款", cr=amt, note="重分类")])
            continue
        if "服务费挂账资产" in title or ("已发生费用未计入当期损益" in title and "冲" not in title):
            amt = f.impact_amount
            push(f, "将挂账预付/其他应收的当期服务费调入销售/管理费用", [
                _line("6601", "销售费用", dr=amt, note="按权责发生制补确认当期费用"),
                _line("1123", "预付账款", cr=amt, note="冲减挂账预付款")])
            continue
        if any(h in title for h in JUDGMENT_REVERSE_HINTS):
            for vid in cited:
                if vid in covered:
                    continue
                v = vouchers[vid]
                push(f, f"冲回违规职业判断分录 {vid}（{f.title[:28]}）", _reverse_full_voucher(v))
                covered.add(vid)
            continue
        if any(h in title for h in REVENUE_TITLE_HINTS):
            for vid in cited:
                if vid in covered:
                    continue
                v = vouchers[vid]
                lines = _reverse_revenue_voucher(v)
                if any(x["account_code"].startswith(REVENUE_PREFIXES) or "业务收入" in x["account_name"] for x in lines):
                    push(f, f"冲回不满足确认条件的收入 {vid}", lines)
                    covered.add(vid)

    # 审定前后冲击
    rev_adj = cost_adj = 0.0
    for a in entries:
        for l in a["lines"]:
            code, name = l["account_code"], l["account_name"]
            if code.startswith(REVENUE_PREFIXES) or "业务收入" in name:
                rev_adj += l["credit"] - l["debit"]
            if code.startswith(COST_PREFIXES) or "业务成本" in name:
                cost_adj += l["debit"] - l["credit"]
    fs = case.financial_summary
    impact: Optional[Dict[str, Any]] = None
    if fs and fs.revenue:
        before_rev, before_cost = fs.revenue, fs.cost_of_sales
        before_np = fs.net_profit
        after_rev = before_rev + rev_adj
        after_cost = before_cost + cost_adj
        profit_delta = rev_adj - cost_adj
        after_np = before_np + profit_delta
        comparable = after_rev >= 0 and abs(rev_adj) <= before_rev and abs(profit_delta) <= max(fs.total_assets or 0, before_rev)
        impact = {
            "comparable": comparable,
            "basis": f"{fs.period or '本期'}财务报表（来源：{fs.provenance or '未注明'}）",
            "revenue_before": round(before_rev, 2), "revenue_after": round(after_rev, 2),
            "cost_before": round(before_cost, 2), "cost_after": round(after_cost, 2),
            "profit_before": round(before_np, 2), "profit_after": round(after_np, 2),
            "profit_delta": round(profit_delta, 2),
            "turns_to_loss": comparable and before_np > 0 and after_np < 0,
            "caveat": ("利润按净利润近似重算，未考虑所得税、减值与其他调整；调整分录须经注册会计师与管理层沟通后确定" if comparable else
                       "调整金额超过本期报表数（涉案凭证可能汇总了多个会计期间），不能直接与单期报表相减，审定后数据须按期间拆分后重算"),
        }
    return {
        "entries": entries,
        "revenue_adjustment": round(rev_adj, 2),
        "cost_adjustment": round(cost_adj, 2),
        "profit_adjustment": round(rev_adj - cost_adj, 2),
        "impact": impact,
        "materiality": sp.get("materiality"),
        "note": "仅对确定性程序锚定到具体凭证的发现项编制；每笔分录借贷平衡",
    }
