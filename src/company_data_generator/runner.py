"""全体オーケストレーション"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential

from company_data_generator.agents.doc_generator import DocGeneratorAgent
from company_data_generator.agents.doc_planner import DocPlannerAgent
from company_data_generator.agents.info_collector import InfoCollectorAgent
from company_data_generator.config import Config
from company_data_generator.interaction import UserInteraction
from company_data_generator.llm_client import LLMClient
from company_data_generator.models import DocumentPlan, GeneratedDocument
from company_data_generator.prompt_store import PromptStore

logger = logging.getLogger(__name__)


class Runner:
    """生成パイプライン全体のオーケストレータ"""

    def __init__(self, interaction: UserInteraction, config: Config) -> None:
        """
        Args:
            interaction: ユーザ対話の実装 (CLIまたはWeb)
            config: アプリケーション設定
        """
        self.interaction = interaction
        self.config = config

        credential = DefaultAzureCredential()
        llm_client = LLMClient(
            endpoint=config.azure_endpoint,
            credential=credential,
        )
        prompt_store = PromptStore(config.prompts_dir)

        self.info_collector = InfoCollectorAgent(llm_client, prompt_store)
        self.doc_planner = DocPlannerAgent(llm_client, prompt_store)
        self.doc_generator = DocGeneratorAgent(llm_client, prompt_store)
        self._llm_client = llm_client
        self._credential = credential

    async def run(
        self,
        company_file: Path,
        domain: str,
        count: int,
        mode: str,
        output_dir: Path,
    ) -> list[Path]:
        """メインパイプラインを実行する。

        Args:
            company_file: 会社情報Markdownファイルのパス
            domain: 対象ドメイン
            count: 生成件数
            mode: "interactive" または "auto"
            output_dir: 出力ディレクトリ

        Returns:
            生成されたドキュメントのファイルパスリスト
        """
        try:
            # Phase 1: 会社情報の収集
            logger.info("Phase 1: 会社情報の収集を開始")
            await self.interaction.notify(
                "📄 アップロードされた会社情報を読み込んでいます。\n"
                "不足している情報がないかチェックしますね。"
            )
            profile = await self.info_collector.run(
                company_file, domain, mode, self.interaction
            )

            # プロファイルを保存
            output_dir.mkdir(parents=True, exist_ok=True)
            profile_path = output_dir / "company_profile.json"
            profile_path.write_text(
                profile.model_dump_json(indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("会社プロファイルを保存: %s", profile_path)
            await self.interaction.notify(
                "会社情報の整理ができました！次のステップに進みます。"
            )

            # Phase 2: ドキュメント計画
            logger.info("Phase 2: ドキュメントのリストアップを開始")
            await self.interaction.notify(
                f"「{domain}」ドメインで生成するドキュメント {count} 件の計画を立てています。\n"
                f"どんな文書が必要か考えていますので、少々お待ちください 🤔"
            )
            plan = await self.doc_planner.run(profile, domain, count)
            await self.interaction.display_plan(plan)
            await self.interaction.notify(
                f"{len(plan.plans)} 件のドキュメント計画ができました！\n"
                f"「計画確認」タブで内容を確認できます。いよいよ文書を書き始めますね ✍️"
            )

            # 計画を保存
            plan_path = output_dir / "document_plan.json"
            plan_path.write_text(
                plan.model_dump_json(indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Phase 3: ドキュメント生成 (並列実行)
            logger.info(
                "Phase 3: ドキュメントの生成を開始 (並列数: %d)",
                self.config.max_concurrency,
            )
            await self.interaction.notify(
                f"{len(plan.plans)} 件のドキュメントを一気に書いていきます！\n"
                f"{self.config.max_concurrency} 件ずつ並列で作業するので、しばらくお待ちください ⏳"
            )
            sem = asyncio.Semaphore(self.config.max_concurrency)
            completed_count = 0
            total = len(plan.plans)

            async def _generate_one(
                i: int, doc_plan: DocumentPlan,
            ) -> tuple[int, GeneratedDocument]:
                nonlocal completed_count
                async with sem:
                    doc = await self.doc_generator.run(
                        profile, doc_plan, index=i + 1
                    )
                    completed_count += 1
                    await self.interaction.show_progress(
                        completed_count, total,
                        f"生成完了: {doc_plan.title}",
                    )
                    return i, doc

            results = await asyncio.gather(
                *[_generate_one(i, dp) for i, dp in enumerate(plan.plans)],
                return_exceptions=True,
            )

            generated: list[Path] = []
            failed_count = 0
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error("ドキュメント生成に失敗しました: %s", result)
                else:
                    _, doc = result
                    path = self._save_document(doc, output_dir)
                    await self.interaction.display_result(doc)
                    generated.append(path)

            if failed_count:
                logger.warning(
                    "%d 件の生成に失敗しました (%d 件成功)",
                    failed_count, len(generated),
                )

            logger.info("全 %d 件のドキュメントを生成しました", len(generated))
            await self.interaction.notify(
                f"🎉 すべて完了しました！ {len(generated)} 件のドキュメントが出来上がりです。\n"
                f"「結果」タブからプレビュー・ダウンロードできます。"
            )
            return generated

        finally:
            await self._llm_client.close()
            await self._credential.close()

    @staticmethod
    def _save_document(doc: GeneratedDocument, output_dir: Path) -> Path:
        """ドキュメントをファイルに保存する"""
        path = output_dir / doc.filename
        path.write_text(doc.content, encoding="utf-8")
        return path
