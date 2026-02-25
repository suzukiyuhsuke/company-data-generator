"""config.py のテスト"""

from pathlib import Path

import pytest

from company_data_generator.config import Config


class TestConfig:
    def test_defaults(self) -> None:
        config = Config(azure_endpoint="https://test.example.com")
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_values(self, tmp_path: Path) -> None:
        config = Config(
            azure_endpoint="https://test.example.com",
            temperature=0.5,
            max_tokens=8192,
            prompts_dir=tmp_path,
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 8192
        assert config.prompts_dir == tmp_path

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://env-test.example.com")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        monkeypatch.setenv("LLM_MAX_TOKENS", "2048")

        config = Config.from_env()
        assert config.azure_endpoint == "https://env-test.example.com"
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
