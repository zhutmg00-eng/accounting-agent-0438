"""
Accounting Data File Importer & Field-Level Validator.
Supports Excel (Vouchers / General Ledger), CSV (Invoices, Bank Flows),
and produces validated AccountingCaseData with actionable field-level diagnostics.
"""

from typing import List, Dict, Any, Tuple, Optional
import io
import re
from datetime import datetime
import pandas as pd
from pydantic import BaseModel, Field

from src.core.schemas import (
    AccountingCaseData, AccountingVoucher, JournalEntryLine,
    InvoiceItem, BankFlowRecord, BusinessContract, FinancialStatementsSummary
)


class FileValidationResult(BaseModel):
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    row_count: int = 0
    file_type: str = ""
    summary: str = ""


def _parse_date(date_val: Any) -> Optional[str]:
    """Normalize date to YYYY-MM-DD string."""
    if pd.isna(date_val):
        return None
    if isinstance(date_val, datetime):
        return date_val.strftime("%Y-%m-%d")
    s = str(date_val).strip()
    # Try multiple common date formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Regex fallback for YYYY.MM.DD
    m = re.match(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def _parse_float(val: Any) -> Optional[float]:
    """Parse string/number to float safely."""
    if pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("¥", "").replace("$", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_vouchers_file(file_obj_or_path: Any, filename: str = "凭证表.xlsx") -> Tuple[List[AccountingVoucher], FileValidationResult]:
    """
    Parse Excel or CSV accounting voucher file.
    Required columns:
    - 凭证号 (voucher_id)
    - 记账日期 (voucher_date)
    - 科目编码 (account_code)
    - 科目名称 (account_name)
    - 借方金额 (debit)
    - 贷方金额 (credit)
    Optional: 摘要 (summary), 关联单据号 (associated_doc_id)
    """
    res = FileValidationResult(file_type="记账凭证表")
    vouchers: List[AccountingVoucher] = []

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_obj_or_path, encoding="utf-8-sig")
        else:
            df = pd.read_excel(file_obj_or_path)
    except Exception as e:
        res.is_valid = False
        res.errors.append(f"文件读取失败，请确认文件格式有效: {str(e)}")
        return vouchers, res

    res.row_count = len(df)
    if df.empty:
        res.is_valid = False
        res.errors.append("上传的凭证文件为空表！")
        return vouchers, res

    # Column normalization
    col_mapping = {
        "凭证号": "voucher_id", "凭证编号": "voucher_id", "voucher_id": "voucher_id",
        "记账日期": "voucher_date", "日期": "voucher_date", "voucher_date": "voucher_date",
        "科目编码": "account_code", "科目代码": "account_code", "account_code": "account_code",
        "科目名称": "account_name", "科目": "account_name", "account_name": "account_name",
        "借方金额": "debit", "借方": "debit", "debit": "debit",
        "贷方金额": "credit", "贷方": "credit", "credit": "credit",
        "摘要": "summary", "业务摘要": "summary", "summary": "summary",
        "关联单据号": "associated_doc_id", "关联单据": "associated_doc_id", "associated_doc_id": "associated_doc_id"
    }

    renamed_cols = {}
    for c in df.columns:
        c_clean = str(c).strip()
        if c_clean in col_mapping:
            renamed_cols[c] = col_mapping[c_clean]
    df = df.rename(columns=renamed_cols)

    required_fields = ["voucher_id", "voucher_date", "account_code", "account_name", "debit", "credit"]
    missing_fields = [f for f in required_fields if f not in df.columns]
    if missing_fields:
        res.is_valid = False
        res.errors.append(f"凭证文件缺少必填列: {', '.join(missing_fields)}。请参考标准导入模板。")
        return vouchers, res

    # Group by voucher_id
    grouped = df.groupby("voucher_id")
    for v_id, grp in grouped:
        v_id_str = str(v_id).strip()
        first_row = grp.iloc[0]
        parsed_date = _parse_date(first_row["voucher_date"])
        if not parsed_date:
            res.errors.append(f"凭证 [{v_id_str}] 的记账日期格式错误: '{first_row['voucher_date']}' (支持 YYYY-MM-DD)")
            res.is_valid = False
            continue

        assoc_doc = None
        if "associated_doc_id" in grp.columns and not pd.isna(first_row.get("associated_doc_id")):
            assoc_doc = str(first_row["associated_doc_id"]).strip()

        entries: List[JournalEntryLine] = []
        for idx, row in grp.iterrows():
            row_num = idx + 2  # Excel 1-based header offset
            deb = _parse_float(row["debit"])
            crd = _parse_float(row["credit"])

            if deb is None:
                res.errors.append(f"第 {row_num} 行凭证 [{v_id_str}] 借方金额格式错误: '{row['debit']}'")
                res.is_valid = False
                deb = 0.0
            if crd is None:
                res.errors.append(f"第 {row_num} 行凭证 [{v_id_str}] 贷方金额格式错误: '{row['credit']}'")
                res.is_valid = False
                crd = 0.0

            entries.append(JournalEntryLine(
                account_code=str(row["account_code"]).strip(),
                account_name=str(row["account_name"]).strip(),
                debit=deb,
                credit=crd,
                summary=str(row.get("summary", "")).strip() if not pd.isna(row.get("summary")) else ""
            ))

        vouchers.append(AccountingVoucher(
            voucher_id=v_id_str,
            voucher_date=parsed_date,
            entries=entries,
            associated_doc_id=assoc_doc,
            source_file=filename,
            row_index=int(grp.index[0]) + 2
        ))

    if res.is_valid:
        res.summary = f"成功解析 {len(vouchers)} 张记账凭证，包含 {len(df)} 行会计分录。"
    return vouchers, res


def parse_invoices_file(file_obj_or_path: Any, filename: str = "发票清单.csv") -> Tuple[List[InvoiceItem], FileValidationResult]:
    """
    Parse CSV or Excel invoice list.
    Required columns:
    - 发票号码 (invoice_no)
    - 开票日期 (invoice_date)
    - 购买方 (buyer_name)
    - 销售方 (seller_name)
    - 价税合计 (total_amount)
    Optional: 不含税金额 (amount_without_tax), 税额 (tax_amount), 商品劳务 (goods_or_service)
    """
    res = FileValidationResult(file_type="增值税发票清单")
    invoices: List[InvoiceItem] = []

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_obj_or_path, encoding="utf-8-sig")
        else:
            df = pd.read_excel(file_obj_or_path)
    except Exception as e:
        res.is_valid = False
        res.errors.append(f"发票清单读取失败: {str(e)}")
        return invoices, res

    res.row_count = len(df)
    if df.empty:
        res.is_valid = False
        res.errors.append("上传的发票清单为空表！")
        return invoices, res

    col_mapping = {
        "发票号码": "invoice_no", "发票号": "invoice_no", "invoice_no": "invoice_no",
        "开票日期": "invoice_date", "日期": "invoice_date", "invoice_date": "invoice_date",
        "购买方名称": "buyer_name", "购买方": "buyer_name", "buyer_name": "buyer_name",
        "销售方名称": "seller_name", "销售方": "seller_name", "seller_name": "seller_name",
        "价税合计": "total_amount", "合计金额": "total_amount", "total_amount": "total_amount",
        "不含税金额": "amount_without_tax", "金额": "amount_without_tax", "amount_without_tax": "amount_without_tax",
        "税额": "tax_amount", "tax_amount": "tax_amount",
        "货物或劳务名称": "goods_or_service", "商品名称": "goods_or_service", "品名": "goods_or_service", "goods_or_service": "goods_or_service"
    }

    renamed_cols = {c: col_mapping[str(c).strip()] for c in df.columns if str(c).strip() in col_mapping}
    df = df.rename(columns=renamed_cols)

    required_fields = ["invoice_no", "invoice_date", "buyer_name", "seller_name", "total_amount"]
    missing = [f for f in required_fields if f not in df.columns]
    if missing:
        res.is_valid = False
        res.errors.append(f"发票清单缺少必填列: {', '.join(missing)}")
        return invoices, res

    for idx, row in df.iterrows():
        row_num = idx + 2
        inv_no = str(row["invoice_no"]).strip()
        p_date = _parse_date(row["invoice_date"])
        if not p_date:
            res.errors.append(f"第 {row_num} 行发票 [{inv_no}] 开票日期格式错误: '{row['invoice_date']}'")
            res.is_valid = False
            continue

        tot = _parse_float(row["total_amount"])
        if tot is None or tot <= 0:
            res.errors.append(f"第 {row_num} 行发票 [{inv_no}] 价税合计金额必须为有效正数: '{row['total_amount']}'")
            res.is_valid = False
            continue

        amt_no_tax = _parse_float(row.get("amount_without_tax", tot / 1.13))
        tax = _parse_float(row.get("tax_amount", tot - amt_no_tax))

        invoices.append(InvoiceItem(
            invoice_no=inv_no,
            invoice_date=p_date,
            buyer_name=str(row["buyer_name"]).strip(),
            seller_name=str(row["seller_name"]).strip(),
            amount_without_tax=amt_no_tax or 0.0,
            tax_amount=tax or 0.0,
            total_amount=tot,
            goods_or_service=str(row.get("goods_or_service", "商品或服务")).strip() if not pd.isna(row.get("goods_or_service")) else "商品或服务",
            source_file=filename
        ))

    if res.is_valid:
        res.summary = f"成功解析 {len(invoices)} 份发票明细，价税合计总额 ¥{sum(i.total_amount for i in invoices):,.2f}。"
    return invoices, res


def parse_bank_flows_file(file_obj_or_path: Any, filename: str = "银行流水.csv") -> Tuple[List[BankFlowRecord], FileValidationResult]:
    """
    Parse CSV or Excel bank statement flow records.
    Required columns:
    - 交易流水号 (transaction_id)
    - 交易时间 (transaction_time)
    - 对手方户名 (counterparty_name)
    - 交易金额 (amount) - 正数流入，负数流出
    Optional: 对手方账号, 余额, 附言摘要
    """
    res = FileValidationResult(file_type="银行对账单流水")
    flows: List[BankFlowRecord] = []

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_obj_or_path, encoding="utf-8-sig")
        else:
            df = pd.read_excel(file_obj_or_path)
    except Exception as e:
        res.is_valid = False
        res.errors.append(f"银行流水读取失败: {str(e)}")
        return flows, res

    res.row_count = len(df)
    if df.empty:
        res.is_valid = False
        res.errors.append("上传的银行流水文件为空表！")
        return flows, res

    col_mapping = {
        "交易流水号": "transaction_id", "流水号": "transaction_id", "transaction_id": "transaction_id",
        "交易时间": "transaction_time", "交易日期": "transaction_time", "日期时间": "transaction_time", "transaction_time": "transaction_time",
        "对手方户名": "counterparty_name", "交易对手方": "counterparty_name", "户名": "counterparty_name", "counterparty_name": "counterparty_name",
        "对手方账号": "counterparty_account", "账号": "counterparty_account", "counterparty_account": "counterparty_account",
        "交易金额": "amount", "金额": "amount", "收支金额": "amount", "amount": "amount",
        "交易后余额": "balance_after", "账户余额": "balance_after", "余额": "balance_after", "balance_after": "balance_after",
        "附言": "remark", "摘要": "remark", "用途": "remark", "remark": "remark"
    }

    renamed_cols = {c: col_mapping[str(c).strip()] for c in df.columns if str(c).strip() in col_mapping}
    df = df.rename(columns=renamed_cols)

    required_fields = ["transaction_id", "transaction_time", "counterparty_name", "amount"]
    missing = [f for f in required_fields if f not in df.columns]
    if missing:
        res.is_valid = False
        res.errors.append(f"银行流水缺少必填列: {', '.join(missing)}")
        return flows, res

    for idx, row in df.iterrows():
        row_num = idx + 2
        t_id = str(row["transaction_id"]).strip()
        amt = _parse_float(row["amount"])
        if amt is None:
            res.errors.append(f"第 {row_num} 行流水 [{t_id}] 金额格式错误: '{row['amount']}'")
            res.is_valid = False
            continue

        flows.append(BankFlowRecord(
            transaction_id=t_id,
            transaction_time=str(row["transaction_time"]).strip(),
            counterparty_name=str(row["counterparty_name"]).strip(),
            counterparty_account=str(row.get("counterparty_account", "622***")).strip() if not pd.isna(row.get("counterparty_account")) else "622***",
            amount=amt,
            balance_after=_parse_float(row.get("balance_after", 0.0)) or 0.0,
            remark=str(row.get("remark", "")).strip() if not pd.isna(row.get("remark")) else "",
            source_file=filename
        ))

    if res.is_valid:
        res.summary = f"成功解析 {len(flows)} 笔银行交易流水。"
    return flows, res


def generate_sample_templates(output_dir: Any):
    """Generate Excel and CSV templates for user download."""
    import os
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Voucher Template (Excel)
    voucher_data = [
        {"凭证号": "202512-记-0001", "记账日期": "2025-12-30", "科目编码": "1122", "科目名称": "应收账款-某科技有限公司", "借方金额": 1000000.0, "贷方金额": 0.0, "摘要": "确认系统开发尾款收入", "关联单据号": "INV-20260105-001"},
        {"凭证号": "202512-记-0001", "记账日期": "2025-12-30", "科目编码": "6001", "科目名称": "主营业务收入", "借方金额": 0.0, "贷方金额": 884955.75, "摘要": "确认系统开发尾款收入", "关联单据号": "INV-20260105-001"},
        {"凭证号": "202512-记-0001", "记账日期": "2025-12-30", "科目编码": "2221", "科目名称": "应交税费-应交增值税(销项税额)", "借方金额": 0.0, "贷方金额": 115044.25, "摘要": "销项税额", "关联单据号": "INV-20260105-001"},
    ]
    pd.DataFrame(voucher_data).to_excel(out / "企业记账凭证模板.xlsx", index=False)

    # 2. Invoice Template (CSV)
    invoice_data = [
        {"发票号码": "INV-20260105-001", "开票日期": "2026-01-05", "购买方名称": "某科技有限公司", "销售方名称": "本企业", "不含税金额": 884955.75, "税额": 115044.25, "价税合计": 1000000.0, "货物或劳务名称": "软件开发与技术服务"}
    ]
    pd.DataFrame(invoice_data).to_csv(out / "增值税发票清单模板.csv", index=False, encoding="utf-8-sig")

    # 3. Bank Flow Template (CSV)
    bank_data = [
        {"交易流水号": "BK-20251230-01", "交易时间": "2025-12-30 10:00", "对手方户名": "某科技有限公司", "对手方账号": "622848001", "交易金额": 300000.0, "交易后余额": 5000000.0, "附言": "支付首期款"}
    ]
    pd.DataFrame(bank_data).to_csv(out / "银行对账单明细模板.csv", index=False, encoding="utf-8-sig")
