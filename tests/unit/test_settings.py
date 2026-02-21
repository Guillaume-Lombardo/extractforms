from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import ValidationError

from extractforms.exceptions import SettingsError
from extractforms.settings import (
    Settings,
    build_httpx_client_kwargs,
    build_ssl_context,
    compile_no_proxy_matchers,
    ensure_env_file_exists,
    get_settings,
)
from extractforms.typing.enums import ExtractionBackendType

if TYPE_CHECKING:
    from pathlib import Path


def test_settings_load_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_payload = (
        f"APP_ENV={'test'}\n"
        f"LOG_LEVEL={'DEBUG'}\n"
        f"LOG_JSON={'false'}\n"
        f"TIMEOUT={12}\n"
        f"MAX_CONNECTIONS={99}\n"
        f"EXTRACTION_BACKEND={'ocr'}\n"
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
    assert settings.extraction_backend == ExtractionBackendType.OCR


def test_settings_rejects_plain_http_openai_base_url_outside_localhost(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://api.example.com/v1")
    with pytest.raises(ValidationError, match="must use https outside local development"):
        Settings()


def test_settings_allows_plain_http_openai_base_url_for_localhost(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:4000/v1")
    settings = Settings()
    assert settings.openai_base_url == "http://localhost:4000/v1"


def test_get_settings_uses_environment(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "ci")

    settings = get_settings()
    assert settings.app_env == "ci"

    get_settings.cache_clear()


def test_get_settings_retries_after_env_template_on_missing(monkeypatch) -> None:
    get_settings.cache_clear()

    attempts = {"count": 0}

    class _DummySettings:
        app_env = "ci"

    def _fake_settings():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("missing")
        return _DummySettings()

    copied = {"done": 0}

    def _mark_env_copied(**kwargs: object) -> None:
        _ = kwargs
        copied["done"] += 1

    monkeypatch.setattr("extractforms.settings.Settings", _fake_settings)
    monkeypatch.setattr("extractforms.settings._is_missing_settings_error", lambda exc: True)
    monkeypatch.setattr("extractforms.settings.ensure_env_file_exists", _mark_env_copied)

    settings = get_settings()
    assert copied["done"] == 1
    assert attempts["count"] == 2
    assert settings.app_env == "ci"

    get_settings.cache_clear()


def test_get_settings_wraps_env_copy_error_on_missing(monkeypatch) -> None:
    get_settings.cache_clear()

    def _fake_settings():
        raise ValueError("missing")

    def _raise_io_error(**kwargs: object) -> None:
        _ = kwargs
        raise OSError("cannot write .env")

    monkeypatch.setattr("extractforms.settings.Settings", _fake_settings)
    monkeypatch.setattr("extractforms.settings._is_missing_settings_error", lambda exc: True)
    monkeypatch.setattr("extractforms.settings.ensure_env_file_exists", _raise_io_error)

    with pytest.raises(SettingsError):
        get_settings()

    get_settings.cache_clear()


def test_get_settings_does_not_copy_env_on_non_missing(monkeypatch) -> None:
    get_settings.cache_clear()

    def _raise_runtime_error():
        raise RuntimeError("boom")

    def _raise_assertion_error(**kwargs: object) -> None:
        _ = kwargs
        raise AssertionError("should not copy env")

    monkeypatch.setattr("extractforms.settings.Settings", _raise_runtime_error)
    monkeypatch.setattr("extractforms.settings._is_missing_settings_error", lambda exc: False)
    monkeypatch.setattr("extractforms.settings.ensure_env_file_exists", _raise_assertion_error)

    with pytest.raises(SettingsError):
        get_settings()

    get_settings.cache_clear()


def test_ensure_env_file_exists_copies_template(tmp_path: Path) -> None:
    template = tmp_path / ".env.template"
    env_file = tmp_path / ".env"
    template.write_text("OPENAI_BASE_URL=https://example.test\n", encoding="utf-8")

    ensure_env_file_exists(env_path=env_file, template_path=template)

    assert env_file.exists()
    assert "OPENAI_BASE_URL" in env_file.read_text(encoding="utf-8")


def test_build_ssl_context_enforces_tls() -> None:
    context = build_ssl_context(Settings())
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2


def test_build_ssl_context_uses_cert_path_when_provided(monkeypatch) -> None:
    class _SettingsStub:
        def __init__(self, cert_path: str | None) -> None:
            self.cert_path = cert_path

    class _FakeContext:
        def __init__(self) -> None:
            self.verify_mode: int | None = None
            self.minimum_version: ssl.TLSVersion | None = None

    calls: list[str | None] = []

    def _fake_create_default_context(*, cafile: str | None = None) -> _FakeContext:
        calls.append(cafile)
        return _FakeContext()

    monkeypatch.setattr("extractforms.settings.ssl.create_default_context", _fake_create_default_context)
    settings = cast("Settings", _SettingsStub("/path/internal-ca.pem"))

    _ = build_ssl_context(settings)

    assert calls == ["/path/internal-ca.pem"]


def test_build_ssl_context_falls_back_to_certifi_when_host_store_empty(monkeypatch) -> None:
    class _SettingsStub:
        def __init__(self, cert_path: str | None) -> None:
            self.cert_path = cert_path

    class _FakeContext:
        def __init__(self) -> None:
            self.verify_mode: int | None = None
            self.minimum_version: ssl.TLSVersion | None = None

    calls: list[str | None] = []

    def _fake_create_default_context(*, cafile: str | None = None) -> _FakeContext:
        calls.append(cafile)
        return _FakeContext()

    monkeypatch.setattr("extractforms.settings.ssl.create_default_context", _fake_create_default_context)
    monkeypatch.setattr("extractforms.settings._cert_store_has_ca", lambda _ctx: False)
    monkeypatch.setattr("extractforms.settings._get_certifi_cafile", lambda: "/path/certifi.pem")

    settings = cast("Settings", _SettingsStub(None))

    _ = build_ssl_context(settings)

    assert calls == [None, "/path/certifi.pem"]


def test_build_ssl_context_keeps_host_store_when_available(monkeypatch) -> None:
    class _SettingsStub:
        def __init__(self, cert_path: str | None) -> None:
            self.cert_path = cert_path

    class _FakeContext:
        def __init__(self) -> None:
            self.verify_mode: int | None = None
            self.minimum_version: ssl.TLSVersion | None = None

    calls: list[str | None] = []

    def _fake_create_default_context(*, cafile: str | None = None) -> _FakeContext:
        calls.append(cafile)
        return _FakeContext()

    monkeypatch.setattr("extractforms.settings.ssl.create_default_context", _fake_create_default_context)
    monkeypatch.setattr("extractforms.settings._cert_store_has_ca", lambda _ctx: True)
    monkeypatch.setattr("extractforms.settings._get_certifi_cafile", lambda: "/path/certifi.pem")

    settings = cast("Settings", _SettingsStub(None))

    _ = build_ssl_context(settings)

    assert calls == [None]


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


def test_build_httpx_client_kwargs_preserves_leading_dot_semantic(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv("NO_PROXY", ".internal.local")
    settings = Settings()

    subdomain_kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://api.internal.local/v1/chat/completions",
    )
    domain_kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://internal.local/v1/chat/completions",
    )

    assert "proxy" not in subdomain_kwargs
    assert domain_kwargs["proxy"] == "http://proxy.local:8080"


def test_build_httpx_client_kwargs_keeps_proxy_when_not_in_no_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv("NO_PROXY", ".internal.local")
    settings = Settings()

    kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://api.external.local/v1/chat/completions",
    )

    assert kwargs["proxy"] == "http://proxy.local:8080"


def test_build_httpx_client_kwargs_respects_no_proxy_host_with_port(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv("NO_PROXY", "api.internal.local:8443")
    settings = Settings()

    kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://api.internal.local/v1/chat/completions",
    )

    assert "proxy" not in kwargs


def test_build_httpx_client_kwargs_respects_no_proxy_wildcard(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv("NO_PROXY", "*")
    settings = Settings()

    kwargs = build_httpx_client_kwargs(
        settings,
        target_url="https://api.anywhere.local/v1/chat/completions",
    )

    assert "proxy" not in kwargs


def test_compile_no_proxy_matchers_supports_wildcard_and_cidr() -> None:
    regex, networks = compile_no_proxy_matchers(
        "localhost, 127.0.0.*, *apim*.banque-france.fr,10.1.70.0/24,10.10.10.10/32,10.200.0.0/24",
    )

    assert regex is not None
    assert regex.fullmatch("localhost")
    assert regex.fullmatch("127.0.0.42")
    assert regex.fullmatch("x-apim-int.banque-france.fr")
    assert not regex.fullmatch("api.banque-france.fr")
    assert len(networks) == 3


def test_settings_should_bypass_proxy_with_regex_and_network(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    monkeypatch.setenv(
        "NO_PROXY",
        "localhost, 127.0.0.*, *apim*.banque-france.fr,10.1.70.0/24",
    )
    settings = Settings()

    assert settings.should_bypass_proxy("https://localhost/v1")
    assert settings.should_bypass_proxy("https://abc-apim-int.banque-france.fr/v1")
    assert settings.should_bypass_proxy("https://10.1.70.42/v1")
    assert not settings.should_bypass_proxy("https://api.openai.com/v1")


def test_settings_initializes_httpx_clients() -> None:
    settings = Settings()

    assert "sync_proxy" in settings.httpx_clients
    assert "sync_no_proxy" in settings.httpx_clients
    assert "async_proxy" in settings.httpx_clients
    assert "async_no_proxy" in settings.httpx_clients
    settings.close_httpx_clients()
    assert settings.httpx_clients == {}


def test_settings_rejects_non_http_openai_base_url(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "file:///tmp/socket")
    with pytest.raises(ValidationError, match="http or https"):
        Settings()


def test_settings_rejects_openai_base_url_without_host(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https:///v1")
    with pytest.raises(ValidationError, match="hostname"):
        Settings()


def test_settings_strips_openai_base_url_whitespace(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "  https://api.example.local/v1  ")
    settings = Settings()
    assert settings.openai_base_url == "https://api.example.local/v1"
