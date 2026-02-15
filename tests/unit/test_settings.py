from __future__ import annotations

import ssl
from typing import TYPE_CHECKING

from extractforms.settings import Settings, build_httpx_client_kwargs, build_ssl_context, get_settings

if TYPE_CHECKING:
    from pathlib import Path


def test_settings_load_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_payload = (
        f"APP_ENV={'test'}\nLOG_LEVEL={'DEBUG'}\nLOG_JSON={'false'}\nTIMEOUT={12}\nMAX_CONNECTIONS={99}\n"
    )
    env_file.write_text(
        env_payload,
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.log_json is False
    assert settings.timeout == 12
    assert settings.max_connections == 99


def test_get_settings_uses_environment(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "ci")

    settings = get_settings()
    assert settings.app_env == "ci"

    get_settings.cache_clear()


def test_build_ssl_context_enforces_tls() -> None:
    context = build_ssl_context(Settings())
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2


def test_build_httpx_client_kwargs_uses_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    settings = Settings()

    kwargs = build_httpx_client_kwargs(settings)

    assert kwargs["timeout"] == settings.timeout
    assert kwargs["proxy"] == "http://proxy.local:8080"


def test_build_httpx_client_kwargs_respects_no_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv("NO_PROXY", ".internal.local,localhost")
    settings = Settings()

    kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://api.internal.local/v1/chat/completions",
    )

    assert kwargs["timeout"] == settings.timeout
    assert "proxy" not in kwargs


def test_build_httpx_client_kwargs_keeps_proxy_when_not_in_no_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv("NO_PROXY", ".internal.local")
    settings = Settings()

    kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://api.external.local/v1/chat/completions",
    )

    assert kwargs["proxy"] == "http://proxy.local:8080"
