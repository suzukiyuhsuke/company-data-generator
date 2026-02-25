"""info_collector エージェントのテスト"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from company_data_generator.agents.info_collector import InfoCollectorAgent
from company_data_generator.models import AutoCompletedProfile, CompanyProfile, MissingInfo


class TestInfoCollectorAgent:
    @pytest.fixture
    def agent(self) -> InfoCollectorAgent:
        mock_llm = AsyncMock()
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "テストプロンプト"
        return InfoCollectorAgent(llm_client=mock_llm, prompt_store=mock_prompts)

    @pytest.mark.asyncio
    async def test_auto_mode(
        self,
        agent: InfoCollectorAgent,
        sample_profile: CompanyProfile,
        sample_company_file: Path,
    ) -> None:
        missing = MissingInfo(questions=["主要顧客は？", "売上規模は？"])
        auto_profile = AutoCompletedProfile(
            profile=sample_profile,
            assumptions=["テスト前提"],
        )
        # 1回目: _analyze_missing_info -> MissingInfo
        # 2回目: _self_answer_questions -> str (テキスト回答)
        # 3回目: _auto_complete (プロファイル構築) -> AutoCompletedProfile
        agent.llm.chat.side_effect = [
            missing,
            "1. 電子部品メーカー\n2. 年間50億円",
            auto_profile,
        ]

        result = await agent.run(
            company_file=sample_company_file,
            domain="営業",
            mode="auto",
            interaction=AsyncMock(),
        )

        assert result.name == "株式会社テスト商事"
        assert agent.llm.chat.call_count == 3

    @pytest.mark.asyncio
    async def test_interactive_mode(
        self,
        agent: InfoCollectorAgent,
        sample_profile: CompanyProfile,
        sample_company_file: Path,
        mock_interaction: AsyncMock,
    ) -> None:
        missing = MissingInfo(questions=["従業員数は？", "主要事業は？"])

        # 最初のcall: analyze_missing_info -> MissingInfo
        # 2番目のcall: _interactive_collect -> CompanyProfile
        agent.llm.chat.side_effect = [missing, sample_profile]

        result = await agent.run(
            company_file=sample_company_file,
            domain="営業",
            mode="interactive",
            interaction=mock_interaction,
        )

        assert result.name == "株式会社テスト商事"
        assert mock_interaction.ask.call_count == 2  # 2つの質問
