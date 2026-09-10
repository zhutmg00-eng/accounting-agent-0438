"""
Global Configuration for DeepSeek Accounting Agent Harness.
Supports DeepSeek-V3 / DeepSeek-R1 API, domestic OpenAI-compatible endpoints, and offline mock mode.
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "cases"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    # LLM Settings
    api_key: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "mock-key"))
    api_base: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"))
    model_name: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    reasoner_model_name: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("TEMPERATURE", "0.1")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "4096")))
    
    # Execution & Harness Settings
    use_mock_llm: bool = Field(default_factory=lambda: os.getenv("USE_MOCK_LLM", "true").lower() in ("true", "1", "yes"))
    timeout_seconds: int = 60
    max_retries: int = 3
    
    # Competition Meta
    competition_name: str = "2026年北京市大学生数智会计创新应用竞赛"
    project_name: str = "DeepSeek-AuditMind: 数智业财融合与舞弊穿透智能体基座"
    version: str = "1.0.0"

    # Paths
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    output_dir: Path = OUTPUT_DIR


settings = Settings()
