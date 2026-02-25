"""WebUI (Gradio) エントリポイント"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import zipfile
from datetime import timedelta, timezone
from pathlib import Path

import gradio as gr

from company_data_generator.config import Config
from company_data_generator.interaction import UserInteraction
from company_data_generator.models import DocumentPlanList, GeneratedDocument, PhaseTokenUsage
from company_data_generator.runner import Runner

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class _WebLogHandler(logging.Handler):
    """WebUI向けのログ収集ハンドラ

    ログレコードをリストに蓄積し、WebUIからポーリングで取得できるようにする。
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []
        self.setFormatter(
            logging.Formatter("[%(asctime)s] %(name)s - %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.records.append(msg)
        except Exception:
            self.handleError(record)

    def get_text(self) -> str:
        """蓄積したログを改行区切りテキストで返す"""
        return "\n".join(self.records)

    def clear(self) -> None:
        """蓄積したログをクリアする"""
        self.records.clear()

DOMAIN_CHOICES = [
    "営業", "人事", "設計", "製造", "カスタマーサポート",
    "総務", "経理", "法務", "情報システム",
]


class WebInteraction(UserInteraction):
    """チャットUI経由でユーザと対話する実装"""

    def __init__(self) -> None:
        self._question_queue: asyncio.Queue[str] = asyncio.Queue()
        self._answer_queue: asyncio.Queue[str] = asyncio.Queue()
        self._notification_queue: asyncio.Queue[str] = asyncio.Queue()
        self._plan: DocumentPlanList | None = None
        self._results: list[GeneratedDocument] = []
        self._progress_current: int = 0
        self._progress_total: int = 0
        self._progress_message: str = ""
        self._phase_usage: PhaseTokenUsage = PhaseTokenUsage()

    async def ask(self, question: str, choices: list[str] | None = None) -> str:
        """質問をチャットUIに送り、ユーザの回答を待つ"""
        prompt = question
        if choices:
            prompt += "\n" + "\n".join(f"  {i + 1}. {c}" for i, c in enumerate(choices))
        await self._question_queue.put(prompt)
        return await self._answer_queue.get()

    async def confirm(self, message: str) -> bool:
        """ユーザに確認を求める"""
        answer = await self.ask(f"{message} (はい/いいえ)")
        return answer.strip().lower() in ("はい", "yes", "y", "ok")

    async def show_progress(self, current: int, total: int, message: str) -> None:
        """進捗を記録する"""
        self._progress_current = current
        self._progress_total = total
        self._progress_message = message

    async def display_plan(self, plan: DocumentPlanList) -> None:
        """ドキュメント計画を保存する"""
        self._plan = plan

    async def display_result(self, document: GeneratedDocument) -> None:
        """生成結果を保存する"""
        self._results.append(document)

    async def notify(self, message: str) -> None:
        """通知メッセージをキューに入れる（応答不要）"""
        await self._notification_queue.put(message)


def launch_web_ui(port: int = 7860) -> None:
    """Gradio WebUIを起動する"""

    web_interaction: WebInteraction | None = None
    runner_task: asyncio.Task | None = None
    runner_ref: Runner | None = None
    generated_paths: list[Path] = []
    log_handler = _WebLogHandler()

    # アプリロガーにWebハンドラを追加（Azure SDK は除外済み）
    app_logger = logging.getLogger("company_data_generator")
    app_logger.addHandler(log_handler)
    if app_logger.level == logging.NOTSET:
        app_logger.setLevel(logging.INFO)

    # Azure SDK ロガーを抑制
    for name in ("azure", "azure.core", "azure.identity"):
        logging.getLogger(name).setLevel(logging.WARNING)

    def _format_token_usage(pu: PhaseTokenUsage) -> str:
        """PhaseTokenUsage をMarkdownテーブルにフォーマットする"""
        avg = ""
        if pu.phase3_doc_count > 0:
            avg_total = pu.phase3.total_tokens // pu.phase3_doc_count
            avg = f"\n\n**Phase 3 ドキュメントあたり平均: {avg_total:,} tokens** ({pu.phase3_doc_count} 件)"
        return (
            "| Phase | 入力トークン | 出力トークン | 合計 |\n"
            "|-------|----------:|----------:|-----:|\n"
            f"| Phase 1 (情報収集) | {pu.phase1.prompt_tokens:,} | {pu.phase1.completion_tokens:,} | {pu.phase1.total_tokens:,} |\n"
            f"| Phase 2 (計画作成) | {pu.phase2.prompt_tokens:,} | {pu.phase2.completion_tokens:,} | {pu.phase2.total_tokens:,} |\n"
            f"| Phase 3 (文書生成) | {pu.phase3.prompt_tokens:,} | {pu.phase3.completion_tokens:,} | {pu.phase3.total_tokens:,} |\n"
            f"| **合計** | **{pu.phase1.prompt_tokens + pu.phase2.prompt_tokens + pu.phase3.prompt_tokens:,}** "
            f"| **{pu.phase1.completion_tokens + pu.phase2.completion_tokens + pu.phase3.completion_tokens:,}** "
            f"| **{pu.phase1.total_tokens + pu.phase2.total_tokens + pu.phase3.total_tokens:,}** |"
            f"{avg}"
        )

    # 7-tuple ヘルパー: 通常の yield 用（トークン使用量は更新しない）
    def _yield_update(chatbot, log_text):
        return chatbot, gr.update(), gr.update(), gr.update(), log_text, gr.update(), gr.update()

    async def start_generation(
        company_file: str | None,
        domain: str,
        count: int,
        mode: str,
        chatbot: list,
    ):
        """生成プロセスを開始し、チャット対話を管理する"""
        nonlocal web_interaction, runner_task, generated_paths, runner_ref

        log_handler.clear()

        if not company_file:
            chatbot.append({
                "role": "assistant",
                "content": "❌ 会社情報ファイルをアップロードしてください。",
            })
            yield _yield_update(chatbot, log_handler.get_text())
            return

        config = Config.from_env()
        if not config.azure_endpoint:
            chatbot.append({
                "role": "assistant",
                "content": "❌ AZURE_AI_ENDPOINT 環境変数を設定してください。",
            })
            yield _yield_update(chatbot, log_handler.get_text())
            return

        web_interaction = WebInteraction()
        runner = Runner(interaction=web_interaction, config=config)
        runner_ref = runner

        company_path = Path(company_file)
        output_dir = Path(tempfile.mkdtemp(prefix="cdg_"))

        chatbot.append({
            "role": "assistant",
            "content": (
                f"🏢 生成を開始します\n"
                f"- ドメイン: {domain}\n"
                f"- 件数: {count}\n"
                f"- モード: {mode}"
            ),
        })
        yield _yield_update(chatbot, log_handler.get_text())

        # Runnerを別タスクで実行
        loop = asyncio.get_running_loop()
        runner_task = loop.create_task(
            runner.run(
                company_file=company_path,
                domain=domain,
                count=int(count),
                mode=mode,
                output_dir=output_dir,
            )
        )

        def _on_task_error(task: asyncio.Task) -> None:
            """runner_task の例外をログに記録する"""
            if task.cancelled():
                logger.warning("生成タスクがキャンセルされました")
            elif task.exception():
                logger.error("生成タスクでエラー: %s", task.exception())

        runner_task.add_done_callback(_on_task_error)

        # Interactive モードの場合、対話ループ
        if mode == "interactive":
            try:
                while not runner_task.done():
                    try:
                        question = await asyncio.wait_for(
                            web_interaction._question_queue.get(), timeout=0.5
                        )
                        chatbot.append({"role": "assistant", "content": question})
                        yield _yield_update(chatbot, log_handler.get_text())
                        # ユーザの入力待ち — ここで一旦yieldして戻る
                        return
                    except TimeoutError:
                        # ログの更新をyield
                        yield _yield_update(chatbot, log_handler.get_text())
                        continue
            except Exception as e:
                chatbot.append({"role": "assistant", "content": f"❌ エラー: {e}"})
                yield _yield_update(chatbot, log_handler.get_text())
                return

        # Auto モードまたは対話完了後、結果を待つ
        try:
            # ポーリングしながらログ・通知を更新
            while not runner_task.done():
                await asyncio.sleep(0.5)
                # 通知キューを排出してチャットに表示
                while not web_interaction._notification_queue.empty():
                    note = web_interaction._notification_queue.get_nowait()
                    chatbot.append({"role": "assistant", "content": note})
                yield _yield_update(chatbot, log_handler.get_text())
            # 最後に残った通知も排出
            while not web_interaction._notification_queue.empty():
                note = web_interaction._notification_queue.get_nowait()
                chatbot.append({"role": "assistant", "content": note})
            generated_paths = runner_task.result()
        except Exception as e:
            chatbot.append({"role": "assistant", "content": f"❌ エラーが発生しました: {e}"})
            yield _yield_update(chatbot, log_handler.get_text())
            return

        # トークン使用量を保存
        web_interaction._phase_usage = runner.phase_usage

        # 計画テーブル
        plan_data = []
        if web_interaction._plan:
            for p in web_interaction._plan.plans:
                plan_data.append([
                    p.title,
                    p.doc_type,
                    p.summary[:60],
                    "✓" if p.includes_diagram else "",
                    p.estimated_length,
                ])

        # 結果ドキュメント選択肢
        result_choices = [doc.filename for doc in web_interaction._results]

        # 事前にZIPを生成してDownloadButtonにセット
        zip_path = _build_zip()

        # トークン使用量テキスト
        token_text = _format_token_usage(web_interaction._phase_usage)

        chatbot.append({
            "role": "assistant",
            "content": (
                f"✅ {len(generated_paths)} 件のドキュメントを生成しました！\n"
                "「計画」タブと「結果」タブで確認できます。"
            ),
        })
        yield (
            chatbot,
            gr.update(value=plan_data if plan_data else None),
            gr.update(choices=result_choices, value=result_choices[0] if result_choices else None),
            gr.update(value=_get_result_content(result_choices[0]) if result_choices else ""),
            log_handler.get_text(),
            gr.update(value=zip_path),
            gr.update(value=token_text),
        )

    async def handle_user_message(user_message: str, chatbot: list):
        """ユーザメッセージを処理する"""
        nonlocal web_interaction, runner_task, runner_ref

        chatbot.append({"role": "user", "content": user_message})

        if web_interaction and not runner_task.done():
            # エージェントに回答を送信
            await web_interaction._answer_queue.put(user_message)

            # 次の質問またはタスク完了を待つ
            try:
                while not runner_task.done():
                    try:
                        question = await asyncio.wait_for(
                            web_interaction._question_queue.get(), timeout=0.5
                        )
                        chatbot.append({"role": "assistant", "content": question})
                        yield _yield_update(chatbot, log_handler.get_text())
                        return
                    except TimeoutError:
                        yield _yield_update(chatbot, log_handler.get_text())
                        continue

                # タスク完了
                generated = runner_task.result()

                # トークン使用量を保存
                if runner_ref:
                    web_interaction._phase_usage = runner_ref.phase_usage

                plan_data = []
                if web_interaction._plan:
                    for p in web_interaction._plan.plans:
                        plan_data.append([
                            p.title,
                            p.doc_type,
                            p.summary[:60],
                            "✓" if p.includes_diagram else "",
                            p.estimated_length,
                        ])

                result_choices = [doc.filename for doc in web_interaction._results]

                # 事前にZIPを生成してDownloadButtonにセット
                zip_path = _build_zip()

                # トークン使用量テキスト
                token_text = _format_token_usage(web_interaction._phase_usage)

                chatbot.append({
                    "role": "assistant",
                    "content": f"✅ {len(generated)} 件のドキュメントを生成しました！",
                })
                yield (
                    chatbot,
                    gr.update(value=plan_data if plan_data else None),
                    gr.update(
                        choices=result_choices,
                        value=result_choices[0] if result_choices else None,
                    ),
                    gr.update(
                        value=_get_result_content(result_choices[0]) if result_choices else ""
                    ),
                    log_handler.get_text(),
                    gr.update(value=zip_path),
                    gr.update(value=token_text),
                )

            except Exception as e:
                chatbot.append({"role": "assistant", "content": f"❌ エラー: {e}"})
                yield _yield_update(chatbot, log_handler.get_text())
        else:
            chatbot.append({
                "role": "assistant",
                "content": "「開始」ボタンを押して生成を開始してください。",
            })
            yield _yield_update(chatbot, log_handler.get_text())

    def _get_result_content(filename: str | None) -> str:
        """ファイル名から生成結果の内容を返す"""
        if not filename or not web_interaction:
            return ""
        for doc in web_interaction._results:
            if doc.filename == filename:
                return doc.content
        return ""

    def on_result_select(filename: str | None) -> str:
        """結果ドキュメント選択時のコールバック"""
        return _get_result_content(filename)

    def _build_zip() -> str | None:
        """全ドキュメントをZIPにまとめてパスを返す"""
        if not web_interaction or not web_interaction._results:
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in web_interaction._results:
                zf.writestr(doc.filename, doc.content)

            # ドキュメント計画をCSVで同梱
            if web_interaction._plan:
                import csv
                import io

                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["タイトル", "種別", "概要", "対象読者", "図", "ボリューム"])
                for p in web_interaction._plan.plans:
                    writer.writerow([
                        p.title,
                        p.doc_type,
                        p.summary,
                        p.target_audience,
                        "あり" if p.includes_diagram else "なし",
                        p.estimated_length,
                    ])
                zf.writestr("document_plan.csv", buf.getvalue())

        return tmp.name

    # --- UI構築 ---
    with gr.Blocks(
        title="会社データジェネレータ",
    ) as app:
        gr.Markdown("# 🏢 会社データジェネレータ")
        gr.Markdown("架空の日本企業の社内データ（内規・議事録・報告書など）を生成します。Markdown形式で記述した会社情報をアップロードすると、AIがそれなりに解釈して指定したドメインで「存在しそうな」ドキュメントを生成します。")

        with gr.Tabs():
            # タブ1: 設定 & 対話
            with gr.Tab("① 設定 & 対話"):
                with gr.Row():
                    with gr.Column(scale=1):
                        file_input = gr.File(
                            label="会社情報 Markdownファイル",
                            file_types=[".md"],
                            type="filepath",
                        )
                        domain_input = gr.Dropdown(
                            choices=DOMAIN_CHOICES,
                            label="ドメイン",
                            value="営業",
                            info="生成するドキュメントの業務領域を選択します",
                        )
                        count_input = gr.Number(
                            minimum=1,
                            maximum=1000,
                            value=5,
                            step=1,
                            precision=0,
                            label="生成件数",
                        )
                        mode_input = gr.Radio(
                            choices=["interactive", "auto"],
                            value="interactive",
                            label="モード",
                            info="interactive: 対話しながら生成内容を調整 / auto: 自動で一括生成",
                        )
                        start_btn = gr.Button("🚀 生成開始", variant="primary")

                    with gr.Column(scale=2):
                        chatbot = gr.Chatbot(
                            label="対話",
                            height=750,
                            group_consecutive_messages=False,
                        )
                        msg_input = gr.Textbox(
                            label="メッセージ入力",
                            placeholder="回答を入力してください...",
                            show_label=False,
                        )

            # タブ2: 計画
            with gr.Tab("② 計画確認"):
                plan_table = gr.Dataframe(
                    headers=["タイトル", "種別", "概要", "図", "ボリューム"],
                    label="ドキュメント計画",
                    interactive=False,
                )

            # タブ3: 結果
            with gr.Tab("③ 結果"):
                with gr.Row():
                    result_selector = gr.Dropdown(
                        label="ドキュメント選択",
                        choices=[],
                        interactive=True,
                    )
                    dl_btn = gr.DownloadButton("📦 一括ダウンロード（ZIP）", variant="secondary")
                result_preview = gr.Markdown(label="プレビュー")

            # タブ4: トークン使用量
            with gr.Tab("④ トークン使用量"):
                token_usage_output = gr.Markdown(
                    value="生成完了後にフェーズ別のトークン使用量が表示されます。",
                    label="トークン使用量",
                )

        # ログ表示（タブグループの外）
        with gr.Accordion("📋 ログ", open=False):
            log_output = gr.Textbox(
                label="アプリケーションログ",
                lines=12,
                max_lines=30,
                interactive=False,
            )

        # イベントバインド
        start_btn.click(
            fn=start_generation,
            inputs=[file_input, domain_input, count_input, mode_input, chatbot],
            outputs=[chatbot, plan_table, result_selector, result_preview, log_output, dl_btn, token_usage_output],
        )

        msg_input.submit(
            fn=handle_user_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, plan_table, result_selector, result_preview, log_output, dl_btn, token_usage_output],
        ).then(fn=lambda: "", outputs=[msg_input])

        result_selector.change(
            fn=on_result_select,
            inputs=[result_selector],
            outputs=[result_preview],
        )

    app.queue()

    # 環境変数 APP_USERNAME / APP_PASSWORD が設定されていれば認証を有効化
    auth_user = os.environ.get("APP_USERNAME")
    auth_pass = os.environ.get("APP_PASSWORD")
    auth = (auth_user, auth_pass) if auth_user and auth_pass else None

    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        auth=auth,
        auth_message="ログインしてください" if auth else None,
        theme=gr.themes.Soft(),
    )
