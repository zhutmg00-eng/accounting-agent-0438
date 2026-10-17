"""
Deterministic Accounting & Audit Tools for AuditMind Plugin.
Includes: Beneish M-Score, Three-Way Reconciliation, Debit-Credit Check, Benford Anomaly Analysis.
"""

from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple
from src.core.schemas import AccountingCaseData, AccountingVoucher, BusinessContract, InvoiceItem, BankFlowRecord


def calculate_beneish_m_score(
    cur_sales: float, prev_sales: float,
    cur_ar: float, prev_ar: float,
    cur_cogs: float, prev_cogs: float,
    cur_assets: float, prev_assets: float,
    cur_depr: float, prev_depr: float,
    cur_ppe: float, prev_ppe: float,
    cur_sga: float, prev_sga: float,
    cur_leverage: float, prev_leverage: float,
    cur_net_income: float, cur_cfo: float,
    cur_ca: Optional[float] = None, prev_ca: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate Beneish M-Score (8-variable model).
    Threshold: M > -1.78 indicates high probability of earnings manipulation.
    """
    eps = 1e-6
    prev_sales = max(prev_sales, eps)
    cur_sales = max(cur_sales, eps)
    prev_assets = max(prev_assets, eps)
    cur_assets = max(cur_assets, eps)

    # 1. DSRI - Days Sales in Receivables Index
    dsri = (cur_ar / cur_sales) / max(prev_ar / prev_sales, eps)
    
    # 2. GMI - Gross Margin Index
    prev_gm = (prev_sales - prev_cogs) / prev_sales
    cur_gm = (cur_sales - cur_cogs) / cur_sales
    # 毛利率为负或为零时 GMI 失去经济含义（分母趋零会把 M 值推到上万），
    # 按中性值 1.0 处理并在结果中标注，而不是输出一个荒谬的分数。
    gmi_neutralized = cur_gm <= 0 or prev_gm <= 0
    gmi = 1.0 if gmi_neutralized else prev_gm / cur_gm
    
    # 3. AQI - Asset Quality Index (Beneish 1999):
    #    AQI = [1 - (CA_t + PPE_t)/TA_t] / [1 - (CA_t-1 + PPE_t-1)/TA_t-1]
    #    流动资产缺失时不再用 1-PPE/TA 近似（那会把流动资产当成"软资产"，系统性高估 AQI），
    #    而是按文献惯例取中性值 1.0 并明确标注。
    aqi_neutralized = cur_ca is None or prev_ca is None
    if aqi_neutralized:
        aqi = 1.0
    else:
        cur_aq = 1.0 - ((cur_ca + cur_ppe) / cur_assets)
        prev_aq = 1.0 - ((prev_ca + prev_ppe) / prev_assets)
        aqi = max(cur_aq, eps) / max(prev_aq, eps)
    
    # 4. SGI - Sales Growth Index
    sgi = cur_sales / prev_sales
    
    # 5. DEPI - Depreciation Index
    cur_depr_rate = cur_depr / max(cur_ppe + cur_depr, eps)
    prev_depr_rate = prev_depr / max(prev_ppe + prev_depr, eps)
    depi = max(prev_depr_rate, eps) / max(cur_depr_rate, eps)
    
    # 6. SGAI - Sales General and Administrative Expenses Index
    sgai = (cur_sga / cur_sales) / max(prev_sga / prev_sales, eps)
    
    # 7. LVGI - Leverage Index
    lvgi = cur_leverage / max(prev_leverage, eps)
    
    # 8. TATA - Total Accruals to Total Assets
    total_accruals = cur_net_income - cur_cfo
    tata = total_accruals / cur_assets

    # Beneish 8-variable formula
    m_score = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )

    is_manipulator = bool(m_score > -1.78)

    return {
        "is_calculable": True,
        "aqi_neutralized": aqi_neutralized,
        "gmi_neutralized": gmi_neutralized,
        "m_score": round(m_score, 4),
        "is_manipulator": is_manipulator,
        "variables": {
            "DSRI (应收账款指数)": round(dsri, 4),
            "GMI (毛利率指数)": round(gmi, 4),
            "AQI (资产质量指数)": round(aqi, 4),
            "SGI (销售增长指数)": round(sgi, 4),
            "DEPI (折旧率指数)": round(depi, 4),
            "SGAI (销售管理费用指数)": round(sgai, 4),
            "LVGI (财务杠杆指数)": round(lvgi, 4),
            "TATA (总应计项比率)": round(tata, 4)
        },
        "conclusion": "Beneish M-Score 超过 -1.78 临界值，财务报表存在重大利润操纵/舞弊嫌疑！" if is_manipulator else "Beneish M-Score 处于正常安全区间，未发现显著财报操纵特征。"
    }


def calculate_beneish_from_case(case: AccountingCaseData) -> Dict[str, Any]:
    """
    Rigorously calculate Beneish M-Score based on genuine comparative (2-period) financial statements.
    If comparative data is absent, returns an explicit uncalculable status and lists missing fields,
    strictly refusing to fake scores or invent dummy multipliers (Addresses Issue #7).
    """
    if not case.financial_summary:
        return {
            "is_calculable": False,
            "m_score": None,
            "is_manipulator": False,
            "reason": "缺少当期财务报表数据，Beneish 8因子量化模型无法执行",
            "missing_fields": ["本期财务报表摘要"],
            "variables": {},
            "conclusion": "未提供财务报表数据，Beneish 模型不可计算"
        }

    cur = case.financial_summary
    prev = case.prior_financial_summary

    if not prev:
        return {
            "is_calculable": False,
            "m_score": None,
            "is_manipulator": False,
            "reason": "缺少对比期（上年同期）财务报表数据，无法计算跨期变动指数（SGI、DSRI、GMI等）",
            "missing_fields": [
                "上期营业收入 (prev_sales)",
                "上期应收账款 (prev_ar)",
                "上期营业成本 (prev_cogs)",
                "上期资产总额 (prev_assets)"
            ],
            "variables": {},
            "conclusion": "缺少对比期财务数据，Beneish 动态模型不可计算（已如实标记，严禁伪造数据）"
        }

    required_fields = {
        "本期固定资产 (fixed_assets)": cur.fixed_assets,
        "上期固定资产 (fixed_assets)": prev.fixed_assets,
        "本期折旧与摊销 (depreciation)": cur.depreciation,
        "上期折旧与摊销 (depreciation)": prev.depreciation,
        "本期销售与管理费用 (sga_expenses)": cur.sga_expenses,
        "上期销售与管理费用 (sga_expenses)": prev.sga_expenses,
        "本期财务杠杆 (leverage_ratio)": cur.leverage_ratio,
        "上期财务杠杆 (leverage_ratio)": prev.leverage_ratio,
    }
    missing_fields = [name for name, value in required_fields.items() if value is None]
    if missing_fields:
        return {
            "is_calculable": False,
            "m_score": None,
            "is_manipulator": False,
            "reason": "缺少 Beneish 8 因子所需的明细财务字段，未使用估算值",
            "missing_fields": missing_fields,
            "variables": {},
            "conclusion": "财务字段不完整，Beneish 模型不可计算",
        }

    cur_ppe = cur.fixed_assets
    prev_ppe = prev.fixed_assets
    cur_depr = cur.depreciation
    prev_depr = prev.depreciation
    cur_sga = cur.sga_expenses
    prev_sga = prev.sga_expenses
    cur_lev = cur.leverage_ratio
    prev_lev = prev.leverage_ratio

    res = calculate_beneish_m_score(
        cur_sales=cur.revenue, prev_sales=prev.revenue,
        cur_ar=cur.accounts_receivable, prev_ar=prev.accounts_receivable,
        cur_cogs=cur.cost_of_sales, prev_cogs=prev.cost_of_sales,
        cur_assets=cur.total_assets, prev_assets=prev.total_assets,
        cur_depr=cur_depr, prev_depr=prev_depr,
        cur_ppe=cur_ppe, prev_ppe=prev_ppe,
        cur_sga=cur_sga, prev_sga=prev.sga_expenses,
        cur_leverage=cur_lev, prev_leverage=prev_lev,
        cur_net_income=cur.net_profit, cur_cfo=cur.operating_cash_flow,
        cur_ca=cur.current_assets, prev_ca=prev.current_assets,
    )
    res["is_calculable"] = True
    estimated = sorted(set(cur.estimated_fields) | {f"上期·{f}" for f in prev.estimated_fields})
    reconstructed = "reconstructed" in {cur.provenance, prev.provenance}
    res["input_quality"] = "reconstructed" if (reconstructed or estimated) else "reported"
    res["estimated_fields"] = estimated
    notes = []
    if res.get("gmi_neutralized"):
        notes.append("本期或上期毛利率≤0，GMI 失去经济含义，按中性值 1.0 处理")
    if res.get("aqi_neutralized"):
        notes.append("缺少流动资产数据，AQI 按 Beneish 文献惯例取中性值 1.0")
    if reconstructed or estimated:
        notes.append("部分输入为按比例结构化重构的估算值，M-Score 仅演示算法流程，不构成对该公司的量化结论；正式使用须替换为年报披露原值")
    res["data_source"] = f"基于 {cur.period} 与 {prev.period} 两期财务数据计算" + ("（" + "；".join(notes) + "）" if notes else "")
    res["caveats"] = notes
    return res


def contract_has_supporting_evidence(contract, case: AccountingCaseData) -> bool:
    """True when a contract-backed transaction is also evidenced by an invoice or a payment."""
    party = (contract.customer_or_vendor or "").strip()
    if not party:
        return False
    for inv in case.invoices:
        if party in (inv.buyer_name or "") or party in (inv.seller_name or ""):
            return True
    for flow in case.bank_flows:
        if party in (flow.counterparty_name or ""):
            return True
    return False


def _document_amount_diff(voucher, v_amount: float, doc_amount: float, extra_doc_amounts: Optional[List[float]] = None) -> float:
    """凭证与单据金额的差异。

    1. 复合凭证常把销售确认与成本结转写在同一张凭证里（借应收/贷收入、销项，借成本/贷存货），
       此时凭证借方合计 = 价税合计 + 成本，直接与发票/合同比对会误报"金额不符"。
    2. 兼营多税率业务（如物流企业收派服务 6% + 运输服务 9%）常在同一张月结凭证中分列多条
       收入与销项税分录，并对应同日开具的多张分税率发票（一证多票）。因此候选值除凭证总额与
       单行金额外，还纳入“单行不含税金额 + 对应税额”的组合，以及同日同客户关联发票合计。
    """
    candidates = [v_amount]
    debits = [e.debit for e in voucher.entries if e.debit]
    credits = [e.credit for e in voucher.entries if e.credit]
    candidates.extend(debits)
    candidates.extend(credits)
    # 组合：同一借方或同一贷方内的分录两两相加（如分税率收入 800万 + 对应销项税 48万 = 848万）
    for side_vals in (debits, credits):
        if 2 <= len(side_vals) <= 8:
            for i in range(len(side_vals)):
                for j in range(i + 1, len(side_vals)):
                    candidates.append(round(side_vals[i] + side_vals[j], 2))
    targets = [doc_amount] + (extra_doc_amounts or [])
    return min(abs(c - t) for c in candidates for t in targets)


def perform_three_way_reconciliation(case: AccountingCaseData) -> Dict[str, Any]:
    """
    Perform 3-way matching between:
    - Accounting Vouchers
    - Business Contracts
    - Invoices
    - Bank Flow Records
    """
    discrepancies = []
    total_audited_amount = 0.0
    total_abnormal_amount = 0.0

    # 按发票号分组（不同发票代码下可能出现相同 8 位发票号，避免字典覆盖导致误报）
    invoices_by_no: Dict[str, List[InvoiceItem]] = defaultdict(list)
    for inv in case.invoices:
        invoices_by_no[inv.invoice_no].append(inv)
    contract_map = {c.contract_id: c for c in case.contracts}
    bank_map = {b.transaction_id: b for b in case.bank_flows}

    for voucher in case.vouchers:
        v_debit = sum(e.debit for e in voucher.entries)
        v_credit = sum(e.credit for e in voucher.entries)
        v_amount = max(v_debit, v_credit)
        total_audited_amount += v_amount

        # 1. Check debit/credit balance
        if abs(v_debit - v_credit) > 0.01:
            diff = abs(v_debit - v_credit)
            discrepancies.append({
                "type": "借贷不平衡",
                "voucher_id": voucher.voucher_id,
                "amount": diff,
                "detail": f"凭证 {voucher.voucher_id} 借方合计({v_debit:.2f}) != 贷方合计({v_credit:.2f})"
            })
            total_abnormal_amount += diff

        # 2. Check doc linkages
        if voucher.associated_doc_id:
            doc_id = voucher.associated_doc_id
            
            # Matched to invoice?
            if doc_id in invoices_by_no:
                inv_candidates = invoices_by_no[doc_id]
                # 选择与当前凭证金额/日期最匹配的发票实例
                inv = min(
                    inv_candidates,
                    key=lambda x: (
                        0 if x.invoice_date == voucher.voucher_date else 1,
                        _document_amount_diff(voucher, v_amount, x.total_amount),
                    ),
                )
                # 同日同买卖双方的合并开票总额（支持一证多票/兼营分票开具）
                same_batch_invoices = [
                    x for x in case.invoices
                    if x.invoice_date == inv.invoice_date
                    and x.buyer_name == inv.buyer_name
                    and x.seller_name == inv.seller_name
                ]
                extra_totals = [round(sum(x.total_amount for x in same_batch_invoices), 2)] if len(same_batch_invoices) > 1 else []

                # Compare amount
                diff = _document_amount_diff(voucher, v_amount, inv.total_amount, extra_totals)
                if diff > 1.0:
                    discrepancies.append({
                        "type": "凭证与发票金额不符",
                        "voucher_id": voucher.voucher_id,
                        "doc_id": doc_id,
                        "amount": diff,
                        "detail": f"凭证金额 ({v_amount:.2f}元) 与发票价税合计 ({inv.total_amount:.2f}元) 存在差异 {diff:.2f}元"
                    })
                    total_abnormal_amount += diff
                
                # Compare date: voucher before invoice date is suspicious (premature revenue recognition)
                if voucher.voucher_date < inv.invoice_date and (v_amount > 100000):
                    discrepancies.append({
                        "type": "凭证开具早于发票日期(疑似跨期提前确认收入)",
                        "voucher_id": voucher.voucher_id,
                        "doc_id": doc_id,
                        "amount": v_amount,
                        "detail": f"记账凭证日期({voucher.voucher_date}) 早于税务发票开具日期({inv.invoice_date})，涉及金额 {v_amount:,.2f}元"
                    })
                    total_abnormal_amount += v_amount

            # Matched to contract?
            elif doc_id in contract_map:
                contract = contract_map[doc_id]
                diff = _document_amount_diff(voucher, v_amount, contract.total_amount)
                if diff > 1.0:
                    discrepancies.append({
                        "type": "凭证与合同金额不符",
                        "voucher_id": voucher.voucher_id,
                        "doc_id": doc_id,
                        "amount": diff,
                        "detail": f"凭证金额 ({v_amount:,.2f}元) 与合同总额 ({contract.total_amount:,.2f}元) 存在差异 {diff:,.2f}元，业财金额勾稽不符。"
                    })
                    total_abnormal_amount += diff
                if contract.is_related_party:
                    terms_txt = f"{contract.payment_terms} {contract.delivery_condition}"
                    disclosed_normal = any(k in terms_txt for k in ("股东大会审议", "董事会审议", "已披露", "日常关联交易")) and contract_has_supporting_evidence(contract, case)
                    if not disclosed_normal:
                        discrepancies.append({
                            "type": "关联方隐蔽重大交易未做专项披露",
                            "voucher_id": voucher.voucher_id,
                            "doc_id": doc_id,
                            "amount": v_amount,
                            "detail": f"该凭证关联方合同 {contract.contract_id}（交易方: {contract.customer_or_vendor}）为关联方重大交易，需穿透商业实质。"
                        })
                        total_abnormal_amount += v_amount
                elif not contract_has_supporting_evidence(contract, case):
                    discrepancies.append({
                        "type": "大额业务单据缺失发票及银行流水(三单勾稽缺失)",
                        "voucher_id": voucher.voucher_id,
                        "doc_id": doc_id,
                        "amount": v_amount,
                        "detail": f"记账凭证引用的合同 '{doc_id}'（交易方: {contract.customer_or_vendor}，金额: {contract.total_amount:,.2f}元）缺乏真实税务发票及银行收付款对账单，三单勾稽严重脱节，涉嫌虚构业务。"
                    })
                    total_abnormal_amount += v_amount
            elif doc_id in bank_map:
                flow = bank_map[doc_id]
                diff = _document_amount_diff(voucher, v_amount, abs(flow.amount))
                if diff > 1.0:
                    discrepancies.append({
                        "type": "凭证与银行流水金额不符",
                        "voucher_id": voucher.voucher_id,
                        "doc_id": doc_id,
                        "amount": diff,
                        "detail": f"凭证金额 ({v_amount:,.2f}元) 与银行流水 {doc_id} ({abs(flow.amount):,.2f}元) 存在差异 {diff:,.2f}元",
                    })
                    total_abnormal_amount += diff
            else:
                discrepancies.append({
                    "type": "单据缺失或虚构/伪造业务单据",
                    "voucher_id": voucher.voucher_id,
                    "doc_id": doc_id,
                    "amount": v_amount,
                    "detail": f"记账凭证引用的单据号 '{doc_id}' 未在真实有效合同库、税务发票库或银行对账流水中登记，存在虚假做账或伪造单据重大嫌疑。"
                })
                total_abnormal_amount += v_amount

    # 3. Check Bank Flow reconciliation
    suspicious_remarks = ["退款", "借款", "暂借", "拆借", "往来", "划拨", "归集", "垫付", "伪造", "虚构", "存单", "过桥", "体外", "占用", "挪用", "异常", "无商业背景", "转出至关联"]
    for flow in case.bank_flows:
        if abs(flow.amount) >= 100000.0:
            if any(kw in flow.remark for kw in suspicious_remarks):
                discrepancies.append({
                    "type": "大额资金异常往来与体外循环/造假嫌疑",
                    "voucher_id": "BANK-" + flow.transaction_id,
                    "amount": abs(flow.amount),
                    "detail": f"银行流水({flow.amount:,.2f}元, 对手方: {flow.counterparty_name}) 附言为'{flow.remark}'，疑似伪造存单或资金体外闭环。"
                })
                total_abnormal_amount += abs(flow.amount)

    voucher_side = [d["amount"] for d in discrepancies if not str(d.get("voucher_id", "")).startswith("BANK-")]
    bank_side = [d["amount"] for d in discrepancies if str(d.get("voucher_id", "")).startswith("BANK-")]
    remaining = list(bank_side)
    for a in voucher_side:
        for j, b in enumerate(remaining):
            if abs(a - b) <= max(abs(a) * 0.001, 1.0):
                remaining.pop(j)
                break
    net_exposure = round(sum(voucher_side) + sum(remaining), 2)

    return {
        "discrepancies": discrepancies,
        "total_discrepancies_count": len(discrepancies),
        "total_audited_amount": total_audited_amount,
        "total_abnormal_amount": total_abnormal_amount,
        "net_exposure_amount": net_exposure,
        "reconciliation_clean": len(discrepancies) == 0
    }
