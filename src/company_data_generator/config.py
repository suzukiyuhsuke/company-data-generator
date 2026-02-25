"""設定管理"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def _find_project_root() -> Path:
    """プロジェクトルートを探索する"""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


class Config(BaseModel):
    """アプリケーション設定"""

    azure_endpoint: str = Field(description="Azure AI Foundry エンドポイントURL")
    temperature: float = Field(default=0.7, description="LLM生成のtemperature")
    max_tokens: int = Field(default=4096, description="1リクエストあたりの最大トークン数")
    max_concurrency: int = Field(default=5, description="Phase3 ドキュメント生成の最大並列数")
    prompts_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "prompts",
        description="プロンプトテンプレートディレクトリ",
    )

    @classmethod
    def from_env(cls) -> Config:
        """環境変数または .env ファイルから設定を読み込む"""
        load_dotenv(PROJECT_ROOT / ".env")

        return cls(
            azure_endpoint=os.environ.get("AZURE_AI_ENDPOINT", ""),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "4096")),
            max_concurrency=int(os.environ.get("LLM_MAX_CONCURRENCY", "5")),
        )
