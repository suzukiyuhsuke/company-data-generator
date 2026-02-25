"""エージェント基底クラス"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from company_data_generator.llm_client import LLMClient
from company_data_generator.prompt_store import PromptStore


class BaseAgent(ABC):
    """エージェントの基底クラス"""

    def __init__(self, llm_client: LLMClient, prompt_store: PromptStore) -> None:
        self.llm = llm_client
        self.prompts = prompt_store

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """エージェントのメイン処理"""
        ...
