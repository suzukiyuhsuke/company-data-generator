"""prompt_store.py のテスト"""

from pathlib import Path

from company_data_generator.prompt_store import PromptStore


class TestPromptStore:
    def test_render_simple(self, tmp_path: Path) -> None:
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test.md.j2").write_text(
            "Hello {{ name }}! Domain: {{ domain }}", encoding="utf-8"
        )

        store = PromptStore(template_dir)
        result = store.render("test.md.j2", name="World", domain="営業")
        assert result == "Hello World! Domain: 営業"

    def test_render_with_loop(self, tmp_path: Path) -> None:
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "loop.md.j2").write_text(
            "{% for item in items %}- {{ item }}\n{% endfor %}",
            encoding="utf-8",
        )

        store = PromptStore(template_dir)
        result = store.render("loop.md.j2", items=["a", "b", "c"])
        assert "- a" in result
        assert "- b" in result
        assert "- c" in result

    def test_render_with_conditionals(self, tmp_path: Path) -> None:
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "cond.md.j2").write_text(
            "{% if flag %}YES{% else %}NO{% endif %}",
            encoding="utf-8",
        )

        store = PromptStore(template_dir)
        assert store.render("cond.md.j2", flag=True) == "YES"
        assert store.render("cond.md.j2", flag=False) == "NO"
