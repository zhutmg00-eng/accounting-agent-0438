"""
Test Suite for Benchmark Ground Truth Isolation & Fact Mutation (Issue #7 & #4).
Verifies:
1. _mock_completion does NOT read ground_truth_findings.
2. Mutating voucher transaction amounts produces matching mutated impact_amount dynamically.
3. Mutating voucher IDs and descriptions updates evidences and workpapers dynamically.
"""

import copy
import pytest
from src.core.harness import AccountingAgentHarness
from src.core.llm_adapter import DeepSeekLLMAdapter
from src.core.schemas import ExecutionMode, AccountingVoucher, JournalEntryLine
from src.benchmark.test_cases import get_benchmark_cases


def test_fact_amount_mutation_dynamically_reflected():
    """
    Test that modifying voucher amount from standard CSRC value to a custom amount
    causes the agent's findings impact_amount to change in lockstep, proving
    it derives output strictly from prompt facts rather than reading ground truth.
    """
    cases = get_benchmark_cases()
    base_case = cases[1]  # 康得新 (standard expected amount: 12,210,000,000.0)
    
    # Mutate the case voucher amount to a unique test value
    mutated_case = copy.deepcopy(base_case)
    mutated_amount = 7654321.0
    mutated_case.vouchers = [
        AccountingVoucher(
            voucher_id="MUTATED-VOUCHER-001",
            voucher_date="2025-12-31",
            preparer="测试出纳",
            associated_doc_id="MUTATED-DOC-99",
            entries=[
                JournalEntryLine(
                    account_code="1002",
                    account_name="银行存款-特定账户",
                    debit=mutated_amount,
                    credit=0.0,
                    summary="变异测试发生额"
                ),
                JournalEntryLine(
                    account_code="6001",
                    account_name="主营业务收入",
                    debit=0.0,
                    credit=mutated_amount,
                    summary="变异测试收入"
                )
            ]
        )
    ]
    # Remove any bank flows to keep it purely dependent on the voucher
    mutated_case.bank_flows = []

    harness = AccountingAgentHarness(llm_adapter=DeepSeekLLMAdapter(mode=ExecutionMode.MOCK))
    report = harness.run_case(mutated_case, plugin_id="audit_fraud_detection")

    assert len(report.findings) > 0
    # The reported impact amount MUST equal the mutated voucher amount, NOT the ground truth 12.21B!
    assert report.findings[0].impact_amount == mutated_amount
    assert report.findings[0].impact_amount != 12210000000.0

    # Evidence trace must capture the mutated voucher ID
    all_evidence = " ".join([e.source_ref + " " + e.detail for e in report.findings[0].evidences])
    assert "MUTATED-VOUCHER-001" in all_evidence or "MUTATED-VOUCHER-001" in report.findings[0].rule_evidence


def test_no_ground_truth_findings_reference_in_mock_llm():
    """
    Ensure src.core.llm_adapter does not import get_benchmark_cases or touch ground_truth_findings.
    """
    import inspect
    from src.core import llm_adapter
    source = inspect.getsource(llm_adapter)
    assert "ground_truth_findings" not in source
    assert "get_benchmark_cases" not in source
