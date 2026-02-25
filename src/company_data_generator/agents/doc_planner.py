"""ドキュメント計画エージェント"""

from __future__ import annotations

import logging

from company_data_generator.agents.base import BaseAgent
from company_data_generator.models import CompanyProfile, DocumentPlanList

logger = logging.getLogger(__name__)


class DocPlannerAgent(BaseAgent):
    """ドキュメント計画エージェント

    指定ドメインで日本企業に一般的なドキュメントを類推し、リスト化する。
    """

    async def run(
        self,
        profile: CompanyProfile,
        domain: str,
        count: int,
    ) -> DocumentPlanList:
        """ドキュメント計画を作成する

        Args:
            profile: 会社プロファイル
            domain: 対象ドメイン
            count: 生成するドキュメントの件数

        Returns:
            ドキュメント計画リスト
        """
        logger.info("ドキュメント計画作成開始 [domain=%s, count=%d]", domain, count)
        logger.info("LLM応答待ち... (ドキュメント計画作成)")

        prompt = self.prompts.render(
            "plan_documents.md.j2",
            profile=profile,
            domain=domain,
            count=count,
        )

        # 100件で約12,000トークン必要なため、件数に応じて max_tokens を算出
        estimated_tokens = max(4096, count * 120 + 512)
        # モデル上限 (16384) でキャップ
        max_tokens = min(estimated_tokens, 16384)

        result = await self.llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは日本企業の社内資料に精通したアシスタントです。"
                        "指定されたドメインで、一般的な日本の会社に存在しそうな資料を"
                        "リストアップしてください。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format=DocumentPlanList,
            max_tokens=max_tokens,
        )

        plan_list: DocumentPlanList = result  # type: ignore[assignment]

        # 件数バリデーション: 多い場合はトリム
        if len(plan_list.plans) > count:
            logger.warning(
                "LLMが %d 件返しましたが、指定 %d 件にトリムしました",
                len(plan_list.plans),
                count,
            )
            plan_list = DocumentPlanList(
                domain=plan_list.domain,
                plans=plan_list.plans[:count],
            )

        return plan_list
