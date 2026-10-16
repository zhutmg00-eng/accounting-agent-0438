"""外部盲测与年报原值相关的回归测试。"""
import json

import pytest

from src.benchmark.blind_synthetic import build_ledger, evaluate
from src.core.schemas import AccountingCaseData
from src.plugins.audit_fraud_plugin.tools import (
    calculate_beneish_m_score, perform_three_way_reconciliation,
)
from src.config import settings


def test_synthetic_blind_benchmark_small_run():
    rep = evaluate([9101, 9102, 9103], size=120)
    for label, r in rep["rules"].items():
        assert r["recall"] == 1.0, label
        assert r["precision"] == 1.0, label
    assert rep["benford"]["tp"] == 3


def test_makeup_workday_is_not_offday():
    from src.plugins.audit_fraud_plugin.analytics import _is_offday
    from datetime import date
    assert _is_offday(date(2024, 9, 16))          # 中秋
    assert not _is_offday(date(2024, 9, 14))      # 调休上班的周六
    assert _is_offday(date(2024, 5, 3))           # 劳动节


def test_blind_clean_controls_produce_no_discrepancy():
    path = settings.base_dir / "data" / "cases" / "blind" / "blind_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    for raw in cases:
        if raw.get("ground_truth_findings"):
            continue
        case = AccountingCaseData(**{k: v for k, v in raw.items() if k != "ground_truth_findings"})
        res = perform_three_way_reconciliation(case)
        assert res["discrepancies"] == [], raw["case_id"]


def test_gmi_neutralized_when_gross_margin_negative():
    res = calculate_beneish_m_score(
        100, 150, 10, 10, 120, 100, 200, 210, 5, 5, 50, 50, 10, 10, 0.5, 0.5, -30, -5, 80, 90,
    )
    assert res["gmi_neutralized"] is True
    assert abs(res["m_score"]) < 50
