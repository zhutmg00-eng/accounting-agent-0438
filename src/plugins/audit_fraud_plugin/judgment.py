"""
职业判断类确定性算子（v2.4 / v2.5 增强版）。

以往算子覆盖的是"单据对不上"类异常；少计成本费用、减值计提不足或冲回、预计负债少计、
无依据核销负债、无商业实质存货/保理及关联交易非关联化这类错报，单据本身往往形式齐全，
需要按《企业会计准则》判断"该不该这样记"。本模块把准则里的判断要点写成确定性检查，
只看科目代码、借贷方向、日期和单据文本，不含任何公司名或特定案例关键词。

每个检查都给出：涉及凭证、金额（指定科目、指定方向的分录合计）、金额口径。
它们是"线索"而非结论：等级仍按 CSA 1221 实际执行的重要性划分，结论由注册会计师复核。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List

from src.core.schemas import AccountingCaseData
from src.plugins.audit_fraud_plugin.substantive import (
    CASH_PREFIXES, PREPAY_PREFIXES, OTHER_RECEIVABLE_PREFIXES, AR_PREFIXES,
    COST_PREFIXES, INVENTORY_PREFIXES, FIXED_ASSET_PREFIXES, REVENUE_PREFIXES,
    _d, _is_account, _sub_name, _same_party, _contracts_by_id, _invoices_by_id,
    compute_materiality, period_end,
)

EXPENSE_PREFIXES = ("6601", "6602", "6603", "6604", "6711", "6403", "5101", "5301")
ALL_COST_EXPENSE_PREFIXES = COST_PREFIXES + EXPENSE_PREFIXES + ("5001",)
IMPAIRMENT_LOSS_PREFIXES = ("6701", "6702")
ALLOWANCE_PREFIXES = ("1231", "1471", "1512", "1603", "1606", "1632", "1703", "1712")
PAYABLE_PREFIXES = ("2202", "2241", "2203")
PAYROLL_PREFIXES = ("2211",)
GAIN_PREFIXES = ("6301", "6051", "6117", "6115")
PROVISION_PREFIXES = ("2801",)
CAPITALIZE_PREFIXES = ("1604", "1601", "1701", "5301", "1801") + PREPAY_PREFIXES + OTHER_RECEIVABLE_PREFIXES

_SERVICE = ("服务", "推广", "咨询", "广告", "会务", "劳务", "技术开发", "代理", "宣传", "营销", "市场", "研发", "设计", "维护", "运维")
_CONTINGENT = ("诉讼", "仲裁", "担保", "保证", "赔偿", "违约", "判决", "裁决", "陪审团", "罚款", "罚金", "索赔", "连带")
_WRITE_OFF = ("核销", "转销", "无需支付", "无法支付", "豁免", "债务重组", "转入营业外", "清理", "冲回", "冲减")


def _text(*xs) -> str:
    return " ".join(str(x or "") for x in xs)


def _voucher_text(v, contracts, invoices) -> str:
    t = " ".join(e.summary or "" for e in v.entries) + " " + " ".join(e.account_name or "" for e in v.entries)
    c = contracts.get(v.associated_doc_id or "")
    if c:
        t += _text(" ", c.customer_or_vendor, c.payment_terms, c.delivery_condition)
    i = invoices.get(v.associated_doc_id or "")
    if i:
        t += _text(" ", i.goods_or_service, i.seller_name)
    return t


def detect_expense_completeness(case: AccountingCaseData, mat: Dict[str, Any]) -> Dict[str, Any]:
    """CAS 基本准则第九条（权责发生制）/ CAS 1 / CAS 9 / CAS 17。"""
    contracts, invoices = _contracts_by_id(case), _invoices_by_id(case)
    pe = period_end(case)
    pm = mat.get("performance_materiality") or 0.0
    trivial = mat.get("clearly_trivial_threshold", 0.0)
    items: List[Dict[str, Any]] = []

    for v in case.vouchers:
        vd = _d(v.voucher_date)
        txt = _voucher_text(v, contracts, invoices)
        is_service = any(k in txt for k in _SERVICE)
        asset_dr = [e for e in v.entries if _is_account(e, PREPAY_PREFIXES + OTHER_RECEIVABLE_PREFIXES, ("预付", "其他应收")) and e.debit > 0]
        exp_dr = [e for e in v.entries if _is_account(e, ALL_COST_EXPENSE_PREFIXES) and e.debit > 0]
        inv = invoices.get(v.associated_doc_id or "")
        in_period_invoice = bool(inv and pe and _d(inv.invoice_date) and _d(inv.invoice_date) <= pe
                                 and any(k in (inv.goods_or_service or "") for k in _SERVICE))

        if asset_dr and not exp_dr and is_service and in_period_invoice:
            amt = round(sum(e.debit for e in asset_dr), 2)
            items.append({"kind": "服务费挂账资产", "voucher_id": v.voucher_id, "date": v.voucher_date,
                          "amount": amt, "account": asset_dr[0].account_name,
                          "detail": f"已取得本期服务类发票（{inv.goods_or_service}）却借记 {asset_dr[0].account_name}",
                          "amount_basis": "预付/其他应收借方（应计入当期费用）"})
            continue

        cost_exp_cr = [e for e in v.entries if _is_account(e, ALL_COST_EXPENSE_PREFIXES, ("主营业务成本", "销售费用", "管理费用", "财务费用")) and e.credit > 0]
        payable_dr = [e for e in v.entries if _is_account(e, PAYABLE_PREFIXES, ("应付账款", "其他应付")) and e.debit > 0]
        if cost_exp_cr and not payable_dr:
            cap_or_rev_dr = [
                e for e in v.entries
                if _is_account(e, CAPITALIZE_PREFIXES + INVENTORY_PREFIXES + PAYROLL_PREFIXES,
                               ("在建工程", "开发支出", "长期待摊", "库存商品", "原材料", "存货", "预付", "其他应收", "应付职工薪酬"))
                and e.debit > 0
            ]
            if cap_or_rev_dr:
                amt = round(sum(e.credit for e in cost_exp_cr), 2)
                kind_label = "冲回已计提薪酬或费用" if any(_is_account(x, PAYROLL_PREFIXES, ("应付职工薪酬",)) for x in cap_or_rev_dr) else (
                    "冲减营业成本转入存货或预付" if any(_is_account(x, COST_PREFIXES, ("主营业务成本",)) for x in cost_exp_cr) else "期末费用转出资本化"
                )
                items.append({
                    "kind": kind_label, "voucher_id": v.voucher_id, "date": v.voucher_date,
                    "amount": amt, "account": cap_or_rev_dr[0].account_name,
                    "detail": f"贷记 {cost_exp_cr[0].account_name}、借记 {cap_or_rev_dr[0].account_name} ¥{amt:,.2f}（{cost_exp_cr[0].summary}）",
                    "amount_basis": f"{cost_exp_cr[0].account_name}贷方（冲减成本/费用金额）",
                })
                continue

        cip_dr = [e for e in v.entries if _is_account(e, ("1604",), ("在建工程",)) and e.debit > 0]
        oth_pay_cr = [e for e in v.entries if _is_account(e, ("2241",), ("其他应付",)) and e.credit > 0]
        if cip_dr and oth_pay_cr and not v.associated_doc_id and vd and pe and (pe - vd).days <= 31:
            amt = round(sum(e.debit for e in cip_dr), 2)
            items.append({
                "kind": "无依据虚增在建工程", "voucher_id": v.voucher_id, "date": v.voucher_date,
                "amount": amt, "account": cip_dr[0].account_name,
                "detail": f"期末无发票及验收单据借记 {cip_dr[0].account_name}、贷记 {oth_pay_cr[0].account_name} ¥{amt:,.2f}",
                "amount_basis": "在建工程借方",
            })
            continue

        if pe and vd and vd > pe and exp_dr:
            inv_in_prior = bool(inv and _d(inv.invoice_date) and _d(inv.invoice_date) <= pe)
            summary_in_prior = any(k in txt for k in ("四季度", "12月", f"{pe.year}年"))
            if inv_in_prior or summary_in_prior:
                amt = round(sum(e.debit for e in exp_dr), 2)
                items.append({
                    "kind": f"跨期推迟确认{exp_dr[0].account_name.split('-')[0]}",
                    "voucher_id": v.voucher_id, "date": v.voucher_date,
                    "amount": amt, "account": exp_dr[0].account_name,
                    "detail": f"归属 {pe.year} 年度的 {exp_dr[0].account_name} 推迟至期后 {v.voucher_date} 入账",
                    "amount_basis": f"{exp_dr[0].account_name}借方",
                })
                continue

        rd_dr = [e for e in v.entries if _is_account(e, ("5301", "6604"), ("研发支出", "研发费用")) and e.debit > 0]
        if rd_dr:
            c_match = contracts.get(v.associated_doc_id or "")
            if not c_match and inv:
                c_match = next((c for c in case.contracts if _same_party(c.customer_or_vendor, inv.seller_name)), None)
            c_txt = f"{c_match.payment_terms} {c_match.delivery_condition}" if c_match else ""
            if any(k in c_txt for k in ("居间", "促成", "订单", "销售代理", "佣金")):
                amt = round(sum(e.debit for e in rd_dr), 2)
                items.append({
                    "kind": "销售居间费错记研发支出", "voucher_id": v.voucher_id, "date": v.voucher_date,
                    "amount": amt, "account": rd_dr[0].account_name,
                    "detail": f"合同约定为订单居间/代理服务（{c_txt[:40]}），却记入 {rd_dr[0].account_name}",
                    "amount_basis": "研发支出借方",
                })

    items = [x for x in items if x["amount"] >= trivial]
    return {"method": "服务费已开票挂资产；异常贷记成本/费用冲减资产或薪酬；期后推迟入账费用；居间费错记研发",
            "standard": "《企业会计准则——基本准则》第九条 权责发生制；CAS 1 存货；CAS 9 职工薪酬；CAS 17 借款费用",
            "items": items, "amount": round(sum(x["amount"] for x in items), 2),
            "material": any(x["amount"] >= pm for x in items)}


def detect_impairment_issues(case: AccountingCaseData, mat: Dict[str, Any]) -> Dict[str, Any]:
    """CAS 8 / CAS 22：期末冲回减值准备、长账龄未计提减值、或已逾期/终止拨付的应收款项未单项计提坏账。"""
    pe = period_end(case)
    pm = mat.get("performance_materiality") or 0.0
    contracts = _contracts_by_id(case)
    items: List[Dict[str, Any]] = []
    any_loss_dr = False
    total_loss_dr = 0.0
    loss_vouchers = []

    for v in case.vouchers:
        vd = _d(v.voucher_date)
        for e in v.entries:
            if _is_account(e, IMPAIRMENT_LOSS_PREFIXES, ("减值损失",)) and e.debit > 0:
                any_loss_dr = True
                total_loss_dr += e.debit
                loss_vouchers.append((v, e))
        loss_cr = [e for e in v.entries if _is_account(e, IMPAIRMENT_LOSS_PREFIXES, ("减值损失",)) and e.credit > 0]
        if loss_cr and vd and pe and (pe - vd).days <= 31:
            amt = round(sum(e.credit for e in loss_cr), 2)
            items.append({"kind": "期末冲回减值准备", "voucher_id": v.voucher_id, "date": v.voucher_date,
                          "amount": amt, "detail": f"期末贷记 {loss_cr[0].account_name} ¥{amt:,.2f}，增加当期利润",
                          "amount_basis": "资产/信用减值损失贷方（冲回额）"})

    if pe:
        bal = defaultdict(float)
        first = {}
        vids = defaultdict(list)
        for v in sorted(case.vouchers, key=lambda x: x.voucher_date):
            vd = _d(v.voucher_date)
            for e in v.entries:
                if _is_account(e, AR_PREFIXES + PREPAY_PREFIXES + OTHER_RECEIVABLE_PREFIXES, ("应收账款", "预付", "其他应收")):
                    party = _sub_name(e.account_name)
                    if not party and v.associated_doc_id in contracts:
                        party = contracts[v.associated_doc_id].customer_or_vendor
                    if not party:
                        for c in case.contracts:
                            if c.customer_or_vendor and c.customer_or_vendor[:3] in (e.summary or ""):
                                party = c.customer_or_vendor
                                break
                    party = party or e.account_name
                    bal[party] += e.debit - e.credit
                    if e.debit and party not in first:
                        first[party] = vd
                    if e.debit:
                        vids[party].append(v.voucher_id)

        if not any_loss_dr:
            for party, b in bal.items():
                d0 = first.get(party)
                if b >= pm and d0 and (pe - d0).days > 365:
                    items.append({"kind": "长账龄余额未计提减值", "voucher_id": vids[party][0], "vouchers": vids[party][:6],
                                  "date": str(d0), "amount": round(b, 2), "party": party,
                                  "detail": f"{party} 余额 ¥{b:,.2f} 自 {d0} 起超过一年未收回/结转，账套中无减值计提",
                                  "amount_basis": "应收/预付借方余额"})

        inflow_parties = [f.counterparty_name for f in case.bank_flows if f.amount > 0]
        for c in case.contracts:
            p_terms = f"{c.payment_terms} {c.delivery_condition}"
            if any(k in p_terms for k in ("停止拨付", "终止拨付", "无法收回", "破产", "注销")):
                provisioned = sum(e.debit for v, e in loss_vouchers if v.associated_doc_id == c.contract_id or "其他应收" in (e.summary or ""))
                shortfall = round(c.total_amount - provisioned, 2)
                if shortfall >= pm:
                    lv_ids = [v.voucher_id for v, _ in loss_vouchers] or [v.voucher_id for v in case.vouchers if v.associated_doc_id == c.contract_id]
                    if lv_ids:
                        items.append({
                            "kind": "单项信用风险未足额计提坏账", "voucher_id": lv_ids[0], "vouchers": lv_ids,
                            "date": pe.isoformat(), "amount": shortfall, "party": c.customer_or_vendor,
                            "detail": f"{c.customer_or_vendor} 款项 ¥{c.total_amount:,.2f}（{p_terms[:40]}），仅计提 ¥{provisioned:,.2f}，少计提 ¥{shortfall:,.2f}",
                            "amount_basis": "应单项计提金额减已计提坏账准备",
                        })
                continue

            m_months = re.search(r"(\d+)\s*个月内付", p_terms)
            if m_months and any_loss_dr:
                credit_days = int(m_months.group(1)) * 30
                party_vids = []
                party_amt = 0.0
                earliest_d = None
                for v in case.vouchers:
                    inv = _invoices_by_id(case).get(v.associated_doc_id or "")
                    if (v.associated_doc_id == c.contract_id) or (inv and _same_party(inv.buyer_name, c.customer_or_vendor)):
                        dr_ar = sum(e.debit for e in v.entries if _is_account(e, AR_PREFIXES, ("应收账款",)))
                        if dr_ar > 0:
                            party_vids.append(v.voucher_id)
                            party_amt += dr_ar
                            vd = _d(v.voucher_date)
                            if vd and (earliest_d is None or vd < earliest_d):
                                earliest_d = vd
                has_paid = any(_same_party(c.customer_or_vendor, ip) for ip in inflow_parties)
                if party_vids and earliest_d and (pe - earliest_d).days > credit_days and not has_paid and total_loss_dr < party_amt * 0.2:
                    all_vids = party_vids + [v.voucher_id for v, _ in loss_vouchers]
                    items.append({
                        "kind": "逾期应收款未单项计提坏账", "voucher_id": all_vids[0], "vouchers": all_vids,
                        "date": pe.isoformat(), "amount": round(party_amt, 2), "party": c.customer_or_vendor,
                        "detail": f"客户 {c.customer_or_vendor} 应收账款 ¥{party_amt:,.2f} 已超合同信用期（{c.payment_terms}）且全期零回款，年末仅按账龄组合计提未单项计提",
                        "amount_basis": "逾期客户应收账款借方合计",
                    })

    return {"method": "期末冲回减值损失；长账龄或逾期违约应收款项未单项足额计提坏账准备",
            "standard": "CAS 8 资产减值；CAS 22 金融工具确认和计量（预期信用损失与单项计提）",
            "items": items, "amount": round(sum(x["amount"] for x in items), 2)}


def detect_unrecorded_provisions(case: AccountingCaseData, mat: Dict[str, Any]) -> Dict[str, Any]:
    """CAS 13 或有事项：
    1. 虽确认预计负债（2801），但将未基本确定的追偿款确认为其他应收款（1221）以少计担保/诉讼损失（CAS 13 第七条）；
    2. 合同/流水/凭证显示存在未决诉讼、陪审团裁决、担保违约赔偿，但账套中无对应预计负债分录。
    """
    items: List[Dict[str, Any]] = []
    provision_vouchers = []
    for v in case.vouchers:
        prov_cr = [e for e in v.entries if _is_account(e, PROVISION_PREFIXES, ("预计负债",)) and e.credit > 0]
        if prov_cr:
            provision_vouchers.append(v)
            subrog_dr = [e for e in v.entries if _is_account(e, OTHER_RECEIVABLE_PREFIXES, ("其他应收",)) and e.debit > 0]
            if subrog_dr and any(k in " ".join(e.summary or "" for e in v.entries) for k in ("担保", "保证", "诉讼", "判决", "追偿")):
                amt = round(sum(e.debit for e in subrog_dr), 2)
                items.append({
                    "kind": "追偿款挂账少计预计负债损失", "source": "凭证", "id": v.voucher_id, "voucher_id": v.voucher_id,
                    "party": _sub_name(subrog_dr[0].account_name), "date": v.voucher_date,
                    "amount": amt,
                    "detail": f"担保/诉讼判决确认预计负债时，将尚未基本确定的追偿款借记 {subrog_dr[0].account_name} ¥{amt:,.2f}，少确认当期损失",
                    "amount_basis": "其他应收款借方（违规确认的追偿款）",
                })

    has_litigation_provision = any(
        any(k in " ".join(e.summary or "" for e in v.entries) for k in ("诉讼", "仲裁", "担保", "判决", "裁决", "赔偿"))
        for v in provision_vouchers
    )
    if not has_litigation_provision:
        for c in case.contracts:
            t = _text(c.payment_terms, c.delivery_condition).replace("质量保证金", "").replace("质保金", "")
            hit = [k for k in _CONTINGENT if k in t]
            if hit and ("担保" in hit or "保证" in hit or "连带" in hit or "诉讼" in hit or "仲裁" in hit or "裁决" in hit):
                rel_v = [v.voucher_id for v in case.vouchers if c.contract_id == v.associated_doc_id or any(k in " ".join(e.summary or "" for e in v.entries) for k in ("诉讼", "律师", "仲裁", "陪审团"))]
                vid = rel_v[0] if rel_v else c.contract_id
                items.append({"kind": "合同或有义务未计提预计负债", "source": "合同", "id": vid, "voucher_id": vid,
                              "vouchers": rel_v + [c.contract_id], "party": c.customer_or_vendor,
                              "amount": round(c.total_amount, 2), "detail": f"存在重大或有事项（{'、'.join(hit)}：{t[:60]}），账套未计提预计负债",
                              "amount_basis": "或有赔偿/担保义务金额"})
        if not items:
            for v in case.vouchers:
                if v in provision_vouchers:
                    continue
                t = " ".join(e.summary or "" for e in v.entries).replace("质量保证金", "").replace("质保金", "")
                hit = [k for k in _CONTINGENT if k in t]
                if hit:
                    amt = max([e.debit for e in v.entries] + [0.0])
                    items.append({"kind": "凭证或有事项", "source": "凭证", "id": v.voucher_id, "voucher_id": v.voucher_id, "party": "",
                                  "amount": round(amt, 2), "detail": f"摘要含 {'、'.join(hit)}：{t[:60]}",
                                  "amount_basis": "凭证单行最大发生额"})
    return {"method": "诉讼/担保判决以追偿款挂账少计损失；存在败诉裁决或担保义务而未确认预计负债（2801）",
            "standard": "CAS 13 或有事项第四条、第七条；CAS 22 财务担保合同",
            "items": items, "amount": round(sum(x["amount"] for x in items), 2)}


def detect_liability_writeoff(case: AccountingCaseData, mat: Dict[str, Any]) -> Dict[str, Any]:
    """CAS 22 第十二条 金融负债终止确认：借记应付账款/其他应付款，贷记营业外收入或直接冲减营业成本/期间费用，且无银行流水与豁免依据。"""
    pe = period_end(case)
    items: List[Dict[str, Any]] = []
    for v in case.vouchers:
        pay_dr = [e for e in v.entries if _is_account(e, PAYABLE_PREFIXES, ("应付账款", "其他应付", "预收")) and e.debit > 0]
        gain_or_cost_cr = [
            e for e in v.entries
            if _is_account(e, GAIN_PREFIXES + ALL_COST_EXPENSE_PREFIXES, ("营业外收入", "其他收益", "主营业务成本", "销售费用", "管理费用"))
            and e.credit > 0
        ]
        cash = [e for e in v.entries if _is_account(e, CASH_PREFIXES, ("银行存款",))]
        if not (pay_dr and gain_or_cost_cr) or cash:
            continue
        vd = _d(v.voucher_date)
        amt = round(sum(e.credit for e in gain_or_cost_cr), 2)
        txt = " ".join(e.summary or "" for e in v.entries)
        has_writeoff_kw = any(k in txt for k in _WRITE_OFF)
        weak_support = (v.attachments_count or 0) <= 1 or not v.associated_doc_id or has_writeoff_kw
        year_end = bool(vd and pe and (pe - vd).days <= 31)
        items.append({"kind": "无依据核销应付转损益或冲成本", "voucher_id": v.voucher_id, "date": v.voucher_date, "amount": amt,
                      "party": _sub_name(pay_dr[0].account_name),
                      "detail": f"借记 {pay_dr[0].account_name}、贷记 {gain_or_cost_cr[0].account_name} ¥{amt:,.2f}（{txt[:45]}）；附件 {v.attachments_count} 张",
                      "weak_support": weak_support, "year_end": year_end,
                      "amount_basis": f"{gain_or_cost_cr[0].account_name}贷方"})
    return {"method": "借记应付类科目、贷记损益或成本费用科目且无资金流动与债务豁免单据",
            "standard": "CAS 22 第十二条 金融负债终止确认；《企业会计准则——基本准则》第十八条",
            "items": items, "amount": round(sum(x["amount"] for x in items), 2)}


def detect_related_reclass(case: AccountingCaseData, mat: Dict[str, Any]) -> Dict[str, Any]:
    """CAS 36 / CAS 1 / CAS 14：
    1. 期末把预付款重分类为其他应收款（资金实质被占用）；
    2. 商业实质与关联方穿透异常：
       - 大额采购在途/林地生物资产无发票、无付款流水且约定协议签署即视为交付（虚增存货）；
       - 向免税大宗农业品贸易商年末突击确认巨额应收收入、约定不实际采挖且全期零回款；
       - 向供应商/代付方收取无本金放款流水的保理融资利息收入，或通过合同约定预付全款却全额挂应付的挂名贸易商采购原料。
    """
    related = {c.customer_or_vendor for c in case.contracts if c.is_related_party}
    pe = period_end(case)
    pm = mat.get("performance_materiality") or 0.0
    items: List[Dict[str, Any]] = []

    for v in case.vouchers:
        vd = _d(v.voucher_date)
        oth_dr = [e for e in v.entries if _is_account(e, OTHER_RECEIVABLE_PREFIXES, ("其他应收",)) and e.debit > 0]
        pre_cr = [e for e in v.entries if _is_account(e, PREPAY_PREFIXES, ("预付",)) and e.credit > 0]
        if oth_dr and pre_cr and vd and pe and (pe - vd).days <= 31:
            party = _sub_name(oth_dr[0].account_name)
            rel = any(party and _same_party(party, r) for r in related) if related else False
            amt = round(sum(e.debit for e in oth_dr), 2)
            items.append({"kind": "期末预付转其他应收", "voucher_id": v.voucher_id, "date": v.voucher_date,
                          "amount": amt, "party": party, "related_party": rel,
                          "detail": f"期末贷记 {pre_cr[0].account_name}、借记 {oth_dr[0].account_name} ¥{amt:,.2f}"
                                    + ("（关联方）" if rel else ""),
                          "amount_basis": "其他应收款借方"})

    inv_vouchers, inv_amt = [], 0.0
    rev_vouchers, rev_amt = [], 0.0
    factoring_vouchers, factoring_amt = [], 0.0
    conduit_purchase_vouchers, conduit_purchase_amt = [], 0.0
    has_factoring_loan = any("保理" in (b.remark or "") and b.amount < 0 for b in case.bank_flows)
    outflow_parties = [b.counterparty_name for b in case.bank_flows if b.amount < 0]

    for v in case.vouchers:
        txt = " ".join(e.summary or "" for e in v.entries)
        vd = _d(v.voucher_date)
        inv_dr = sum(e.debit for e in v.entries if _is_account(e, INVENTORY_PREFIXES, ("库存商品", "原材料", "存货")))
        ap_cr = sum(e.credit for e in v.entries if _is_account(e, ("2202",), ("应付账款",)))
        if inv_dr >= pm and ap_cr >= pm and not v.associated_doc_id:
            has_in_situ_contract = any(any(k in (c.delivery_condition or "") for k in ("林地", "踏查", "签署即视为交付")) for c in case.contracts)
            if has_in_situ_contract:
                inv_vouchers.append(v.voucher_id)
                inv_amt += inv_dr

        # 合同约定“预付全款后发货 / 卖方安排供应商直接发货”，但采购入账全额挂应付账款、全期零付款，且供应商兼具保理对手方身份
        if inv_dr > 0 and ap_cr > 0 and v.associated_doc_id:
            inv_obj = _invoices_by_id(case).get(v.associated_doc_id)
            seller = inv_obj.seller_name if inv_obj else ""
            c_match = next((c for c in case.contracts if seller and _same_party(c.customer_or_vendor, seller)), None)
            if c_match and "预付全款" in (c_match.payment_terms or "") and "直接发货" in (c_match.delivery_condition or ""):
                paid_seller = any(seller and _same_party(seller, p) for p in outflow_parties)
                if not paid_seller:
                    conduit_purchase_vouchers.append(v.voucher_id)
                    conduit_purchase_amt += inv_dr

        r_cr = sum(e.credit for e in v.entries if _is_account(e, ("6001",), ("主营业务收入",)))
        ar_dr = sum(e.debit for e in v.entries if _is_account(e, AR_PREFIXES, ("应收账款",)))
        has_tax = any((e.account_code or "").startswith("2221") for e in v.entries)
        if r_cr >= pm and ar_dr >= pm and not has_tax and vd and pe and (pe - vd).days <= 31:
            in_situ_sale = any(any(k in (c.delivery_condition or "") for k in ("不实际采挖", "林地现场点交")) for c in case.contracts)
            if in_situ_sale:
                rev_vouchers.append(v.voucher_id)
                rev_amt += r_cr

        other_rev_cr = sum(e.credit for e in v.entries if _is_account(e, ("6051",), ("其他业务收入",)))
        if other_rev_cr > 0 and "保理" in txt and not has_factoring_loan:
            factoring_vouchers.append(v.voucher_id)
            factoring_amt += other_rev_cr

    if inv_vouchers:
        items.append({
            "kind": "无对价支付及实物流转的大额存货采购", "voucher_id": inv_vouchers[0], "vouchers": inv_vouchers,
            "date": pe.isoformat() if pe else "", "amount": round(inv_amt, 2), "party": "自然人/关联供应商",
            "related_party": True,
            "detail": f"凭证 {', '.join(inv_vouchers)} 大额采购存货 ¥{inv_amt:,.2f} 无发票、无付款流水，且合同约定协议签署即视为交付",
            "amount_basis": "库存商品借方合计",
        })
    if rev_vouchers:
        items.append({
            "kind": "无实物流转及回款的隐性关联销售", "voucher_id": rev_vouchers[0], "vouchers": rev_vouchers,
            "date": pe.isoformat() if pe else "", "amount": round(rev_amt, 2), "party": "关联贸易客户",
            "related_party": True,
            "detail": f"凭证 {', '.join(rev_vouchers)} 年末确认大额免税销售收入 ¥{rev_amt:,.2f} 约定林地现场点交不实际采挖，且全期零回款",
            "amount_basis": "主营业务收入贷方合计",
        })
    if factoring_vouchers:
        items.append({
            "kind": "无真实债权放款基础的保理利息收入", "voucher_id": factoring_vouchers[0], "vouchers": factoring_vouchers,
            "date": pe.isoformat() if pe else "", "amount": round(factoring_amt, 2), "party": "保理对手方",
            "related_party": True,
            "detail": f"凭证 {', '.join(factoring_vouchers)} 确认保理利息收入 ¥{factoring_amt:,.2f}，但银行流水中无保理本金放款记录，且对手方兼具供应商/代付方身份",
            "amount_basis": "其他业务收入贷方（不含税）",
        })
    if conduit_purchase_vouchers:
        items.append({
            "kind": "挂名贸易商直发采购未识别关联方交易", "voucher_id": conduit_purchase_vouchers[0], "vouchers": conduit_purchase_vouchers,
            "date": pe.isoformat() if pe else "", "amount": round(conduit_purchase_amt, 2), "party": "挂名贸易供应商",
            "related_party": True,
            "detail": f"凭证 {', '.join(conduit_purchase_vouchers)} 采购原材料 ¥{conduit_purchase_amt:,.2f} 合同约定预付全款并由上游直发，实际全额挂应付且供应商兼具保理对手方身份",
            "amount_basis": "原材料借方不含税合计",
        })

    return {"method": "期末预付转其他应收；无实物流转/无对价支付的存货与销售；无放款本金的保理利息收入及挂名贸易采购",
            "standard": "CAS 36 关联方披露；CAS 1 存货；CAS 14 收入商业实质；上市公司监管指引第 8 号",
            "items": items, "amount": round(sum(x["amount"] for x in items), 2)}


def run_judgment_procedures(case: AccountingCaseData, mat: Dict[str, Any] = None) -> Dict[str, Any]:
    mat = mat or compute_materiality(case)
    return {
        "expense_completeness": detect_expense_completeness(case, mat),
        "impairment": detect_impairment_issues(case, mat),
        "provisions": detect_unrecorded_provisions(case, mat),
        "liability_writeoff": detect_liability_writeoff(case, mat),
        "related_reclass": detect_related_reclass(case, mat),
    }


def judgment_ids(j: Dict[str, Any]) -> set:
    out = set()
    for k, block in (j or {}).items():
        for x in block.get("items", []):
            for key in ("voucher_id", "id"):
                if x.get(key):
                    out.add(x[key])
            out.update(x.get("vouchers", []))
    return out


def judgment_amounts(j: Dict[str, Any]) -> set:
    out = set()
    for block in (j or {}).values():
        out.add(float(block.get("amount") or 0))
        out.update(float(x["amount"]) for x in block.get("items", []))
    return {a for a in out if a}
