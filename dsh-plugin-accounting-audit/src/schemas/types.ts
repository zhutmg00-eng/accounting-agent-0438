export type RiskLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'CLEAN';

export interface JournalEntryLine {
  accountCode: string;
  accountName: string;
  debit: number;
  credit: number;
  summary: string;
}

export interface AccountingVoucher {
  voucherId: string;
  voucherDate: string;
  preparer: string;
  checker?: string;
  entries: JournalEntryLine[];
  attachmentsCount?: number;
  associatedDocId?: string;
}

export interface BusinessContract {
  contractId: string;
  customerOrVendor: string;
  signDate: string;
  totalAmount: number;
  paymentTerms: string;
  deliveryCondition: string;
  isRelatedParty: boolean;
}

export interface InvoiceItem {
  invoiceNo: string;
  invoiceDate: string;
  buyerName: string;
  sellerName: string;
  amountWithoutTax: number;
  taxAmount: number;
  totalAmount: number;
  goodsOrService: string;
}

export interface BankFlowRecord {
  transactionId: string;
  transactionTime: string;
  counterpartyName: string;
  counterpartyAccount: string;
  amount: number;
  balanceAfter: number;
  remark: string;
}

export interface FinancialStatementsSummary {
  period: string;
  revenue: number;
  costOfSales: number;
  grossMargin: number;
  netProfit: number;
  accountsReceivable: number;
  inventory: number;
  totalAssets: number;
  operatingCashFlow: number;
}

export interface AccountingCaseData {
  caseId: string;
  companyName: string;
  industry: string;
  auditPeriod: string;
  description: string;
  financialSummary?: FinancialStatementsSummary;
  vouchers: AccountingVoucher[];
  contracts: BusinessContract[];
  invoices: InvoiceItem[];
  bankFlows: BankFlowRecord[];
  groundTruthRisks?: string[];
}

export interface EvidenceItem {
  evidenceType: string;
  sourceRef: string;
  detail: string;
}

export interface RiskFinding {
  findingId: string;
  title: string;
  riskLevel: RiskLevel;
  accountingStandard: string;
  impactAmount: number;
  suspectedMechanism: string;
  evidences: EvidenceItem[];
  suggestedProcedure: string;
}

export interface WorkpaperRow {
  voucherNo: string;
  date: string;
  summary: string;
  ledgerAmount: number;
  verifiedAmount: number;
  discrepancy: number;
  auditConclusion: string;
}

export interface AuditWorkpaper {
  workpaperId: string;
  title: string;
  preparedBy: string;
  reviewDate: string;
  sampleCount: number;
  totalAuditedAmount: number;
  abnormalAmount: number;
  rows: WorkpaperRow[];
  auditOpinionSummary: string;
}

export interface AuditReportResult {
  caseId: string;
  companyName: string;
  pluginName: string;
  overallRiskRating: RiskLevel;
  beneishMScore?: number;
  isBeneishManipulator?: boolean;
  findings: RiskFinding[];
  workpapers: AuditWorkpaper[];
  executiveSummary: string;
  executionTimeSeconds: number;
}
