"""
Standard Benchmark Test Cases with Ground Truth Annotations.
Simulates real-world audit scenarios (Revenue fraud, Ghost inventory, Related-party loop, Clean baseline).
"""

from typing import List
from src.core.schemas import (
    AccountingCaseData, FinancialStatementsSummary, AccountingVoucher, 
    JournalEntryLine, BusinessContract, InvoiceItem, BankFlowRecord
)


def get_benchmark_cases() -> List[AccountingCaseData]:
    # Case 1: Revenue Cutoff Fraud
    case_revenue = AccountingCaseData(
        case_id="CASE_2025_001",
        company_name="华创数智科技股份有限公司",
        industry="软件与信息技术服务业",
        audit_period="2025年度",
        description="华创科技在2025年12月30日突击确认多笔大额系统集成项目收入，但实际客户终验报告签署于2026年1月，涉嫌通过跨期调节收入以达成对赌业绩目标。",
        ground_truth_risks=["跨期提前确认营业收入", "三单勾稽时间差异常", "应收账款虚增"],
        financial_summary=FinancialStatementsSummary(
            period="2025年度",
            revenue=120000000.0,
            cost_of_sales=70000000.0,
            gross_margin=0.4167,
            net_profit=18000000.0,
            accounts_receivable=65000000.0,
            inventory=15000000.0,
            total_assets=220000000.0,
            operating_cash_flow=-5000000.0
        ),
        contracts=[
            BusinessContract(
                contract_id="HT-2025-089",
                customer_or_vendor="华东大数据中心",
                sign_date="2025-06-15",
                total_amount=12500000.0,
                payment_terms="合同生效付30%，终验合格付65%，质保金5%",
                delivery_condition="以双方签署的《最终验收与控制权转移报告》为准",
                is_related_party=False
            )
        ],
        invoices=[
            InvoiceItem(
                invoice_no="INV-20260110-001",
                invoice_date="2026-01-10",
                buyer_name="华东大数据中心",
                seller_name="华创数智科技股份有限公司",
                amount_without_tax=11061946.90,
                tax_amount=1438053.10,
                total_amount=12500000.0,
                goods_or_service="大数据分析平台集成服务"
            )
        ],
        bank_flows=[
            BankFlowRecord(
                transaction_id="BK-20250620-01",
                transaction_time="2025-06-20 10:30",
                counterparty_name="华东大数据中心",
                counterparty_account="6222***001",
                amount=3750000.0,
                balance_after=25000000.0,
                remark="HT-2025-089首期项目款"
            )
        ],
        vouchers=[
            AccountingVoucher(
                voucher_id="202512-记-0042",
                voucher_date="2025-12-30",
                preparer="王财务",
                checker="赵主管",
                associated_doc_id="INV-20260110-001",
                entries=[
                    JournalEntryLine(account_code="1122", account_name="应收账款-华东大数据", debit=12500000.0, credit=0.0, summary="确认华东大数据集成项目尾款收入"),
                    JournalEntryLine(account_code="6001", account_name="主营业务收入", debit=0.0, credit=11061946.90, summary="确认华东大数据集成项目尾款收入"),
                    JournalEntryLine(account_code="2221", account_name="应交税费-应交增值税(销项税额)", debit=0.0, credit=1438053.10, summary="销项税额")
                ]
            )
        ]
    )

    # Case 2: Ghost Inventory & Fictitious Procurement
    case_inventory = AccountingCaseData(
        case_id="CASE_2025_002",
        company_name="恒远重工制造有限公司",
        industry="通用设备制造业",
        audit_period="2025年度",
        description="恒远重工年末大额采购特种钢材并在途挂账860万元，供应商为新成立空壳企业，库房无入库记录与物流记录。",
        ground_truth_risks=["虚假采购", "存货在途挂账异常", "入库单缺失"],
        financial_summary=FinancialStatementsSummary(
            period="2025年度",
            revenue=85000000.0,
            cost_of_sales=62000000.0,
            gross_margin=0.2705,
            net_profit=3200000.0,
            accounts_receivable=25000000.0,
            inventory=42000000.0,
            total_assets=150000000.0,
            operating_cash_flow=1200000.0
        ),
        contracts=[
            BusinessContract(
                contract_id="CG-2025-110",
                customer_or_vendor="鑫泰新材料商贸（成立2个月）",
                sign_date="2025-12-01",
                total_amount=8600000.0,
                payment_terms="预付100%全款发货",
                delivery_condition="厂区车板交货",
                is_related_party=False
            )
        ],
        invoices=[
            InvoiceItem(
                invoice_no="INV-20251220-888",
                invoice_date="2025-12-20",
                buyer_name="恒远重工制造有限公司",
                seller_name="鑫泰新材料商贸",
                amount_without_tax=7610619.47,
                tax_amount=989380.53,
                total_amount=8600000.0,
                goods_or_service="特种合金钢材"
            )
        ],
        bank_flows=[
            BankFlowRecord(
                transaction_id="BK-20251210-99",
                transaction_time="2025-12-10 14:20",
                counterparty_name="鑫泰新材料商贸",
                counterparty_account="6217***888",
                amount=-8600000.0,
                balance_after=4500000.0,
                remark="支付特种合金钢材采购预付款"
            )
        ],
        vouchers=[
            AccountingVoucher(
                voucher_id="202512-记-0089",
                voucher_date="2025-12-25",
                preparer="孙会计",
                checker="周主管",
                associated_doc_id="INV-20251220-888",
                entries=[
                    JournalEntryLine(account_code="1401", account_name="在途物资-特种钢材", debit=7610619.47, credit=0.0, summary="采购特种合金钢材"),
                    JournalEntryLine(account_code="2221", account_name="应交税费-应交增值税(进项税额)", debit=989380.53, credit=0.0, summary="进项税额"),
                    JournalEntryLine(account_code="1002", account_name="银行存款", debit=0.0, credit=8600000.0, summary="付鑫泰新材料款")
                ]
            )
        ]
    )

    # Case 3: Related Party Circular Fund Loop
    case_related = AccountingCaseData(
        case_id="CASE_2025_003",
        company_name="天辰供应链科技集团",
        industry="商贸与供应链物流",
        audit_period="2025年度",
        description="天辰供应链通过隐蔽关联方控制的公司进行无实物空转贸易，资金在三日内原路经由关联借款返还，涉嫌虚增贸易规模。",
        ground_truth_risks=["关联方隐蔽重大交易", "资金体外循环", "商业实质缺失"],
        contracts=[
            BusinessContract(
                contract_id="SCM-2025-77",
                customer_or_vendor="天宇合力实业（实控人表弟持股90%）",
                sign_date="2025-11-10",
                total_amount=15000000.0,
                payment_terms="发货前付清",
                delivery_condition="仓单静态转让",
                is_related_party=True
            )
        ],
        bank_flows=[
            BankFlowRecord(
                transaction_id="BK-20251112-01",
                transaction_time="2025-11-12 09:00",
                counterparty_name="天宇合力实业",
                counterparty_account="6228***777",
                amount=-15000000.0,
                balance_after=8000000.0,
                remark="采购仓单货款"
            ),
            BankFlowRecord(
                transaction_id="BK-20251115-02",
                transaction_time="2025-11-15 16:30",
                counterparty_name="天宇合力实业",
                counterparty_account="6228***777",
                amount=15000000.0,
                balance_after=23000000.0,
                remark="退款/短期资金拆借还款"
            )
        ],
        vouchers=[
            AccountingVoucher(
                voucher_id="202511-记-0033",
                voucher_date="2025-11-12",
                associated_doc_id="SCM-2025-77",
                entries=[
                    JournalEntryLine(account_code="1221", account_name="其他应收款-天宇合力", debit=15000000.0, credit=0.0, summary="暂付贸易往来款"),
                    JournalEntryLine(account_code="1002", account_name="银行存款", debit=0.0, credit=15000000.0, summary="电汇天宇合力")
                ]
            )
        ]
    )

    # Case 4: Clean Baseline Company
    case_clean = AccountingCaseData(
        case_id="CASE_2025_004",
        company_name="北方精密工业股份有限公司",
        industry="高端精密仪器制造",
        audit_period="2025年度",
        description="北方精密工业内控完善，三单勾稽一致，收入严格按照完工验收确认，银行流水充沛真实，属于合规企业基准对照组。",
        ground_truth_risks=[],
        financial_summary=FinancialStatementsSummary(
            period="2025年度",
            revenue=98000000.0,
            cost_of_sales=55000000.0,
            gross_margin=0.4388,
            net_profit=16500000.0,
            accounts_receivable=18000000.0,
            inventory=12000000.0,
            total_assets=180000000.0,
            operating_cash_flow=19000000.0
        ),
        contracts=[
            BusinessContract(
                contract_id="BF-2025-001",
                customer_or_vendor="国家电网智能电网研究院",
                sign_date="2025-03-10",
                total_amount=5000000.0,
                payment_terms="终验后电汇",
                delivery_condition="客户现场验收合格签署签收单",
                is_related_party=False
            )
        ],
        invoices=[
            InvoiceItem(
                invoice_no="INV-20250915-001",
                invoice_date="2025-09-15",
                buyer_name="国家电网智能电网研究院",
                seller_name="北方精密工业股份有限公司",
                amount_without_tax=4424778.76,
                tax_amount=575221.24,
                total_amount=5000000.0,
                goods_or_service="精密测量传感器系统"
            )
        ],
        bank_flows=[
            BankFlowRecord(
                transaction_id="BK-20250920-01",
                transaction_time="2025-09-20 11:00",
                counterparty_name="国家电网智能电网研究院",
                counterparty_account="6225***999",
                amount=5000000.0,
                balance_after=35000000.0,
                remark="支付BF-2025-001项目全款"
            )
        ],
        vouchers=[
            AccountingVoucher(
                voucher_id="202509-记-0015",
                voucher_date="2025-09-15",
                associated_doc_id="INV-20250915-001",
                entries=[
                    JournalEntryLine(account_code="1002", account_name="银行存款", debit=5000000.0, credit=0.0, summary="收到国网智研院传感器系统款"),
                    JournalEntryLine(account_code="6001", account_name="主营业务收入", debit=0.0, credit=4424778.76, summary="传感器系统销售收入"),
                    JournalEntryLine(account_code="2221", account_name="应交税费-应交增值税(销项税额)", debit=0.0, credit=575221.24, summary="销项税额")
                ]
            )
        ]
    )

    return [case_revenue, case_inventory, case_related, case_clean]
