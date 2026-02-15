"""Runtime settings loaded from `.env` and environment variables."""

from __future__ import annotations

import ssl
from functools import lru_cache
from typing import Any

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
    app_env: str = Field(default="dev", validation_alias="APP_ENV")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=True, validation_alias="LOG_JSON")
    log_file: str | None = Field(default=None, validation_alias="LOG_FILE")

    http_proxy: str | None = Field(default=None, validation_alias="HTTP_PROXY")
    https_proxy: str | None = Field(default=None, validation_alias="HTTPS_PROXY")
    all_proxy: str | None = Field(default=None, validation_alias="ALL_PROXY")
    no_proxy: str | None = Field(default=None, validation_alias="NO_PROXY")

    cert_path: str | None = Field(default=None, validation_alias="CERT_PATH")
    timeout: float = Field(default=30.0, validation_alias="TIMEOUT")
    max_connections: int = Field(default=20, validation_alias="MAX_CONNECTIONS")

    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    results_dir: str = Field(default="results", validation_alias="RESULTS_DIR")
    schema_cache_dir: str = Field(default="results/schemas", validation_alias="SCHEMA_CACHE_DIR")
    null_sentinel: str = Field(default="NULL", validation_alias="NULL_SENTINEL")


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


def build_httpx_client_kwargs(settings: Settings) -> dict[str, Any]:
    """Build kwargs used for `httpx.Client` and `httpx.AsyncClient`.

    Args:
        settings: Runtime settings.

    Returns:
        dict[str, Any]: Arguments for client constructors.
    """
    proxy_url = settings.https_proxy or settings.http_proxy or settings.all_proxy

    kwargs: dict[str, Any] = {
        "verify": build_ssl_context(settings),
        "timeout": settings.timeout,
    }

    if proxy_url:
        # `proxy` is accepted in modern httpx versions.
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
