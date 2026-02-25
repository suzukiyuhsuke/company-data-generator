"""llm_client.py のテスト"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from company_data_generator.llm_client import LLMClient
from company_data_generator.models import MissingInfo


class TestLLMClient:
    @pytest.fixture
    def mock_credential(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def client(self, mock_credential: AsyncMock) -> LLMClient:
        return LLMClient(
            endpoint="https://test.models.ai.azure.com",
            credential=mock_credential,
        )

    @pytest.mark.asyncio
    async def test_chat_returns_string(self, client: LLMClient) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "テスト応答"

        mock_sdk_client = AsyncMock()
        mock_sdk_client.complete.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_sdk_client):
            result = await client.chat(
                messages=[{"role": "user", "content": "テスト"}]
            )
            assert result == "テスト応答"

    @pytest.mark.asyncio
    async def test_chat_with_response_format(self, client: LLMClient) -> None:
        response_data = {"questions": ["質問1", "質問2"]}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_data)

        mock_sdk_client = AsyncMock()
        mock_sdk_client.complete.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_sdk_client):
            result = await client.chat(
                messages=[{"role": "user", "content": "テスト"}],
                response_format=MissingInfo,
            )
            assert isinstance(result, MissingInfo)
            assert len(result.questions) == 2

    @pytest.mark.asyncio
    async def test_close(self, client: LLMClient) -> None:
        mock_sdk_client = AsyncMock()
        client._client = mock_sdk_client

        await client.close()
        mock_sdk_client.close.assert_called_once()
        assert client._client is None
