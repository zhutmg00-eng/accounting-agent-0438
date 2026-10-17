"""
AuditMind Plugin Implementation.
"""

import json
from typing import Dict, Any, List
from src.core.plugin_base import BaseAccountingPlugin
from src.core.schemas import (
    AccountingCaseData, AnalysisReportResult, RiskFinding, 
    AuditWorkpaper, RiskLevel, EvidenceItem, WorkpaperColumn
)
from src.plugins.audit_fraud_plugin.tools import (
    calculate_beneish_m_score,
    calculate_beneish_from_case,
    perform_three_way_reconciliation
)
from src.plugins.audit_fraud_plugin.prompts import AUDIT_SYSTEM_PROMPT
from src.plugins.audit_fraud_plugin.analytics import run_population_analytics, is_routine_closing_accrual
from src.plugins.audit_fraud_plugin.substantive import run_substantive_procedures
from src.plugins.audit_fraud_plugin.rule_reasoner import build_rule_findings
from src.plugins.audit_fraud_plugin.adjustments import build_adjustments


def _source_ids(case: AccountingCaseData) -> set:
    """Every document identifier that genuinely exists in the engagement data."""
    ids = set()
    for v in case.vouchers:
        ids.add(v.voucher_id)
        if v.associated_doc_id:
            ids.add(v.associated_doc_id)
    ids.update(c.contract_id for c in case.contracts)
    ids.update(i.invoice_no for i in case.invoices)
    for b in case.bank_flows:
        ids.add(b.transaction_id)
    return {i for i in ids if i and len(i) >= 4}


def _source_amounts(case: AccountingCaseData, cited: List[str]) -> set:
    """Every amount that genuinely appears on the cited documents."""
    cited_set = set(cited)
    out = set()
    for v in case.vouchers:
        if v.voucher_id in cited_set or (v.associated_doc_id and v.associated_doc_id in cited_set):
            out.add(max(sum(e.debit for e in v.entries), sum(e.credit for e in v.entries)))
            out.update(e.debit for e in v.entries if e.debit)
            out.update(e.credit for e in v.entries if e.credit)
    from src.plugins.audit_fraud_plugin.substantive import revenue_net
    cited_v = [v for v in case.vouchers if v.voucher_id in cited_set]
    if len(cited_v) > 1:
        out.add(round(sum(max(revenue_net(v), 0.0) for v in cited_v), 2))
        out.add(round(sum(max(sum(e.debit for e in v.entries), sum(e.credit for e in v.entries)) for v in cited_v), 2))
    out.update(c.total_amount for c in case.contracts if c.contract_id in cited_set)
    for i in case.invoices:
        if i.invoice_no in cited_set:
            out.update({i.total_amount, i.amount_without_tax})
    out.update(abs(b.amount) for b in case.bank_flows if b.transaction_id in cited_set)
    return {a for a in out if a}


def _operator_amounts(tool_results: Dict[str, Any]) -> set:
    """专项程序与全量分析给出的金额（含按口径汇总的合计），供金额复核。"""
    out = set()
    sp = tool_results.get("substantive") or {}
    bb = sp.get("book_to_bank") or {}
    out.add(float(bb.get("book_without_bank_amount") or 0))
    out.update(float(x["amount"]) for x in bb.get("book_without_bank", []))
    out.update(float(x["amount"]) for x in bb.get("restricted_cash_signals", []))
    b2b = sp.get("back_to_back") or {}
    out.add(float(b2b.get("revenue_in_pairs") or 0))
    out.update(float(p["revenue"]) for p in b2b.get("pairs", []))
    cc = sp.get("cutoff_and_cost") or {}
    out.update({float(cc.get("cutoff_revenue") or 0), float(cc.get("cost_gap_amount") or 0)})
    out.update(float(x["revenue"]) for x in cc.get("cutoff_items", []))
    tp = sp.get("third_party_and_prepay") or {}
    out.update({float(tp.get("third_party_amount") or 0), float(tp.get("prepay_outstanding") or 0)})
    out.update(float(x["amount"]) for x in tp.get("third_party_receipts", []))
    out.update(float(x["amount"]) for x in tp.get("prepayments", []) if "amount" in x)
    out.update(float(x["outstanding"]) for x in tp.get("prepayments", []))
    rt = (tool_results.get("analytics") or {}).get("fund_round_trips") or {}
    out.add(float(rt.get("loop_amount") or 0))
    from src.plugins.audit_fraud_plugin.judgment import judgment_amounts
    out |= judgment_amounts(sp.get("judgment") or {})
    return {a for a in out if a}


def ground_findings(findings, case: AccountingCaseData, recon: Dict[str, Any],
                    tool_results: Dict[str, Any] = None) -> Dict[str, Any]:
    """Grounding guard: model findings must cite real documents, amounts must be traceable."""
    ids = _source_ids(case)
    operator_amounts = {float(d.get("amount", 0.0)) for d in recon.get("discrepancies", [])}
    operator_amounts.add(float(recon.get("net_exposure_amount", recon.get("total_abnormal_amount", 0.0))))
    operator_amounts |= _operator_amounts(tool_results or {})

    grounded_n = unverified_n = 0
    for f in findings:
        text = " ".join(
            [f.rule_evidence or "", f.title or ""]
            + [f"{e.source_ref} {e.detail}" for e in f.evidences]
        )
        cited = sorted(i for i in ids if i in text)
        f.cited_refs = cited
        notes = []
        if not cited:
            f.grounded = False
            f.human_verification_flag = "【证据未锚定】模型结论未引用任何源数据单据号，须注册会计师人工复核后方可采信"
            notes.append("未在源数据中找到该发现项引用的单据号")
        else:
            f.grounded = True
            grounded_n += 1
        if f.impact_amount:
            pool = (_source_amounts(case, cited) | operator_amounts) - {0.0}
            computed = (f.amount_basis or {}).get("computed")
            if computed and abs(f.impact_amount - computed) <= max(computed * 0.001, 1.0):
                notes.append("金额由账套按模型声明口径（"
                             f"{f.amount_basis.get('account_code')} {'贷方' if f.amount_basis.get('side') == 'credit' else '借方'}）加总复算"
                             + (f"，模型原报 ¥{f.model_reported_amount:,.2f}" if f.model_reported_amount else ""))
            elif any(abs(f.impact_amount - a) <= max(abs(a) * 0.01, 1.0) for a in pool):
                notes.append("金额可在源单据或算子结果中复核")
            else:
                unverified_n += 1
                notes.append(f"金额 ¥{f.impact_amount:,.2f} 未能在引用单据或算子结果中复核，须人工确认口径")
                if f.grounded:
                    f.human_verification_flag = "【金额待复核】" + (f.human_verification_flag or "")
        else:
            notes.append("未量化金额")
        f.verification_note = "；".join(notes)
    return {
        "findings_total": len(findings),
        "grounded": grounded_n,
        "ungrounded": len(findings) - grounded_n,
        "amount_unverified": unverified_n,
        "rule": "每条发现须引用源数据中真实存在的单据号；量化金额须能在引用单据或算子结果中复核（容差 1%）",
    }


def operator_flagged_ids(tool_results: Dict[str, Any]):
    """确定性算子指向的单据号：(强锚点, 弱锚点)。

    强锚点：三单勾稽、专项实质性程序、职业判断算子（达到实际执行重要性）、资金往返；
    弱锚点：全量分录测试的风险标识及未达重要性的职业判断线索。
    """
    strong, weak = set(), set()
    for d in (tool_results.get("reconciliation") or {}).get("discrepancies", []):
        vid = str(d.get("voucher_id", ""))
        strong.add(vid.replace("BANK-", ""))
        if d.get("doc_id"):
            strong.add(str(d["doc_id"]))
    sp = tool_results.get("substantive") or {}
    for x in (sp.get("book_to_bank") or {}).get("book_without_bank", []):
        strong.add(x["voucher_id"])
    for x in (sp.get("book_to_bank") or {}).get("restricted_cash_signals", []):
        strong.add(x["id"])
    for p in (sp.get("back_to_back") or {}).get("pairs", []):
        strong.update({p["sale_voucher"], p["purchase_voucher"]})
    cc = sp.get("cutoff_and_cost") or {}
    for x in cc.get("cutoff_items", []):
        strong.update({x["voucher_id"], x["contract_id"]})
        strong.update(b["transaction_id"] for b in x["post_period_work_payments"])
    for g in cc.get("cost_gaps", []):
        strong.update(g["vouchers"])
    tp = sp.get("third_party_and_prepay") or {}
    for x in tp.get("third_party_receipts", []):
        strong.update({x["voucher_id"], x["transaction_id"]})
    for x in tp.get("prepayments", []):
        strong.update(x["vouchers"])
    jd = sp.get("judgment") or {}
    pm = (sp.get("materiality") or {}).get("performance_materiality") or 0.0
    for key in ("expense_completeness", "liability_writeoff", "related_reclass", "impairment", "provisions"):
        for x in (jd.get(key) or {}).get("items", []):
            ids_x = [x.get("voucher_id") or x.get("id") or ""] + list(x.get("vouchers") or [])
            target = strong if x.get("amount", 0.0) >= pm else weak
            target.update(i for i in ids_x if i)
    an = tool_results.get("analytics") or {}
    for l in (an.get("fund_round_trips") or {}).get("loops", []):
        strong.update({l["out_id"], l["in_id"]})
    for f in (an.get("journal_entry_testing") or {}).get("flagged", []):
        if f.get("score", 0) >= 5:
            weak.add(f["voucher_id"])
    strong.discard("")
    weak.discard("")
    return strong, weak - strong


def recompute_amount(f, case: AccountingCaseData) -> None:
    """按模型声明的口径（凭证 + 科目代码 + 借贷方向）在账套中加总，替换模型自报金额。"""
    b = f.amount_basis or {}
    vids = [str(x) for x in (b.get("vouchers") or []) if x]
    code = str(b.get("account_code") or "").strip()
    side = str(b.get("side") or "").lower()
    side = "credit" if side in ("credit", "贷", "贷方", "cr") else ("debit" if side in ("debit", "借", "借方", "dr") else "")
    if not vids or not code or not side:
        return
    vmap = {v.voucher_id: v for v in case.vouchers}
    found = [vmap[x] for x in vids if x in vmap]
    if not found:
        return
    total = round(sum(getattr(e, side) for v in found for e in v.entries
                      if (e.account_code or "").strip().startswith(code)), 2)
    if total <= 0:
        return
    if abs(total - (f.impact_amount or 0)) > max(total * 0.001, 1.0):
        f.model_reported_amount = f.impact_amount
        f.impact_amount = total
    f.amount_basis = {"vouchers": [v.voucher_id for v in found], "account_code": code, "side": side,
                      "computed": total, "method": "账套按口径加总"}


def calibrate_model_findings(findings, case: AccountingCaseData, tool_results: Dict[str, Any]) -> Dict[str, Any]:
    """按"证据 + 重要性"给模型发现项定级（CSA 1221 / CSA 1141）。"""
    strong, weak = operator_flagged_ids(tool_results)
    ids = _source_ids(case)
    vmap = {v.voucher_id: v for v in case.vouchers}

    def vote_ok(f) -> bool:
        if not f.vote_support:
            return True
        k, n = (int(x) for x in f.vote_support.split("/"))
        return k >= 2 or n == 1

    def is_only_routine_closing_accrual(cited_ids: set) -> bool:
        """若发现项引用的凭证全部是季末/年末常规正向计提（如计提年终奖、折旧、市场支持费、质保金、暂估成本），
        且未被任何强确定性算子标记，则属于正常期末权责发生制核算，最高作为 LOW 关注事项，不升为 MEDIUM 误报。
        """
        cited_vouchers = [vmap[i] for i in cited_ids if i in vmap]
        if not cited_vouchers:
            return False
        return all(is_routine_closing_accrual(v) for v in cited_vouchers)

    pm = ((tool_results.get("substantive") or {}).get("materiality") or {}).get("performance_materiality") or 0.0
    changed = []
    for f in findings:
        text = " ".join([f.rule_evidence or "", f.title or ""] + [f"{e.source_ref} {e.detail}" for e in f.evidences])
        cited = {i for i in ids if i in text}
        before = f.risk_level
        if cited & strong:
            if f.risk_level == RiskLevel.HIGH and f.impact_amount and f.impact_amount < pm:
                f.risk_level = RiskLevel.MEDIUM
                reason = "金额低于实际执行的重要性"
            else:
                reason = ""
        elif is_only_routine_closing_accrual(cited):
            if f.risk_level != RiskLevel.LOW:
                f.risk_level = RiskLevel.LOW
            reason = "属季末/年末常规正向权责发生制计提或结转且无确定性异常支撑，列为 LOW 关注事项"
        elif cited & weak:
            if f.risk_level == RiskLevel.HIGH:
                f.risk_level = RiskLevel.MEDIUM
            reason = "仅有分录测试风险标识支撑"
        elif (cited and f.risk_level != RiskLevel.LOW and (f.amount_basis or {}).get("computed")
              and f.impact_amount >= pm and vote_ok(f)):
            if f.risk_level == RiskLevel.HIGH:
                f.risk_level = RiskLevel.MEDIUM
            reason = "无确定性算子支撑，但单据锚定、金额可复算且多次采样一致，最高 MEDIUM"
        else:
            if f.risk_level != RiskLevel.LOW:
                f.risk_level = RiskLevel.LOW
            reason = "未引用确定性程序检出的异常单据，列为关注事项"
        if f.risk_level != before:
            changed.append({"finding_id": f.finding_id, "title": f.title, "from": before.value, "to": f.risk_level.value, "reason": reason})
            f.human_verification_flag = f"【定级校准：{before.value}→{f.risk_level.value}，{reason}】" + (f.human_verification_flag or "")
    return {"performance_materiality": pm, "recalibrated": changed,
            "rule": "HIGH 须有确定性异常单据支撑且达到实际执行的重要性；无确定性支撑但单据锚定、金额可由账套复算且≥执行重要性、多次采样一致的非日常计提判断最高 MEDIUM；其余列为 LOW 关注事项"}


def deterministic_workpaper(case: AccountingCaseData, findings) -> List[AuditWorkpaper]:
    from src.plugins.audit_fraud_plugin.substantive import component_amount
    vouchers = {v.voucher_id: v for v in case.vouchers}
    rows, seen, abnormal = [], set(), 0.0
    for f in findings:
        if f.risk_level not in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            continue
        for vid in f.cited_refs or []:
            v = vouchers.get(vid)
            if v is None or vid in seen:
                continue
            seen.add(vid)
            amt, basis = component_amount(v, "revenue")
            rows.append(WorkpaperColumn(
                voucher_no=vid, date=v.voucher_date,
                summary=("；".join(sorted({e.summary for e in v.entries if e.summary})) or basis)[:50],
                ledger_amount=amt, verified_amount=0.0, discrepancy=amt,
                audit_conclusion=f"{f.title}（{f.risk_level.value}）",
                source_file=v.source_file or "", evidence_trace=v.associated_doc_id or basis,
            ))
            abnormal += amt
    total = sum(max(sum(e.debit for e in v.entries), sum(e.credit for e in v.entries)) for v in case.vouchers)
    return [AuditWorkpaper(
        workpaper_id="WP-001", title="确定性程序检出事项实质性核查底稿", prepared_by="DeepSeek-AuditMind",
        review_date=__import__("datetime").date.today().isoformat(), sample_count=len(rows),
        total_audited_amount=round(total, 2), abnormal_amount=round(abnormal, 2), rows=rows,
        audit_opinion_summary=(f"确定性程序锚定异常凭证 {len(rows)} 张，涉及金额 ¥{abnormal:,.2f}，待注册会计师复核" if rows
                               else "确定性程序未锚定到达到重要性的异常凭证"),
    )]


class AuditFraudPlugin(BaseAccountingPlugin):
    @property
    def plugin_id(self) -> str:
        return "audit_fraud_detection"

    @property
    def plugin_name(self) -> str:
        return "数智审计与舞弊穿透智能体插件 (AuditMind)"

    @property
    def category(self) -> str:
        return "Audit"

    @property
    def description(self) -> str:
        return "围绕注册会计师审计与内部审计场景，执行三单勾稽比对、Beneish M-Score指标分析、跨期收入排查及标准审计工作底稿自动生成。"

    def get_system_prompt(self) -> str:
        return AUDIT_SYSTEM_PROMPT

    def execute_tools(self, case: AccountingCaseData) -> Dict[str, Any]:
        """Execute deterministic audit tools on case data with strict input verification."""
        results = {}
        results["reconciliation"] = perform_three_way_reconciliation(case)
        results["beneish"] = calculate_beneish_from_case(case)
        results["analytics"] = run_population_analytics(case)
        results["substantive"] = run_substantive_procedures(case)
        return results

    def offline_report(self, case: AccountingCaseData, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        from src.plugins.audit_fraud_plugin.rule_reasoner import offline_report_json
        return offline_report_json(case, tool_results)

    def build_user_prompt(self, case: AccountingCaseData, tool_results: Dict[str, Any]) -> str:
        """Construct the LLM user prompt."""
        recon = tool_results.get("reconciliation", {})
        beneish = tool_results.get("beneish")

        prompt_parts = [
            f"【被审计单位】：{case.company_name}（所属行业：{case.industry}，审计期间：{case.audit_period}）",
            f"【案例背景】：{case.description}\n",
            "【确定性工具核查比对事实（Deterministic Audit Tool Findings）】：",
        ]

        if beneish:
            if beneish.get("is_calculable"):
                prompt_parts.append(
                    f"- Beneish M-Score: {beneish['m_score']} (操纵预警线: -1.78, 研判结论: {beneish['conclusion']})"
                )
                for k, v in beneish.get("variables", {}).items():
                    prompt_parts.append(f"  * {k}: {v}")
            else:
                prompt_parts.append(
                    f"- Beneish M-Score: 【不可计算】({beneish.get('reason')})，缺失字段: {', '.join(beneish.get('missing_fields', []))}"
                )

        prompt_parts.append(
            f"- 三单勾稽比对异常数量: {recon.get('total_discrepancies_count', 0)} 处，逐项加总 {recon.get('total_abnormal_amount', 0.0):,.2f} 元，"
            f"去重后净资金敞口 {recon.get('net_exposure_amount', 0.0):,.2f} 元（同一笔资金在凭证与流水中只计一次，报告金额请以净敞口为准）"
        )
        for disc in recon.get("discrepancies", []):
            disc_amt = disc.get('amount', 0.0)
            prompt_parts.append(f"  * [{disc.get('type')}] 关联单据: {disc.get('voucher_id', '')} | 涉及金额: {disc_amt:.2f}元 | 详情: {disc.get('detail')}")

        analytics = tool_results.get("analytics") or {}
        je = analytics.get("journal_entry_testing") or {}
        if je.get("applicable"):
            prompt_parts.append(
                f"- 全量分录测试：覆盖凭证 {je['population']} 张（100%），命中风险标识 {je['flagged_count']} 张，其中高风险 {je['high_risk_count']} 张"
            )
            for item in je.get("flagged", [])[:5]:
                prompt_parts.append(f"  * {item['voucher_id']} | {item['date']} | ¥{item['amount']:,.2f} | 风险分 {item['score']} | {'、'.join(item['rule_names'])}")
        loops = analytics.get("fund_round_trips") or {}
        if loops.get("loop_count"):
            prompt_parts.append(f"- 资金闭环识别：检出 {loops['loop_count']} 组资金往返，合计 ¥{loops['loop_amount']:,.2f}")
            for lp in loops.get("loops", [])[:5]:
                prompt_parts.append(f"  * 流出 {lp['out_id']}（{lp['out_party']}）→ {lp['days']} 天后流入 {lp['in_id']}（{lp['in_party']}），{lp['pattern']}")
        bf = analytics.get("benford") or {}
        if bf.get("applicable"):
            prompt_parts.append(f"- Benford 首位数字检验：样本 {bf['sample_size']}，MAD={bf['mad']}，结论：{bf['verdict']}")
        if beneish and beneish.get("caveats"):
            prompt_parts.append("- Beneish 输入数据质量提示：" + "；".join(beneish["caveats"]))

        sp = tool_results.get("substantive") or {}
        mat = sp.get("materiality") or {}
        if mat:
            prompt_parts.append(
                f"- 审计重要性（CSA 1221）：基准 {mat['benchmark']} ¥{mat['benchmark_amount']:,.2f} × 0.5% → 整体重要性 ¥{mat['overall_materiality']:,.2f}，"
                f"实际执行的重要性 ¥{mat['performance_materiality']:,.2f}，明显微小错报临界值 ¥{mat['clearly_trivial_threshold']:,.2f}")
        bb = sp.get("book_to_bank") or {}
        for x in (bb.get("book_without_bank") or [])[:8]:
            prompt_parts.append(f"  * [有账无流] 凭证 {x['voucher_id']} {x['date']} {x['direction']} ¥{x['amount']:,.2f}，对账单无对应流水")
        for x in (bb.get("restricted_cash_signals") or [])[:5]:
            prompt_parts.append(f"  * [受限资金线索] {x['source']} {x['id']}：{x['party']} {x['detail']}")
        for p in ((sp.get("back_to_back") or {}).get("pairs") or [])[:6]:
            prompt_parts.append(f"  * [购销配对] 销售 {p['sale_voucher']} ¥{p['revenue']:,.2f}（{p['customer']}）↔ 采购 {p['purchase_voucher']} ¥{p['cost']:,.2f}（{p['supplier']}），毛利率 {p['gross_margin']:.2%}；条款：{p['terms']}")
        cc = sp.get("cutoff_and_cost") or {}
        for x in (cc.get("cutoff_items") or [])[:6]:
            pp = "；期后付款 " + "、".join(b["transaction_id"] for b in x["post_period_work_payments"]) if x["post_period_work_payments"] else ""
            prompt_parts.append(f"  * [截止] 凭证 {x['voucher_id']} {x['date']} 收入 ¥{x['revenue']:,.2f}，合同 {x['contract_id']} 条款「{x['contract_condition']}」，入账依据 {x['recognition_evidence']}{pp}")
        for g in (cc.get("cost_gaps") or [])[:6]:
            prompt_parts.append(f"  * [成本配比] 单据 {g['doc']} 收入 ¥{g['revenue']:,.2f}，发出商品余额 ¥{g['goods_shipped_balance']:,.2f}，已结转成本 ¥{g['cost_carried']:,.2f}（凭证 {', '.join(g['vouchers'][:4])}）")
        tp = sp.get("third_party_and_prepay") or {}
        for x in (tp.get("third_party_receipts") or [])[:6]:
            prompt_parts.append(f"  * [第三方回款] 凭证 {x['voucher_id']} / 流水 {x['transaction_id']}：账面客户 {x['customer_on_books']}，付款方 {x['actual_payer']}，¥{x['amount']:,.2f}")
        for x in (tp.get("prepayments") or [])[:6]:
            prompt_parts.append(f"  * [预付挂账] {x['party']} 余额 ¥{x['outstanding']:,.2f}（凭证 {', '.join(x['vouchers'][:4])}{'，关联方' if x['related_party'] else ''}）")

        # 注入职业判断类算子结果（v2.4/v2.5）
        jd = sp.get("judgment") or {}
        for j_key, j_label in (
            ("expense_completeness", "费用完整性/冲减成本"),
            ("impairment", "资产/信用减值异常"),
            ("provisions", "或有事项/预计负债异常"),
            ("liability_writeoff", "无依据核销负债"),
            ("related_reclass", "关联方重分类/商业实质异常"),
        ):
            for x in ((jd.get(j_key) or {}).get("items") or [])[:6]:
                ref_id = ", ".join(x.get("vouchers") or [x.get("voucher_id") or x.get("id") or ""])
                prompt_parts.append(
                    f"  * [{j_label}] 单据 {ref_id} ({x.get('date', '')})：¥{x.get('amount', 0.0):,.2f} | {x.get('detail', '')}（口径：{x.get('amount_basis', '')}）"
                )

        # Prompt budget: include both strong and weak operator-flagged vouchers
        flagged_ids = {d.get("voucher_id") for d in recon.get("discrepancies", [])}
        flagged_ids |= {f["voucher_id"] for f in (je.get("flagged") or [])[:10]}
        s_ids, w_ids = operator_flagged_ids(tool_results)
        flagged_ids |= s_ids | w_ids
        focus = [v for v in case.vouchers if v.voucher_id in flagged_ids]
        focus += [v for v in case.vouchers if v.voucher_id not in flagged_ids][: max(0, 5 - len(focus))]
        focus = focus[:30]
        prompt_parts.append(f"\n【记账凭证明细（算子指向的重点凭证 {len(focus)} 张 / 全量 {len(case.vouchers)} 张）】：")
        for v in focus:
            entries_str = "; ".join([f"{e.account_name}(借:{e.debit:.2f}, 贷:{e.credit:.2f})" for e in v.entries])
            prompt_parts.append(f"- 凭证号: {v.voucher_id} | 日期: {v.voucher_date} | 关联单号: {v.associated_doc_id or '无'} | 分录: {entries_str}")

        prompt_parts.append("\n【合同与发票抽样明细】：")
        for c in case.contracts[:20]:
            prompt_parts.append(f"- 合同: {c.contract_id} | 交易方: {c.customer_or_vendor} | 金额: {c.total_amount:,.2f}元 | 关联方: {c.is_related_party}")
        focus_docs = {v.associated_doc_id for v in focus if v.associated_doc_id}
        invs = [i for i in case.invoices if i.invoice_no in focus_docs] or case.invoices[:5]
        for inv in invs[:20]:
            prompt_parts.append(f"- 发票: {inv.invoice_no} | 日期: {inv.invoice_date} | 价税合计: {inv.total_amount:,.2f}元 | 品目: {inv.goods_or_service}")
        if len(case.invoices) > len(invs[:20]) or len(case.vouchers) > len(focus):
            prompt_parts.append("（其余记录已由确定性算子全量处理，结论以算子结果为准）")

        prompt_parts.append(
            "\n【口径与分级要求】①收入类金额按主营/其他业务收入贷方不含税金额计量，不要用价税合计，也不要把同一凭证里的成本结转加进去；"
            "同一舞弊手法、同一会计科目口径下的多张同构凭证（如期末多笔同类提前确认收入、多笔同类无付款存货采购）请合并为一条发现项并在 amount_basis.vouchers 中列出全部涉案凭证号；"
            "②HIGH 级发现必须有上面确定性算子列出的异常单据作支撑，并达到实际执行的重要性；"
            "③没有确定性异常支撑的职业判断请标为 LOW（关注事项），不要因为'可能'而升级；"
            "④日常费用（销售/管理/财务费用、工资、折旧、质保金、市场支持费计提）有银行流水或正常期末计提依据即属正常，不要求购销合同；"
            "⑤若所有算子均未检出异常，overall_risk_rating 输出 CLEAN 或 LOW，可只列关注事项。")
        prompt_parts.append("\n请基于上述事实与准则规范，输出完整的审计穿透研判 JSON 报告。")
        return "\n".join(prompt_parts)

    @staticmethod
    def _analytics_findings(analytics: Dict[str, Any], start: int = 0) -> List[RiskFinding]:
        out: List[RiskFinding] = []
        rt = analytics.get("fund_round_trips") or {}
        if rt.get("loop_count"):
            loops = rt["loops"]
            out.append(RiskFinding(
                finding_id=f"RF-{start + len(out) + 1:03d}",
                title=f"疑似资金体外循环：{len(loops)} 组同一/关联对手方资金往返",
                risk_level=RiskLevel.HIGH if len(loops) >= 2 else RiskLevel.MEDIUM,
                accounting_standard="CSA 1141 舞弊风险 / CAS 36 关联方披露",
                impact_amount=float(rt.get("loop_amount", 0.0)),
                suspected_mechanism="资金以预付款、往来款等名义流出后短期内由同一或关联对手方流回，可能用于虚构回款或粉饰现金流",
                evidences=[EvidenceItem(
                    evidence_type="资金往返",
                    source_ref=f"流水[{l['out_id']}] → 流水[{l['in_id']}]",
                    detail=f"{l['out_party']} 流出 ¥{l['out_amount']:,.2f}，{l['days']} 天后流入 ¥{l['in_amount']:,.2f}",
                ) for l in loops[:10]],
                suggested_procedure="获取对手方工商与股权信息识别隐性关联方；函证往来余额；检查资金流出的合同与审批、流回的业务实质",
                rule_evidence=rt.get("method", ""),
                model_explanation="由确定性全量分析程序生成，未经大模型",
            ))
        je = analytics.get("journal_entry_testing") or {}
        high = [f for f in je.get("flagged", []) if f.get("score", 0) >= 5]
        if je.get("applicable") and je.get("population", 0) >= 30 and high:
            out.append(RiskFinding(
                finding_id=f"RF-{start + len(out) + 1:03d}",
                title=f"高风险会计分录 {je.get('high_risk_count', len(high))} 张（全量分录测试）",
                risk_level=RiskLevel.MEDIUM,
                accounting_standard="CSA 1141 第三十二条 会计分录测试",
                impact_amount=float(sum(f["amount"] for f in high)),
                suspected_mechanism="多项风险标识叠加（" + "、".join(sorted({n for f in high for n in f["rule_names"]})) + "）",
                evidences=[EvidenceItem(
                    evidence_type="分录测试",
                    source_ref=f"凭证[{f['voucher_id']}]",
                    detail=f"{f['date']} ¥{f['amount']:,.2f} 风险分 {f['score']}：{'、'.join(f['rule_names'])}",
                    source_file=f.get("source_file") or "",
                    row_index=f.get("row_index"),
                ) for f in high[:10]],
                suggested_procedure="对高风险分录逐张检查原始凭证与审批记录，询问制单人与复核人，执行截止测试",
                rule_evidence=je.get("method", ""),
                model_explanation="由确定性全量分析程序生成，未经大模型",
            ))
        return out

    def parse_and_verify(
        self,
        raw_json: Dict[str, Any],
        tool_results: Dict[str, Any],
        case: AccountingCaseData
    ) -> AnalysisReportResult:
        """Parse JSON response and merge with deterministic checks."""
        recon = tool_results.get("reconciliation", {})
        beneish = tool_results.get("beneish")

        findings = []
        for f in raw_json.get("risk_findings", []):
            evidences = [
                EvidenceItem(
                    evidence_type=e.get("evidence_type", "单据比对异常"),
                    source_ref=e.get("source_ref", "凭证库"),
                    detail=e.get("detail", "")
                )
                for e in f.get("evidences", [])
            ]
            level_str = str(f.get("risk_level", "MEDIUM")).upper()
            level = RiskLevel.HIGH if "HIGH" in level_str else (RiskLevel.MEDIUM if "MED" in level_str else RiskLevel.LOW)
            findings.append(
                RiskFinding(
                    finding_id=f.get("finding_id", f"RF-{len(findings)+1:03d}"),
                    title=f.get("title", "未命名风险"),
                    risk_level=level,
                    accounting_standard=f.get("accounting_standard", "CAS 14 / CSA 1141"),
                    impact_amount=float(f.get("impact_amount", 0.0)),
                    suspected_mechanism=f.get("suspected_mechanism", ""),
                    evidences=evidences,
                    suggested_procedure=f.get("suggested_procedure", "执行函证与穿透抽凭"),
                    rule_evidence=f.get("rule_evidence", ""),
                    model_explanation=f.get("model_explanation", ""),
                    human_verification_flag=f.get("human_verification_flag", "待注册会计师实施现场核实程序"),
                    amount_basis=f.get("amount_basis") if isinstance(f.get("amount_basis"), dict) else None,
                    vote_support=f.get("_vote_support"),
                )
            )
            recompute_amount(findings[-1], case)

        workpapers = []
        for wp in raw_json.get("workpapers", []):
            rows = [
                WorkpaperColumn(
                    voucher_no=r.get("voucher_no", ""),
                    date=r.get("date", ""),
                    summary=r.get("summary", ""),
                    ledger_amount=float(r.get("ledger_amount", 0.0)),
                    verified_amount=float(r.get("verified_amount", 0.0)),
                    discrepancy=float(r.get("discrepancy", 0.0)),
                    audit_conclusion=r.get("audit_conclusion", "正常")
                )
                for r in wp.get("rows", [])
            ]
            workpapers.append(
                AuditWorkpaper(
                    workpaper_id=wp.get("workpaper_id", f"WP-{len(workpapers)+1:03d}"),
                    title=wp.get("title", "实质性底稿"),
                    prepared_by=wp.get("prepared_by", "DeepSeek-AuditMind"),
                    review_date=wp.get("review_date", "2026-09-01"),
                    sample_count=int(wp.get("sample_count", len(rows))),
                    total_audited_amount=float(wp.get("total_audited_amount", recon.get("total_audited_amount", 0.0))),
                    abnormal_amount=float(wp.get("abnormal_amount", recon.get("total_abnormal_amount", 0.0))),
                    rows=rows,
                    audit_opinion_summary=wp.get("audit_opinion_summary", "底稿核对完毕")
                )
            )

        rule_findings = raw_json.get("_rule_findings")
        offline = rule_findings is not None
        calibration: Dict[str, Any] = {}
        if offline:
            findings = list(rule_findings)
        else:
            calibration = calibrate_model_findings(findings, case, tool_results)
            text = " ".join(" ".join([f.rule_evidence or "", f.title or ""] + [f"{e.source_ref} {e.detail}" for e in f.evidences]) for f in findings)
            model_cited = {i for i in _source_ids(case) if i in text}
            findings.extend(build_rule_findings(case, tool_results, skip_ids=model_cited))
        findings.extend(self._analytics_findings(tool_results.get("analytics") or {}, start=len(findings)))
        for i, f in enumerate(findings, 1):
            if not f.finding_id or f.finding_id.startswith("RF-R") or offline:
                f.finding_id = f"RF-{i:03d}"
        verification = ground_findings(findings, case, recon, tool_results)
        if calibration:
            verification["calibration"] = calibration
        adjustments = build_adjustments(case, findings, tool_results)
        if offline or not workpapers:
            workpapers = deterministic_workpaper(case, findings)

        overall_rating_str = str(raw_json.get("overall_risk_rating", "MEDIUM")).upper()
        overall_rating = RiskLevel.HIGH if "HIGH" in overall_rating_str else (RiskLevel.MEDIUM if "MED" in overall_rating_str else (RiskLevel.CLEAN if "CLEAN" in overall_rating_str else RiskLevel.LOW))
        levels = {f.risk_level for f in findings}
        ceiling = RiskLevel.HIGH if RiskLevel.HIGH in levels else (RiskLevel.MEDIUM if RiskLevel.MEDIUM in levels else (RiskLevel.LOW if findings else RiskLevel.CLEAN))
        order = [RiskLevel.CLEAN, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
        if order.index(overall_rating) > order.index(ceiling):
            overall_rating = ceiling
        if offline:
            overall_rating = ceiling

        return AnalysisReportResult(
            case_id=case.case_id,
            company_name=case.company_name,
            plugin_name=self.plugin_name,
            overall_risk_rating=overall_rating,
            beneish_m_score=beneish["m_score"] if beneish else None,
            is_beneish_manipulator=beneish["is_manipulator"] if beneish else None,
            findings=findings,
            workpapers=workpapers,
            executive_summary=raw_json.get("executive_summary", "审计穿透分析已完成。"),
            analytics=tool_results.get("analytics") or {},
            verification=verification,
            substantive=tool_results.get("substantive") or {},
            adjustments=adjustments,
        )
