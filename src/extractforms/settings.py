"""Runtime settings loaded from `.env` and environment variables."""

from __future__ import annotations

from functools import lru_cache

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
