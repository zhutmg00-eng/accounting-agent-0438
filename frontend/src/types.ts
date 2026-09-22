export interface CaseListItem {
  case_id: string
  company_name: string
  stock_code: string
  case_category: string
  penalty_decision_no: string
  audit_period: string
  industry: string
  csrc_summary: string
  voucher_count: number
  invoice_count: number
  contract_count: number
  bank_flow_count: number
  ground_truth_count: number
  is_clean: boolean
}

export interface JournalEntryLine {
  account_code: string
  account_name: string
  debit: number
  credit: number
  summary: string
}

export interface AccountingVoucher {
  voucher_id: string
  voucher_date: string
  entries: JournalEntryLine[]
  associated_doc_id?: string
  source_file?: string
}

export interface InvoiceItem {
  invoice_no: string
  invoice_date: string
  customer_or_vendor: string
  amount: number
  tax_amount: number
  total_amount: number
  item_name: string
}

export interface BankFlowRecord {
  transaction_id: string
  transaction_time: string
  counterparty_name: string
  counterparty_account: string
  amount: number
  balance_after: number
  remark: string
  source_file?: string
}

export interface BusinessContract {
  contract_id: string
  contract_name: string
  customer_or_vendor: string
  sign_date: string
  contract_amount: number
  is_related_party: boolean
}

export interface EvidenceItem {
  evidence_type?: string
  source_ref?: string
  detail?: string
  source_file?: string
  row_index?: number
}

export interface RiskFinding {
  finding_id: string
  title: string
  risk_level: string
  risk_category?: string
  accounting_standard?: string
  csrc_standard_clause?: string
  impact_amount?: number
  abnormal_amount?: number
  suspicious_amount?: number
  confidence_score?: number
  audit_evidence?: string
  evidences?: EvidenceItem[]
  suggested_procedure?: string
  audit_procedure_recommendation?: string
  suspected_mechanism?: string
  rule_evidence?: string
  model_explanation?: string
  human_verification_flag?: string
}

export interface WorkpaperRow {
  voucher_no: string
  date: string
  summary: string
  ledger_amount: number
  verified_amount: number
  discrepancy: number
  audit_conclusion: string
  source_file: string
  evidence_trace: string
}

export interface WorkpaperData {
  workpaper_id: string
  title: string
  prepared_by: string
  review_date: string
  sample_count: number
  total_audited_amount: number
  abnormal_amount: number
  audit_opinion_summary: string
  rows: WorkpaperRow[]
}

export interface AnalysisReportResult {
  case_id: string
  company_name: string
  stock_code: string
  penalty_decision_no: string
  case_category: string
  csrc_summary: string
  overall_risk_rating: string
  beneish_m_score?: number | null
  is_beneish_manipulator?: boolean | null
  executive_summary: string
  findings: RiskFinding[]
  workpapers: WorkpaperData[]
  tool_outputs: Record<string, any>
  reasoning_content: string
  execution_mode: string
  execution_time_seconds: number
  token_usage: Record<string, number>
}

export interface CategorySummary {
  name: string
  count: number
}

export interface DeepSeekModelProfile {
  id: string
  display_name: string
  series: string
  description: string
  has_thinking_mode: boolean
  supports_tools: boolean
  context_window: string
  throughput_tier: string
  recommended_scenario: string
  is_latest_2026: boolean
}

export interface DeepSeekModelsResponse {
  status: string
  is_mock: boolean
  api_base: string
  detected_model: string
  active_model: string
  active_model_profile: DeepSeekModelProfile
  available_models: string[]
  models_detail: DeepSeekModelProfile[]
  latency_ms: number
  message: string
  error_detail?: string
}

export interface AgentToolCall {
  tool_name: string
  tool_input: any
  tool_output: any
  status: string
}

export interface AgentMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoning_content?: string
  tool_calls?: AgentToolCall[]
  timestamp: string
  is_streaming?: boolean
}

export interface AgentGoalStep {
  step: number
  title: string
  status: string
  detail: string
}

export interface AgentGoalResponse {
  status: string
  goal: string
  case_id: string
  company_name: string
  steps: AgentGoalStep[]
  report: AnalysisReportResult
  tool_outputs: Record<string, any>
  elapsed_seconds: number
  execution_mode: string
  model_name: string
}

