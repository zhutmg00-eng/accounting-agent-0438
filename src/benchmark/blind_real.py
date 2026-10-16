"""
外部盲测：真实处罚案例盲测集 + Beneish 年报原值检验。

1. 盲测集 data/cases/blind/blind_cases.json
   由一个**看不到本项目任何代码与检测规则**的独立出题方，依据证监会/地方证监局行政处罚
   决定书原文编写（10 家舞弊公司 + 4 家合规对照，均不在 28 例开发集中），摘要和附言不得
   出现"虚构/伪造"等泄露答案的字样。系统对这些案例从未调参。
2. Beneish 检验：用 28 例开发集中摘自年报原始发布版的两期数据，统计 M-Score 对舞弊组的
   检出率与对合规组的误报率（不使用任何真值标签调参）。

用法：uv run python -m src.benchmark.blind_real [--mode mock|online] [--out output/blind_real_report.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.config import settings
from src.core.schemas import AccountingCaseData, ExecutionMode

BLIND_FILE = settings.base_dir / "data" / "cases" / "blind" / "blind_cases.json"
DEV_FILE = settings.base_dir / "data" / "cases" / "real_cases_database.json"


def beneish_on_reported_financials() -> Dict[str, Any]:
    from src.plugins.audit_fraud_plugin.tools import calculate_beneish_from_case

    rows = []
    for raw in json.loads(DEV_FILE.read_text(encoding="utf-8")):
        case = AccountingCaseData(**raw)
        res = calculate_beneish_from_case(case)
        rows.append({
            "case_id": case.case_id, "company": case.company_name,
            "group": "fraud" if not case.case_id.startswith("REAL_CLEAN") else "clean",
            "m_score": res.get("m_score"), "flagged": bool(res.get("is_manipulator")),
            "input_quality": res.get("input_quality"), "caveats": res.get("caveats", []),
        })
    reported = [r for r in rows if r["input_quality"] == "reported"]
    fraud = [r for r in reported if r["group"] == "fraud"]
    clean = [r for r in reported if r["group"] == "clean"]
    return {
        "scope": "仅统计两期数据均为年报披露原值的案例（重构数据的案例单列，不计入）",
        "fraud_cases": len(fraud),
        "fraud_flagged": sum(r["flagged"] for r in fraud),
        "detection_rate": round(sum(r["flagged"] for r in fraud) / max(len(fraud), 1), 4),
        "clean_cases": len(clean),
        "clean_false_positive": sum(r["flagged"] for r in clean),
        "excluded_reconstructed": [r["company"] for r in rows if r["input_quality"] != "reported"],
        "rows": rows,
    }


LEAKY_FIELDS = ("csrc_summary", "case_category", "penalty_decision_no", "source_url", "ground_truth_findings")


def _cited_ids(finding) -> str:
    parts = [finding.rule_evidence or "", finding.title or "", finding.suspected_mechanism or ""]
    for e in finding.evidences:
        parts += [e.source_ref or "", e.detail or "", e.source_file or ""]
    return " ".join(parts)


def evaluate_blind_cases(mode: str = "mock") -> Dict[str, Any]:
    """按证据锚点评分（与措辞无关）：某条真值的任一应识别单据号被系统发现项引用，即视为命中。

    系统运行时看到的是剥离了答案字段（处罚摘要、案件类别、文号、链接、真值）的案例。
    """
    from src.core.harness import AccountingAgentHarness
    from src.core.llm_adapter import DeepSeekLLMAdapter
    from src.plugins.audit_fraud_plugin.analytics import journal_entry_testing, detect_fund_round_trips

    if not BLIND_FILE.exists():
        return {"available": False, "reason": f"未找到盲测集 {BLIND_FILE}"}
    mode_enum = ExecutionMode.STRICT_ONLINE if mode == "online" else ExecutionMode.MOCK
    harness = AccountingAgentHarness(llm_adapter=DeepSeekLLMAdapter(mode=mode_enum))
    rows: List[Dict[str, Any]] = []
    for raw in json.loads(BLIND_FILE.read_text(encoding="utf-8")):
        truth = raw.get("ground_truth_findings") or []
        visible = {k: v for k, v in raw.items() if k not in LEAKY_FIELDS}
        case = AccountingCaseData(**visible)
        report = harness.run_case(case)
        je = journal_entry_testing(case, top_n=10_000)
        je_flagged = {f["voucher_id"] for f in je["flagged"]}
        loops = detect_fund_round_trips(case)["loops"]
        loop_ids = {l["out_id"] for l in loops} | {l["in_id"] for l in loops}
        sig = [f for f in report.findings if f.risk_level in ("HIGH", "MEDIUM")]
        per_truth = []
        for gt in truth:
            ids = gt.get("expected_vouchers") or []
            hit = None
            for f in report.findings:
                cited = _cited_ids(f)
                if any(i and i in cited for i in ids):
                    hit = f
                    break
            amount_ok = bool(hit) and abs(hit.impact_amount - gt["expected_amount"]) / max(gt["expected_amount"], 1) <= 0.01
            per_truth.append({
                "finding_type": gt["finding_type"], "expected_amount": gt["expected_amount"],
                "agent_hit": bool(hit), "agent_title": hit.title if hit else None,
                "amount_within_1pct": amount_ok,
                "analytics_flagged_ids": [i for i in ids if i in je_flagged or i in loop_ids],
            })
        rows.append({
            "case_id": raw["case_id"], "company": raw["company_name"],
            "group": "fraud" if truth else "clean",
            "case_flagged": len(sig) > 0,
            "high_medium_findings": len(sig),
            "findings": [f"[{f.risk_level}] {f.title}" for f in report.findings],
            "truth": per_truth,
            "source_url": raw.get("source_url"),
        })
    fraud = [r for r in rows if r["group"] == "fraud"]
    clean = [r for r in rows if r["group"] == "clean"]
    truths = [t for r in fraud for t in r["truth"]]
    return {
        "available": True,
        "mode": mode,
        "protocol": "出题方未接触代码；运行时剥离答案字段；按证据锚点评分。",
        "cases": len(rows),
        "fraud_cases": len(fraud),
        "fraud_cases_flagged": sum(r["case_flagged"] for r in fraud),
        "truth_items": len(truths),
        "truth_items_hit_by_agent": sum(t["agent_hit"] for t in truths),
        "truth_items_amount_within_1pct": sum(t["amount_within_1pct"] for t in truths),
        "truth_items_with_analytics_flag": sum(bool(t["analytics_flagged_ids"]) for t in truths),
        "clean_cases": len(clean),
        "clean_cases_flagged": sum(r["case_flagged"] for r in clean),
        "clean_cases_with_high": sum(any(f.startswith("[RiskLevel.HIGH]") or f.startswith("[HIGH]") for f in r["findings"]) for r in clean),
        "per_case": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["mock", "online"], default="mock")
    ap.add_argument("--out", default="output/blind_real_report.json")
    args = ap.parse_args()
    rep = {"beneish_reported": beneish_on_reported_financials(), "blind_cases": evaluate_blind_cases(args.mode)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    b = rep["beneish_reported"]
    print(f"Beneish 年报原值：舞弊组检出 {b['fraud_flagged']}/{b['fraud_cases']}，合规组误报 {b['clean_false_positive']}/{b['clean_cases']}")
    bc = rep["blind_cases"]
    if bc.get("available"):
        print(f"盲测集（{bc['mode']}）：舞弊公司被标出 {bc['fraud_cases_flagged']}/{bc['fraud_cases']}；"
              f"真值条目命中 {bc['truth_items_hit_by_agent']}/{bc['truth_items']}（金额±1% {bc['truth_items_amount_within_1pct']}）；"
              f"全量分析覆盖 {bc['truth_items_with_analytics_flag']}/{bc['truth_items']}；合规组误报 {bc['clean_cases_flagged']}/{bc['clean_cases']}")
        for r in bc["per_case"]:
            print(" ", r["case_id"], r["company"][:8], "flag" if r["case_flagged"] else "----",
                  [("✓" if t["agent_hit"] else "✗") + t["finding_type"][:14] for t in r["truth"]], r["findings"][:4])


if __name__ == "__main__":
    main()
