"""Runtime settings loaded from `.env` and environment variables."""

from __future__ import annotations

import ssl
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from extractforms.exceptions import SettingsError


class Settings(BaseSettings):
    """Package settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "extractforms"
    app_env: str = Field(
        default="dev",
        validation_alias="APP_ENV",
        description="Application environment, e.g. 'dev', 'prod'.",
    )

    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Logging level, e.g. 'INFO', 'DEBUG'.",
    )
    log_json: bool = Field(
        default=True,
        validation_alias="LOG_JSON",
        description="Enable JSON formatted logs.",
    )
    log_file: str | None = Field(
        default=None,
        validation_alias="LOG_FILE",
        description="File path for log output.",
    )
    http_proxy: str | None = Field(default=None, validation_alias="HTTP_PROXY", description="HTTP proxy URL.")
    https_proxy: str | None = Field(
        default=None,
        validation_alias="HTTPS_PROXY",
        description="HTTPS proxy URL.",
    )
    all_proxy: str | None = Field(default=None, validation_alias="ALL_PROXY", description="All proxy URL.")
    no_proxy: str | None = Field(
        default=None,
        validation_alias="NO_PROXY",
        description="Comma-separated list of hosts to bypass proxy.",
    )

    cert_path: str | None = Field(
        default=None,
        validation_alias="CERT_PATH",
        description="Path to SSL certificate.",
    )
    timeout: float = Field(
        default=30.0,
        validation_alias="TIMEOUT",
        description="Request timeout in seconds.",
    )
    max_connections: int = Field(
        default=20,
        validation_alias="MAX_CONNECTIONS",
        description="Maximum number of concurrent connections.",
    )

    openai_base_url: str | None = Field(
        default=None,
        validation_alias="OPENAI_BASE_URL",
        description="Base URL for OpenAI API.",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        description="API key for OpenAI.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_MODEL",
        description="OpenAI model to use.",
    )

    results_dir: str = Field(
        default="results",
        validation_alias="RESULTS_DIR",
        description="Directory to store results.",
    )
    schema_cache_dir: str = Field(
        default="results/schemas",
        validation_alias="SCHEMA_CACHE_DIR",
        description="Directory to cache schemas.",
    )
    null_sentinel: str = Field(
        default="NULL",
        validation_alias="NULL_SENTINEL",
        description="Sentinel value for null fields.",
    )


def build_ssl_context(settings: Settings) -> ssl.SSLContext:
    """Build a strict SSL context from settings.

    Args:
        settings: Runtime settings.

    Returns:
        ssl.SSLContext: Configured TLS context.
    """
    ssl_context = ssl.create_default_context(cafile=settings.cert_path)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    return ssl_context


def _normalize_no_proxy_entry(raw_entry: str) -> str:
    """Normalize one NO_PROXY entry for hostname matching.

    Args:
        raw_entry: Raw NO_PROXY entry.

    Returns:
        str: Normalized hostname pattern.
    """
    entry = raw_entry.lower()
    # Prefix with // so urlparse can split host:port even without scheme.
    hostname = urlparse(entry).hostname if "://" in entry else urlparse(f"//{entry}").hostname
    normalized = (hostname or entry).lower()
    return normalized.strip("[]").removeprefix(".")


def _is_no_proxy_target(target_url: str | None, no_proxy: str | None) -> bool:
    """Return whether the target URL should bypass proxies.

    Args:
        target_url: Target request URL.
        no_proxy: Comma-separated no-proxy entries.

    Returns:
        bool: True when proxy must be bypassed.
    """
    if not target_url or not no_proxy:
        return False

    parsed = urlparse(target_url)
    hostname = parsed.hostname
    if not hostname:
        return False

    host = hostname.lower().strip("[]")
    for raw_entry in (entry.strip() for entry in no_proxy.split(",")):
        if not raw_entry:
            continue
        if raw_entry == "*":
            return True

        entry = _normalize_no_proxy_entry(raw_entry)
        if not entry:
            continue

        if host == entry or host.endswith(f".{entry}"):
            return True

    return False


def build_httpx_client_kwargs(
    settings: Settings,
    *,
    target_url: str | None = None,
) -> dict[str, Any]:
    """Build kwargs used for `httpx.Client` and `httpx.AsyncClient`.

    Args:
        settings: Runtime settings.
        target_url: Optional target URL used for NO_PROXY evaluation.

    Returns:
        dict[str, Any]: Arguments for client constructors.
    """
    proxy_url = settings.https_proxy or settings.http_proxy or settings.all_proxy

    kwargs: dict[str, Any] = {
        "verify": build_ssl_context(settings),
        "timeout": settings.timeout,
    }

    if proxy_url and not _is_no_proxy_target(target_url, settings.no_proxy):
        kwargs["proxy"] = proxy_url

    return kwargs


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance.

    Raises:
        SettingsError: If settings cannot be loaded or validated.

    Returns:
        Settings: The loaded settings instance.
    """
    try:
        return Settings()
    except Exception as exc:
        raise SettingsError(exc=exc) from exc
