from __future__ import annotations

from typing import TYPE_CHECKING

from extractforms.settings import Settings, get_settings

if TYPE_CHECKING:
    from pathlib import Path


def test_settings_load_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=test\nLOG_LEVEL=DEBUG\nLOG_JSON=false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.log_json is False


def test_get_settings_uses_environment(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "ci")

    settings = get_settings()
    assert settings.app_env == "ci"

    get_settings.cache_clear()
