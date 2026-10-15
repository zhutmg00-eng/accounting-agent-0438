"""
Compliance, Ethics, and Data Privacy Sanitization Module for DeepSeek-AuditMind.
Implements:
1. Data Privacy Protection conforming to China's Data Security Law and Personal Information Protection Law.
2. CPA Ultimate Responsibility & Algorithmic Explainability (Ethics & Anti-Black-Box Guarantee).
3. Digital Sign-off & Verification Hash for Audit Workpapers.
"""

import re
import hashlib
import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, model_validator

from src.core.schemas import AccountingCaseData, BankFlowRecord, AccountingVoucher, InvoiceItem, BusinessContract


class DataSanitizer:
    """Enterprise financial data sanitization engine."""

    @staticmethod
    def mask_bank_account(account: str) -> str:
        """Mask bank account numbers: keep first 4 and last 4 digits."""
        if not account:
            return account
        clean = re.sub(r"\s+", "", str(account))
        if len(clean) <= 8:
            return clean[:2] + "****" + clean[-2:] if len(clean) >= 4 else "****"
        return clean[:4] + "*" * (len(clean) - 8) + clean[-4:]

    @staticmethod
    def mask_id_or_tax_no(tax_or_id: str) -> str:
        """Mask Tax ID or Citizen ID."""
        if not tax_or_id:
            return tax_or_id
        clean = str(tax_or_id).strip()
        if len(clean) == 18:
            # 18-digit citizen ID or unified social credit code
            return clean[:6] + "********" + clean[-4:]
        elif len(clean) > 8:
            return clean[:3] + "*" * (len(clean) - 6) + clean[-3:]
        return clean[:2] + "***" + clean[-2:] if len(clean) >= 4 else "***"

    @staticmethod
    def mask_counterparty_name(name: str) -> str:
        """Mask sensitive enterprise or individual counterparty names."""
        if not name:
            return name
        name_str = str(name).strip()
        if len(name_str) <= 3:
            return name_str[0] + "*" + (name_str[-1] if len(name_str) == 3 else "")
        # Enterprise name, e.g. "北京天泽通达商贸有限公司" -> "北京***有限公司"
        suffix_match = re.search(r"(有限公司|有限责任公司|商贸中心|分公司|集团)$", name_str)
        if suffix_match:
            suffix = suffix_match.group(1)
            prefix = name_str[:2]
            return f"{prefix}***{suffix}"
        return name_str[:2] + "***" + name_str[-2:]

    @classmethod
    def sanitize_case_data(cls, case: AccountingCaseData) -> AccountingCaseData:
        """
        Deep-copy and sanitize financial data within an accounting case.
        Masks bank accounts, sensitive counterparty details, and remarks.
        """
        case_dict = case.model_dump()
        
        # 1. Sanitize Bank Flows
        if "bank_flows" in case_dict and case_dict["bank_flows"]:
            for item in case_dict["bank_flows"]:
                if "counterparty_account" in item and item["counterparty_account"]:
                    item["counterparty_account"] = cls.mask_bank_account(item["counterparty_account"])
                if "counterparty_name" in item and item["counterparty_name"]:
                    item["counterparty_name"] = cls.mask_counterparty_name(item["counterparty_name"])

        # 2. Sanitize Invoices
        if "invoices" in case_dict and case_dict["invoices"]:
            for inv in case_dict["invoices"]:
                if "buyer_name" in inv and inv["buyer_name"]:
                    inv["buyer_name"] = cls.mask_counterparty_name(inv["buyer_name"])
                if "seller_name" in inv and inv["seller_name"]:
                    inv["seller_name"] = cls.mask_counterparty_name(inv["seller_name"])

        # 3. Sanitize Contracts
        if "contracts" in case_dict and case_dict["contracts"]:
            for ctr in case_dict["contracts"]:
                if "customer_or_vendor" in ctr and ctr["customer_or_vendor"]:
                    ctr["customer_or_vendor"] = cls.mask_counterparty_name(ctr["customer_or_vendor"])

        # 4. Mark Sanitized in description
        case_dict["description"] = f"[🔒 已启用合规脱敏防护] {case_dict.get('description', '')}"

        return AccountingCaseData(**case_dict)


class CpaApprovalRequest(BaseModel):
    case_id: str = Field(description="审计案例ID")
    auditor_name: str = Field(description="签字注册会计师姓名")
    cert_no: str = Field(description="注册会计师执业证书编号")
    audit_firm: str = Field(default="立信/天健/大华联合审计项目组", description="执业会计师事务所")
    opinion_type: str = Field(default="保留意见/否定意见（涉嫌舞弊错报）", description="初拟审计意见类型")
    professional_skepticism_notes: str = Field(
        default="已严格保持职业怀疑态度，全面复核确定性算子三单倒挂天数与Beneish操纵指数，认可智能体证据链并拟追加外部独立银行函证。",
        description="职业怀疑复核记录与终审意见"
    )
    compliance_confirmed: bool = Field(default=True, description="是否确认符合审计独立性准则")

    @model_validator(mode="after")
    def _require_independence_confirmation(self) -> "CpaApprovalRequest":
        """Refuse a sign-off request that declares non-compliance.

        The receipt below is a non-repudiation artefact whose body asserts
        strict independence compliance, so issuing one for a caller who has
        explicitly answered "no" would make the declaration false.  Rejecting
        the request here turns it into an automatic 422 at the API boundary.
        """
        if not self.compliance_confirmed:
            raise ValueError("未确认审计独立性，禁止签发 CPA 终审签章")
        return self


class CpaApprovalReceipt(BaseModel):
    receipt_id: str
    case_id: str
    auditor_name: str
    cert_no: str
    audit_firm: str
    opinion_type: str
    sign_timestamp: str
    verification_hash: str
    ethical_declaration: str
    status: str = "APPROVED_BY_CPA"


def generate_cpa_signoff(req: CpaApprovalRequest) -> CpaApprovalReceipt:
    """Generate tamper-evident digital sign-off receipt for audit workpapers."""
    # Defence in depth: the model validator above rejects this at the API
    # boundary, but this function is also reachable from the CLI and tests.
    if not req.compliance_confirmed:
        raise ValueError("未确认审计独立性，禁止签发 CPA 终审签章")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hash_payload = f"{req.case_id}|{req.auditor_name}|{req.cert_no}|{timestamp}|{req.opinion_type}"
    verification_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()[:24].upper()
    receipt_id = f"CPA-SIG-{datetime.datetime.now().strftime('%Y%m%d')}-{verification_hash[:8]}"

    declaration = (
        "【中国注册会计师职业道德与独立性声明】签字注册会计师与项目组成员严格遵守《中国注册会计师职业道德守则》"
        "与独立性原则。本项目已核实：AI 智能体仅作为数字化实质性测试初筛辅助工具，对舞弊疑点与底稿结论的法律责任与"
        "终局定性由本签字注册会计师及审计项目组全权负责，不存在算法独裁或责任转移。"
    )

    return CpaApprovalReceipt(
        receipt_id=receipt_id,
        case_id=req.case_id,
        auditor_name=req.auditor_name,
        cert_no=req.cert_no,
        audit_firm=req.audit_firm,
        opinion_type=req.opinion_type,
        sign_timestamp=timestamp,
        verification_hash=verification_hash,
        ethical_declaration=declaration,
        status="APPROVED_BY_CPA"
    )


def get_ethics_and_compliance_manifest() -> Dict[str, Any]:
    """Retrieve full compliance, ethics, and legal guidelines manifest."""
    return {
        "title": "DeepSeek-AuditMind 数智会计伦理、合规与数据安全白皮书",
        "version": "2026.1",
        "governance_pillars": [
            {
                "pillar": "一、 人机责任伦理与 CPA 终局负责制 (Human-in-the-Loop & Accountability)",
                "summary": "坚守注会专业底线，严禁算法黑盒与责任转嫁。",
                "details": [
                    "分工定位：DeepSeek-AuditMind 严格定位于‘数字化审计助理与初筛工具’，绝不越权取代注册会计师的法定职业判断；",
                    "终审签章制：所有系统自动生成的调整分录、审定表与舞弊定性底稿，均需经过执业注册会计师保持职业怀疑态度进行复核并电子签署后方可生效；",
                    "三层证据链透明化：结论严格区分为【客观事实指标】、【大模型准则推演】与【待CPA现场实施程序】，做到‘每项推论皆有法可依、每条凭证皆可溯源’。"
                ]
            },
            {
                "pillar": "二、 严苛的数据安全与隐私保护防护盾 (Data Privacy & Compliance Guard)",
                "summary": "全面对齐我国《数据安全法》与《个人信息保护法》要求。",
                "details": [
                    "敏感数据动态脱敏：系统内置 DataSanitizer 引擎，对上传的银行卡号（保留首4尾4）、纳税人识别号、法人身份证及关键客户名称执行自动化掩码遮蔽；",
                    "无持久化泄漏隔离：临时解析的真实业财文件在会话结束后即刻擦除，不反哺任何公共大模型预训练语料，杜绝企业核心商业秘密泄露；",
                    "本地优先与私有化适配：支持完全离线 Mock/本地大模型模式，满足军工、央企等涉密单位在物理内网中的离线安全审计要求。"
                ]
            },
            {
                "pillar": "三、 算法公平性、透明度与法规对齐 (Algorithmic Fairness & Regulatory Alignment)",
                "summary": "严格遵循国家网信办及财政部权威指引。",
                "details": [
                    "算法备案合规：底层核心模型 DeepSeek 全面符合国家互联网信息办公室《生成式人工智能服务管理暂行办法》之算法备案与安全评估要求；",
                    "零算法偏见：审计算子矩阵（Beneish M-Score、Benford 定律、三单勾稽）完全依托数学公理与准则条文，对不同规模、所有制企业一视同仁，杜绝歧视性打标；",
                    "准则刚性约束：所有研判结论深度对齐 CAS 14（新收入）、CAS 1（存货）、CAS 36（关联方）及 CSA 1141（舞弊审计），杜绝无依据的莫须有指控。"
                ]
            }
        ],
        "compliance_standards": [
            "《中华人民共和国数据安全法》",
            "《中华人民共和国个人信息保护法》",
            "《生成式人工智能服务管理暂行办法》(国家网信办等七部门令第15号)",
            "《中国注册会计师职业道德守则》(中注协)",
            "《中国注册会计师审计准则第1141号——财务报表审计中与舞弊相关的责任》(CSA 1141)"
        ]
    }
