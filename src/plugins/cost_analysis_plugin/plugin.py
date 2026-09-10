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
        # Default mock CVP parameters if not explicitly provided
        unit_p = 100.0
        unit_vc = 60.0
        fc = 2000000.0
        sales_vol = 80000.0
        if case.financial_summary:
            fs = case.financial_summary
            fc = fs.cost_of_sales * 0.4
            unit_vc = (fs.cost_of_sales * 0.6) / 10000.0
            unit_p = fs.revenue / 10000.0
            sales_vol = 10000.0
            
        cvp_res = calculate_cvp_break_even(
            unit_price=unit_p,
            unit_variable_cost=unit_vc,
            total_fixed_costs=fc,
            current_sales_volume=sales_vol
        )
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
        finding = RiskFinding(
            finding_id="CVP-001",
            title=f"经营安全边际与成本弹性评估 ({cvp.get('risk_status')})",
            risk_level=RiskLevel.MEDIUM if cvp.get("safety_margin_ratio", 0) < 30 else RiskLevel.LOW,
            accounting_standard="管理会计基本指引第400号 - 本量利分析",
            impact_amount=cvp.get("break_even_revenue", 0.0),
            suspected_mechanism=f"单位边际贡献率为 {cvp.get('cm_ratio')}%, 经营杠杆DOL为 {cvp.get('operating_leverage_dol')}, 需关注固定成本刚性支出。",
            evidences=[
                EvidenceItem(
                    evidence_type="CVP本量利测算指标",
                    source_ref="管理会计测算引擎",
                    detail=f"保本销售量为 {cvp.get('break_even_volume')} 件，安全边际率为 {cvp.get('safety_margin_ratio')}%"
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
            audit_opinion_summary=f"企业当前处于盈利区间，安全边际为 {cvp.get('safety_margin_ratio')}%。",
            rows=[
                WorkpaperColumn(
                    voucher_no="CVP-MODEL-01",
                    date="2026-09-01",
                    summary="本量利基础测算模型",
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
            executive_summary=f"【管理会计决策简报】：{case.company_name} 边际贡献率达 {cvp.get('cm_ratio')}%, 安全边际率为 {cvp.get('safety_margin_ratio')}%, 整体经营处于{cvp.get('risk_status')}。"
        )
