"""
Tests for FastAPI Backend Server (Issue: Modern Web Frontend Upgrade).
"""

import pytest
from fastapi.testclient import TestClient
from src.api.server import app

client = TestClient(app)


def test_api_health():
    """Verify health check endpoint."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["cases_count"] >= 25
    assert data["categories_count"] >= 5


def test_api_categories():
    """Verify category breakdown endpoint."""
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) >= 5
    assert data["total_cases"] >= 25


def test_api_cases_list():
    """Verify case listing and category filtering."""
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 25
    assert len(data["cases"]) >= 25

    # Filter by category dynamically
    cats_resp = client.get("/api/categories")
    first_cat = cats_resp.json()["categories"][0]["name"]
    resp_filtered = client.get(f"/api/cases?category={first_cat}")
    assert resp_filtered.status_code == 200
    f_data = resp_filtered.json()
    assert f_data["total"] >= 1
    for c in f_data["cases"]:
        assert c["case_category"] == first_cat


def test_api_case_detail():
    """Verify single case retrieval."""
    resp = client.get("/api/cases/REAL_CSRC_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "REAL_CSRC_001"
    assert "康美药业" in data["company_name"]
    assert "〔2020〕24号" in data["penalty_decision_no"]
    assert len(data["vouchers"]) > 0


def test_api_audit_run_mock():
    """Verify running audit analysis on a real case."""
    resp = client.post("/api/audit/run", json={
        "case_id": "REAL_CSRC_001",
        "plugin_id": "audit_fraud_detection",
        "mode": "MOCK"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "REAL_CSRC_001"
    assert data["overall_risk_rating"] in ["HIGH", "CRITICAL"]
    assert len(data["findings"]) > 0
    assert len(data["workpapers"]) > 0


def test_api_tools_reconcile():
    """Verify independent three-way reconciliation endpoint."""
    resp = client.post("/api/tools/reconcile?case_id=REAL_CSRC_001")
    assert resp.status_code == 200
    data = resp.json()
    assert "discrepancies" in data
    assert data["reconciliation_clean"] is False
    assert data["total_abnormal_amount"] > 0


def test_frontend_static_serving():
    """Verify that frontend/dist/index.html is served on root /."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "DeepSeek-AuditMind" in resp.text
