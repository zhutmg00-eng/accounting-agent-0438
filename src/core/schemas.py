"""
Pydantic Schemas for Accounting Agent, Audit Findings, and Benchmark Harness.
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    STRICT_ONLINE = "strict-online"  # 严格在线模式 (失败直接报错，绝不静默降级)
    ONLINE = "online"                # 在线优先模式 (支持显式降级标记)
    MOCK = "mock"                    # 离线确定性演示模式 (标注模拟结果)


class RiskLevel(str, Enum):
    HIGH = "HIGH"          # 高风险 (重大错报/舞弊嫌疑)
    MEDIUM = "MEDIUM"      # 中风险 (合规瑕疵/需进一步取证)
    LOW = "LOW"            # 低风险 (一般性关注)
    CLEAN = "CLEAN"        # 无异常 (合规)


class AccountingStandard(str, Enum):
    CAS_14_REVENUE = "CAS 14 - 收入准则 (新收入准则五步法)"
    CAS_1_INVENTORY = "CAS 1 - 存货准则"
    CAS_36_RELATED_PARTY = "CAS 36 - 关联方披露准则"
    CAS_28_ACCOUNTING_CHANGES = "CAS 28 - 会计政策、估计变更和差错更正"
    CSA_1101_AUDIT_OBJECTIVE = "CSA 1101 - 注册会计师审计准则第1101号"
    CSA_1141_FRAUD_RESPONSIBILITY = "CSA 1141 - 财务报表审计中与舞弊相关的责任"


# 1. 业务凭证与业财基础数据
class JournalEntryLine(BaseModel):
    account_code: str = Field(description="会计科目编码，例如 1002, 1122, 6001")
    account_name: str = Field(description="科目名称，如 银行存款、应收账款、主营业务收入")
    debit: float = Field(default=0.0, description="借方发生额")
    credit: float = Field(default=0.0, description="贷方发生额")
    summary: str = Field(default="", description="摘要")


class AccountingVoucher(BaseModel):
    voucher_id: str = Field(description="凭证号，例如 202512-记-0042")
    voucher_date: str = Field(description="记账日期 YYYY-MM-DD")
    preparer: str = Field(default="张三", description="制单人")
    checker: Optional[str] = Field(default="李四", description="复核人")
    entries: List[JournalEntryLine] = Field(default_factory=list, description="分录明细")
    attachments_count: int = Field(default=1, description="原始凭证附件张数")
    associated_doc_id: Optional[str] = Field(default=None, description="关联业务单据号 (合同/发票/出库单)")
    source_file: Optional[str] = Field(default="内建凭证库", description="数据来源文件")
    row_index: Optional[int] = Field(default=None, description="来源行号")


class BusinessContract(BaseModel):
    contract_id: str = Field(description="合同编号")
    customer_or_vendor: str = Field(description="交易对手方名称")
    sign_date: str = Field(description="签署日期 YYYY-MM-DD")
    total_amount: float = Field(description="合同总金额(元)")
    payment_terms: str = Field(description="付款/信用条款")
    delivery_condition: str = Field(description="控制权转移/验收条款")
    is_related_party: bool = Field(default=False, description="是否为关联方")
    source_file: Optional[str] = Field(default="内建合同库", description="数据来源文件")


class InvoiceItem(BaseModel):
    invoice_no: str = Field(description="发票号码")
    invoice_date: str = Field(description="开票日期 YYYY-MM-DD")
    buyer_name: str = Field(description="购买方名称")
    seller_name: str = Field(description="销售方名称")
    amount_without_tax: float = Field(description="不含税金额")
    tax_amount: float = Field(description="税额")
    total_amount: float = Field(description="价税合计")
    goods_or_service: str = Field(description="商品或劳务名称")
    source_file: Optional[str] = Field(default="内建发票清单", description="数据来源文件")


class BankFlowRecord(BaseModel):
    transaction_id: str = Field(description="银行交易流水号")
    transaction_time: str = Field(description="交易时间 YYYY-MM-DD HH:MM")
    counterparty_name: str = Field(description="对手方户名")
    counterparty_account: str = Field(description="对手方账号")
    amount: float = Field(description="交易金额 (正数流入/负数流出)")
    balance_after: float = Field(description="交易后余额")
    remark: str = Field(default="", description="银行附言/用途")
    source_file: Optional[str] = Field(default="内建银行对账单", description="数据来源文件")


class FinancialStatementsSummary(BaseModel):
    period: str = Field(description="会计期间，例如 2025Q4 或 2025年度")
    revenue: float = Field(description="营业收入")
    cost_of_sales: float = Field(description="营业成本")
    gross_margin: float = Field(description="毛利率")
    net_profit: float = Field(description="净利润")
    accounts_receivable: float = Field(description="应收账款期末余额")
    inventory: float = Field(description="存货期末余额")
    total_assets: float = Field(description="资产总计")
    operating_cash_flow: float = Field(description="经营活动现金流净额")


# 2. 案例输入结构 (Case Input) 与基准标准答案 (Ground Truth)
class GroundTruthRiskItem(BaseModel):
    finding_type: str = Field(description="风险类型标准名称，例如 跨期提前确认营业收入, 虚假采购存货在途挂账, 关联方隐蔽资金闭环空转")
    expected_risk_level: RiskLevel = Field(default=RiskLevel.HIGH, description="预期风险等级")
    expected_amount: float = Field(default=0.0, description="预期涉案错报金额(元)")
    expected_vouchers: List[str] = Field(default_factory=list, description="必须捕获的问题凭证编号或银行流水号")
    standard_clause: str = Field(default="", description="对应的会计或审计准则条款")


class AccountingCaseData(BaseModel):
    case_id: str = Field(description="案例唯一ID")
    company_name: str = Field(description="被审计/分析企业名称")
    stock_code: Optional[str] = Field(default=None, description="真实上市公司股票代码 (如 600518, 002450)")
    penalty_decision_no: Optional[str] = Field(default=None, description="中国证监会行政处罚决定书文号 / 财政部公告文号")
    case_category: Optional[str] = Field(default="综合审计舞弊案例", description="舞弊类型大类")
    csrc_summary: Optional[str] = Field(default=None, description="监管机构处罚决定官方认定摘要")
    industry: str = Field(default="制造业/软件与信息技术", description="所属行业")
    audit_period: str = Field(default="2025年度", description="审计或核算期间")
    description: str = Field(description="案例背景与简述")
    financial_summary: Optional[FinancialStatementsSummary] = None
    vouchers: List[AccountingVoucher] = Field(default_factory=list)
    contracts: List[BusinessContract] = Field(default_factory=list)
    invoices: List[InvoiceItem] = Field(default_factory=list)
    bank_flows: List[BankFlowRecord] = Field(default_factory=list)
    ground_truth_risks: Optional[List[str]] = Field(default=None, description="兼容旧版字符串真值")
    ground_truth_findings: Optional[List[GroundTruthRiskItem]] = Field(default=None, description="强类型字段级基准真值")


# 3. 智能体分析研判与结构化输出 (Audit & Analysis Output)
class EvidenceItem(BaseModel):
    evidence_type: str = Field(description="证据类型，例如: 凭证与流水差异、发票时间矛盾、合同验收缺失")
    source_ref: str = Field(description="证据源引用，例如: 凭证[202512-记-0042] vs 流水[BK2025123101]")
    detail: str = Field(description="具体异常比对描述")
    source_file: Optional[str] = Field(default="", description="数据来源文件")
    row_index: Optional[int] = Field(default=None, description="来源数据行号")


class RiskFinding(BaseModel):
    finding_id: str = Field(description="发现项编号，如 RF-001")
    title: str = Field(description="风险或舞弊疑点简述")
    risk_level: RiskLevel = Field(description="风险等级")
    accounting_standard: str = Field(description="违背或依据的准则条款 (如 CAS 14 新收入准则)")
    impact_amount: float = Field(default=0.0, description="涉嫌影响金额或错报预估金额 (元)")
    suspected_mechanism: str = Field(description="手法剖析 (如: 提前确认收入、三单不一致、虚构采购资金循环)")
    evidences: List[EvidenceItem] = Field(default_factory=list, description="结构化证据链条")
    suggested_procedure: str = Field(description="建议执行的实质性审计程序 (如: 发函询证、实地盘点、检查期后退货)")
    # 证据链三层结构 (Issue 5)
    rule_evidence: str = Field(default="", description="【确定性规则发现】：算法计算得出的客观事实指标（如倒挂天数、借贷差额）")
    model_explanation: str = Field(default="", description="【DeepSeek模型推理解析】：大语言模型准则认定与实质推断")
    human_verification_flag: str = Field(default="待注册会计师实施现场核实程序", description="【待人工确认事项】：需人工跟进的审计程序")


class WorkpaperColumn(BaseModel):
    voucher_no: str
    date: str
    summary: str
    ledger_amount: float
    verified_amount: float
    discrepancy: float
    audit_conclusion: str
    source_file: Optional[str] = Field(default="", description="底稿数据源文件")
    evidence_trace: Optional[str] = Field(default="", description="证据追溯链接")


class AuditWorkpaper(BaseModel):
    workpaper_id: str = Field(description="底稿索引号，例如: WP-REV-01")
    title: str = Field(description="底稿名称，例如: 营业收入与应收账款截止测试及穿透核对表")
    prepared_by: str = Field(default="DeepSeek-AuditMind Agent")
    review_date: str = Field(description="生成与复核日期")
    sample_count: int = Field(description="抽凭样本数量")
    total_audited_amount: float = Field(description="核查业务总金额(元)")
    abnormal_amount: float = Field(description="异常/错报金额(元)")
    rows: List[WorkpaperColumn] = Field(default_factory=list, description="明细表格数据")
    audit_opinion_summary: str = Field(description="审计底稿综合结论与处理建议")


class AnalysisReportResult(BaseModel):
    case_id: str
    company_name: str
    plugin_name: str
    overall_risk_rating: RiskLevel
    beneish_m_score: Optional[float] = Field(default=None, description="Beneish M-Score 舞弊得分")
    is_beneish_manipulator: Optional[bool] = Field(default=None, description="M-Score 是否超过 -1.78 预警线")
    findings: List[RiskFinding] = Field(default_factory=list)
    workpapers: List[AuditWorkpaper] = Field(default_factory=list)
    executive_summary: str = Field(description="管理层与评委摘要")
    execution_time_seconds: float = Field(default=0.0)
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total": 0})
    # 可靠性元数据 (Issue 3)
    execution_mode: ExecutionMode = Field(default=ExecutionMode.MOCK, description="实际执行模式")
    model_name: str = Field(default="deepseek-chat", description="实际执行模型")
    fallback_occurred: bool = Field(default=False, description="是否发生过降级回退")
    fallback_reason: Optional[str] = Field(default=None, description="降级回退原因详情")


# 4. 字段级与金额级精细化评测指标 (Benchmark Harness Metrics - Issue 4)
class CaseEvalScore(BaseModel):
    case_id: str
    case_name: str
    # 基础综合指标
    precision: float = Field(description="查准率 (Precision)")
    recall: float = Field(description="查全率 (Recall)")
    f1_score: float = Field(description="F1 综合指标")
    # 字段级与金额级严谨指标 (Issue 4)
    type_accuracy_rate: float = Field(default=1.0, description="风险类型字段准确率")
    risk_level_accuracy_rate: float = Field(default=1.0, description="风险严重度等级准确率")
    amount_accuracy_rate: float = Field(default=1.0, description="金额精准度 (误差<=1%)")
    evidence_hit_rate: float = Field(default=1.0, description="证据凭证来源命中率")
    false_positive_count: int = Field(default=0, description="误报风险点数量")
    # 质量与稳定性指标
    json_schema_valid: bool = Field(description="JSON 结构化合规性 (100% 格式对齐)")
    math_accuracy_rate: float = Field(description="数字计算准确率 (零算术幻觉)")
    standards_accuracy_rate: float = Field(description="会计准则引用准确率")
    latency_seconds: float = Field(description="端到端耗时")
    total_tokens: int = Field(description="Token消耗")
    passed: bool = Field(description="是否通过基准考核")


class BenchmarkSummary(BaseModel):
    total_cases: int
    passed_cases: int
    mean_precision: float
    mean_recall: float
    mean_f1_score: float
    # 新增严谨指标
    mean_amount_accuracy: float = Field(default=1.0, description="平均金额精准率")
    mean_type_accuracy: float = Field(default=1.0, description="平均类型准确率")
    mean_evidence_hit_rate: float = Field(default=1.0, description="平均凭证来源命中率")
    false_positive_rate: float = Field(default=0.0, description="对照组误报率")
    # 基础质量
    schema_valid_rate: float
    math_accuracy_rate: float
    mean_latency: float
    execution_mode: str = Field(default="mock", description="评测执行模式")
    case_scores: List[CaseEvalScore] = Field(default_factory=list)
