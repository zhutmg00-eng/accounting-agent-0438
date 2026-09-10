"""
Benchmark Harness Runner.
Executes test cases against ground truth, calculates Precision, Recall, F1, 
Field-level Risk Type Accuracy, Risk Level Accuracy, Amount Accuracy (error <= 1%),
and False Positive Rates.
"""

from typing import List, Optional
import sys
import os
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.core.schemas import BenchmarkSummary, CaseEvalScore
from src.core.harness import AccountingAgentHarness
from src.benchmark.test_cases import get_benchmark_cases

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def run_benchmark_suite(
    harness: Optional[AccountingAgentHarness] = None,
    plugin_id: str = "audit_fraud_detection"
) -> BenchmarkSummary:
    """Run full rigorous evaluation suite across all benchmark cases."""
    console = Console(legacy_windows=False)
    harness = harness or AccountingAgentHarness()
    cases = get_benchmark_cases()

    mode_display = harness.llm.mode.value.upper()
    console.print(Panel.fit(
        f"[bold cyan]2026年北京市大学生数智会计创新应用竞赛[/bold cyan]\n"
        f"[bold green]DeepSeek-AuditMind 智能体评测基座 (Benchmark Harness)[/bold green]\n"
        f"当前执行模式: [bold yellow]{mode_display}[/bold yellow] | 模型: [magenta]{harness.llm.model_name}[/magenta]",
        border_style="cyan"
    ))

    case_scores: List[CaseEvalScore] = []
    
    for case in cases:
        console.print(f"[yellow][RUN][/yellow] 正在评测案例: [bold]{case.case_id}[/bold] - {case.company_name} ...")
        score = harness.evaluate_case(case, plugin_id=plugin_id)
        case_scores.append(score)
        status_str = "[green][PASS] 通过[/green]" if score.passed else "[red][FAIL] 未通过[/red]"
        console.print(
            f"   -> {status_str} | F1: [bold]{score.f1_score:.2f}[/bold] | "
            f"金额精准率: [bold]{score.amount_accuracy_rate:.1%}[/bold] | "
            f"类型命中: {score.type_accuracy_rate:.1%} | 耗时: {score.latency_seconds:.4f}s"
        )

    # Aggregate Metrics
    n = len(case_scores)
    passed_count = sum(1 for s in case_scores if s.passed)
    mean_p = sum(s.precision for s in case_scores) / max(n, 1)
    mean_r = sum(s.recall for s in case_scores) / max(n, 1)
    mean_f1 = sum(s.f1_score for s in case_scores) / max(n, 1)
    mean_amount_acc = sum(s.amount_accuracy_rate for s in case_scores) / max(n, 1)
    mean_type_acc = sum(s.type_accuracy_rate for s in case_scores) / max(n, 1)
    mean_evidence_hit = sum(s.evidence_hit_rate for s in case_scores) / max(n, 1)
    total_fp = sum(s.false_positive_count for s in case_scores)
    schema_valid_rate = sum(1 for s in case_scores if s.json_schema_valid) / max(n, 1)
    math_acc = sum(s.math_accuracy_rate for s in case_scores) / max(n, 1)
    mean_latency = sum(s.latency_seconds for s in case_scores) / max(n, 1)

    summary = BenchmarkSummary(
        total_cases=n,
        passed_cases=passed_count,
        mean_precision=round(mean_p, 4),
        mean_recall=round(mean_r, 4),
        mean_f1_score=round(mean_f1, 4),
        mean_amount_accuracy=round(mean_amount_acc, 4),
        mean_type_accuracy=round(mean_type_acc, 4),
        mean_evidence_hit_rate=round(mean_evidence_hit, 4),
        false_positive_rate=round(total_fp / max(n, 1), 4),
        schema_valid_rate=round(schema_valid_rate, 4),
        math_accuracy_rate=round(math_acc, 4),
        mean_latency=round(mean_latency, 4),
        execution_mode=harness.llm.mode.value,
        case_scores=case_scores
    )

    # Print Rich Scorecard
    table = Table(title="DeepSeek-AuditMind 字段与金额级评测得分卡 (Rigorous Benchmark Scorecard)", show_header=True, header_style="bold magenta")
    table.add_column("案例编号", style="cyan", width=14)
    table.add_column("企业名称", width=22)
    table.add_column("类型命中率", justify="right")
    table.add_column("金额准确率(≤1%)", justify="right", style="bold yellow")
    table.add_column("证据溯源率", justify="right")
    table.add_column("F1-Score", justify="right", style="bold green")
    table.add_column("误报数(FP)", justify="center")
    table.add_column("耗时(s)", justify="right")
    table.add_column("评测状态", justify="center")

    for s in case_scores:
        status_text = "[bold green]PASSED[/bold green]" if s.passed else "[bold red]FAILED[/bold red]"
        table.add_row(
            s.case_id,
            s.case_name,
            f"{s.type_accuracy_rate:.1%}",
            f"{s.amount_accuracy_rate:.1%}",
            f"{s.evidence_hit_rate:.1%}",
            f"{s.f1_score:.2f}",
            f"{s.false_positive_count}",
            f"{s.latency_seconds:.4f}",
            status_text
        )

    console.print(table)
    return summary


if __name__ == "__main__":
    run_benchmark_suite()
