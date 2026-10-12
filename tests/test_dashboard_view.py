"""
Tests for Data Anomaly Dashboard (dashboard_view.py).
Ensures robustness, lack of attribute crashes, and consistency between
3-way reconciliation, DeepSeek audit findings, and dashboard KPIs.
"""

import pytest
from src.benchmark.test_cases import get_benchmark_cases
from src.core.harness import AccountingAgentHarness
from src.ui.dashboard_view import calculate_case_diagnostics
from src.core.schemas import (
    AccountingCaseData, AccountingVoucher, BusinessContract,
    InvoiceItem, BankFlowRecord, RiskLevel, AnalysisReportResult, RiskFinding
)


def test_dashboard_diagnostics_all_benchmark_cases():
    """Verify diagnostics for all 28 benchmark cases without crashes or contradictions."""
    cases = get_benchmark_cases()
    assert len(cases) == 28

    for c in cases:
        diag = calculate_case_diagnostics(c)
        assert "health_score" in diag
        assert "total_audited" in diag
        assert "total_abnormal" in diag
        assert "anomaly_items" in diag

        if "CLEAN" in c.case_id:
            assert diag["health_score"] == 100, f"{c.case_id} clean case should have 100 health score"
            assert len(diag["anomaly_items"]) == 0, f"{c.case_id} clean case should have 0 anomalies"
        else:
            assert diag["health_score"] < 50, f"{c.case_id} fraud case should have health score < 50"
            assert len(diag["anomaly_items"]) > 0, f"{c.case_id} fraud case should have at least 1 anomaly"


def test_dashboard_diagnostics_with_report():
    """Verify diagnostics synchronize with audit report findings and risk ratings."""
    harness = AccountingAgentHarness()
    cases = get_benchmark_cases()
    fraud_case = cases[0]  # Kangmei
    clean_case = cases[25] # Clean

    # Run fraud case
    fraud_report = harness.run_case(fraud_case, plugin_id="audit_fraud_detection")
    fraud_diag = calculate_case_diagnostics(fraud_case, fraud_report)
    assert fraud_diag["health_score"] <= 35
    assert len(fraud_diag["anomaly_items"]) >= 1

    # Run clean case
    clean_report = harness.run_case(clean_case, plugin_id="audit_fraud_detection")
    clean_diag = calculate_case_diagnostics(clean_case, clean_report)
    assert clean_diag["health_score"] == 100
    assert len(clean_diag["anomaly_items"]) == 0


def test_dashboard_contract_and_bank_attributes():
    """Ensure no crashes on contract total_amount or bank flow transaction_time."""
    c = AccountingCaseData(
        case_id="TEST_ATTR",
        company_name="测试企业",
        description="测试属性兼容性",
        audit_period="2025年度",
        contracts=[
            BusinessContract(
                contract_id="CT-01",
                customer_or_vendor="关联方甲",
                sign_date="2025-01-01",
                total_amount=5000000.0,
                payment_terms="预付全款",
                delivery_condition="无",
                is_related_party=True
            )
        ],
        bank_flows=[
            BankFlowRecord(
                transaction_id="BK-01",
                transaction_time="2025-01-02 10:00",
                counterparty_name="关联方甲",
                counterparty_account="622200001",
                amount=-5000000.0,
                balance_after=100000.0,
                remark="退款原路退回"
            )
        ],
        vouchers=[
            AccountingVoucher(
                voucher_id="V-01",
                voucher_date="2025-01-01",
                associated_doc_id="CT-01",
                entries=[]
            )
        ]
    )
    diag = calculate_case_diagnostics(c)
    assert len(diag["anomaly_items"]) >= 1
    assert diag["health_score"] < 100
