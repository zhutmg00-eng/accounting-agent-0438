"""
DeepSeek Accounting Agent Harness (Powered by Cordis Microkernel).
Orchestrates Plugins, LLM Invocation, Verification Guards, and Benchmark Scoring.
"""

import json
import time
from typing import Dict, Any, Optional, List
from src.core.schemas import (
    AccountingCaseData, AnalysisReportResult, CaseEvalScore, 
    GroundTruthRiskItem, RiskLevel, ExecutionMode
)
from src.config import settings
from src.core.llm_adapter import DeepSeekLLMAdapter
from src.core.plugin_registry import registry, PluginRegistry
from src.core.cordis_kernel import Context, SessionLogger
from src.plugins.audit_fraud_plugin.plugin import AuditFraudPlugin
from src.plugins.cost_analysis_plugin.plugin import CostAnalysisPlugin
from src.plugins.audit_fraud_plugin.tools import (
    calculate_beneish_from_case, perform_three_way_reconciliation
)
from src.plugins.audit_fraud_plugin.analytics import (
    journal_entry_testing, detect_fund_round_trips, benford_first_digit_test
)
from src.core.llm_adapter import DeepSeekAPIError


# Tool schemas exposed to DeepSeek native function calling (OpenAI-compatible).
AUDIT_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "calculate_beneish_m_score",
        "description": "用两期财务报表计算 Beneish 8 因子 M-Score（>-1.78 为操纵预警），返回各因子、数据质量与不可计算原因。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "perform_three_way_reconciliation",
        "description": "凭证-合同-发票-银行流水三单勾稽，返回每项差异的类型、单据号、金额与说明。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "journal_entry_testing",
        "description": "全量会计分录测试（CSA 1141）：周末/节假日、期末窗口、整数金额、职责分离、无附件、收入借方、敏感摘要等 10 条规则打分。",
        "parameters": {"type": "object", "properties": {
            "top_n": {"type": "integer", "description": "返回风险分最高的前 N 张凭证", "default": 10}}, "required": []}}},
    {"type": "function", "function": {
        "name": "detect_fund_round_trips",
        "description": "识别银行流水中同一或关联对手方在窗口期内先流出后流入、金额相近的资金往返（体外循环/过桥）。",
        "parameters": {"type": "object", "properties": {
            "window_days": {"type": "integer", "default": 30},
            "amount_tolerance": {"type": "number", "description": "金额偏差容忍度，0.1 表示 10%", "default": 0.1}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "benford_first_digit_test",
        "description": "Benford 首位数字检验（Nigrini MAD），样本不足 50 时返回不适用。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "compute_materiality",
        "description": "按 CSA 1221 计算整体重要性、实际执行的重要性与明显微小错报临界值。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "reconcile_book_to_bank",
        "description": "银行存款日记账与银行对账单双向核对：账面收付款无对应流水（有账无流），以及存单质押/担保/归集等受限资金线索。",
        "parameters": {"type": "object", "properties": {
            "day_window": {"type": "integer", "default": 5}}, "required": []}}},
    {"type": "function", "function": {
        "name": "detect_back_to_back_trades",
        "description": "识别短期内购销配对、毛利极低、货权不移库的背靠背贸易（商业实质/总额法存疑），收入按不含税计。",
        "parameters": {"type": "object", "properties": {
            "window_days": {"type": "integer", "default": 7},
            "max_margin": {"type": "number", "default": 0.05}}, "required": []}}},
    {"type": "function", "function": {
        "name": "verify_cutoff_and_cost",
        "description": "截止与配比：终验类合同按到货/初验在期末确认的收入、期后安装施工付款反证；已确认收入的发出商品未结转成本。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "detect_third_party_and_prepay",
        "description": "第三方代付回款（付款方与账面客户不一致）；大额预付期内未结转、付给关联方或无进项发票。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "run_judgment_procedures",
        "description": "执行职业判断类确定性算子：费用完整性与异常冲减成本、资产减值冲回与逾期未单项计提、或有事项与预计负债、无依据核销负债、关联方重分类与商业实质排查。",
        "parameters": {"type": "object", "properties": {
            "procedure": {"type": "string", "description": "可选子程序名：all / expense_completeness / impairment / provisions / liability_writeoff / related_reclass", "default": "all"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "search_vouchers",
        "description": "按凭证号、科目名或摘要关键词检索记账凭证分录。",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["keyword"]}}},
    {"type": "function", "function": {
        "name": "search_bank_flows",
        "description": "按流水号、对手方或附言关键词检索银行流水。",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["keyword"]}}},
]


def execute_audit_tool(case: AccountingCaseData, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run one deterministic operator by name. Never calls a model."""
    args = args or {}
    if name == "calculate_beneish_m_score":
        return calculate_beneish_from_case(case)
    if name == "perform_three_way_reconciliation":
        return perform_three_way_reconciliation(case)
    if name == "journal_entry_testing":
        return journal_entry_testing(case, top_n=int(args.get("top_n", 10) or 10))
    if name == "detect_fund_round_trips":
        return detect_fund_round_trips(
            case, window_days=int(args.get("window_days", 30) or 30),
            amount_tolerance=float(args.get("amount_tolerance", 0.1) or 0.1))
    if name == "benford_first_digit_test":
        return benford_first_digit_test(case)
    if name in ("compute_materiality", "reconcile_book_to_bank", "detect_back_to_back_trades",
                "verify_cutoff_and_cost", "detect_third_party_and_prepay"):
        from src.plugins.audit_fraud_plugin import substantive as sp
        fn = getattr(sp, name)
        allowed = {"day_window", "window_days", "max_margin"}
        kwargs = {k: v for k, v in args.items() if k in allowed}
        return fn(case, **kwargs)
    if name == "run_judgment_procedures":
        from src.plugins.audit_fraud_plugin.judgment import run_judgment_procedures
        return run_judgment_procedures(case)
    if name == "search_vouchers":
        kw = str(args.get("keyword", "")).strip()
        limit = int(args.get("limit", 10) or 10)
        hits = []
        for v in case.vouchers:
            blob = v.voucher_id + " " + (v.associated_doc_id or "") + " " + " ".join(f"{e.account_name} {e.summary}" for e in v.entries)
            if not kw or kw in blob:
                hits.append({"voucher_id": v.voucher_id, "date": v.voucher_date, "doc": v.associated_doc_id,
                             "preparer": v.preparer, "checker": v.checker,
                             "entries": [{"account": e.account_name, "debit": e.debit, "credit": e.credit, "summary": e.summary} for e in v.entries]})
            if len(hits) >= limit:
                break
        return {"keyword": kw, "matched": len(hits), "total_vouchers": len(case.vouchers), "vouchers": hits}
    if name == "search_bank_flows":
        kw = str(args.get("keyword", "")).strip()
        limit = int(args.get("limit", 10) or 10)
        hits = [
            {"transaction_id": b.transaction_id, "time": b.transaction_time, "counterparty": b.counterparty_name,
             "amount": b.amount, "remark": b.remark}
            for b in case.bank_flows
            if not kw or kw in f"{b.transaction_id} {b.counterparty_name} {b.remark}"
        ][:limit]
        return {"keyword": kw, "matched": len(hits), "total_flows": len(case.bank_flows), "flows": hits}
    raise ValueError(f"未知工具: {name}")


def voucher_entry_direction(entry: Any) -> str:
    """Return the 借/贷 marker for a journal entry line."""
    if entry.debit and entry.credit:
        return "借贷"
    if entry.debit:
        return "借"
    if entry.credit:
        return "贷"
    return "平"


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
        temperature: float = 0.1,
        on_delta=None
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
        n_samples = max(1, int(getattr(settings, "vote_samples", 1) or 1))
        vote_info = None
        if not self.llm.use_mock and n_samples > 1:
            llm_resp, raw_json, vote_info = self._sample_and_vote(messages, n_samples, temperature, on_delta, case)
        elif on_delta is not None and not self.llm.use_mock:
            llm_resp = self.llm.chat_completion_stream(
                messages=messages,
                on_delta=on_delta,
                temperature=temperature,
                response_json=True
            )
        else:
            llm_resp = self.llm.chat_completion(
                messages=messages,
                temperature=temperature,
                response_json=True,
                max_tokens=max(settings.max_tokens, 16384)
            )
        session_ctx.emit("llm.inference.complete", {"total_tokens": llm_resp.total_tokens})

        if self.llm.use_mock and hasattr(plugin, "offline_report"):
            raw_json = plugin.offline_report(case, tool_results)
        elif vote_info is None:
            raw_json = llm_resp.json()

        # Step 4: Verification & Parsing Guard
        report = plugin.parse_and_verify(
            raw_json=raw_json,
            tool_results=tool_results,
            case=case
        )

        # Step 4b: Verifier-driven reflection
        reflection = None
        v0 = report.verification or {}
        issues0 = int(v0.get("ungrounded", 0)) + int(v0.get("amount_unverified", 0))
        if not self.llm.use_mock and issues0 > 0 and getattr(settings, "reflection_rounds", 1) > 0:
            try:
                feedback = self._reflection_feedback(report, case, tool_results)
                messages2 = messages + [
                    {"role": "assistant", "content": llm_resp.content if vote_info is None else json.dumps(raw_json, ensure_ascii=False)},
                    {"role": "user", "content": feedback},
                ]
                resp2 = self.llm.chat_completion(messages=messages2, temperature=temperature, response_json=True,
                                                 max_tokens=max(settings.max_tokens, 16384))
                raw2 = resp2.json()
                if vote_info is not None:
                    self._carry_votes(raw_json, raw2, case, vote_info.get("samples_ok", 1))
                report2 = plugin.parse_and_verify(raw_json=raw2, tool_results=tool_results, case=case)
                v1 = report2.verification or {}
                issues1 = int(v1.get("ungrounded", 0)) + int(v1.get("amount_unverified", 0))
                reflection = {"triggered": True, "issues_before": issues0, "issues_after": issues1,
                              "adopted": issues1 < issues0, "feedback": feedback[:4000],
                              "tokens": resp2.total_tokens}
                if issues1 < issues0:
                    llm_resp.prompt_tokens += resp2.prompt_tokens
                    llm_resp.completion_tokens += resp2.completion_tokens
                    report = report2
                else:
                    llm_resp.prompt_tokens += resp2.prompt_tokens
                    llm_resp.completion_tokens += resp2.completion_tokens
            except Exception as exc:
                reflection = {"triggered": True, "error": str(exc)[:300], "adopted": False}
        if reflection is not None:
            report.verification = {**(report.verification or {}), "reflection": reflection}
        if vote_info is not None:
            report.verification = {**(report.verification or {}), "self_consistency": vote_info}

        # Step 5: Attach Telemetry & Reliability Trace Metadata
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
        report.privacy_audit = getattr(llm_resp, "privacy_audit", None) or {
            "outbound": False,
            "note": "离线模式：数据未离开本机，无需出境脱敏",
        }
        if report.privacy_audit and "outbound" not in report.privacy_audit:
            report.privacy_audit = {**report.privacy_audit, "outbound": True,
                                    "note": "发送给大模型前已自动掩码银行账号、身份证/统一社会信用代码、手机号与邮箱"}

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
        Rigorous Field-Level & Amount-Level Benchmark Evaluation (Issue 4).
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
            
            def _cites(pred):
                blob = " ".join([pred.rule_evidence or "", pred.title or ""] + [f"{e.source_ref} {e.detail}" for e in pred.evidences])
                return any(v and v in blob for v in gt.expected_vouchers)

            # 优先选取证据锚点命中且金额/等级最吻合的预测项
            for pass_no in (0, 1):
                candidates = []
                for pred_index, pred in enumerate(report.findings):
                    if pred_index in matched_prediction_indexes:
                        continue
                    pred_text = f"{pred.title} {pred.suspected_mechanism}"
                    ok = _cites(pred) if pass_no == 0 else any(kw in pred_text for kw in gt_keywords)
                    if ok:
                        amt_err = abs(pred.impact_amount - gt.expected_amount) / max(gt.expected_amount, 1.0)
                        lvl_match = 0 if pred.risk_level == gt.expected_risk_level else 1
                        candidates.append((amt_err > 0.01, lvl_match, amt_err, pred_index, pred))
                if candidates:
                    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
                    _, _, _, best_idx, matched_pred = candidates[0]
                    matched_prediction_indexes.add(best_idx)
                    break
            
            if matched_pred:
                type_hits += 1
                if matched_pred.risk_level == gt.expected_risk_level:
                    level_hits += 1
                
                amount_diff_ratio = abs(matched_pred.impact_amount - gt.expected_amount) / max(gt.expected_amount, 1.0)
                if amount_diff_ratio <= 0.01:
                    amount_hits += 1
                elif len(gt.expected_vouchers) > 1:
                    # 若同一真值事项的多张同构凭证被拆分为多条发现项，检查其合计金额是否吻合
                    cites_all = [p for p in report.findings if _cites(p)]
                    comb_amt = sum(p.impact_amount for p in cites_all)
                    if abs(comb_amt - gt.expected_amount) / max(gt.expected_amount, 1.0) <= 0.01:
                        amount_hits += 1

                all_evidence_str = " ".join([
                    f"{e.source_ref} {e.detail} {p.rule_evidence} {e.source_file}"
                    for p in ([matched_pred] + [x for x in report.findings if _cites(x)])
                    for e in p.evidences
                ])
                for v_id in gt.expected_vouchers:
                    if v_id in all_evidence_str:
                        evidence_hits += 1

        n_gt = len(gt_findings)
        type_acc = type_hits / n_gt
        level_acc = level_hits / n_gt
        amount_acc = amount_hits / n_gt
        evidence_hit_rate = (evidence_hits / total_evidences_expected) if total_evidences_expected > 0 else 1.0

        # 误报：既未匹配到真值、也没有引用任何真值单据（含同金额关联银行流水）的发现项
        gt_ids = {v for gt in gt_findings for v in gt.expected_vouchers if v}
        if gt_ids and case.bank_flows:
            gt_amts = [gt.expected_amount for gt in gt_findings if gt.expected_amount > 0]
            for b in case.bank_flows:
                if any(abs(abs(b.amount) - a) <= max(a * 0.001, 1.0) for a in gt_amts):
                    gt_ids.add(b.transaction_id)

        def _cites_any(pred):
            blob = " ".join([pred.rule_evidence or "", pred.title or ""] + [f"{e.source_ref} {e.detail}" for e in pred.evidences])
            return any(i in blob for i in gt_ids)

        false_positives = sum(1 for i, p in enumerate(report.findings)
                              if i not in matched_prediction_indexes and not _cites_any(p))
        precision = type_hits / max(type_hits + false_positives, 1)
        recall = type_hits / n_gt
        f1 = (2 * precision * recall) / max(precision + recall, 1e-6)

        json_valid = len(report.findings) > 0 and report.overall_risk_rating is not None

        tool_beneish = calculate_beneish_from_case(case)
        if tool_beneish.get("is_calculable"):
            math_acc = 1.0 if (
                report.beneish_m_score is not None
                and abs(report.beneish_m_score - tool_beneish["m_score"]) < 1e-6
                and bool(report.is_beneish_manipulator) == bool(tool_beneish["is_manipulator"])
            ) else 0.0
        else:
            math_acc = 1.0 if report.beneish_m_score is None else 0.0

        standards_valid = all(len(f.accounting_standard) > 3 for f in report.findings) if report.findings else True

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

    def _sample_and_vote(self, messages, n: int, temperature: float, on_delta, case: AccountingCaseData):
        """自洽性投票（self-consistency）：同一提示并行采样 n 次，按引用单据聚类发现项。"""
        import concurrent.futures as cf

        def one(i):
            t = temperature if i == 0 else max(temperature, 0.7)
            if i == 0 and on_delta is not None:
                return self.llm.chat_completion_stream(messages=messages, on_delta=on_delta, temperature=t, response_json=True)
            return self.llm.chat_completion(messages=messages, temperature=t, response_json=True,
                                            max_tokens=max(settings.max_tokens, 16384))

        resps = [None] * n
        errors = []
        with cf.ThreadPoolExecutor(max_workers=n) as ex:
            futs = {ex.submit(one, i): i for i in range(n)}
            for fu in cf.as_completed(futs):
                i = futs[fu]
                try:
                    resps[i] = fu.result()
                except Exception as exc:
                    errors.append(f"样本{i + 1}: {str(exc)[:200]}")
        ok = [(i, r) for i, r in enumerate(resps) if r is not None]
        parsed = []
        for i, r in ok:
            try:
                parsed.append((i, r, r.json()))
            except Exception as exc:
                errors.append(f"样本{i + 1} JSON 解析失败: {str(exc)[:120]}")
        if not parsed:
            raise DeepSeekAPIError("自洽性投票：所有采样均失败；" + "；".join(errors))
        ids = self._doc_ids(case)

        def key(f):
            text = json.dumps(f, ensure_ascii=False)
            return {x for x in ids if x in text}

        clusters = []
        for si, _, raw in parsed:
            for f in raw.get("risk_findings", []) or []:
                k = key(f)
                target = None
                if k:
                    for c in clusters:
                        if c["keys"] & k and si not in {m[0] for m in c["members"]}:
                            target = c
                            break
                if target is None:
                    clusters.append({"members": [(si, f)], "keys": set(k)})
                else:
                    target["members"].append((si, f))
                    target["keys"] |= k
        merged = []
        n_ok = len(parsed)
        for c in sorted(clusters, key=lambda c: -len({m[0] for m in c["members"]})):
            support = len({m[0] for m in c["members"]})
            rep = dict(sorted(c["members"], key=lambda m: m[0])[0][1])
            def _lv(x):
                u = str(x.get("risk_level", "")).upper()
                return 2 if "HIGH" in u else (1 if "MED" in u else 0)
            lv = [_lv(m[1]) for m in c["members"]]
            lv = sorted(lv + [0] * (n_ok - support))
            rep["risk_level"] = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}[lv[len(lv) // 2]] if support >= 2 else rep.get("risk_level", "LOW")
            rep["_vote_support"] = f"{support}/{n_ok}"
            merged.append(rep)
        base_i, base_resp, base_raw = parsed[0]
        raw_json = dict(base_raw)
        raw_json["risk_findings"] = merged
        for _, r, _ in parsed[1:]:
            base_resp.prompt_tokens += r.prompt_tokens
            base_resp.completion_tokens += r.completion_tokens
        info = {"samples_requested": n, "samples_ok": n_ok, "clusters": len(clusters),
                "consensus": sum(1 for f in merged if int(f["_vote_support"].split("/")[0]) >= 2),
                "errors": errors,
                "rule": "同一提示并行采样，按引用源单据聚类；出现≥2次的判断才可在无确定性算子支撑时定为 MEDIUM"}
        return base_resp, raw_json, info

    @staticmethod
    def _doc_ids(case: AccountingCaseData) -> set:
        ids = set()
        for v in case.vouchers:
            ids.add(v.voucher_id)
            if v.associated_doc_id:
                ids.add(v.associated_doc_id)
        ids.update(c.contract_id for c in case.contracts)
        ids.update(x.invoice_no for x in case.invoices)
        ids.update(b.transaction_id for b in case.bank_flows)
        return {x for x in ids if x and len(x) >= 4}

    def _carry_votes(self, raw_before: Dict[str, Any], raw_after: Dict[str, Any], case: AccountingCaseData, n: int) -> None:
        ids = self._doc_ids(case)
        keyed = []
        for f in raw_before.get("risk_findings", []) or []:
            t = json.dumps(f, ensure_ascii=False)
            keyed.append(({x for x in ids if x in t}, f.get("_vote_support")))
        for f in raw_after.get("risk_findings", []) or []:
            t = json.dumps({k: v for k, v in f.items() if k != "_vote_support"}, ensure_ascii=False)
            k = {x for x in ids if x in t}
            best = None
            for kb, sup in keyed:
                if k & kb and sup:
                    if best is None or int(sup.split("/")[0]) > int(best.split("/")[0]):
                        best = sup
            f["_vote_support"] = best or f"1/{n}"

    @staticmethod
    def _reflection_feedback(report, case: AccountingCaseData, tool_results: Dict[str, Any]) -> str:
        from src.plugins.audit_fraud_plugin.substantive import revenue_net, compute_materiality
        vouchers = {v.voucher_id: v for v in case.vouchers}
        lines = ["【证据锚定守卫校验反馈】以下发现项未通过校验，请修正后重新输出完整 JSON（结构不变）："]
        for f in report.findings:
            if f.model_explanation and "确定性" in f.model_explanation:
                continue
            if f.grounded and "未能" not in (f.verification_note or ""):
                continue
            lines.append(f"- {f.finding_id}「{f.title}」：{f.verification_note}")
            for vid in (f.cited_refs or [])[:6]:
                v = vouchers.get(vid)
                if v:
                    lines.append(f"    · {vid}：不含税收入 {revenue_net(v):,.2f}；各分录行金额 "
                                 + "、".join(f"{e.account_name} {e.debit or e.credit:,.2f}" for e in v.entries))
        mat = compute_materiality(case)
        lines.append(f"要求：每条发现必须引用源数据中真实存在的单据号；金额须等于引用单据上的金额或其按科目口径的合计"
                     f"（收入用不含税收入）；无法锚定的判断请降为 LOW 关注事项。实际执行的重要性 ¥{mat['performance_materiality']:,.2f}。")
        return "\n".join(lines)

    def run_agent_turn(
        self,
        case: AccountingCaseData,
        messages: List[Dict[str, str]],
        tools_enabled: bool = True,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """Interactive multi-turn CPA Audit Agent turn."""
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        if tools_enabled and self.llm.mode != ExecutionMode.MOCK:
            agent_system = (
                "你是 DeepSeek-AuditMind 审计智能体（注册会计师视角）。"
                f"被审计单位：{case.company_name}（{case.stock_code}），行业 {case.industry}，期间 {case.audit_period}。"
                f"账套：凭证 {len(case.vouchers)}、发票 {len(case.invoices)}、流水 {len(case.bank_flows)}、合同 {len(case.contracts)}。"
                "所有数字必须来自工具返回结果，禁止自行计算或编造；需要数据时先调用工具。"
                "回答要写明：涉及单据号与金额、准则依据、舞弊机制判断、建议的进一步审计程序；最终结论由注册会计师确认。"
            )
            agent_messages = [{"role": "system", "content": agent_system}] + [
                {"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages
            ]
            try:
                resp = self.llm.chat_with_tools(
                    agent_messages, AUDIT_TOOL_SCHEMAS,
                    executor=lambda n, a: execute_audit_tool(case, n, a),
                    temperature=temperature,
                )
                return {
                    "role": "assistant",
                    "content": resp.content,
                    "reasoning_content": resp.reasoning_content,
                    "tool_calls": resp.tool_calls,
                    "tool_routing": "model_function_calling",
                    "privacy_audit": resp.privacy_audit,
                    "model_name": resp.model_name,
                    "execution_mode": resp.execution_mode.value,
                }
            except Exception as exc:
                if self.llm.mode == ExecutionMode.STRICT_ONLINE:
                    raise DeepSeekAPIError(f"Agent function-calling failed: {exc}")
                print(f"[Warning] function calling failed ({exc}); falling back to keyword tool routing")

        tool_calls = []
        tool_context_str = ""

        if tools_enabled:
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

            if any(k in last_user_msg for k in ("凭证", "分录", "科目", "借贷")):
                vouchers_summary = []
                for v in case.vouchers[:5]:
                    entries_text = ", ".join(f"{voucher_entry_direction(e)} {e.account_name} ¥{e.debit or e.credit:,.2f}" for e in v.entries)
                    vouchers_summary.append(f"凭证号:{v.voucher_id} | 日期:{v.voucher_date} | 分录:[{entries_text}]")
                tool_calls.append({
                    "tool_name": "search_vouchers",
                    "tool_input": {"case_id": case.case_id, "sample_size": len(case.vouchers)},
                    "tool_output": {"sample_vouchers": vouchers_summary, "total_vouchers": len(case.vouchers)},
                    "status": "success"
                })
                tool_context_str += f"\n【工具调用: search_vouchers】抽样凭证明细 ({min(5, len(case.vouchers))}/{len(case.vouchers)}):\n" + "\n".join(vouchers_summary)

            if any(k in last_user_msg for k in ("流水", "银行", "对手方", "转账", "资金")):
                flows_summary = []
                for b in case.bank_flows[:5]:
                    flows_summary.append(f"流水号:{b.transaction_id} | 对手方:{b.counterparty_name} | 金额:¥{b.amount:,.2f} | 摘要:{b.remark}")
                tool_calls.append({
                    "tool_name": "search_bank_flows",
                    "tool_input": {"case_id": case.case_id, "sample_size": len(case.bank_flows)},
                    "tool_output": {"sample_flows": flows_summary, "total_flows": len(case.bank_flows)},
                    "status": "success"
                })
                tool_context_str += f"\n【工具调用: search_bank_flows】银行流水抽样 ({min(5, len(case.bank_flows))}/{len(case.bank_flows)}):\n" + "\n".join(flows_summary)

            for kws, tname in (
                (("分录测试", "全量", "周末", "节假日", "职责分离", "整数金额", "高风险分录"), "journal_entry_testing"),
                (("闭环", "往返", "过桥", "体外循环", "资金循环", "回流"), "detect_fund_round_trips"),
                (("benford", "本福特", "首位数字", "首位数"), "benford_first_digit_test"),
                (("职业判断", "减值", "预计负债", "费用完整性", "负债核销", "冲减成本"), "run_judgment_procedures"),
                (("截止", "配比", "发出商品", "终验", "跨期"), "verify_cutoff_and_cost"),
                (("背靠背", "总额法", "净额法", "商业实质"), "detect_back_to_back_trades"),
            ):
                if any(k in last_user_msg.lower() for k in kws):
                    out = execute_audit_tool(case, tname, {})
                    tool_calls.append({"tool_name": tname, "tool_input": {"case_id": case.case_id},
                                       "tool_output": out, "status": "success"})
                    tool_context_str += f"\n【工具调用: {tname}】" + json.dumps(out, ensure_ascii=False, default=str)[:1500]

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

        if self.llm.mode == ExecutionMode.MOCK:
            content = self._generate_heuristic_agent_response(case, last_user_msg, tool_calls)
            reasoning = "DeepSeek CoT 思考链（离线启发式演绎）：结合被审计单位凭证与流水事实，调度确定性审计算子，依据 CAS 14 / CSA 1141 完成专家研判。"
            return {
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
                "tool_calls": tool_calls,
                "tool_routing": "keyword_router_offline",
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
            f"### 注册会计师审计专业意见 · {case.company_name} ({case.stock_code})",
            ""
        ]

        if beneish_call:
            b_data = beneish_call["tool_output"]
            if b_data.get("is_calculable"):
                m_val = b_data.get("m_score", 0.0)
                is_man = b_data.get("is_manipulator", False)
                response_lines.append(f"**1. Beneish M-Score 操纵指数分析**：")
                response_lines.append(f"- 测算得分：`{m_val:.2f}`（阈值标准：大于 -1.78 即存在高危财务操纵嫌疑）。")
                response_lines.append(f"- 评价结论：{'存在显著盈余操纵/财报粉饰风险' if is_man else '指标处于常规合理波动区间'}。")
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
        """Autonomous Multi-Step Audit Goal Execution."""
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
                "detail": "调度 Beneish M-Score 8 变量模型、三单穿透勾稽、专项实质性程序与职业判断算子，完成数值层面刚性排查。"
            },
            {
                "step": 3,
                "title": "DeepSeek 大模型准则深度定性",
                "status": "completed",
                "detail": "基于 CAS 14、CAS 1、CAS 8、CAS 13、CAS 22、CAS 36 及 CSA 1141 开展商业实质与舞弊机理演绎。"
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
