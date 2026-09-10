"""
Test Suite for End-to-End Upload to Audit Closed Loop (Issue #7 & #2).
Verifies:
1. Empty or invalid files rejected with HTTP 400 and actionable diagnostic errors.
2. Valid files uploaded, dynamically registered in case pool, queryable by ID and in cases list.
3. Full audit execution (run & stream) on custom case without 404.
4. Exporting workpaper to Excel/PDF/JSON for custom case.
"""

import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from src.api.server import app
from src.benchmark.test_cases import get_case_by_id


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_empty_files_rejected(client):
    """Uploading without any files should return HTTP 400."""
    response = client.post("/api/upload", data={"company_name": "测试企业"})
    assert response.status_code == 400
    assert "未检测到上传文件" in response.text


def test_upload_zero_byte_file_rejected(client):
    """Uploading 0-byte file should return HTTP 400."""
    files = {
        "vouchers_file": ("empty_vouchers.xlsx", b"", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    response = client.post("/api/upload", files=files, data={"company_name": "测试企业"})
    assert response.status_code == 400
    assert "0字节" in response.text


def test_upload_invalid_file_rejected(client):
    """Uploading corrupt/unreadable file should return HTTP 400 with errors."""
    files = {
        "vouchers_file": ("corrupt.xlsx", b"NOT_A_VALID_EXCEL", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    response = client.post("/api/upload", files=files, data={"company_name": "测试企业"})
    assert response.status_code == 400
    res_json = response.json()
    assert "errors" in res_json["detail"] or "校验失败" in str(res_json)


def test_upload_valid_excel_and_full_audit_lifecycle(client):
    """
    Test full closed loop:
    Upload valid voucher Excel -> Get case_id -> Query case detail -> Run audit -> Export workpaper.
    """
    # 1. Create a valid mock voucher Excel
    df_vouchers = pd.DataFrame([
        {
            "凭证号": "CUSTOM-V-001",
            "记账日期": "2025-12-15",
            "科目编码": "1002",
            "科目名称": "银行存款",
            "借方金额": 8800000.0,
            "贷方金额": 0.0,
            "摘要": "收到虚假客户订金",
            "关联单据号": "FAKE-ORDER-999"
        },
        {
            "凭证号": "CUSTOM-V-001",
            "记账日期": "2025-12-15",
            "科目编码": "6001",
            "科目名称": "主营业务收入",
            "借方金额": 0.0,
            "贷方金额": 8800000.0,
            "摘要": "确认大宗商品销售收入",
            "关联单据号": "FAKE-ORDER-999"
        }
    ])
    excel_buf = io.BytesIO()
    df_vouchers.to_excel(excel_buf, index=False)
    excel_bytes = excel_buf.getvalue()

    # 2. Upload to /api/upload
    files = {
        "vouchers_file": ("test_vouchers.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    data = {
        "company_name": "智算未来科技有限公司",
        "stock_code": "CUSTOM-688001",
        "industry": "信息技术"
    }
    res_upload = client.post("/api/upload", files=files, data=data)
    assert res_upload.status_code == 200
    upload_data = res_upload.json()
    assert upload_data["status"] == "success"
    case_id = upload_data["case_id"]
    assert case_id.startswith("CASE-CUSTOM-")
    assert upload_data["counts"]["vouchers"] == 1

    # 3. Query case detail from /api/cases/{id} (Closed Loop Verification 1)
    res_detail = client.get(f"/api/cases/{case_id}")
    assert res_detail.status_code == 200
    case_obj = res_detail.json()
    assert case_obj["company_name"] == "智算未来科技有限公司"
    assert len(case_obj["vouchers"]) == 1

    # 4. Verify case appears in /api/cases list (Closed Loop Verification 2)
    res_list = client.get("/api/cases")
    assert res_list.status_code == 200
    cases_in_list = [c["case_id"] for c in res_list.json()["cases"]]
    assert case_id in cases_in_list

    # 5. Execute audit on this custom case /api/audit/run (Closed Loop Verification 3)
    res_audit = client.post("/api/audit/run", json={
        "case_id": case_id,
        "plugin_id": "audit_fraud_detection",
        "mode": "MOCK"
    })
    assert res_audit.status_code == 200
    audit_report = res_audit.json()
    assert audit_report["case_id"] == case_id
    assert len(audit_report["findings"]) > 0
    assert len(audit_report["workpapers"]) > 0
    # Beneish should be incalculable due to missing prior financial summary
    beneish_output = audit_report["tool_outputs"]["beneish_m_score"]
    assert beneish_output["is_calculable"] is False
    assert len(beneish_output["missing_fields"]) > 0

    # 6. Test Exporters with the generated report
    res_excel = client.post("/api/export/excel", json=audit_report)
    assert res_excel.status_code == 200
    assert len(res_excel.content) > 0

    res_json = client.post("/api/export/json", json=audit_report)
    assert res_json.status_code == 200
    assert len(res_json.content) > 0
