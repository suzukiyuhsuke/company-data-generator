"""情報収集エージェント"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from company_data_generator.agents.base import BaseAgent
from company_data_generator.interaction import UserInteraction
from company_data_generator.models import AutoCompletedProfile, CompanyProfile, MissingInfo

logger = logging.getLogger(__name__)


class InfoCollectorAgent(BaseAgent):
    """会社情報を収集・補完するエージェント

    会社情報Markdownを読み込み、不足情報をユーザ対話またはLLM自動補完で収集する。
    """

    async def run(
        self,
        company_file: Path,
        domain: str,
        mode: str,
        interaction: UserInteraction,
    ) -> CompanyProfile:
        """情報収集のメイン処理

        Args:
            company_file: 会社情報Markdownファイルのパス
            domain: 対象ドメイン
            mode: "interactive" または "auto"
            interaction: ユーザ対話インターフェース

        Returns:
            完成したCompanyProfile
        """
        logger.info("情報収集開始 [mode=%s, domain=%s]", mode, domain)

        # 会社情報Markdownを読み込み
        company_md = company_file.read_text(encoding="utf-8")

        if mode == "auto":
            return await self._auto_complete(company_md, domain, interaction)
        else:
            return await self._interactive_collect(company_md, domain, interaction)

    async def _analyze_missing_info(self, company_md: str, domain: str) -> MissingInfo:
        """不足情報を分析する"""
        logger.info("不足情報の分析中...")
        prompt = self.prompts.render(
            "collect_info.md.j2",
            company_md=company_md,
            domain=domain,
        )

        sys_msg = "あなたは日本企業の社内資料に精通したアシスタントです。"
        logger.info("LLM応答待ち... (不足情報分析)")
        result = await self.llm.chat(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            response_format=MissingInfo,
        )
        return result  # type: ignore[return-value]

    async def _interactive_collect(
        self,
        company_md: str,
        domain: str,
        interaction: UserInteraction,
    ) -> CompanyProfile:
        """対話モードで情報を収集する"""
        # 不足情報を分析
        missing = await self._analyze_missing_info(company_md, domain)

        # ユーザに質問して回答を収集
        answers: list[str] = []
        for question in missing.questions:
            answer = await interaction.ask(question)
            answers.append(answer)

        # 収集した情報からプロファイルを構築
        logger.info("対話情報からプロファイル構築中...")
        logger.info("LLM応答待ち... (プロファイル構築)")
        prompt = self.prompts.render(
            "auto_complete.md.j2",
            company_md=company_md,
            domain=domain,
            additional_info="\n".join(
                f"Q: {q}\nA: {a}" for q, a in zip(missing.questions, answers)
            ),
        )

        sys_msg = "あなたは日本企業の社内資料に精通したアシスタントです。"
        result = await self.llm.chat(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            response_format=CompanyProfile,
        )
        return result  # type: ignore[return-value]

    async def _auto_complete(
        self, company_md: str, domain: str, interaction: UserInteraction,
    ) -> CompanyProfile:
        """Autoモードで不足情報をLLMに自動補完させる

        2ステップで処理する:
        1. 不足情報を質問リストとして分析
        2. LLM自身がその質問に回答し、プロファイルを構築
        """
        # Step 1: 不足情報を分析（interactiveモードと同じ）
        logger.info("Auto補完 Step 1: 不足情報の分析")
        missing = await self._analyze_missing_info(company_md, domain)
        logger.info("Auto補完: %d 件の不足情報を検出", len(missing.questions))
        await interaction.notify(
            f"会社情報を確認したところ、{len(missing.questions)} 件ほど足りない情報がありました。\n"
            f"こちらで推定して補完しますね 🔍"
        )

        # Step 2: LLM自身に質問へ回答させる
        logger.info("Auto補完 Step 2: 不足情報の自動推定")
        logger.info("LLM応答待ち... (不足情報の自動回答)")
        self_answers = await self._self_answer_questions(
            company_md, domain, missing.questions
        )

        # Step 3: 回答を含めてプロファイルを構築
        additional_info = "\n".join(
            f"Q: {q}\nA: {a}" for q, a in zip(missing.questions, self_answers)
        )
        logger.info("Auto補完 Step 3: プロファイル構築")
        logger.info("LLM応答待ち... (プロファイル構築)")

        prompt = self.prompts.render(
            "auto_complete.md.j2",
            company_md=company_md,
            domain=domain,
            additional_info=additional_info if additional_info else "（追加情報なし）",
        )

        sys_msg = "あなたは日本企業の社内資料に精通したアシスタントです。"
        result = await self.llm.chat(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            response_format=AutoCompletedProfile,
        )
        auto_completed: AutoCompletedProfile = result  # type: ignore[assignment]
        logger.info("Auto補完の前提条件: %s", auto_completed.assumptions)

        # 自動補完の内容を通知
        qa_lines = "\n".join(
            f"- **Q:** {q}\n  **A:** {a}" for q, a in zip(missing.questions, self_answers)
        )
        await interaction.notify(
            f"以下の内容で補完しました 📝\n\n{qa_lines}"
        )
        if auto_completed.assumptions:
            await interaction.notify(
                f"なお、補完にあたって以下を前提としています。\n{auto_completed.assumptions}"
            )

        return auto_completed.profile

    async def _self_answer_questions(
        self, company_md: str, domain: str, questions: list[str]
    ) -> list[str]:
        """LLM自身に不足情報の質問へ回答させる"""
        if not questions:
            return []

        q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = (
            f"以下は、ある日本企業の「{domain}」ドメインのドキュメントを生成するために\n"
            f"不足している情報に関する質問です。\n\n"
            f"## 会社情報\n{company_md}\n\n"
            f"## 質問\n{q_list}\n\n"
            f"## 指示\n"
            f"あなたは上記の会社情報を踏まえた上で、各質問に対して\n"
            f"日本の同業種・同規模の企業で一般的に想定される内容を\n"
            f"具体的かつ詳細に推定して回答してください。\n"
            f"各回答は 1〜3 文程度で、具体的な数字・名称・制度名などを含めてください。\n"
            f"回答のみを改行区切りで出力してください（番号付き）。"
        )

        content: str = await self.llm.chat(  # type: ignore[assignment]
            messages=[
                {
                    "role": "system",
                    "content": "あなたは日本企業の経営・組織に精通したコンサルタントです。",
                },
                {"role": "user", "content": prompt},
            ],
        )

        # 番号付き回答をパースする
        answers = []
        for line in content.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # "1. ..." や "1) ..." の番号を除去
            cleaned = re.sub(r"^\d+[.)\s]+", "", line).strip()
            if cleaned:
                answers.append(cleaned)

        # 質問数と回答数が合わない場合の安全策
        while len(answers) < len(questions):
            answers.append("（推定情報なし）")

        for q, a in zip(questions, answers):
            logger.info("  Q: %s", q)
            logger.info("  A: %s", a)

        return answers[:len(questions)]
