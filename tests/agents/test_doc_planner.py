"""doc_planner エージェントのテスト"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from company_data_generator.agents.doc_planner import DocPlannerAgent
from company_data_generator.models import CompanyProfile, DocumentPlanList


class TestDocPlannerAgent:
    @pytest.fixture
    def agent(self) -> DocPlannerAgent:
        mock_llm = AsyncMock()
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "テストプロンプト"
        return DocPlannerAgent(llm_client=mock_llm, prompt_store=mock_prompts)

    @pytest.mark.asyncio
    async def test_run(
        self,
        agent: DocPlannerAgent,
        sample_profile: CompanyProfile,
        sample_plan_list: DocumentPlanList,
    ) -> None:
        agent.llm.chat.return_value = sample_plan_list

        result = await agent.run(profile=sample_profile, domain="営業", count=1)

        assert result.domain == "営業"
        assert len(result.plans) == 1
        assert agent.llm.chat.called

    @pytest.mark.asyncio
    async def test_trims_excess_plans(
        self,
        agent: DocPlannerAgent,
        sample_profile: CompanyProfile,
        sample_plan_list: DocumentPlanList,
    ) -> None:
        # LLMが要求より多い件数を返した場合
        from company_data_generator.models import DocumentPlan

        extra_plan = DocumentPlan(
            title="余分な計画",
            doc_type="報告書",
            summary="テスト",
            target_audience="全社員",
            includes_diagram=False,
            estimated_length="short",
        )
        many_plans = DocumentPlanList(
            domain="営業",
            plans=[sample_plan_list.plans[0], extra_plan, extra_plan],
        )
        agent.llm.chat.return_value = many_plans

        result = await agent.run(profile=sample_profile, domain="営業", count=2)
        assert len(result.plans) == 2
