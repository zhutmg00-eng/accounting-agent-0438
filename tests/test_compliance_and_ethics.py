"""
Tests for Ethics, Compliance, and Data Privacy Sanitization Module.
"""

from fastapi.testclient import TestClient
from src.api.server import app
from src.core.compliance import DataSanitizer

client = TestClient(app)


def test_compliance_manifest_endpoint():
    res = client.get("/api/compliance/manifest")
    assert res.status_code == 200
    data = res.json()
    assert "governance_pillars" in data
    assert len(data["governance_pillars"]) >= 3
    assert "《中华人民共和国数据安全法》" in data["compliance_standards"]


def test_cpa_approval_endpoint():
    payload = {
        "case_id": "REAL_CSRC_001",
        "auditor_name": "张宇 (执业CPA)",
        "cert_no": "110000240982",
        "audit_firm": "数智会计联合审计项目组",
        "opinion_type": "保留意见",
        "professional_skepticism_notes": "保持职业怀疑态度，复核证据链完毕。",
        "compliance_confirmed": True
    }
    res = client.post("/api/compliance/cpa-approval", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "APPROVED_BY_CPA"
    assert data["case_id"] == "REAL_CSRC_001"
    assert len(data["verification_hash"]) == 24
    assert "CPA-SIG-" in data["receipt_id"]


def test_sanitize_case_endpoint():
    res = client.post("/api/compliance/sanitize-case/REAL_CSRC_001")
    assert res.status_code == 200
    data = res.json()
    assert data["sanitized"] is True
    assert "[🔒 已启用合规脱敏防护]" in data["data"]["description"]


def test_data_sanitizer_masks():
    masked_acc = DataSanitizer.mask_bank_account("6222020200112233")
    assert masked_acc.startswith("6222")
    assert masked_acc.endswith("2233")
    assert "********" in masked_acc

    masked_name = DataSanitizer.mask_counterparty_name("北京天泽通达商贸有限公司")
    assert masked_name.endswith("有限公司")
    assert "***" in masked_name


def test_system_health_endpoint():
    res = client.get("/api/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["loaded_cases_count"] >= 28
    assert data["compliance_engine"] == "active"
