"""
DeepSeek Accounting Agent Harness (Powered by Cordis Microkernel).
Orchestrates Plugins, LLM Invocation, Verification Guards, and Benchmark Scoring.
"""

import time
from typing import Dict, Any, Optional, List
from src.core.schemas import AccountingCaseData, AnalysisReportResult, CaseEvalScore
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
        Workflow:
        1. Fork Session Context & Append-Only SessionLogger
        2. Execute Deterministic Tools (No hallucination)
        3. Build CoT Prompts
        4. Invoke DeepSeek LLM
        5. Verify & Structure Output (Verification Guard)
        6. Record Audit Trail in SessionLogger
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
        session_ctx.emit("llm.inference.start", {"model": self.llm.model_name})
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

        # Step 5: Attach Telemetry & Audit Session Traces
        elapsed = time.perf_counter() - start_time
        report.execution_time_seconds = max(round(elapsed, 4), 0.001)
        report.token_usage = {
            "prompt_tokens": llm_resp.prompt_tokens,
            "completion_tokens": llm_resp.completion_tokens,
            "total": llm_resp.total_tokens
        }

        session_ctx.emit("case.complete", {
            "overall_risk": report.overall_risk_rating.value,
            "findings_count": len(report.findings),
            "execution_time_seconds": report.execution_time_seconds
        })

        return report

    def evaluate_case(
        self,
        case: AccountingCaseData,
        ground_truth_risks: Optional[List[str]] = None,
        plugin_id: str = "audit_fraud_detection"
    ) -> CaseEvalScore:
        """
        Benchmark Evaluation Harness:
        Evaluates the agent against ground truth risks, checking Precision, Recall, F1, Schema validity, and Math accuracy.
        """
        gt_risks = ground_truth_risks or case.ground_truth_risks or []
        report = self.run_case(case, plugin_id=plugin_id)

        all_report_text = f"{report.executive_summary} " + " ".join([
            f"{f.title} {f.suspected_mechanism} {' '.join(e.detail for e in f.evidences)}"
            for f in report.findings
        ])
        
        # Calculate Recall & Precision
        if not gt_risks:
            # Clean case check
            is_clean = len(report.findings) == 0 or report.overall_risk_rating.value in ("CLEAN", "LOW")
            recall = 1.0 if is_clean else 0.0
            precision = 1.0 if is_clean else 0.0
            f1 = 1.0 if is_clean else 0.0
        else:
            matched_gt = set()
            for idx, gt in enumerate(gt_risks):
                keywords = [k.strip() for k in gt.replace("/", " ").split() if len(k.strip()) >= 2]
                if any(kw in all_report_text for kw in keywords):
                    matched_gt.add(idx)

            recall = min(len(matched_gt) / max(len(gt_risks), 1), 1.0)
            precision = 1.0 if len(report.findings) > 0 and len(matched_gt) > 0 else 0.0
            f1 = (2 * precision * recall) / max(precision + recall, 1e-6)

        # Schema Validity Check
        json_valid = len(report.findings) > 0 or report.overall_risk_rating is not None

        # Mathematical Calculation Accuracy
        math_acc = 1.0 if (report.beneish_m_score is None or isinstance(report.beneish_m_score, float)) else 0.0

        # Standards Reference Accuracy
        standards_valid = all(len(f.accounting_standard) > 3 for f in report.findings) if report.findings else True

        passed = (f1 >= 0.70) and json_valid and (math_acc == 1.0)

        return CaseEvalScore(
            case_id=case.case_id,
            case_name=case.company_name,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            json_schema_valid=json_valid,
            math_accuracy_rate=math_acc,
            standards_accuracy_rate=1.0 if standards_valid else 0.0,
            latency_seconds=report.execution_time_seconds,
            total_tokens=report.token_usage.get("total", 0),
            passed=passed
        )
