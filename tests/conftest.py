"""テスト用共通フィクスチャ"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from company_data_generator.config import Config
from company_data_generator.interaction import UserInteraction
from company_data_generator.models import (
    CompanyProfile,
    DocumentPlan,
    DocumentPlanList,
    GeneratedDocument,
)


@pytest.fixture
def sample_company_file(tmp_path: Path) -> Path:
    """サンプル会社情報Markdownファイル"""
    content = """# 株式会社テスト商事

## 基本情報
- 会社名: 株式会社テスト商事
- 業種: 商社
- 設立: 2000年
- 従業員数: 100名
- 本社: 東京都千代田区

## 事業概要
各種商品の輸出入および国内販売を行う総合商社。
"""
    path = tmp_path / "test_company.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def sample_profile() -> CompanyProfile:
    """サンプル会社プロファイル"""
    return CompanyProfile(
        name="株式会社テスト商事",
        industry="商社",
        employee_count=100,
        founded_year=2000,
        headquarters="東京都千代田区",
        business_description="各種商品の輸出入および国内販売を行う総合商社。",
        departments=["営業部", "経理部", "人事部", "総務部"],
        additional_context={"主要取扱商品": "電子部品、化学品"},
    )


@pytest.fixture
def sample_plan() -> DocumentPlan:
    """サンプルドキュメント計画"""
    return DocumentPlan(
        title="情報セキュリティポリシー",
        doc_type="内規",
        summary="全社員が遵守すべき情報セキュリティに関する基本方針を定めたドキュメント。",
        target_audience="全社員",
        includes_diagram=True,
        estimated_length="medium",
    )


@pytest.fixture
def sample_plan_list(sample_plan: DocumentPlan) -> DocumentPlanList:
    """サンプルドキュメント計画リスト"""
    return DocumentPlanList(
        domain="営業",
        plans=[sample_plan],
    )


@pytest.fixture
def sample_generated_document(sample_plan: DocumentPlan) -> GeneratedDocument:
    """サンプル生成ドキュメント"""
    return GeneratedDocument(
        plan=sample_plan,
        content="# 情報セキュリティポリシー\n\n## 1. 目的\n\n...",
        filename="01_内規_情報セキュリティポリシー.md",
    )


@pytest.fixture
def mock_interaction() -> AsyncMock:
    """モックUserInteraction"""
    mock = AsyncMock(spec=UserInteraction)
    mock.ask.return_value = "テスト回答"
    mock.confirm.return_value = True
    return mock


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """テスト用設定"""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    return Config(
        azure_endpoint="https://test.models.ai.azure.com",
        prompts_dir=prompts_dir,
    )
