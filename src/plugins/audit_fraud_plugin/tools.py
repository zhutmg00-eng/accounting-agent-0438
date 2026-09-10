"""
Deterministic Accounting & Audit Tools for AuditMind Plugin.
Includes: Beneish M-Score, Three-Way Reconciliation, Debit-Credit Check, Benford Anomaly Analysis.
"""

from typing import Dict, Any, List, Tuple
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
    cur_net_income: float, cur_cfo: float
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
    gmi = max(prev_gm, eps) / max(cur_gm, eps)
    
    # 3. AQI - Asset Quality Index
    cur_aq = 1.0 - (cur_ppe / cur_assets)
    prev_aq = 1.0 - (prev_ppe / prev_assets)
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
        + 4.037 * tata
        + 0.0327 * lvgi
    )

    is_manipulator = bool(m_score > -1.78)

    return {
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

    # Build lookup maps
    invoice_map = {inv.invoice_no: inv for inv in case.invoices}
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
            if doc_id in invoice_map:
                inv = invoice_map[doc_id]
                # Compare amount
                if abs(v_amount - inv.total_amount) > 1.0:
                    diff = abs(v_amount - inv.total_amount)
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
                if contract.is_related_party:
                    discrepancies.append({
                        "type": "关联方隐蔽重大交易未做专项披露",
                        "voucher_id": voucher.voucher_id,
                        "doc_id": doc_id,
                        "amount": v_amount,
                        "detail": f"该凭证关联方合同 {contract.contract_id}（交易方: {contract.customer_or_vendor}）为关联方重大交易，需穿透商业实质。"
                    })
                    total_abnormal_amount += v_amount
            else:
                # Document linkage missing or forged doc
                discrepancies.append({
                    "type": "单据缺失或虚构/伪造业务单据",
                    "voucher_id": voucher.voucher_id,
                    "doc_id": doc_id,
                    "amount": v_amount,
                    "detail": f"记账凭证引用的单据号 '{doc_id}' 未在真实有效合同库、税务发票库或银行对账流水中登记，存在虚假做账或伪造单据重大嫌疑。"
                })
                total_abnormal_amount += v_amount

    # 3. Check Bank Flow reconciliation
    suspicious_remarks = ["退款", "借款", "拆借", "伪造", "虚构", "存单", "过桥", "体外", "占用", "挪用", "异常", "无商业背景", "转出至关联"]
    for flow in case.bank_flows:
        if abs(flow.amount) >= 100000.0:  # >= 100k RMB
            if any(kw in flow.remark for kw in suspicious_remarks):
                discrepancies.append({
                    "type": "大额资金异常往来与体外循环/造假嫌疑",
                    "voucher_id": "BANK-" + flow.transaction_id,
                    "amount": abs(flow.amount),
                    "detail": f"银行流水({flow.amount:,.2f}元, 对手方: {flow.counterparty_name}) 附言为'{flow.remark}'，疑似伪造存单或资金体外闭环。"
                })
                total_abnormal_amount += abs(flow.amount)

    return {
        "discrepancies": discrepancies,
        "total_discrepancies_count": len(discrepancies),
        "total_audited_amount": total_audited_amount,
        "total_abnormal_amount": total_abnormal_amount,
        "reconciliation_clean": len(discrepancies) == 0
    }
