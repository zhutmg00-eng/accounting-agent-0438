import { AccountingCaseData } from '../schemas/types';

export function performThreeWayReconciliation(caseData: AccountingCaseData) {
  const discrepancies: Array<{
    type: string;
    voucherId: string;
    docId?: string;
    amount: number;
    detail: string;
  }> = [];

  let totalAuditedAmount = 0;
  let totalAbnormalAmount = 0;

  const invoiceMap = new Map(caseData.invoices.map(inv => [inv.invoiceNo, inv]));
  const contractMap = new Map(caseData.contracts.map(c => [c.contractId, c]));

  for (const voucher of caseData.vouchers) {
    const debitSum = voucher.entries.reduce((sum, e) => sum + e.debit, 0);
    const creditSum = voucher.entries.reduce((sum, e) => sum + e.credit, 0);
    const vAmount = Math.max(debitSum, creditSum);
    totalAuditedAmount += vAmount;

    // 1. Check debit/credit balance
    if (Math.abs(debitSum - creditSum) > 0.01) {
      const diff = Math.abs(debitSum - creditSum);
      discrepancies.push({
        type: '借贷不平衡',
        voucherId: voucher.voucherId,
        amount: diff,
        detail: `凭证 ${voucher.voucherId} 借方(${debitSum.toFixed(2)}) != 贷方(${creditSum.toFixed(2)})`
      });
      totalAbnormalAmount += diff;
    }

    // 2. Document linkage & timeline check
    if (voucher.associatedDocId) {
      const docId = voucher.associatedDocId;
      const inv = invoiceMap.get(docId);
      if (inv) {
        if (Math.abs(vAmount - inv.totalAmount) > 1.0) {
          const diff = Math.abs(vAmount - inv.totalAmount);
          discrepancies.push({
            type: '凭证与发票金额不符',
            voucherId: voucher.voucherId,
            docId,
            amount: diff,
            detail: `凭证金额(¥${vAmount.toLocaleString()}) 与发票价税合计(¥${inv.totalAmount.toLocaleString()}) 差异 ¥${diff.toFixed(2)}`
          });
          totalAbnormalAmount += diff;
        }

        if (voucher.voucherDate < inv.invoiceDate && vAmount > 100000) {
          discrepancies.push({
            type: '凭证开具早于发票日期(疑似跨期提前确认收入)',
            voucherId: voucher.voucherId,
            docId,
            amount: vAmount,
            detail: `记账凭证日期(${voucher.voucherDate}) 早于发票开具日期(${inv.invoiceDate})`
          });
          totalAbnormalAmount += vAmount;
        }
      }

      const contract = contractMap.get(docId);
      if (contract && contract.isRelatedParty) {
        discrepancies.push({
          type: '关联方隐蔽重大交易未作专项披露',
          voucherId: voucher.voucherId,
          docId,
          amount: vAmount,
          detail: `关联方合同 ${contract.contractId} (交易方: ${contract.customerOrVendor}) 涉嫌体外资金循环或非商业实质交易`
        });
        totalAbnormalAmount += vAmount;
      }
    }
  }

  // 3. Bank flow matching
  for (const flow of caseData.bankFlows) {
    if (Math.abs(flow.amount) >= 1000000) {
      if (flow.remark.includes('退款') || flow.remark.includes('借款') || flow.remark.includes('拆借')) {
        discrepancies.push({
          type: '大额资金异常往来与体外循环嫌疑',
          voucherId: `BANK-${flow.transactionId}`,
          amount: Math.abs(flow.amount),
          detail: `大额流水(¥${flow.amount.toLocaleString()}, 对手方: ${flow.counterpartyName}) 附言为'${flow.remark}'，存在资金闭环回流特征`
        });
        totalAbnormalAmount += Math.abs(flow.amount);
      }
    }
  }

  return {
    discrepancies,
    totalDiscrepanciesCount: discrepancies.length,
    totalAuditedAmount,
    totalAbnormalAmount,
    reconciliationClean: discrepancies.length === 0
  };
}
