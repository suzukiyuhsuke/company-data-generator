"""doc_generator エージェントのテスト"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from company_data_generator.agents.doc_generator import DocGeneratorAgent, _sanitize_filename
from company_data_generator.models import CompanyProfile, DocumentPlan


class TestSanitizeFilename:
    def test_basic(self) -> None:
        assert _sanitize_filename("テスト文書") == "テスト文書"

    def test_removes_invalid_chars(self) -> None:
        assert _sanitize_filename('test:file?"name') == "testfilename"

    def test_replaces_spaces(self) -> None:
        assert _sanitize_filename("hello world test") == "hello_world_test"

    def test_nfkc_normalization(self) -> None:
        # 全角 -> 半角
        assert _sanitize_filename("ＡＢＣ") == "ABC"


class TestDocGeneratorAgent:
    @pytest.fixture
    def agent(self) -> DocGeneratorAgent:
        mock_llm = AsyncMock()
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "テストプロンプト"
        return DocGeneratorAgent(llm_client=mock_llm, prompt_store=mock_prompts)

    @pytest.mark.asyncio
    async def test_run(
        self,
        agent: DocGeneratorAgent,
        sample_profile: CompanyProfile,
        sample_plan: DocumentPlan,
    ) -> None:
        agent.llm.chat.return_value = "# テスト文書\n\nテスト本文"

        result = await agent.run(profile=sample_profile, plan=sample_plan, index=1)

        assert "---" in result.content  # frontmatter
        assert "テスト文書" in result.content
        assert result.filename.startswith("01_")
        assert result.filename.endswith(".md")

    @pytest.mark.asyncio
    async def test_filename_format(
        self,
        agent: DocGeneratorAgent,
        sample_profile: CompanyProfile,
        sample_plan: DocumentPlan,
    ) -> None:
        agent.llm.chat.return_value = "# 内容"

        result = await agent.run(profile=sample_profile, plan=sample_plan, index=5)

        assert result.filename.startswith("05_")
        assert "内規" in result.filename
        assert "情報セキュリティポリシー" in result.filename
