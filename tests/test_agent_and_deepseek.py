"""
Tests for DeepSeek model auto-detection and Agent Workbench endpoints (Issue #9).
"""
import pytest
from fastapi.testclient import TestClient
from src.api.server import app
from src.core.llm_adapter import detect_deepseek_models, MODEL_PROFILES


@pytest.fixture
def client():
    return TestClient(app)


def test_model_detection_mock_mode():
    """Verify detect_deepseek_models returns valid 2026 profiles in mock mode."""
    res = detect_deepseek_models(api_key="mock-key")
    assert res["status"] == "mock_mode"
    assert res["is_mock"] is True
    assert "deepseek-v4.1-flash" in res["available_models"]
    assert "deepseek-v4-pro" in res["available_models"]
    assert res["active_model_profile"]["is_latest_2026"] is True


def test_api_deepseek_models_endpoint(client):
    """Verify GET /api/deepseek/models returns active model and profiles."""
    resp = client.get("/api/deepseek/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_model" in data
    assert "active_model_profile" in data
    assert len(data["available_models"]) >= 3


def test_api_deepseek_config_endpoint(client):
    """Verify switching active model dynamically."""
    resp = client.post("/api/deepseek/config", json={"model_name": "deepseek-v4-pro"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_model"] == "deepseek-v4-pro"
    assert data["active_model_profile"]["has_thinking_mode"] is True

    # Restore to v4.1-flash
    resp2 = client.post("/api/deepseek/config", json={"model_name": "deepseek-v4.1-flash"})
    assert resp2.status_code == 200
    assert resp2.json()["active_model"] == "deepseek-v4.1-flash"


def test_agent_chat_endpoint_with_tools(client):
    """Verify POST /api/agent/chat executes domain tools and returns audit response."""
    resp = client.post("/api/agent/chat", json={
        "case_id": "REAL_CSRC_001",
        "messages": [
            {"role": "user", "content": "请帮我计算本案例的 Beneish M-Score 并执行业财三单勾稽核对。"}
        ],
        "tools_enabled": True,
        "mode": "MOCK"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "assistant"
    assert len(data["tool_calls"]) >= 1
    assert any(tc["tool_name"] == "calculate_beneish_m_score" for tc in data["tool_calls"])
    assert any(tc["tool_name"] == "perform_three_way_reconciliation" for tc in data["tool_calls"])
    assert "Beneish" in data["content"] or "勾稽" in data["content"]


def test_agent_chat_voucher_search_uses_debit_credit_direction(client):
    """Voucher search should derive 借/贷 from amounts, not a missing model field."""
    resp = client.post("/api/agent/chat", json={
        "case_id": "REAL_CSRC_001",
        "messages": [{"role": "user", "content": "请核查本案例的凭证和分录。"}],
        "tools_enabled": True,
        "mode": "MOCK"
    })
    assert resp.status_code == 200
    data = resp.json()
    voucher_tool = next(tc for tc in data["tool_calls"] if tc["tool_name"] == "search_vouchers")
    sample_vouchers = "\n".join(voucher_tool["tool_output"]["sample_vouchers"])
    assert "借 " in sample_vouchers
    assert "贷 " in sample_vouchers


def test_agent_goal_endpoint(client):
    """Verify POST /api/agent/goal autonomously executes multi-step audit workflow."""
    resp = client.post("/api/agent/goal", json={
        "case_id": "REAL_CSRC_001",
        "goal": "自主执行全流程舞弊穿透审计",
        "mode": "MOCK"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["steps"]) == 4
    assert "report" in data
    assert "tool_outputs" in data
    assert data["tool_outputs"]["three_way_reconciliation"]["total_discrepancies_count"] >= 0


def test_agent_stream_endpoint(client):
    """Verify GET /api/agent/stream streams events via SSE."""
    resp = client.get("/api/agent/stream?case_id=REAL_CSRC_001&message=核查凭证与流水&mode=MOCK&tools_enabled=true")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    text = resp.text
    assert "data: " in text
    assert "[DONE]" in text
