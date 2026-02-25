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
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

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
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 10

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
    async def test_token_usage_tracking(self, client: LLMClient) -> None:
        """トークン使用量が累積されること"""
        mock_response1 = MagicMock()
        mock_response1.choices = [MagicMock()]
        mock_response1.choices[0].message.content = "応答1"
        mock_response1.usage.prompt_tokens = 100
        mock_response1.usage.completion_tokens = 50

        mock_response2 = MagicMock()
        mock_response2.choices = [MagicMock()]
        mock_response2.choices[0].message.content = "応答2"
        mock_response2.usage.prompt_tokens = 200
        mock_response2.usage.completion_tokens = 80

        mock_sdk_client = AsyncMock()
        mock_sdk_client.complete.side_effect = [mock_response1, mock_response2]

        with patch.object(client, "_get_client", return_value=mock_sdk_client):
            await client.chat(messages=[{"role": "user", "content": "テスト1"}])
            await client.chat(messages=[{"role": "user", "content": "テスト2"}])

        usage = client.get_usage()
        assert usage.prompt_tokens == 300
        assert usage.completion_tokens == 130
        assert usage.total_tokens == 430

    @pytest.mark.asyncio
    async def test_reset_usage(self, client: LLMClient) -> None:
        """reset_usage でカウントがリセットされること"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "応答"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_sdk_client = AsyncMock()
        mock_sdk_client.complete.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_sdk_client):
            await client.chat(messages=[{"role": "user", "content": "テスト"}])

        assert client.get_usage().total_tokens == 150

        client.reset_usage()
        usage = client.get_usage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    @pytest.mark.asyncio
    async def test_close(self, client: LLMClient) -> None:
        mock_sdk_client = AsyncMock()
        client._client = mock_sdk_client

        await client.close()
        mock_sdk_client.close.assert_called_once()
        assert client._client is None
