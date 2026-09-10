"""
CLI Runner for DeepSeek-AuditMind Agent Harness.
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure root path is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.core.harness import AccountingAgentHarness
from src.benchmark.test_cases import get_benchmark_cases
from src.benchmark.benchmark_runner import run_benchmark_suite
from src.exporters.excel_exporter import export_workpaper_to_excel
from src.exporters.pdf_exporter import export_report_to_pdf
from src.exporters.json_exporter import export_report_to_json
from src.config import settings, OUTPUT_DIR
from rich.console import Console
from rich.panel import Panel

console = Console(legacy_windows=False)


def main():
    parser = argparse.ArgumentParser(description="DeepSeek Accounting Agent Harness CLI")
    parser.add_argument("--benchmark", action="store_true", help="Run full benchmark evaluation suite")
    parser.add_argument("--case", type=int, default=0, help="Run specific case index (0-3)")
    parser.add_argument("--plugin", type=str, default="audit_fraud_detection", help="Plugin ID to execute")
    parser.add_argument("--export", action="store_true", help="Export Excel/PDF/JSON artifacts")
    args = parser.parse_args()

    harness = AccountingAgentHarness()

    if args.benchmark:
        run_benchmark_suite(harness, plugin_id=args.plugin)
        return

    cases = get_benchmark_cases()
    if args.case < 0 or args.case >= len(cases):
        console.print(f"[red]Invalid case index. Choose between 0 and {len(cases)-1}.[/red]")
        return

    case = cases[args.case]
    console.print(Panel.fit(
        f"[bold cyan]正在运行案例:[/bold cyan] {case.case_id} - {case.company_name}\n"
        f"[bold yellow]选用插件:[/bold yellow] {args.plugin}",
        border_style="cyan"
    ))

    report = harness.run_case(case, plugin_id=args.plugin)

    console.print(f"[bold green][OK] 穿透研判完成！综合风险评级:[/bold green] [bold red]{report.overall_risk_rating.value}[/bold red]")
    console.print(f"[bold]摘要:[/bold] {report.executive_summary}\n")
    console.print(f"[bold]发现风险项数量:[/bold] {len(report.findings)}")
    for f in report.findings:
        console.print(f"  * [{f.finding_id}] [bold]{f.title}[/bold] ({f.risk_level.value}) -> 金额: ¥{f.impact_amount:,.2f} (依据: {f.accounting_standard})")

    if args.export:
        out_dir = OUTPUT_DIR
        e_path = export_workpaper_to_excel(report, out_dir / f"{case.company_name}_底稿.xlsx")
        p_path = export_report_to_pdf(report, out_dir / f"{case.company_name}_报告.pdf")
        j_path = export_report_to_json(report, out_dir / f"{case.company_name}_数据.json")
        console.print(f"[green][OK] 成果导出成功:[/green]\n  Excel: {e_path}\n  PDF: {p_path}\n  JSON: {j_path}")


if __name__ == "__main__":
    main()
