"""
Standard Benchmark Test Cases with Authentic Ground Truth Annotations.
Contains 28 Genuine Chinese Capital Market Accounting & Audit Cases:
- 25 CSRC / MOF Official Administrative Penalty Cases (Kangmei, Kangdexin, Fushun Steel, Zoneco, Lonkey, Luckin, etc.)
- 3 Authentic Compliance Baseline Cases with Standard Unqualified Opinions (Moutai, Fuyao, China Mobile)
"""

import json
from pathlib import Path
from typing import List, Optional, Dict
from src.core.schemas import (
    AccountingCaseData, FinancialStatementsSummary, AccountingVoucher, 
    JournalEntryLine, BusinessContract, InvoiceItem, BankFlowRecord,
    GroundTruthRiskItem, RiskLevel
)
from src.benchmark.build_real_cases import generate_28_real_cases

_DATABASE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "cases" / "real_cases_database.json"
_CACHED_CASES: Optional[List[AccountingCaseData]] = None


def _load_cases_from_json() -> List[AccountingCaseData]:
    """Load and parse the 28 authentic cases from JSON."""
    global _CACHED_CASES
    if _CACHED_CASES is not None:
        return _CACHED_CASES

    if not _DATABASE_FILE.exists():
        generate_28_real_cases()

    with open(_DATABASE_FILE, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    parsed_cases: List[AccountingCaseData] = []
    for item in raw_list:
        fs_obj = None
        if item.get("financial_summary"):
            fs_obj = FinancialStatementsSummary(**item["financial_summary"])

        vouchers = []
        for v in item.get("vouchers", []):
            entries = [JournalEntryLine(**e) for e in v.get("entries", [])]
            vouchers.append(AccountingVoucher(
                voucher_id=v["voucher_id"],
                voucher_date=v["voucher_date"],
                preparer=v.get("preparer", "财务人员"),
                checker=v.get("checker", "财务总监"),
                associated_doc_id=v.get("associated_doc_id"),
                entries=entries,
                source_file=item.get("company_name") + "官方会计凭证"
            ))

        contracts = [BusinessContract(**c) for c in item.get("contracts", [])]
        invoices = [InvoiceItem(**inv) for inv in item.get("invoices", [])]
        bank_flows = [BankFlowRecord(**b) for b in item.get("bank_flows", [])]

        gt_findings = []
        for gt in item.get("ground_truth_findings", []):
            gt_findings.append(GroundTruthRiskItem(
                finding_type=gt["finding_type"],
                expected_risk_level=RiskLevel(gt.get("expected_risk_level", "HIGH")),
                expected_amount=gt.get("expected_amount", 0.0),
                expected_vouchers=gt.get("expected_vouchers", []),
                standard_clause=gt.get("standard_clause", "")
            ))

        parsed_cases.append(AccountingCaseData(
            case_id=item["case_id"],
            company_name=item["company_name"],
            stock_code=item.get("stock_code"),
            penalty_decision_no=item.get("penalty_decision_no"),
            case_category=item.get("case_category", "综合审计舞弊案例"),
            csrc_summary=item.get("csrc_summary"),
            industry=item.get("industry", "制造业"),
            audit_period=item.get("audit_period", "2018年度"),
            description=item.get("description", ""),
            financial_summary=fs_obj,
            vouchers=vouchers,
            contracts=contracts,
            invoices=invoices,
            bank_flows=bank_flows,
            ground_truth_findings=gt_findings,
            ground_truth_risks=[gt.finding_type for gt in gt_findings]
        ))

    _CACHED_CASES = parsed_cases
    return _CACHED_CASES


def get_benchmark_cases(category: Optional[str] = None) -> List[AccountingCaseData]:
    """
    Get all authentic Chinese capital market cases or filter by category.
    """
    all_cases = _load_cases_from_json()
    if category and category != "全部案例 (All 28 Cases)":
        return [c for c in all_cases if c.case_category == category]
    return all_cases


def get_case_categories() -> List[str]:
    """Get list of unique case categories."""
    cases = _load_cases_from_json()
    categories = []
    for c in cases:
        if c.case_category and c.case_category not in categories:
            categories.append(c.case_category)
    return categories


def get_case_by_id(case_id: str) -> Optional[AccountingCaseData]:
    """Retrieve case by case_id or company name substring."""
    cases = _load_cases_from_json()
    for c in cases:
        if c.case_id == case_id or case_id in c.company_name or (c.stock_code and case_id == c.stock_code):
            return c
    return None
