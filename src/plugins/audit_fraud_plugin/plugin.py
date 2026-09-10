"""
AuditMind Plugin Implementation.
"""

import json
from typing import Dict, Any
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
        
        # 1. 3-way Reconciliation
        recon_res = perform_three_way_reconciliation(case)
        results["reconciliation"] = recon_res
        
        # 2. Beneish M-Score (rigorous 2-period verification, refusal to fake numbers)
        m_res = calculate_beneish_from_case(case)
        results["beneish"] = m_res

        return results

    def build_user_prompt(self, case: AccountingCaseData, tool_results: Dict[str, Any]) -> str:
        """Construct the LLM user prompt."""
        recon = tool_results.get("reconciliation", {})
        beneish = tool_results.get("beneish")

        prompt_parts = [
            f"【被审计单位】：{case.company_name}（所属行业：{case.industry}，审计期间：{case.audit_period}）",
            f"【案例背景】：{case.description}\n",
            "【确定性工具核查比对事实（Deterministic Audit Tool Findings）】："
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
            f"- 三单勾稽比对异常数量: {recon.get('total_discrepancies_count', 0)} 处，涉及异常金额: {recon.get('total_abnormal_amount', 0.0):,.2f} 元"
        )
        for disc in recon.get("discrepancies", []):
            disc_amt = disc.get('amount', 0.0)
            prompt_parts.append(f"  * [{disc.get('type')}] 关联单据: {disc.get('voucher_id', '')} | 涉及金额: {disc_amt:.2f}元 | 详情: {disc.get('detail')}")

        prompt_parts.append("\n【记账凭证抽样明细】：")
        for v in case.vouchers:
            entries_str = "; ".join([f"{e.account_name}(借:{e.debit:.2f}, 贷:{e.credit:.2f})" for e in v.entries])
            prompt_parts.append(f"- 凭证号: {v.voucher_id} | 日期: {v.voucher_date} | 关联单号: {v.associated_doc_id or '无'} | 分录: {entries_str}")

        prompt_parts.append("\n【合同与发票抽样明细】：")
        for c in case.contracts:
            prompt_parts.append(f"- 合同: {c.contract_id} | 交易方: {c.customer_or_vendor} | 金额: {c.total_amount:,.2f}元 | 关联方: {c.is_related_party}")
        for inv in case.invoices:
            prompt_parts.append(f"- 发票: {inv.invoice_no} | 日期: {inv.invoice_date} | 价税合计: {inv.total_amount:,.2f}元 | 品目: {inv.goods_or_service}")

        prompt_parts.append("\n请基于上述事实与准则规范，输出完整的审计穿透研判 JSON 报告。")
        return "\n".join(prompt_parts)

    def parse_and_verify(
        self,
        raw_json: Dict[str, Any],
        tool_results: Dict[str, Any],
        case: AccountingCaseData
    ) -> AnalysisReportResult:
        """Parse JSON response and merge with deterministic checks."""
        recon = tool_results.get("reconciliation", {})
        beneish = tool_results.get("beneish")

        # Parse findings
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
            
            # map risk level
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
                    human_verification_flag=f.get("human_verification_flag", "待注册会计师实施现场核实程序")
                )
            )

        # Parse workpapers
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

        overall_rating_str = str(raw_json.get("overall_risk_rating", "MEDIUM")).upper()
        overall_rating = RiskLevel.HIGH if "HIGH" in overall_rating_str else (RiskLevel.MEDIUM if "MED" in overall_rating_str else (RiskLevel.CLEAN if "CLEAN" in overall_rating_str else RiskLevel.LOW))

        return AnalysisReportResult(
            case_id=case.case_id,
            company_name=case.company_name,
            plugin_name=self.plugin_name,
            overall_risk_rating=overall_rating,
            beneish_m_score=beneish["m_score"] if beneish else None,
            is_beneish_manipulator=beneish["is_manipulator"] if beneish else None,
            findings=findings,
            workpapers=workpapers,
            executive_summary=raw_json.get("executive_summary", "审计穿透分析已完成。")
        )
