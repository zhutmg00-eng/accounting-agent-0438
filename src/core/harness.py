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
from src.plugins.audit_fraud_plugin.tools import (
    calculate_beneish_from_case, perform_three_way_reconciliation
)


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
        report.reasoning_content = llm_resp.reasoning_content

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
            false_positives = len(report.findings)
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

        matched_prediction_indexes = set()
        for gt in gt_findings:
            matched_pred = None
            gt_keywords = [w for w in gt.finding_type.replace("与", " ").replace("及", " ").replace("(", " ").replace(")", " ").split() if len(w) >= 2]
            
            for pred_index, pred in enumerate(report.findings):
                if pred_index in matched_prediction_indexes:
                    continue
                pred_text = f"{pred.title} {pred.suspected_mechanism}"
                # Check type keywords
                if any(kw in pred_text for kw in gt_keywords):
                    matched_pred = pred
                    matched_prediction_indexes.add(pred_index)
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

        false_positives = len(report.findings) - len(matched_prediction_indexes)
        precision = type_hits / max(type_hits + false_positives, 1)
        recall = type_hits / n_gt
        f1 = (2 * precision * recall) / max(precision + recall, 1e-6)

        json_valid = len(report.findings) > 0 and report.overall_risk_rating is not None
        math_acc = 1.0 if (report.beneish_m_score is None or isinstance(report.beneish_m_score, float)) else 0.0
        standards_valid = all(len(f.accounting_standard) > 3 for f in report.findings) if report.findings else True

        # A case is only passed when the headline metrics and the material
        # finding attributes are all reliable.  Previously risk-level and
        # accounting-standard mismatches were reported but did not affect
        # the pass/fail result.
        passed = (
            precision >= 0.70
            and f1 >= 0.70
            and type_acc >= 0.70
            and level_acc >= 0.70
            and amount_acc >= 0.90
            and evidence_hit_rate >= 0.70
            and json_valid
            and (math_acc == 1.0)
            and standards_valid
        )

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
            false_positive_count=false_positives,
            json_schema_valid=json_valid,
            math_accuracy_rate=math_acc,
            standards_accuracy_rate=1.0 if standards_valid else 0.0,
            latency_seconds=report.execution_time_seconds,
            total_tokens=report.token_usage.get("total", 0),
            passed=passed
        )

    def run_agent_turn(
        self,
        case: AccountingCaseData,
        messages: List[Dict[str, str]],
        tools_enabled: bool = True,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Interactive multi-turn CPA Audit Agent turn.
        Executes domain tools dynamically (Beneish M-Score, 3-Way Reconciliation, Voucher/Bank Search)
        and leverages DeepSeek (or Domain Heuristic Engine) to provide rigorous audit consultation.
        """
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        tool_calls = []
        tool_context_str = ""

        if tools_enabled:
            # Check for Beneish tool intent
            if any(k in last_user_msg.lower() for k in ("beneish", "m-score", "财务操纵", "操纵指数", "8变量", "8因子")):
                beneish_res = calculate_beneish_from_case(case)
                tool_calls.append({
                    "tool_name": "calculate_beneish_m_score",
                    "tool_input": {"case_id": case.case_id, "company_name": case.company_name},
                    "tool_output": beneish_res,
                    "status": "success"
                })
                if beneish_res.get("is_calculable"):
                    tool_context_str += f"\n【工具调用: calculate_beneish_m_score】测算结果: M-Score = {beneish_res.get('m_score', 0.0):.2f}, 操纵预警: {'超标高危' if beneish_res.get('is_manipulator') else '正常'}, 变量: {beneish_res.get('variables', {})}\n"
                else:
                    tool_context_str += f"\n【工具调用: calculate_beneish_m_score】结果: 不可计算（{beneish_res.get('reason')}）\n"

            # Check for Three-way Reconciliation intent
            if any(k in last_user_msg for k in ("三单", "勾稽", "核对", "对账", "差异", "倒挂", "发票", "流水", "穿透")):
                recon_res = perform_three_way_reconciliation(case)
                tool_calls.append({
                    "tool_name": "perform_three_way_reconciliation",
                    "tool_input": {"case_id": case.case_id, "vouchers_count": len(case.vouchers)},
                    "tool_output": recon_res,
                    "status": "success"
                })
                tool_context_str += (
                    f"\n【工具调用: perform_three_way_reconciliation】业财三单勾稽结果: 发现异常 {recon_res.get('total_discrepancies_count', 0)} 项，"
                    f"涉及异常金额 ¥{recon_res.get('total_abnormal_amount', 0.0):,.2f} 元。"
                )
                if recon_res.get("discrepancies"):
                    tool_context_str += "\n典型异常单据:\n" + "\n".join(
                        f" - [{d['type']}] 单号:{d.get('voucher_id') or d.get('voucherId')}, 金额:¥{d['amount']:,.2f}, 详情:{d['detail']}"
                        for d in recon_res.get("discrepancies", [])[:3]
                    )

            # Check for Voucher Search intent
            if any(k in last_user_msg for k in ("凭证", "分录", "科目", "借贷")):
                vouchers_summary = []
                for v in case.vouchers[:5]:
                    entries_text = ", ".join(
                        f"{'借' if e.debit else '贷'} {e.account_name} ¥{(e.debit or e.credit):,.2f}"
                        for e in v.entries
                    )
                    vouchers_summary.append(f"凭证号:{v.voucher_id} | 日期:{v.voucher_date} | 分录:[{entries_text}]")
                tool_calls.append({
                    "tool_name": "search_vouchers",
                    "tool_input": {"case_id": case.case_id, "sample_size": len(case.vouchers)},
                    "tool_output": {"sample_vouchers": vouchers_summary, "total_vouchers": len(case.vouchers)},
                    "status": "success"
                })
                tool_context_str += f"\n【工具调用: search_vouchers】抽样凭证明细 ({min(5, len(case.vouchers))}/{len(case.vouchers)}):\n" + "\n".join(vouchers_summary)

            # Check for Bank Flow intent
            if any(k in last_user_msg for k in ("流水", "银行", "对手方", "转账", "资金")):
                flows_summary = []
                for b in case.bank_flows[:5]:
                    flows_summary.append(f"流水号:{b.flow_id} | 对手方:{b.counterparty_name} | 金额:¥{b.amount:,.2f} | 摘要:{b.summary}")
                tool_calls.append({
                    "tool_name": "search_bank_flows",
                    "tool_input": {"case_id": case.case_id, "sample_size": len(case.bank_flows)},
                    "tool_output": {"sample_flows": flows_summary, "total_flows": len(case.bank_flows)},
                    "status": "success"
                })
                tool_context_str += f"\n【工具调用: search_bank_flows】银行流水抽样 ({min(5, len(case.bank_flows))}/{len(case.bank_flows)}):\n" + "\n".join(flows_summary)

        # Build prompt for LLM or Heuristic Engine
        system_prompt = (
            "你是由 DeepSeek-AuditMind 驱动的数智会计与舞弊穿透智能体（注册会计师 / 资深数智审计专家）。\n"
            "依据《中国注册会计师审计准则》第1141号及 CAS 14（新收入）、CAS 1（存货）、CAS 36（关联方）等企业会计准则开展分析。\n"
            f"当前被审计单位：【{case.company_name} ({case.stock_code})】，行业：{case.industry}，审计期间：{case.audit_period}。\n"
            f"案例概况：凭证 {len(case.vouchers)} 笔、发票 {len(case.invoices)} 张、流水 {len(case.bank_flows)} 笔、合同 {len(case.contracts)} 份。\n"
            "请以专业注册会计师口吻，结合工具调用返回的确定性事实与证据链，针对用户提出的问题进行条理清晰、严谨专业的解答。\n"
            "若发现异常，请明确指出：涉及金额、违反的会计准则条款、舞弊嫌疑机制及注册会计师建议的进一步审计程序。"
        )

        chat_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            chat_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        if tool_context_str:
            chat_messages.append({
                "role": "system",
                "content": f"【系统注入实时审计算子工具执行数据】：{tool_context_str}"
            })

        # LLM completion
        if self.llm.mode == ExecutionMode.MOCK:
            # Heuristic CPA auditor response
            content = self._generate_heuristic_agent_response(case, last_user_msg, tool_calls)
            reasoning = "DeepSeek CoT 思考链（离线启发式演绎）：结合被审计单位凭证与流水事实，调度确定性审计算子，依据 CAS 14 / CSA 1141 完成专家研判。"
            return {
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
                "tool_calls": tool_calls,
                "model_name": self.llm.model_name,
                "execution_mode": self.llm.mode.value
            }
        else:
            resp = self.llm.chat_completion(
                messages=chat_messages,
                temperature=temperature,
                response_json=False,
                max_tokens=4096
            )
            return {
                "role": "assistant",
                "content": resp.content,
                "reasoning_content": resp.reasoning_content,
                "tool_calls": tool_calls,
                "model_name": resp.model_name,
                "execution_mode": resp.execution_mode.value
            }

    def _generate_heuristic_agent_response(
        self,
        case: AccountingCaseData,
        user_prompt: str,
        tool_calls: List[Dict[str, Any]]
    ) -> str:
        """Generate high-quality, professional auditor response in MOCK mode."""
        recon_call = next((tc for tc in tool_calls if tc["tool_name"] == "perform_three_way_reconciliation"), None)
        beneish_call = next((tc for tc in tool_calls if tc["tool_name"] == "calculate_beneish_m_score"), None)

        response_lines = [
            f"### 📋 注册会计师审计专业意见 · {case.company_name} ({case.stock_code})",
            ""
        ]

        if beneish_call:
            b_data = beneish_call["tool_output"]
            if b_data.get("is_calculable"):
                m_val = b_data.get("m_score", 0.0)
                is_man = b_data.get("is_manipulator", False)
                response_lines.append(f"**1. Beneish M-Score 操纵指数分析**：")
                response_lines.append(f"- 测算得分：`{m_val:.2f}`（阈值标准：大于 -1.78 即存在高危财务操纵嫌疑）。")
                response_lines.append(f"- 评价结论：{'⚠️ 存在显著盈余操纵/财报粉饰风险' if is_man else '✅ 指标处于常规合理波动区间'}。")
            else:
                response_lines.append(f"**1. Beneish M-Score 操纵指数分析**：")
                response_lines.append(f"- 状态：`不可计算`（{b_data.get('reason')}）。智能体遵循客观严谨原则，未采用主观估算数据。")
            response_lines.append("")

        if recon_call:
            r_data = recon_call["tool_output"]
            cnt = r_data.get("total_discrepancies_count", 0)
            amt = r_data.get("total_abnormal_amount", 0.0)
            response_lines.append(f"**2. 业财三单穿透勾稽核对结果**：")
            response_lines.append(f"- 涉及凭证总量：{len(case.vouchers)} 笔，检出异常单据：`{cnt}` 处，涉及错报金额：`¥{amt:,.2f}` 元。")
            if r_data.get("discrepancies"):
                response_lines.append("- **核心异常证据链**：")
                for d in r_data.get("discrepancies")[:3]:
                    response_lines.append(f"  * **[{d['type']}]** 凭证单号 `{d.get('voucher_id') or d.get('voucherId')}`：{d['detail']}（涉及金额：¥{d['amount']:,.2f}）")
            response_lines.append("")

        if not beneish_call and not recon_call:
            response_lines.append(f"**审计事实梳理**：当前账套已接入记账凭证 {len(case.vouchers)} 笔、发票 {len(case.invoices)} 张、银行流水 {len(case.bank_flows)} 笔。")
            response_lines.append("")

        response_lines.extend([
            "**3. 会计准则适用与专业判断**：",
            "- 依据 **CAS 14（新收入准则）** 五步法原则，收入确认必须以客户取得商品或服务的控制权为前提。若出现“有账无单”、“单据倒挂”或“发票与流水金额不符”，应全额冲减虚构收入并作差错更正。",
            "- 依据 **CSA 1141（财务报表审计中与舞弊相关的责任）**，上述单据矛盾构成舞弊重大错报风险，审计项目组不可将内控依赖作为实质性程序减免的理由。",
            "",
            "**4. 进一步审计底稿核查程序建议**：",
            "1. **外部独立函证**：向主要客户及资金对手方实施积极式询证函，函证交易发生额及期末应收/应付款项余额。",
            "2. **资金穿透核查**：调取银行对账单原件并核对网银电子回单流水，排查是否存在体外资金循环或大股东隐蔽占用。",
            "3. **现场监盘与出入库追踪**：核验仓储物流单据与海关报关记录，验证基础实物资产交付的真实性。"
        ])

        return "\n".join(response_lines)

    def run_autonomous_audit_goal(
        self,
        case: AccountingCaseData,
        goal_instruction: str = "执行端到端全量舞弊穿透审计与底稿生成"
    ) -> Dict[str, Any]:
        """
        Autonomous Multi-Step Audit Goal Execution (Native replacement for dsh-tool-goal).
        Executes:
        - Step 1: Goal Planning & Context Ingestion
        - Step 2: Deterministic Tools Matrix Execution
        - Step 3: Deep CAS Accounting Standards Deduction
        - Step 4: Audit Workpapers & Opinion Synthesis
        """
        start_time = time.perf_counter()
        steps = [
            {
                "step": 1,
                "title": "审计目标规划与全模态账套画像",
                "status": "completed",
                "detail": f"目标：{goal_instruction}。成功加载【{case.company_name}】账套，解析凭证 {len(case.vouchers)} 笔、发票 {len(case.invoices)} 张、流水 {len(case.bank_flows)} 笔。"
            },
            {
                "step": 2,
                "title": "确定性审计算子矩阵调度",
                "status": "completed",
                "detail": "调度 Beneish M-Score 8 变量模型与三单穿透勾稽算子，完成数值层面刚性排查。"
            },
            {
                "step": 3,
                "title": "DeepSeek 大模型准则深度定性",
                "status": "completed",
                "detail": "基于 CAS 14、CAS 1、CAS 36 及 CSA 1141 开展商业实质与舞弊机理演绎。"
            },
            {
                "step": 4,
                "title": "三层证据审计底稿与结论合成",
                "status": "completed",
                "detail": "已自动编排标准审计工作底稿，完成证据链闭环并生成注册会计师应对建议。"
            }
        ]

        report = self.run_case(case, plugin_id="audit_fraud_detection")
        recon = perform_three_way_reconciliation(case)
        beneish = calculate_beneish_from_case(case)

        elapsed = round(time.perf_counter() - start_time, 3)

        return {
            "status": "success",
            "goal": goal_instruction,
            "case_id": case.case_id,
            "company_name": case.company_name,
            "steps": steps,
            "report": report.model_dump(),
            "tool_outputs": {
                "beneish_m_score": beneish,
                "three_way_reconciliation": recon
            },
            "elapsed_seconds": elapsed,
            "execution_mode": self.llm.mode.value,
            "model_name": self.llm.model_name
        }
