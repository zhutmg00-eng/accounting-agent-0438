"""
JSON Exporter and Schema Validator.
"""

import json
from pathlib import Path
from src.core.schemas import AnalysisReportResult


def export_report_to_json(report: AnalysisReportResult, output_path: Path) -> Path:
    """Export structured report to JSON format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    return output_path
