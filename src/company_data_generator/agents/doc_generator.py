"""ドキュメント生成エージェント"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from company_data_generator.agents.base import BaseAgent
from company_data_generator.models import (
    CompanyProfile,
    DocumentPlan,
    GeneratedDocument,
)

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def _sanitize_filename(text: str) -> str:
    """ファイル名に使えない文字を除去・変換する"""
    # NFKC正規化
    text = unicodedata.normalize("NFKC", text)
    # ファイル名に使えない文字を除去
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    # 空白をアンダースコアに
    text = re.sub(r"\s+", "_", text)
    return text


class DocGeneratorAgent(BaseAgent):
    """ドキュメント生成エージェント

    計画に従い、リアルなMarkdownドキュメントを生成する。
    """

    async def run(
        self,
        profile: CompanyProfile,
        plan: DocumentPlan,
        index: int = 1,
    ) -> GeneratedDocument:
        """1件のドキュメントを生成する

        Args:
            profile: 会社プロファイル
            plan: ドキュメント計画
            index: ドキュメントの連番

        Returns:
            生成されたドキュメント
        """
        logger.info("ドキュメント生成開始: [%d] %s (%s)", index, plan.title, plan.doc_type)
        logger.info("LLM応答待ち... (ドキュメント生成)")

        prompt = self.prompts.render(
            "generate_document.md.j2",
            profile=profile,
            plan=plan,
        )

        content: str = await self.llm.chat(  # type: ignore[assignment]
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは日本企業の社内資料を作成する専門家です。"
                        "指定された仕様に従い、リアルなMarkdownドキュメントを生成してください。"
                        "ドキュメントにはYAML frontmatterを含めないでください。"
                        "必要に応じてMermaid形式の図を含めてください。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        # YAML frontmatter を付与
        now = datetime.now(JST).isoformat()
        frontmatter = (
            f"---\n"
            f'title: "{plan.title}"\n'
            f'doc_type: "{plan.doc_type}"\n'
            f'domain: "{plan.doc_type}"\n'
            f'company: "{profile.name}"\n'
            f'generated_at: "{now}"\n'
            f"---\n\n"
        )
        full_content = frontmatter + content

        # ファイル名を生成
        doc_type = _sanitize_filename(plan.doc_type)
        title = _sanitize_filename(plan.title)
        filename = f"{index:02d}_{doc_type}_{title}.md"

        logger.info("ドキュメント生成完了: %s", filename)

        return GeneratedDocument(
            plan=plan,
            content=full_content,
            filename=filename,
        )
