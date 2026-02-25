"""interaction.py のテスト"""

import pytest

from company_data_generator.interaction import CLIInteraction
from company_data_generator.models import DocumentPlanList, GeneratedDocument


class TestCLIInteraction:
    @pytest.fixture
    def cli_interaction(self) -> CLIInteraction:
        return CLIInteraction()

    @pytest.mark.asyncio
    async def test_show_progress(self, cli_interaction: CLIInteraction) -> None:
        # エラーが起きないことを確認
        await cli_interaction.show_progress(1, 5, "テスト進捗")

    @pytest.mark.asyncio
    async def test_display_plan(
        self,
        cli_interaction: CLIInteraction,
        sample_plan_list: DocumentPlanList,
    ) -> None:
        # エラーが起きないことを確認
        await cli_interaction.display_plan(sample_plan_list)

    @pytest.mark.asyncio
    async def test_display_result(
        self,
        cli_interaction: CLIInteraction,
        sample_generated_document: GeneratedDocument,
    ) -> None:
        # エラーが起きないことを確認
        await cli_interaction.display_result(sample_generated_document)

    @pytest.mark.asyncio
    async def test_notify(self, cli_interaction: CLIInteraction) -> None:
        # エラーが起きないことを確認
        await cli_interaction.notify("テスト通知メッセージ")
