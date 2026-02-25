"""プロンプトテンプレートの管理"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptStore:
    """プロンプトテンプレートの管理

    Jinja2テンプレートを読み込み、コンテキストに応じてレンダリングする。
    """

    def __init__(self, template_dir: Path) -> None:
        """prompts/ ディレクトリからテンプレートを読み込む

        Args:
            template_dir: テンプレートが格納されたディレクトリのパス
        """
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **kwargs: object) -> str:
        """テンプレートをレンダリングして文字列を返す

        Args:
            template_name: テンプレートファイル名 (例: "collect_info.md.j2")
            **kwargs: テンプレートに渡す変数

        Returns:
            レンダリングされた文字列
        """
        template = self.env.get_template(template_name)
        return template.render(**kwargs)
