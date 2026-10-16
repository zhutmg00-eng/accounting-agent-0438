"""
AuditMind Plugin Implementation.
"""

import json
from typing import Dict, Any, List
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
from src.plugins.audit_fraud_plugin.analytics import run_population_analytics


def _source_ids(case: AccountingCaseData) -> set:
    """Every document identifier that genuinely exists in the engagement data."""
    ids = set()
    for v in case.vouchers:
        ids.add(v.voucher_id)
        if v.associated_doc_id:
            ids.add(v.associated_doc_id)
    ids.update(c.contract_id for c in case.contracts)
    ids.update(i.invoice_no for i in case.invoices)
    for b in case.bank_flows:
        ids.add(b.transaction_id)
    return {i for i in ids if i and len(i) >= 4}


def _source_amounts(case: AccountingCaseData, cited: List[str]) -> set:
    """Every amount that genuinely appears on the cited documents."""
    cited_set = set(cited)
    out = set()
    for v in case.vouchers:
        if v.voucher_id in cited_set or (v.associated_doc_id and v.associated_doc_id in cited_set):
            out.add(max(sum(e.debit for e in v.entries), sum(e.credit for e in v.entries)))
            out.update(e.debit for e in v.entries if e.debit)
            out.update(e.credit for e in v.entries if e.credit)
    out.update(c.total_amount for c in case.contracts if c.contract_id in cited_set)
    for i in case.invoices:
        if i.invoice_no in cited_set:
            out.update({i.total_amount, i.amount_without_tax})
    out.update(abs(b.amount) for b in case.bank_flows if b.transaction_id in cited_set)
    return {a for a in out if a}


def ground_findings(findings, case: AccountingCaseData, recon: Dict[str, Any]) -> Dict[str, Any]:
    """Grounding guard: model findings must cite real documents, amounts must be traceable.

    * A finding that cites no identifier present in the source data is marked
      ``grounded=False`` and routed to human review instead of being trusted.
    * A quantified finding's ``impact_amount`` must equal (±1%) an amount that
      appears on a cited document or that a deterministic operator produced.
      Otherwise it is flagged as unverifiable.  The guard never rewrites the
      model's figure: replacing one number with another would itself be an
      unexplained judgement.
    """
    ids = _source_ids(case)
    operator_amounts = {float(d.get("amount", 0.0)) for d in recon.get("discrepancies", [])}
    # 用去重后的净敞口，不用简单加总（简单加总会把同一笔资金重复计算）
    operator_amounts.add(float(recon.get("net_exposure_amount", recon.get("total_abnormal_amount", 0.0))))

    grounded_n = unverified_n = 0
    for f in findings:
        text = " ".join(
            [f.rule_evidence or "", f.title or ""]
            + [f"{e.source_ref} {e.detail}" for e in f.evidences]
        )
        cited = sorted(i for i in ids if i in text)
        f.cited_refs = cited
        notes = []
        if not cited:
            f.grounded = False
            f.human_verification_flag = "【证据未锚定】模型结论未引用任何源数据单据号，须注册会计师人工复核后方可采信"
            notes.append("未在源数据中找到该发现项引用的单据号")
        else:
            f.grounded = True
            grounded_n += 1
        if f.impact_amount:
            pool = (_source_amounts(case, cited) | operator_amounts) - {0.0}
            if any(abs(f.impact_amount - a) <= max(abs(a) * 0.01, 1.0) for a in pool):
                notes.append("金额可在源单据或算子结果中复核")
            else:
                unverified_n += 1
                notes.append(f"金额 ¥{f.impact_amount:,.2f} 未能在引用单据或算子结果中复核，须人工确认口径")
                if f.grounded:
                    f.human_verification_flag = "【金额待复核】" + (f.human_verification_flag or "")
        else:
            notes.append("未量化金额")
        f.verification_note = "；".join(notes)
    return {
        "findings_total": len(findings),
        "grounded": grounded_n,
        "ungrounded": len(findings) - grounded_n,
        "amount_unverified": unverified_n,
        "rule": "每条发现须引用源数据中真实存在的单据号；量化金额须能在引用单据或算子结果中复核（容差 1%）",
    }


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

        # 3. Population-level analytics (JE testing / fund round-trips / Benford)
        results["analytics"] = run_population_analytics(case)

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
            f"- 三单勾稽比对异常数量: {recon.get('total_discrepancies_count', 0)} 处，逐项加总 {recon.get('total_abnormal_amount', 0.0):,.2f} 元，"
            f"去重后净资金敞口 {recon.get('net_exposure_amount', 0.0):,.2f} 元（同一笔资金在凭证与流水中只计一次，报告金额请以净敞口为准）"
        )
        for disc in recon.get("discrepancies", []):
            disc_amt = disc.get('amount', 0.0)
            prompt_parts.append(f"  * [{disc.get('type')}] 关联单据: {disc.get('voucher_id', '')} | 涉及金额: {disc_amt:.2f}元 | 详情: {disc.get('detail')}")

        analytics = tool_results.get("analytics") or {}
        je = analytics.get("journal_entry_testing") or {}
        if je.get("applicable"):
            prompt_parts.append(
                f"- 全量分录测试：覆盖凭证 {je['population']} 张（100%），命中风险标识 {je['flagged_count']} 张，其中高风险 {je['high_risk_count']} 张"
            )
            for item in je.get("flagged", [])[:5]:
                prompt_parts.append(f"  * {item['voucher_id']} | {item['date']} | ¥{item['amount']:,.2f} | 风险分 {item['score']} | {'、'.join(item['rule_names'])}")
        loops = analytics.get("fund_round_trips") or {}
        if loops.get("loop_count"):
            prompt_parts.append(f"- 资金闭环识别：检出 {loops['loop_count']} 组资金往返，合计 ¥{loops['loop_amount']:,.2f}")
            for lp in loops.get("loops", [])[:5]:
                prompt_parts.append(f"  * 流出 {lp['out_id']}（{lp['out_party']}）→ {lp['days']} 天后流入 {lp['in_id']}（{lp['in_party']}），{lp['pattern']}")
        bf = analytics.get("benford") or {}
        if bf.get("applicable"):
            prompt_parts.append(f"- Benford 首位数字检验：样本 {bf['sample_size']}，MAD={bf['mad']}，结论：{bf['verdict']}")
        if beneish and beneish.get("caveats"):
            prompt_parts.append("- Beneish 输入数据质量提示：" + "；".join(beneish["caveats"]))

        # Prompt budget: the operators already processed the full population, so the
        # model only needs the vouchers they point at (plus a small head sample).
        flagged_ids = {d.get("voucher_id") for d in recon.get("discrepancies", [])}
        flagged_ids |= {f["voucher_id"] for f in (je.get("flagged") or [])[:10]}
        focus = [v for v in case.vouchers if v.voucher_id in flagged_ids]
        focus += [v for v in case.vouchers if v.voucher_id not in flagged_ids][: max(0, 5 - len(focus))]
        focus = focus[:30]
        prompt_parts.append(f"\n【记账凭证明细（算子指向的重点凭证 {len(focus)} 张 / 全量 {len(case.vouchers)} 张）】：")
        for v in focus:
            entries_str = "; ".join([f"{e.account_name}(借:{e.debit:.2f}, 贷:{e.credit:.2f})" for e in v.entries])
            prompt_parts.append(f"- 凭证号: {v.voucher_id} | 日期: {v.voucher_date} | 关联单号: {v.associated_doc_id or '无'} | 分录: {entries_str}")

        prompt_parts.append("\n【合同与发票抽样明细】：")
        for c in case.contracts[:20]:
            prompt_parts.append(f"- 合同: {c.contract_id} | 交易方: {c.customer_or_vendor} | 金额: {c.total_amount:,.2f}元 | 关联方: {c.is_related_party}")
        focus_docs = {v.associated_doc_id for v in focus if v.associated_doc_id}
        invs = [i for i in case.invoices if i.invoice_no in focus_docs] or case.invoices[:5]
        for inv in invs[:20]:
            prompt_parts.append(f"- 发票: {inv.invoice_no} | 日期: {inv.invoice_date} | 价税合计: {inv.total_amount:,.2f}元 | 品目: {inv.goods_or_service}")
        if len(case.invoices) > len(invs[:20]) or len(case.vouchers) > len(focus):
            prompt_parts.append("（其余记录已由确定性算子全量处理，结论以算子结果为准）")

        prompt_parts.append("\n请基于上述事实与准则规范，输出完整的审计穿透研判 JSON 报告。")
        return "\n".join(prompt_parts)

    @staticmethod
    def _analytics_findings(analytics: Dict[str, Any], start: int = 0) -> List[RiskFinding]:
        """Promote population-analytics results to findings, deterministically.

        * Every detected fund round-trip group becomes one finding.
        * High-risk journal entries (score ≥5) become one finding, but only when
          the population is large enough (≥30 vouchers) for JE testing to be a
          population procedure rather than a one-voucher anecdote.
        These findings are produced without any model call and say so.
        """
        out: List[RiskFinding] = []
        rt = analytics.get("fund_round_trips") or {}
        if rt.get("loop_count"):
            loops = rt["loops"]
            out.append(RiskFinding(
                finding_id=f"RF-{start + len(out) + 1:03d}",
                title=f"疑似资金体外循环：{len(loops)} 组同一/关联对手方资金往返",
                risk_level=RiskLevel.HIGH if len(loops) >= 2 else RiskLevel.MEDIUM,
                accounting_standard="CSA 1141 舞弊风险 / CAS 36 关联方披露",
                impact_amount=float(rt.get("loop_amount", 0.0)),
                suspected_mechanism="资金以预付款、往来款等名义流出后短期内由同一或关联对手方流回，可能用于虚构回款或粉饰现金流",
                evidences=[EvidenceItem(
                    evidence_type="资金往返",
                    source_ref=f"流水[{l['out_id']}] → 流水[{l['in_id']}]",
                    detail=f"{l['out_party']} 流出 ¥{l['out_amount']:,.2f}，{l['days']} 天后流入 ¥{l['in_amount']:,.2f}",
                ) for l in loops[:10]],
                suggested_procedure="获取对手方工商与股权信息识别隐性关联方；函证往来余额；检查资金流出的合同与审批、流回的业务实质",
                rule_evidence=rt.get("method", ""),
                model_explanation="由确定性全量分析程序生成，未经大模型",
            ))
        je = analytics.get("journal_entry_testing") or {}
        high = [f for f in je.get("flagged", []) if f.get("score", 0) >= 5]
        if je.get("applicable") and je.get("population", 0) >= 30 and high:
            out.append(RiskFinding(
                finding_id=f"RF-{start + len(out) + 1:03d}",
                title=f"高风险会计分录 {je.get('high_risk_count', len(high))} 张（全量分录测试）",
                risk_level=RiskLevel.MEDIUM,
                accounting_standard="CSA 1141 第三十二条 会计分录测试",
                impact_amount=float(sum(f["amount"] for f in high)),
                suspected_mechanism="多项风险标识叠加（" + "、".join(sorted({n for f in high for n in f["rule_names"]})) + "）",
                evidences=[EvidenceItem(
                    evidence_type="分录测试",
                    source_ref=f"凭证[{f['voucher_id']}]",
                    detail=f"{f['date']} ¥{f['amount']:,.2f} 风险分 {f['score']}：{'、'.join(f['rule_names'])}",
                    source_file=f.get("source_file") or "",
                    row_index=f.get("row_index"),
                ) for f in high[:10]],
                suggested_procedure="对高风险分录逐张检查原始凭证与审批记录，询问制单人与复核人，执行截止测试",
                rule_evidence=je.get("method", ""),
                model_explanation="由确定性全量分析程序生成，未经大模型",
            ))
        return out

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

        findings.extend(self._analytics_findings(tool_results.get("analytics") or {}, start=len(findings)))
        verification = ground_findings(findings, case, recon)

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
            executive_summary=raw_json.get("executive_summary", "审计穿透分析已完成。"),
            analytics=tool_results.get("analytics") or {},
            verification=verification,
        )
