"""
Base Plugin Interface for Accounting & Auditing Domain Agents.
Implements the "Everything is a Plugin" (一切皆插件) paradigm.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from src.core.schemas import AccountingCaseData, AnalysisReportResult, RiskFinding, AuditWorkpaper, RiskLevel


class BaseAccountingPlugin(ABC):
    """
    Abstract Base Class for Accounting Agents Plugins.
    Each plugin encapsulates:
    1. Domain Knowledge & Prompts (CAS / IFRS / CSA Rules)
    2. Algorithmic Tools (Beneish M-Score, 3-Way Reconciliation, Ratio Calculators)
    3. Structural Post-Processing & Deterministic Verification Guards
    """
    
    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique ID of the plugin, e.g., 'audit_fraud_detection'"""
        pass

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Display name of the plugin, e.g., '数智审计与舞弊穿透智能体插件'"""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Category: 'Audit' | 'ManagementAccounting' | 'TaxCompliance' | 'CostAccounting'"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of plugin capabilities"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """System prompt defining the persona, standards, and strict JSON output schema."""
        pass

    @abstractmethod
    def execute_tools(self, case: AccountingCaseData) -> Dict[str, Any]:
        """
        Deterministic algorithmic computation (Tool Calling layer).
        Computes financial ratios, Beneish M-Score, 3-way discrepancies without LLM hallucinations.
        """
        pass

    @abstractmethod
    def build_user_prompt(self, case: AccountingCaseData, tool_results: Dict[str, Any]) -> str:
        """Build user prompt combining raw case data and calculated tool outputs."""
        pass

    @abstractmethod
    def parse_and_verify(
        self,
        raw_json: Dict[str, Any],
        tool_results: Dict[str, Any],
        case: AccountingCaseData
    ) -> AnalysisReportResult:
        """
        Verify and reconcile LLM reasoning against deterministic tool results.
        Ensures 100% mathematical integrity and strict schema compliance.
        """
        pass
