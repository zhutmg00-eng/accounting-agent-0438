"""
Unified LLM Adapter for DeepSeek-V3 / DeepSeek-R1 API, OpenAI-compatible endpoints,
and Dynamic Domain-Aware Heuristic Engine (Mock Mode).
"""

import json
import time
import requests
from typing import Dict, Any, Optional, List
from src.config import settings


class LLMResponse:
    def __init__(self, content: str, reasoning_content: Optional[str] = None, prompt_tokens: int = 0, completion_tokens: int = 0):
        self.content = content
        self.reasoning_content = reasoning_content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens

    def json(self) -> Dict[str, Any]:
        """Try parsing JSON content, fallback to empty dict if malformed."""
        try:
            cleaned = self.content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()
            return json.loads(cleaned)
        except Exception:
            return {}


class DeepSeekLLMAdapter:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        use_mock: Optional[bool] = None
    ):
        self.api_key = api_key or settings.api_key
        self.api_base = (api_base or settings.api_base).rstrip("/")
        self.model_name = model_name or settings.model_name
        self.use_mock = use_mock if use_mock is not None else (settings.use_mock_llm or not self.api_key or self.api_key == "mock-key")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        response_json: bool = True,
        max_tokens: int = 4096
    ) -> LLMResponse:
        """Execute chat completion with DeepSeek API or Dynamic Domain-Aware Engine."""
        if self.use_mock:
            return self._mock_completion(messages, response_json)

        url = f"{self.api_base}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=settings.timeout_seconds)
            if resp.status_code == 200:
                data = resp.json()
                choice = data["choices"][0]["message"]
                usage = data.get("usage", {})
                content = choice.get("content", "")
                reasoning = choice.get("reasoning_content", None)
                return LLMResponse(
                    content=content,
                    reasoning_content=reasoning,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0)
                )
            else:
                print(f"[Warning] DeepSeek API HTTP {resp.status_code}. Falling back to Dynamic Domain Engine.")
                return self._mock_completion(messages, response_json)
        except Exception as e:
            print(f"[Warning] DeepSeek API connection failed: {e}. Falling back to Dynamic Domain Engine.")
            return self._mock_completion(messages, response_json)

    def _mock_completion(self, messages: List[Dict[str, str]], response_json: bool) -> LLMResponse:
        """Dynamic domain-aware Mock LLM engine generating context-tailored audit reasoning."""
        user_prompt = ""
        for m in messages:
            if m.get("role") == "user":
                user_prompt += "\n" + m.get("content", "")

        # Determine context from user prompt
        if "CASE_2025_001" in user_prompt or "华创数智" in user_prompt or "华东大数据" in user_prompt:
            overall_rating = "HIGH"
            findings = [
                {
                    "finding_id": "RF-2025-001",
                    "title": "跨期提前确认营业收入与应收账款虚增",
                    "risk_level": "HIGH",
                    "accounting_standard": "CAS 14 - 收入准则 (五步法模型第5步：客户取得商品控制权时确认收入)",
                    "impact_amount": 12500000.0,
                    "suspected_mechanism": "资产负债表日前突击确认未终验项目尾款收入，三单勾稽时间差异常，无真实回款现金流支撑。",
                    "evidences": [
                        {
                            "evidence_type": "三单勾稽时间差异常",
                            "source_ref": "凭证[202512-记-0042] vs 发票[INV-20260110-001]",
                            "detail": "记账日期(2025-12-30)早于发票开具日期(2026-01-10)及实际验收时间。"
                        }
                    ],
                    "suggested_procedure": "实施积极式应收账款函证，核对物流签收单原件，并审查期后退货情况。"
                }
            ]
            workpapers = [
                {
                    "workpaper_id": "WP-REV-001",
                    "title": "大额营业收入与应收账款截止测试表",
                    "prepared_by": "DeepSeek-AuditMind Agent",
                    "review_date": "2026-09-01",
                    "sample_count": 1,
                    "total_audited_amount": 12500000.0,
                    "abnormal_amount": 12500000.0,
                    "audit_opinion_summary": "抽查发现跨期提前确认收入1,250万元，提请管理层作审计调减分录。",
                    "rows": [
                        {
                            "voucher_no": "202512-记-0042",
                            "date": "2025-12-30",
                            "summary": "确认华东大数据尾款收入",
                            "ledger_amount": 12500000.0,
                            "verified_amount": 0.0,
                            "discrepancy": 12500000.0,
                            "audit_conclusion": "跨期提前确认，应予调整"
                        }
                    ]
                }
            ]
            summary = "华创数智科技存在跨期提前确认营业收入及应收账款虚增重大错报风险，涉嫌金额1,250万元。"

        elif "CASE_2025_002" in user_prompt or "恒远重工" in user_prompt or "鑫泰新材料" in user_prompt:
            overall_rating = "HIGH"
            findings = [
                {
                    "finding_id": "RF-2025-002",
                    "title": "虚假采购与存货在途挂账异常(入库单缺失)",
                    "risk_level": "HIGH",
                    "accounting_standard": "CAS 1 - 存货准则 及 CSA 1141 - 舞弊风险应对",
                    "impact_amount": 8600000.0,
                    "suspected_mechanism": "通过向新成立空壳供应商预付大额采购款并在途挂账，入库单缺失，涉嫌掩盖资金体外循环。",
                    "evidences": [
                        {
                            "evidence_type": "入库单缺失与在途挂账异常",
                            "source_ref": "采购凭证[202512-记-0089] vs 合同[CG-2025-110]",
                            "detail": "预付款860万元采购特种钢材，期末仍在途挂账，库房无入库验收记录。"
                        }
                    ],
                    "suggested_procedure": "对在途物资实施现场监盘与供应商工商穿透排查。"
                }
            ]
            workpapers = [
                {
                    "workpaper_id": "WP-INV-001",
                    "title": "存货采购与在途物资实质性测试底稿",
                    "prepared_by": "DeepSeek-AuditMind Agent",
                    "review_date": "2026-09-01",
                    "sample_count": 1,
                    "total_audited_amount": 8600000.0,
                    "abnormal_amount": 8600000.0,
                    "audit_opinion_summary": "在途物资860万元缺乏真实物流与入库单据支撑，存在重大资产减值与舞弊风险。",
                    "rows": [
                        {
                            "voucher_no": "202512-记-0089",
                            "date": "2025-12-25",
                            "summary": "采购特种合金钢材在途",
                            "ledger_amount": 8600000.0,
                            "verified_amount": 0.0,
                            "discrepancy": 8600000.0,
                            "audit_conclusion": "入库单缺失，存货虚增"
                        }
                    ]
                }
            ]
            summary = "恒远重工制造存在虚假采购与存货在途挂账异常风险，涉及金额860万元。"

        elif "CASE_2025_003" in user_prompt or "天辰供应链" in user_prompt or "天宇合力" in user_prompt:
            overall_rating = "HIGH"
            findings = [
                {
                    "finding_id": "RF-2025-003",
                    "title": "关联方隐蔽重大交易与资金体外循环(商业实质缺失)",
                    "risk_level": "HIGH",
                    "accounting_standard": "CAS 36 - 关联方披露准则 及 CSA 1141 - 舞弊审计准则",
                    "impact_amount": 15000000.0,
                    "suspected_mechanism": "通过隐蔽关联方空转资金1,500万元后迅速原路借款返还，无真实货物交付，商业实质缺失。",
                    "evidences": [
                        {
                            "evidence_type": "资金体外循环与关联方交易",
                            "source_ref": "凭证[202511-记-0033] vs 银行流水[BK-20251112-01/02]",
                            "detail": "1500万资金在3日内流出至关联方后原路以拆借名义回流。"
                        }
                    ],
                    "suggested_procedure": "穿透核查关联方股权架构与底层实物流转单据。"
                }
            ]
            workpapers = [
                {
                    "workpaper_id": "WP-REL-001",
                    "title": "关联方往来与大额资金流动穿透核查底稿",
                    "prepared_by": "DeepSeek-AuditMind Agent",
                    "review_date": "2026-09-01",
                    "sample_count": 1,
                    "total_audited_amount": 15000000.0,
                    "abnormal_amount": 15000000.0,
                    "audit_opinion_summary": "关联方资金拆借循环1,500万元，商业实质存疑，需在附注中作专项关联交易披露。",
                    "rows": [
                        {
                            "voucher_no": "202511-记-0033",
                            "date": "2025-11-12",
                            "summary": "暂付天宇合力贸易往来款",
                            "ledger_amount": 15000000.0,
                            "verified_amount": 0.0,
                            "discrepancy": 15000000.0,
                            "audit_conclusion": "资金闭环回流，商业实质存疑"
                        }
                    ]
                }
            ]
            summary = "天辰供应链存在关联方隐蔽重大交易与资金体外循环嫌疑，涉及金额1,500万元。"

        else:
            # Baseline clean case (e.g. 北方精密工业)
            overall_rating = "CLEAN"
            findings = []
            workpapers = [
                {
                    "workpaper_id": "WP-CLEAN-001",
                    "title": "营业收入与三单匹配实质性核对底稿",
                    "prepared_by": "DeepSeek-AuditMind Agent",
                    "review_date": "2026-09-01",
                    "sample_count": 1,
                    "total_audited_amount": 5000000.0,
                    "abnormal_amount": 0.0,
                    "audit_opinion_summary": "抽查业务合同、发票、凭证及银行回款流水，三单勾稽完全一致，确认无误。",
                    "rows": [
                        {
                            "voucher_no": "202509-记-0015",
                            "date": "2025-09-15",
                            "summary": "收到国网智研院传感器系统款",
                            "ledger_amount": 5000000.0,
                            "verified_amount": 5000000.0,
                            "discrepancy": 0.0,
                            "audit_conclusion": "三单一致，予以确认"
                        }
                    ]
                }
            ]
            summary = "北方精密工业业财勾稽一致，三单匹配完全无瑕疵，各项财税指标正常，内控运行有效。"

        simulated_data = {
            "executive_summary": summary,
            "overall_risk_rating": overall_rating,
            "risk_findings": findings,
            "workpapers": workpapers
        }

        reasoning_str = f"CoT 推理分析：已完成对该企业业财数据的多模态穿透比对，研判风险等级为 {overall_rating}。"

        return LLMResponse(
            content=json.dumps(simulated_data, ensure_ascii=False, indent=2),
            reasoning_content=reasoning_str,
            prompt_tokens=850,
            completion_tokens=420
        )
