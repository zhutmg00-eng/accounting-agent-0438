"""
Tests for Execution Modes, Strict-Online Errors, and Mock Isolation (Issue 3).
"""

import pytest
from src.core.schemas import ExecutionMode, AccountingCaseData
from src.core.llm_adapter import DeepSeekLLMAdapter, DeepSeekAPIError
from src.core.harness import AccountingAgentHarness
from src.benchmark.test_cases import get_benchmark_cases


def test_mock_mode_execution():
    """Verify that MOCK mode executes cleanly without network calls."""
    adapter = DeepSeekLLMAdapter(mode=ExecutionMode.MOCK)
    assert adapter.mode == ExecutionMode.MOCK
    assert adapter.use_mock is True
    
    resp = adapter.chat_completion([{"role": "user", "content": "测试 CASE_2025_001"}])
    assert resp.execution_mode == ExecutionMode.MOCK
    assert "华创数智" in resp.content or "RF-2025-001" in resp.content


def test_strict_online_mode_failure_raises_error():
    """Verify that STRICT_ONLINE mode raises DeepSeekAPIError on invalid API connection."""
    adapter = DeepSeekLLMAdapter(
        api_key="invalid-test-key-12345",
        api_base="https://invalid-api-endpoint.nonexistent",
        mode=ExecutionMode.STRICT_ONLINE
    )
    assert adapter.mode == ExecutionMode.STRICT_ONLINE

    with pytest.raises(DeepSeekAPIError) as exc_info:
        adapter.chat_completion([{"role": "user", "content": "Hello"}])
    
    assert "DeepSeek API" in str(exc_info.value) or "connection failed" in str(exc_info.value)


def test_harness_records_execution_mode():
    """Verify that Harness stamps report with exact execution mode."""
    harness = AccountingAgentHarness(llm_adapter=DeepSeekLLMAdapter(mode=ExecutionMode.MOCK))
    cases = get_benchmark_cases()
    report = harness.run_case(cases[0])
    
    assert report.execution_mode == ExecutionMode.MOCK
    assert report.model_name == "domain-heuristic-engine"
    assert report.fallback_occurred is False
