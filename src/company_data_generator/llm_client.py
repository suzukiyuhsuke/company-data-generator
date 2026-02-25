"""Azure AI Foundry model-router LLMクライアント"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from azure.ai.inference.aio import ChatCompletionsClient
from azure.ai.inference.models import (
    JsonSchemaFormat,
    SystemMessage,
    UserMessage,
)
from azure.core.exceptions import HttpResponseError

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _prepare_schema_for_azure(schema: dict) -> dict:
    """Pydantic の JSON Schema を Azure OpenAI Structured Output 向けに変換する。

    1. $ref をインライン展開し、$ref + 他キーワードの共存を解消
    2. 全オブジェクトに additionalProperties: false を付与
    3. $defs を除去（インライン展開済みのため不要）
    """
    defs = schema.pop("$defs", {})

    def _resolve(node: object) -> object:
        if isinstance(node, dict):
            # $ref を展開
            if "$ref" in node:
                ref_path = node["$ref"]  # e.g. "#/$defs/CompanyProfile"
                ref_name = ref_path.rsplit("/", 1)[-1]
                resolved = defs.get(ref_name, {}).copy()
                # $ref 以外のキーワード（description 等）をマージ
                for k, v in node.items():
                    if k != "$ref":
                        resolved.setdefault(k, v)
                node = resolved

            # 再帰処理
            result = {}
            for key, value in node.items():
                result[key] = _resolve(value)

            # additionalProperties: false を付与
            if result.get("type") == "object" or "properties" in result:
                result["additionalProperties"] = False

            return result

        if isinstance(node, list):
            return [_resolve(item) for item in node]

        return node

    return _resolve(schema)  # type: ignore[return-value]


class LLMClient:
    """Azure AI Foundry model-router クライアント"""

    def __init__(self, endpoint: str, credential: AsyncTokenCredential) -> None:
        """
        Args:
            endpoint: Azure AI Foundry のエンドポイントURL
                      (ターゲットURIから /chat/completions 以降を除いた部分)
            credential: Entra ID 認証情報 (DefaultAzureCredential)
        """
        self.endpoint = endpoint
        self.credential = credential
        self._client: ChatCompletionsClient | None = None

    def _get_client(self) -> ChatCompletionsClient:
        """クライアントを取得（遅延初期化）"""
        if self._client is None:
            # エンドポイントに応じてトークンスコープを切り替える
            # cognitiveservices.azure.com → Cognitive Services スコープ
            # それ以外 → Azure ML スコープ (SDK デフォルト)
            kwargs: dict = {}
            if "cognitiveservices.azure.com" in self.endpoint:
                kwargs["credential_scopes"] = [
                    "https://cognitiveservices.azure.com/.default"
                ]

            self._client = ChatCompletionsClient(
                endpoint=self.endpoint,
                credential=self.credential,
                api_version="2024-12-01-preview",
                **kwargs,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        """LLMにリクエストを送信する。

        response_format が指定された場合、Structured Output として
        Pydanticモデルにパースして返す。

        Args:
            messages: メッセージリスト [{"role": "system"|"user", "content": "..."}]
            temperature: 生成のtemperature
            max_tokens: 最大トークン数
            response_format: Structured Output用のPydanticモデルクラス

        Returns:
            文字列レスポンス、または response_format 指定時はPydanticモデルインスタンス
        """
        client = self._get_client()

        # メッセージを SDK のモデルに変換
        sdk_messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                sdk_messages.append(SystemMessage(content=content))
            else:
                sdk_messages.append(UserMessage(content=content))

        kwargs: dict = {
            "messages": sdk_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format is not None:
            schema = _prepare_schema_for_azure(
                response_format.model_json_schema()
            )
            kwargs["response_format"] = JsonSchemaFormat(
                name=response_format.__name__,
                schema=schema,
                strict=True,
            )

        model_name = response_format.__name__ if response_format else "(text)"
        logger.info("LLMリクエスト送信 [response_format=%s]", model_name)

        max_retries = 3
        base_delay = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    client.complete(**kwargs), timeout=300
                )
            except TimeoutError:
                logger.error(
                    "LLMリクエストがタイムアウトしました (300秒) [試行 %d/%d]",
                    attempt, max_retries,
                )
                raise TimeoutError("LLMリクエストが300秒以内に応答しませんでした") from None
            except HttpResponseError as e:
                # APIエラーレスポンスの詳細をログに出力
                error_body = ""
                try:
                    if e.response and e.response.text():
                        error_body = e.response.text()
                except Exception:
                    error_body = str(e)
                if not error_body:
                    error_body = str(e)

                logger.error(
                    "LLM APIエラー [status=%s, 試行 %d/%d]:\n%s",
                    e.status_code, attempt, max_retries, error_body,
                )

                if e.status_code == 429 and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "レート制限 (429)。%d秒後にリトライします",
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            # --- レスポンス検証 ---
            if not response.choices:
                # 生レスポンス情報をログ出力
                raw_body = getattr(response, "__dict__", response)
                logger.error(
                    "LLMから空の choices を受信 [試行 %d/%d]。レスポンス: %s",
                    attempt, max_retries, raw_body,
                )
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning("%d秒後にリトライします", delay)
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError("LLMから空のレスポンスが返されました (choices が空)")

            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)

            # content_filter で停止した場合
            if finish_reason == "content_filter":
                logger.warning(
                    "コンテンツフィルタによりレスポンスが切り捨てられました [試行 %d/%d]",
                    attempt, max_retries,
                )
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning("%d秒後にリトライします", delay)
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError("コンテンツフィルタにより生成がブロックされました")

            content = choice.message.content

            # 空コンテンツのチェック
            if not content or not content.strip():
                logger.error(
                    "LLMから空のコンテンツを受信 [試行 %d/%d, finish_reason=%s]",
                    attempt, max_retries, finish_reason,
                )
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning("%d秒後にリトライします", delay)
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(
                    "LLMから空のレスポンスが返されました "
                    f"(finish_reason={finish_reason})"
                )

            usage = response.usage
            if usage:
                logger.info(
                    "LLMレスポンス受信 [prompt=%d tokens, completion=%d tokens]",
                    usage.prompt_tokens,
                    usage.completion_tokens,
                )

            if response_format is not None:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(
                        "LLMレスポンスのJSONパースに失敗 [試行 %d/%d]: %s\n"
                        "レスポンス先頭200文字: %s",
                        attempt, max_retries, e, content[:200],
                    )
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning("%d秒後にリトライします", delay)
                        await asyncio.sleep(delay)
                        continue
                    raise RuntimeError(
                        f"LLMレスポンスのJSONパースに失敗しました: {e}"
                    ) from e
                return response_format.model_validate(parsed)

            return content

        # ここには到達しないはず
        raise RuntimeError("リトライ上限に達しました")

    async def close(self) -> None:
        """クライアントをクローズする"""
        if self._client is not None:
            await self._client.close()
            self._client = None
