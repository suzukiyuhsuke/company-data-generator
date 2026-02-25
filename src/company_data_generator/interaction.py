"""ユーザ対話プロトコルと実装"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

if TYPE_CHECKING:
    from company_data_generator.models import DocumentPlanList, GeneratedDocument


@runtime_checkable
class UserInteraction(Protocol):
    """ユーザ対話の抽象プロトコル

    CLIとWebUIの両方がこのプロトコルを実装し、
    Runner / Agent は具体的なUIを意識せずにユーザとやり取りできる。
    """

    async def ask(self, question: str, choices: list[str] | None = None) -> str:
        """ユーザに質問して回答を得る"""
        ...

    async def confirm(self, message: str) -> bool:
        """ユーザに確認を求める (Yes/No)"""
        ...

    async def show_progress(self, current: int, total: int, message: str) -> None:
        """進捗を表示する"""
        ...

    async def display_plan(self, plan: DocumentPlanList) -> None:
        """ドキュメント計画を表示する"""
        ...

    async def display_result(self, document: GeneratedDocument) -> None:
        """生成結果を表示する"""
        ...

    async def notify(self, message: str) -> None:
        """ユーザに情報を通知する（応答不要）"""
        ...


class CLIInteraction:
    """CLIベースのユーザ対話実装"""

    def __init__(self) -> None:
        self.console = Console()

    async def ask(self, question: str, choices: list[str] | None = None) -> str:
        """ユーザに質問して回答を得る"""
        if choices:
            self.console.print(f"\n[bold]{question}[/bold]")
            for i, choice in enumerate(choices, 1):
                self.console.print(f"  {i}. {choice}")
            answer = Prompt.ask("選択してください (番号)")
            try:
                idx = int(answer) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            except ValueError:
                pass
            return answer
        else:
            return Prompt.ask(f"\n[bold]{question}[/bold]")

    async def confirm(self, message: str) -> bool:
        """ユーザに確認を求める (Yes/No)"""
        return Confirm.ask(message)

    async def show_progress(self, current: int, total: int, message: str) -> None:
        """進捗を表示する"""
        self.console.print(f"  [{current}/{total}] {message}")

    async def display_plan(self, plan: DocumentPlanList) -> None:
        """ドキュメント計画を表示する"""
        table = Table(title=f"ドキュメント計画 - {plan.domain}")
        table.add_column("#", style="dim", width=4)
        table.add_column("タイトル", style="bold")
        table.add_column("種別")
        table.add_column("概要", max_width=40)
        table.add_column("図", justify="center")
        table.add_column("量")

        for i, p in enumerate(plan.plans, 1):
            table.add_row(
                str(i),
                p.title,
                p.doc_type,
                p.summary[:40] + "..." if len(p.summary) > 40 else p.summary,
                "✓" if p.includes_diagram else "",
                p.estimated_length,
            )

        self.console.print()
        self.console.print(table)

    async def display_result(self, document: GeneratedDocument) -> None:
        """生成結果を表示する"""
        self.console.print(f"  ✓ [green]{document.filename}[/green] を生成しました")

    async def notify(self, message: str) -> None:
        """ユーザに情報を通知する（応答不要）"""
        self.console.print(f"\n[dim]{message}[/dim]")
