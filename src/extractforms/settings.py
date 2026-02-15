"""Runtime settings loaded from `.env` and environment variables."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import ssl
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, PrivateAttr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from extractforms.exceptions import SettingsError

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency at runtime
    httpx: Any
    httpx = None

NoProxyNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
NoProxyRegex = re.Pattern[str]
logger = logging.getLogger(__name__)


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
    _no_proxy_regex: NoProxyRegex | None = PrivateAttr(default=None)
    _no_proxy_networks: tuple[NoProxyNetwork, ...] = PrivateAttr(default=())
    _httpx_clients: dict[str, object] = PrivateAttr(default_factory=dict)
    _close_tasks: set[asyncio.Task[None]] = PrivateAttr(default_factory=set)

    def model_post_init(self, __context: object, /) -> None:
        """Initialize derived runtime settings."""
        self._no_proxy_regex, self._no_proxy_networks = compile_no_proxy_matchers(self.no_proxy)
        self._initialize_httpx_clients()

    @property
    def no_proxy_regex(self) -> NoProxyRegex | None:
        """Return compiled NO_PROXY regex."""
        return self._no_proxy_regex

    @property
    def no_proxy_networks(self) -> tuple[NoProxyNetwork, ...]:
        """Return parsed NO_PROXY CIDR networks."""
        return self._no_proxy_networks

    @property
    def httpx_clients(self) -> dict[str, object]:
        """Return cached HTTPX clients."""
        return self._httpx_clients

    def should_bypass_proxy(self, target_url: str | None) -> bool:
        """Return whether the URL should bypass proxies."""
        return _is_no_proxy_target(target_url, self)

    def select_sync_httpx_client(self, target_url: str | None) -> object | None:
        """Return sync HTTPX client selected for target URL."""
        if not self._httpx_clients:
            return None
        if self.should_bypass_proxy(target_url):
            return self._httpx_clients["sync_no_proxy"]
        return self._httpx_clients["sync_proxy"]

    def select_async_httpx_client(self, target_url: str | None) -> object | None:
        """Return async HTTPX client selected for target URL."""
        if not self._httpx_clients:
            return None
        if self.should_bypass_proxy(target_url):
            return self._httpx_clients["async_no_proxy"]
        return self._httpx_clients["async_proxy"]

    def _initialize_httpx_clients(self) -> None:
        """Create and cache sync/async HTTPX clients for proxy and no-proxy paths."""
        if httpx is None:
            self._httpx_clients = {}
            return

        sync_proxy_kwargs = build_httpx_client_kwargs(self)
        sync_no_proxy_kwargs = build_httpx_client_kwargs(self, force_no_proxy=True)
        limits = httpx.Limits(max_connections=self.max_connections)

        self._httpx_clients = {
            "sync_proxy": httpx.Client(**sync_proxy_kwargs, limits=limits),
            "sync_no_proxy": httpx.Client(**sync_no_proxy_kwargs, limits=limits),
            "async_proxy": httpx.AsyncClient(**sync_proxy_kwargs, limits=limits),
            "async_no_proxy": httpx.AsyncClient(**sync_no_proxy_kwargs, limits=limits),
        }

    def close_httpx_clients(self) -> None:
        """Close cached sync/async HTTPX clients (best effort)."""
        if not self._httpx_clients:
            return

        self._close_sync_clients(("sync_proxy", "sync_no_proxy"))
        async_clients = (
            ("async_proxy", self._httpx_clients.get("async_proxy")),
            ("async_no_proxy", self._httpx_clients.get("async_no_proxy")),
        )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._aclose_async_clients(async_clients))
        else:
            task = loop.create_task(self._aclose_async_clients(async_clients))
            self._close_tasks.add(task)
            task.add_done_callback(self._on_close_task_done)

        self._httpx_clients = {}

    async def aclose_httpx_clients(self) -> None:
        """Asynchronously close cached sync/async HTTPX clients."""
        if not self._httpx_clients:
            return

        self._close_sync_clients(("sync_proxy", "sync_no_proxy"))
        await self._aclose_async_clients(
            (
                ("async_proxy", self._httpx_clients.get("async_proxy")),
                ("async_no_proxy", self._httpx_clients.get("async_no_proxy")),
            ),
        )

        self._httpx_clients = {}

    def _close_sync_clients(self, keys: tuple[str, ...]) -> None:
        """Close sync HTTPX clients with best effort."""
        for key in keys:
            client = self._httpx_clients.get(key)
            close = getattr(client, "close", None)
            if not close:
                continue
            try:
                close()
            except Exception:
                logger.warning("Failed to close sync HTTPX client", extra={"client_key": key})

    @staticmethod
    async def _aclose_async_clients(
        clients: tuple[tuple[str, object | None], ...],
    ) -> None:
        """Close async HTTPX clients with best effort."""
        for key, client in clients:
            aclose = getattr(client, "aclose", None)
            if not aclose:
                continue
            try:
                await aclose()
            except Exception:
                logger.warning("Failed to close async HTTPX client", extra={"client_key": key})

    def _on_close_task_done(self, task: asyncio.Task[None]) -> None:
        """Handle completion of async close tasks."""
        self._close_tasks.discard(task)
        try:
            task.result()
        except Exception:
            logger.warning("Async HTTPX close task failed")


def build_ssl_context(settings: Settings) -> ssl.SSLContext:
    """Build a strict SSL context from settings.

    Args:
        settings (Settings): Runtime settings.

    Returns:
        ssl.SSLContext: Configured TLS context.
    """
    ssl_context = ssl.create_default_context(cafile=settings.cert_path)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    return ssl_context


def _iter_no_proxy_entries(no_proxy: str | None) -> list[str]:
    """Split NO_PROXY into normalized entries.

    Args:
        no_proxy (str | None): Raw NO_PROXY value.

    Returns:
        list[str]: Normalized entries.
    """
    if not no_proxy:
        return []
    return [entry.strip() for entry in no_proxy.split(",") if entry.strip()]


def _normalize_no_proxy_host(entry: str) -> str:
    """Normalize host entry from NO_PROXY.

    Args:
        entry (str): Raw NO_PROXY entry.

    Returns:
        str: Host expression usable for host matching.
    """
    candidate = entry.lower().strip()
    if "://" in candidate:
        candidate = (urlparse(candidate).hostname or "").lower()
    else:
        parsed = urlparse(f"//{candidate}")
        if parsed.hostname:
            candidate = parsed.hostname.lower()
    return candidate.strip("[]").removeprefix(".")


def _compile_no_proxy_regex(no_proxy: str | None) -> NoProxyRegex | None:
    """Compile NO_PROXY host/wildcard entries as one regex.

    Args:
        no_proxy (str | None): Raw NO_PROXY value.

    Returns:
        NoProxyRegex | None: Compiled regex for host matching.
    """
    entries = _iter_no_proxy_entries(no_proxy)
    if not entries:
        return None

    regex_parts: list[str] = []
    for entry in entries:
        subdomain_only = entry.startswith(".")
        if entry == "*":
            return re.compile(r"^.*$", re.IGNORECASE)

        try:
            ipaddress.ip_network(entry, strict=False)
            continue
        except ValueError:
            pass

        host_pattern = _normalize_no_proxy_host(entry)
        if not host_pattern:
            continue

        escaped = re.escape(host_pattern).replace(r"\*", ".*")
        if "*" in host_pattern or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host_pattern):
            regex_parts.append(escaped)
        elif subdomain_only:
            regex_parts.append(rf"(?:.*\.){escaped}")
        else:
            regex_parts.append(rf"(?:{escaped}|(?:.*\.){escaped})")

    if not regex_parts:
        return None
    return re.compile(rf"^(?:{'|'.join(regex_parts)})$", re.IGNORECASE)


def _parse_no_proxy_networks(no_proxy: str | None) -> tuple[NoProxyNetwork, ...]:
    """Parse CIDR entries from NO_PROXY.

    Args:
        no_proxy (str | None): Raw NO_PROXY value.

    Returns:
        tuple[NoProxyNetwork, ...]: Parsed networks.
    """
    networks: list[NoProxyNetwork] = []
    for entry in _iter_no_proxy_entries(no_proxy):
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        networks.append(network)
    return tuple(networks)


def compile_no_proxy_matchers(no_proxy: str | None) -> tuple[NoProxyRegex | None, tuple[NoProxyNetwork, ...]]:
    """Compile NO_PROXY regex and CIDR networks.

    Args:
        no_proxy (str | None): Raw NO_PROXY value.

    Returns:
        tuple[NoProxyRegex | None, tuple[NoProxyNetwork, ...]]: Compiled host regex and networks.
    """
    return _compile_no_proxy_regex(no_proxy), _parse_no_proxy_networks(no_proxy)


def _is_no_proxy_target(target_url: str | None, settings: Settings) -> bool:
    """Return whether the target URL should bypass proxies.

    Args:
        target_url (str | None): Target request URL.
        settings (Settings): Runtime settings.

    Returns:
        bool: True when proxy must be bypassed.
    """
    if not target_url:
        return False

    hostname = urlparse(target_url).hostname
    if not hostname:
        return False

    host = hostname.lower().strip("[]")
    regex = settings.no_proxy_regex
    if regex and regex.fullmatch(host):
        return True

    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(host_ip in network for network in settings.no_proxy_networks)


def build_httpx_client_kwargs(
    settings: Settings,
    *,
    target_url: str | None = None,
    force_no_proxy: bool = False,
) -> dict[str, Any]:
    """Build kwargs used for `httpx.Client` and `httpx.AsyncClient`.

    Args:
        settings (Settings): Runtime settings.
        target_url (str | None): Optional target URL used for NO_PROXY evaluation.
        force_no_proxy (bool): If true, always build kwargs without proxy.

    Returns:
        dict[str, Any]: Arguments for client constructors.
    """
    proxy_url = settings.https_proxy or settings.http_proxy or settings.all_proxy

    kwargs: dict[str, Any] = {
        "verify": build_ssl_context(settings),
        "timeout": settings.timeout,
    }

    should_bypass = force_no_proxy or _is_no_proxy_target(target_url, settings)
    if proxy_url and not should_bypass:
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
        if _is_missing_settings_error(exc):
            ensure_env_file_exists()
            try:
                return Settings()
            except Exception as retry_exc:
                raise SettingsError(exc=retry_exc) from retry_exc
        raise SettingsError(exc=exc) from exc


def ensure_env_file_exists(
    *,
    env_path: Path = Path(".env"),
    template_path: Path = Path(".env.template"),
) -> None:
    """Create `.env` from template when missing.

    Args:
        env_path (Path): Target environment file path.
        template_path (Path): Template file path.
    """
    if env_path.exists() or not template_path.exists():
        return
    env_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    logger.info(
        "Created environment file from template",
        extra={"env_path": str(env_path), "template_path": str(template_path)},
    )


def _is_missing_settings_error(exc: Exception) -> bool:
    """Return whether the settings failure is due to missing values.

    Args:
        exc (Exception): Caught settings initialization error.

    Returns:
        bool: True when the error represents missing settings values.
    """
    if not isinstance(exc, ValidationError):
        return False
    return any(error.get("type") == "missing" for error in exc.errors())
