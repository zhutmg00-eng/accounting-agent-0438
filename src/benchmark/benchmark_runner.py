"""
Benchmark Harness Runner.
Executes test cases against ground truth, calculates Precision, Recall, F1, Math Accuracy, and formats a scorecard.
"""

from typing import List, Optional
import sys
import os
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
    """Run full evaluation suite across all benchmark cases."""
    console = Console(legacy_windows=False)
    harness = harness or AccountingAgentHarness()
    cases = get_benchmark_cases()

    console.print(Panel.fit(
        "[bold cyan]2026年北京市大学生数智会计创新应用竞赛[/bold cyan]\n"
        "[bold green]DeepSeek-AuditMind 智能体评测基座 (Benchmark Harness) 启动中...[/bold green]",
        border_style="cyan"
    ))

    case_scores: List[CaseEvalScore] = []
    
    for case in cases:
        console.print(f"[yellow][RUN][/yellow] 正在评测案例: [bold]{case.case_id}[/bold] - {case.company_name} ...")
        score = harness.evaluate_case(case, plugin_id=plugin_id)
        case_scores.append(score)
        status_str = "[green][PASS] 通过[/green]" if score.passed else "[red][FAIL] 未通过[/red]"
        console.print(f"   -> {status_str} | F1: [bold]{score.f1_score:.2f}[/bold] | 准全率(P/R): {score.precision:.2f}/{score.recall:.2f} | 耗时: {score.latency_seconds:.4f}s")

    # Aggregate Metrics
    n = len(case_scores)
    passed_count = sum(1 for s in case_scores if s.passed)
    mean_p = sum(s.precision for s in case_scores) / max(n, 1)
    mean_r = sum(s.recall for s in case_scores) / max(n, 1)
    mean_f1 = sum(s.f1_score for s in case_scores) / max(n, 1)
    schema_valid_rate = sum(1 for s in case_scores if s.json_schema_valid) / max(n, 1)
    math_acc = sum(s.math_accuracy_rate for s in case_scores) / max(n, 1)
    mean_latency = sum(s.latency_seconds for s in case_scores) / max(n, 1)

    summary = BenchmarkSummary(
        total_cases=n,
        passed_cases=passed_count,
        mean_precision=round(mean_p, 4),
        mean_recall=round(mean_r, 4),
        mean_f1_score=round(mean_f1, 4),
        schema_valid_rate=round(schema_valid_rate, 4),
        math_accuracy_rate=round(math_acc, 4),
        mean_latency=round(mean_latency, 4),
        case_scores=case_scores
    )

    # Print Rich Scorecard
    table = Table(title="DeepSeek-AuditMind 综合评测基准得分卡 (Benchmark Scorecard)", show_header=True, header_style="bold magenta")
    table.add_column("案例编号", style="cyan", width=14)
    table.add_column("企业名称", width=22)
    table.add_column("查准率(P)", justify="right")
    table.add_column("查全率(R)", justify="right")
    table.add_column("F1-Score", justify="right", style="bold green")
    table.add_column("JSON结构合规", justify="center")
    table.add_column("数学计算准确率", justify="center")
    table.add_column("耗时(s)", justify="right")
    table.add_column("评测状态", justify="center")

    for s in case_scores:
        status_text = "[bold green]PASSED[/bold green]" if s.passed else "[bold red]FAILED[/bold red]"
        json_text = "[OK] 100%" if s.json_schema_valid else "[ERR]"
        math_text = "[OK] 100%" if s.math_accuracy_rate == 1.0 else "[ERR]"
        table.add_row(
            s.case_id,
            s.case_name,
            f"{s.precision:.2%}",
            f"{s.recall:.2%}",
            f"{s.f1_score:.2f}",
            json_text,
            math_text,
            f"{s.latency_seconds:.4f}",
            status_text
        )

    console.print(table)

    summary_panel = (
        f"[bold]总评测案例数:[/bold] {n}  |  [bold]通过案例数:[/bold] [green]{passed_count}[/green] ({passed_count/n:.1%})\n"
        f"[bold]平均查准率 (Mean Precision):[/bold] [cyan]{mean_p:.2%}[/cyan]\n"
        f"[bold]平均查全率 (Mean Recall):[/bold] [cyan]{mean_r:.2%}[/cyan]\n"
        f"[bold]平均综合 F1 指标:[/bold] [bold green]{mean_f1:.4f}[/bold green]\n"
        f"[bold]结构化输出达标率 (Schema Compliance):[/bold] [green]{schema_valid_rate:.1%}[/green]\n"
        f"[bold]算术与勾稽零幻觉率 (Math Accuracy):[/bold] [green]{math_acc:.1%}[/green]\n"
        f"[bold]平均响应延迟 (Mean Latency):[/bold] {mean_latency:.4f} 秒"
    )
    console.print(Panel(summary_panel, title="评测基准综合指标汇总", border_style="green"))

    return summary


if __name__ == "__main__":
    run_benchmark_suite()
