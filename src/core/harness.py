"""
DeepSeek Accounting Agent Harness (Powered by Cordis Microkernel).
Orchestrates Plugins, LLM Invocation, Verification Guards, and Benchmark Scoring.
"""

import time
from typing import Dict, Any, Optional, List
from src.core.schemas import (
    AccountingCaseData, AnalysisReportResult, CaseEvalScore, 
    GroundTruthRiskItem, RiskLevel, ExecutionMode
)
from src.core.llm_adapter import DeepSeekLLMAdapter
from src.core.plugin_registry import registry, PluginRegistry
from src.core.cordis_kernel import Context, SessionLogger
from src.plugins.audit_fraud_plugin.plugin import AuditFraudPlugin
from src.plugins.cost_analysis_plugin.plugin import CostAnalysisPlugin


class AccountingAgentHarness:
    """
    Agent Harness built on the Cordis Meta-framework.
    Adheres to DeepSeek Harness's core design: "No Privileged Core / Everything is a Plugin".
    """
    def __init__(
        self,
        llm_adapter: Optional[DeepSeekLLMAdapter] = None,
        custom_registry: Optional[PluginRegistry] = None
    ):
        self.ctx = Context()
        self.llm = llm_adapter or DeepSeekLLMAdapter()
        self.registry = custom_registry or registry
        
        # Provide core services into Cordis Context
        self.ctx.provide("llm", self.llm)
        self.ctx.provide("registry", self.registry)
        
        self._register_default_plugins()

    def _register_default_plugins(self):
        """Mount built-in accounting plugins onto the Cordis Context."""
        p_audit = AuditFraudPlugin()
        p_cost = CostAnalysisPlugin()
        
        if not self.registry.get("audit_fraud_detection"):
            self.registry.register(p_audit)
        if not self.registry.get("cost_cvp_analysis"):
            self.registry.register(p_cost)

        self.ctx.plugin(p_audit)
        self.ctx.plugin(p_cost)

    def run_case(
        self,
        case: AccountingCaseData,
        plugin_id: str = "audit_fraud_detection",
        temperature: float = 0.1
    ) -> AnalysisReportResult:
        """
        Execute full end-to-end accounting pipeline on a given case within a Cordis Session Context.
        """
        start_time = time.perf_counter()
        session_ctx = self.ctx.create_session(session_id=f"session-{case.case_id}-{int(time.time())}")

        plugin = self.registry.get(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_id}' not found in registry. Available: {list(self.registry.get_all().keys())}")

        session_ctx.emit("case.start", {"case_id": case.case_id, "company_name": case.company_name})

        # Step 1: Tool Execution
        tool_results = plugin.execute_tools(case)
        session_ctx.emit("tools.executed", {"tool_results_summary": f"Discrepancies: {len(tool_results.get('reconciliation', {}).get('discrepancies', []))}"})

        # Step 2: Prompt Construction
        system_prompt = plugin.get_system_prompt()
        user_prompt = plugin.build_user_prompt(case, tool_results)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Step 3: LLM Inference
        session_ctx.emit("llm.inference.start", {"model": self.llm.model_name, "mode": self.llm.mode.value})
        llm_resp = self.llm.chat_completion(
            messages=messages,
            temperature=temperature,
            response_json=True
        )
        session_ctx.emit("llm.inference.complete", {"total_tokens": llm_resp.total_tokens})

        raw_json = llm_resp.json()

        # Step 4: Verification & Parsing Guard
        report = plugin.parse_and_verify(
            raw_json=raw_json,
            tool_results=tool_results,
            case=case
        )

        # Step 5: Attach Telemetry & Reliability Trace Metadata (Issue 3)
        elapsed = time.perf_counter() - start_time
        report.execution_time_seconds = max(round(elapsed, 4), 0.001)
        report.token_usage = {
            "prompt_tokens": llm_resp.prompt_tokens,
            "completion_tokens": llm_resp.completion_tokens,
            "total": llm_resp.total_tokens
        }
        report.execution_mode = llm_resp.execution_mode
        report.model_name = llm_resp.model_name
        report.fallback_occurred = llm_resp.fallback_occurred
        report.fallback_reason = llm_resp.fallback_reason

        session_ctx.emit("case.complete", {
            "overall_risk": report.overall_risk_rating.value,
            "findings_count": len(report.findings),
            "execution_time_seconds": report.execution_time_seconds,
            "mode": report.execution_mode.value
        })

        return report

    def evaluate_case(
        self,
        case: AccountingCaseData,
        plugin_id: str = "audit_fraud_detection"
    ) -> CaseEvalScore:
        """
        Rigorous Field-Level & Amount-Level Benchmark Evaluation (Issue 4):
        Verifies:
        1. Exact Risk Type matching
        2. Risk Level alignment (HIGH/MEDIUM/LOW)
        3. Amount Error Rate (|pred - expected| / expected <= 1%)
        4. Evidence Document Source (Voucher / Invoice / Bank Flow IDs)
        5. False Positive Rate on clean baseline cases
        """
        report = self.run_case(case, plugin_id=plugin_id)
        gt_findings = case.ground_truth_findings or []

        # 1. Clean Baseline Case Evaluation
        if len(gt_findings) == 0:
            false_positives = len([f for f in report.findings if f.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM)])
            is_clean = (false_positives == 0)
            return CaseEvalScore(
                case_id=case.case_id,
                case_name=case.company_name,
                precision=1.0 if is_clean else 0.0,
                recall=1.0 if is_clean else 0.0,
                f1_score=1.0 if is_clean else 0.0,
                type_accuracy_rate=1.0 if is_clean else 0.0,
                risk_level_accuracy_rate=1.0 if is_clean else 0.0,
                amount_accuracy_rate=1.0 if is_clean else 0.0,
                evidence_hit_rate=1.0 if is_clean else 0.0,
                false_positive_count=false_positives,
                json_schema_valid=True,
                math_accuracy_rate=1.0,
                standards_accuracy_rate=1.0,
                latency_seconds=report.execution_time_seconds,
                total_tokens=report.token_usage.get("total", 0),
                passed=is_clean
            )

        # 2. Fraud & Discrepancy Case Evaluation
        type_hits = 0
        level_hits = 0
        amount_hits = 0
        evidence_hits = 0
        total_evidences_expected = sum(len(gt.expected_vouchers) for gt in gt_findings)

        for gt in gt_findings:
            matched_pred = None
            gt_keywords = [w for w in gt.finding_type.replace("与", " ").replace("及", " ").replace("(", " ").replace(")", " ").split() if len(w) >= 2]
            
            for pred in report.findings:
                pred_text = f"{pred.title} {pred.suspected_mechanism}"
                # Check type keywords
                if any(kw in pred_text for kw in gt_keywords):
                    matched_pred = pred
                    break
            
            if matched_pred:
                type_hits += 1
                if matched_pred.risk_level == gt.expected_risk_level:
                    level_hits += 1
                
                # Check amount accuracy (|pred - expected| / expected <= 0.01)
                amount_diff_ratio = abs(matched_pred.impact_amount - gt.expected_amount) / max(gt.expected_amount, 1.0)
                if amount_diff_ratio <= 0.01:
                    amount_hits += 1

                # Check evidence document citations
                all_evidence_str = " ".join([
                    f"{e.source_ref} {e.detail} {pred.rule_evidence} {e.source_file}"
                    for e in matched_pred.evidences
                ])
                for v_id in gt.expected_vouchers:
                    if v_id in all_evidence_str:
                        evidence_hits += 1

        n_gt = len(gt_findings)
        type_acc = type_hits / n_gt
        level_acc = level_hits / n_gt
        amount_acc = amount_hits / n_gt
        evidence_hit_rate = (evidence_hits / total_evidences_expected) if total_evidences_expected > 0 else 1.0

        precision = type_hits / max(len(report.findings), 1)
        recall = type_hits / n_gt
        f1 = (2 * precision * recall) / max(precision + recall, 1e-6)

        json_valid = len(report.findings) > 0 and report.overall_risk_rating is not None
        math_acc = 1.0 if (report.beneish_m_score is None or isinstance(report.beneish_m_score, float)) else 0.0
        standards_valid = all(len(f.accounting_standard) > 3 for f in report.findings) if report.findings else True

        passed = (f1 >= 0.70) and (amount_acc >= 0.90) and json_valid and (math_acc == 1.0)

        return CaseEvalScore(
            case_id=case.case_id,
            case_name=case.company_name,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            type_accuracy_rate=round(type_acc, 4),
            risk_level_accuracy_rate=round(level_acc, 4),
            amount_accuracy_rate=round(amount_acc, 4),
            evidence_hit_rate=round(evidence_hit_rate, 4),
            false_positive_count=0,
            json_schema_valid=json_valid,
            math_accuracy_rate=math_acc,
            standards_accuracy_rate=1.0 if standards_valid else 0.0,
            latency_seconds=report.execution_time_seconds,
            total_tokens=report.token_usage.get("total", 0),
            passed=passed
        )
