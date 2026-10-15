"""
Cost Analysis & Management Accounting Plugin Implementation.
"""

from typing import Dict, Any
from src.core.plugin_base import BaseAccountingPlugin
from src.core.schemas import (
    AccountingCaseData, AnalysisReportResult, RiskFinding, 
    AuditWorkpaper, RiskLevel, EvidenceItem, WorkpaperColumn
)
from src.plugins.cost_analysis_plugin.tools import calculate_cvp_break_even


class CostAnalysisPlugin(BaseAccountingPlugin):
    @property
    def plugin_id(self) -> str:
        return "cost_cvp_analysis"

    @property
    def plugin_name(self) -> str:
        return "动态本量利与管理会计经营决策智能体插件 (CostAgent)"

    @property
    def category(self) -> str:
        return "ManagementAccounting"

    @property
    def description(self) -> str:
        return "围绕管理会计与成本控制场景，执行本量利(CVP)敏感性测算、盈亏平衡点分解、安全边际分析与经营杠杆风险研判。"

    def get_system_prompt(self) -> str:
        return """你是由北京市大学生数智会计创新应用竞赛专家组认证的【管理会计与成本决策智能体 (CostAgent)】。
请基于管理会计原理，对企业成本结构、变动成本、固定成本与本量利指标进行结构化推演并输出 JSON 报告。"""

    def execute_tools(self, case: AccountingCaseData) -> Dict[str, Any]:
        """Aggregate CVP derived only from disclosed figures.

        本量利测算需要单位经济数据（单位售价、单位变动成本、销售数量）。真实年报
        并不披露这些，而把年度营业成本除以一个假定的产量会**凭空制造**出被测算的
        数字本身，因此这里改用总量口径：以 1 元营业收入为一个计量单位，变动成本取
        营业成本，固定成本取期间费用。全部输入均来自已披露数据，不含任何假设常数。
        """
        fs = case.financial_summary
        if fs is None or not fs.revenue or not fs.cost_of_sales or fs.sga_expenses is None:
            return {"cvp": {
                "is_calculable": False,
                "reason": "缺少营业收入、营业成本或期间费用，不满足本量利(CVP)测算条件。",
            }}

        unit_cm = (fs.revenue - fs.cost_of_sales) / fs.revenue
        if unit_cm <= 0:
            return {"cvp": {
                "is_calculable": False,
                "reason": "边际贡献率非正（营业成本不低于营业收入），本量利模型不适用。",
            }}

        cvp_res = calculate_cvp_break_even(
            unit_price=1.0,
            unit_variable_cost=fs.cost_of_sales / fs.revenue,
            total_fixed_costs=fs.sga_expenses,
            current_sales_volume=fs.revenue,
        )
        cvp_res["is_calculable"] = True
        cvp_res["basis"] = "总量口径：以 1 元营业收入为一个计量单位，变动成本取营业成本，固定成本取期间费用。"
        return {"cvp": cvp_res}

    def build_user_prompt(self, case: AccountingCaseData, tool_results: Dict[str, Any]) -> str:
        cvp = tool_results.get("cvp", {})
        return f"分析企业 {case.company_name} 的成本指标与经营风险。CVP测算结果：单位边际贡献={cvp.get('unit_cm')}，盈亏平衡量={cvp.get('break_even_volume')}，安全边际率={cvp.get('safety_margin_ratio')}%。"

    def parse_and_verify(
        self,
        raw_json: Dict[str, Any],
        tool_results: Dict[str, Any],
        case: AccountingCaseData
    ) -> AnalysisReportResult:
        cvp = tool_results.get("cvp", {})

        # When the inputs are absent the honest output is "cannot compute", not a
        # verdict.  A fabricated "低风险(安全边际充足)" on a company we have no cost
        # data for is the single most damaging thing this agent could say.
        if not cvp.get("is_calculable"):
            reason = cvp.get("reason", "数据不足，无法执行本量利测算。")
            finding = RiskFinding(
                finding_id="CVP-001",
                title="本量利分析未执行（输入数据不足）",
                risk_level=RiskLevel.MEDIUM,
                accounting_standard="管理会计基本指引第400号 - 本量利分析",
                impact_amount=0.0,
                suspected_mechanism=reason,
                evidences=[
                    EvidenceItem(
                        evidence_type="数据完备性检查",
                        source_ref="管理会计测算引擎",
                        detail=reason
                    )
                ],
                suggested_procedure="取得分产品单位售价、单位变动成本、销售数量与固定成本明细后重新执行本量利测算。"
            )
            wp = AuditWorkpaper(
                workpaper_id="WP-CVP-01",
                title="管理会计本量利与盈亏平衡测算表",
                prepared_by="DeepSeek-CostAgent",
                review_date="2026-09-01",
                sample_count=0,
                total_audited_amount=0.0,
                abnormal_amount=0.0,
                audit_opinion_summary=f"未执行测算：{reason}",
                rows=[]
            )
            return AnalysisReportResult(
                case_id=case.case_id,
                company_name=case.company_name,
                plugin_name=self.plugin_name,
                overall_risk_rating=RiskLevel.MEDIUM,
                findings=[finding],
                workpapers=[wp],
                executive_summary=f"【管理会计决策简报】：{case.company_name} —— 未执行本量利测算。{reason}"
            )

        basis = cvp.get("basis", "")
        funding_note = "当前处于盈利区间" if cvp.get("is_profitable") else "当前处于亏损区间"
        finding = RiskFinding(
            finding_id="CVP-001",
            title=f"经营安全边际与成本弹性评估 ({cvp.get('risk_status')})",
            risk_level=RiskLevel.MEDIUM if cvp.get("safety_margin_ratio", 0) < 30 else RiskLevel.LOW,
            accounting_standard="管理会计基本指引第400号 - 本量利分析",
            impact_amount=cvp.get("break_even_revenue", 0.0),
            suspected_mechanism=f"单位边际贡献率为 {cvp.get('cm_ratio')}%, 经营杠杆DOL为 {cvp.get('operating_leverage_dol')}, 需关注固定成本刚性支出。{basis}",
            evidences=[
                EvidenceItem(
                    evidence_type="CVP本量利测算指标",
                    source_ref="管理会计测算引擎",
                    detail=f"保本销售额为 {cvp.get('break_even_revenue')} 元，安全边际率为 {cvp.get('safety_margin_ratio')}%。{basis}"
                )
            ],
            suggested_procedure="实施作业成本法(ABC)细化间接费用分配，优化固定成本开支。"
        )

        wp = AuditWorkpaper(
            workpaper_id="WP-CVP-01",
            title="管理会计本量利与盈亏平衡测算表",
            prepared_by="DeepSeek-CostAgent",
            review_date="2026-09-01",
            sample_count=1,
            total_audited_amount=cvp.get("break_even_revenue", 0.0),
            abnormal_amount=0.0,
            audit_opinion_summary=f"企业{funding_note}，安全边际为 {cvp.get('safety_margin_ratio')}%。{basis}",
            rows=[
                WorkpaperColumn(
                    voucher_no="CVP-MODEL-01",
                    date="2026-09-01",
                    summary="本量利基础测算模型（总量口径）",
                    ledger_amount=cvp.get("break_even_revenue", 0.0),
                    verified_amount=cvp.get("break_even_revenue", 0.0),
                    discrepancy=0.0,
                    audit_conclusion="测算完成，指标合规"
                )
            ]
        )

        return AnalysisReportResult(
            case_id=case.case_id,
            company_name=case.company_name,
            plugin_name=self.plugin_name,
            overall_risk_rating=RiskLevel.MEDIUM if cvp.get("safety_margin_ratio", 0) < 30 else RiskLevel.LOW,
            findings=[finding],
            workpapers=[wp],
            executive_summary=f"【管理会计决策简报】：{case.company_name} 边际贡献率达 {cvp.get('cm_ratio')}%, 安全边际率为 {cvp.get('safety_margin_ratio')}%, 整体经营处于{cvp.get('risk_status')}。{basis}"
        )
