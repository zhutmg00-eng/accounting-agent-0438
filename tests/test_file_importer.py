"""
Tests for Excel/CSV File Importer and Field-Level Validation (Issue 2).
"""

from pathlib import Path
import pytest
from src.data_loader.file_importer import (
    parse_vouchers_file, parse_invoices_file, parse_bank_flows_file,
    generate_sample_templates
)


@pytest.fixture(scope="module")
def sample_templates():
    tmp_dir = Path("data/templates")
    generate_sample_templates(tmp_dir)
    return tmp_dir


def test_parse_vouchers_excel(sample_templates):
    """Test reading standard vouchers Excel template."""
    v_path = sample_templates / "企业记账凭证模板.xlsx"
    vouchers, res = parse_vouchers_file(v_path, filename=v_path.name)
    
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert len(vouchers) >= 1
    assert vouchers[0].voucher_id == "202512-记-0001"
    assert len(vouchers[0].entries) == 3


def test_parse_invoices_csv(sample_templates):
    """Test reading standard invoices CSV template."""
    i_path = sample_templates / "增值税发票清单模板.csv"
    invoices, res = parse_invoices_file(i_path, filename=i_path.name)
    
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert len(invoices) >= 1
    assert invoices[0].invoice_no == "INV-20260105-001"
    assert invoices[0].total_amount == 1000000.0


def test_parse_bank_flows_csv(sample_templates):
    """Test reading standard bank statement CSV template."""
    b_path = sample_templates / "银行对账单明细模板.csv"
    flows, res = parse_bank_flows_file(b_path, filename=b_path.name)
    
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert len(flows) >= 1
    assert flows[0].transaction_id == "BK-20251230-01"
    assert flows[0].amount == 300000.0


def test_validation_missing_required_columns(tmp_path):
    """Test field-level validation errors when required columns are absent."""
    import pandas as pd
    bad_df = pd.DataFrame([{"备注": "测试数据"}])
    bad_file = tmp_path / "bad_voucher.xlsx"
    bad_df.to_excel(bad_file, index=False)

    vouchers, res = parse_vouchers_file(bad_file, filename="bad_voucher.xlsx")
    assert res.is_valid is False
    assert any("缺少必填列" in err for err in res.errors)
