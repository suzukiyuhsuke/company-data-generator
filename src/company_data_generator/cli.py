"""CLIエントリポイント"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from company_data_generator.config import Config
from company_data_generator.interaction import CLIInteraction
from company_data_generator.runner import Runner

console = Console()


def _setup_logging(verbose: bool) -> None:
    """ロギングをセットアップする

    アプリケーション (company_data_generator) のログは INFO 以上を表示し、
    Azure SDK の冗長な HTTP リクエスト/レスポンスログは WARNING 以上に抑制する。
    """
    level = logging.DEBUG if verbose else logging.INFO

    # ルートロガーは WARNING にしておき、アプリロガーだけ INFO/DEBUG にする
    handler = RichHandler(console=console, show_path=verbose)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(level=logging.WARNING, format="%(message)s", handlers=[handler])

    # アプリケーションロガーを有効化
    app_logger = logging.getLogger("company_data_generator")
    app_logger.setLevel(level)

    # Azure SDK の冗長ログを明示的に抑制
    for name in ("azure", "azure.core", "azure.identity"):
        logging.getLogger(name).setLevel(logging.WARNING)


async def _run_generate(
    company_file: Path,
    domain: str,
    count: int,
    mode: str,
    output_dir: Path,
) -> None:
    """非同期で生成パイプラインを実行"""
    config = Config.from_env()
    if not config.azure_endpoint:
        console.print("[red]エラー: AZURE_AI_ENDPOINT 環境変数を設定してください[/red]")
        sys.exit(1)

    interaction = CLIInteraction()
    runner = Runner(interaction=interaction, config=config)

    console.print()
    console.print("[bold blue]🏢 会社データジェネレータ[/bold blue]")
    console.print(f"  会社情報: {company_file}")
    console.print(f"  ドメイン: {domain}")
    console.print(f"  件数:     {count}")
    console.print(f"  モード:   {mode}")
    console.print(f"  出力先:   {output_dir}")
    console.print()

    results = await runner.run(
        company_file=company_file,
        domain=domain,
        count=count,
        mode=mode,
        output_dir=output_dir,
    )

    console.print()
    console.print(f"[bold green]✅ {len(results)} 件のドキュメントを生成しました[/bold green]")
    console.print(f"  出力先: {output_dir}")


class _WebFlagEagerOption(click.Option):
    """--web フラグを先読みし、他の必須オプション/引数のバリデーションをスキップする"""

    def handle_parse_result(
        self,
        ctx: click.Context,
        opts: dict,
        args: list[str],
    ) -> tuple:
        if opts.get("web"):
            # --web が付いている場合、他パラメータの required を無効化
            for param in ctx.command.params:
                param.required = False
        return super().handle_parse_result(ctx, opts, args)


@click.command()
@click.argument("company_file", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--domain", required=True, help="生成対象のドメイン (例: 営業, 人事, 設計, 製造)")
@click.option("--count", default=5, show_default=True, help="生成するドキュメント数")
@click.option(
    "--mode",
    type=click.Choice(["interactive", "auto"]),
    default="interactive",
    show_default=True,
    help="情報収集モード",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("./output"),
    show_default=True,
    help="出力ディレクトリ",
)
@click.option(
    "--web",
    is_flag=True,
    is_eager=True,
    cls=_WebFlagEagerOption,
    help="WebUIモードで起動",
)
@click.option("--port", default=7860, show_default=True, help="WebUIのポート番号")
@click.option("--verbose", is_flag=True, help="詳細ログ出力")
def main(
    company_file: Path | None,
    domain: str | None,
    count: int,
    mode: str,
    output_dir: Path,
    web: bool,
    port: int,
    verbose: bool,
) -> None:
    """会社データジェネレータ - 架空の日本企業の社内データを生成

    COMPANY_FILE: 会社情報を記述したMarkdownファイル
    """
    _setup_logging(verbose)

    if web:
        from company_data_generator.web import launch_web_ui

        launch_web_ui(port=port)
    else:
        if company_file is None:
            console.print("[red]エラー: COMPANY_FILE を指定してください[/red]")
            sys.exit(1)
        if domain is None:
            console.print("[red]エラー: --domain を指定してください[/red]")
            sys.exit(1)

        asyncio.run(
            _run_generate(
                company_file=company_file,
                domain=domain,
                count=count,
                mode=mode,
                output_dir=output_dir,
            )
        )

if __name__ == "__main__":
    main()
