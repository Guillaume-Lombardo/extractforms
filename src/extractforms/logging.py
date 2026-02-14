"""Structlog configuration for package-wide logging."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

from extractforms.settings import Settings, get_settings

if TYPE_CHECKING:
    from structlog.typing import EventDict

_LOGGING_CONFIGURED = False


def _rename_event_key(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: EventDict,
) -> EventDict:
    """Normalize structlog payload keys.

    Args:
        logger: The logger instance (unused).
        method_name: The logging method name (unused).
        event_dict: The original event dictionary.

    Returns:
        The modified event dictionary with "message" key instead of "event".
    """
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def configure_logging(*, settings: Settings | None = None, force: bool = False) -> None:
    """Configure structlog and stdlib logging once for the package."""
    global _LOGGING_CONFIGURED  # noqa: PLW0603

    if _LOGGING_CONFIGURED and not force:
        return

    config = settings or get_settings()
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if config.log_file:
        handlers.append(logging.FileHandler(config.log_file, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=handlers,
        force=force,
    )

    renderer: Any = structlog.processors.JSONRenderer()
    if not config.log_json:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _rename_event_key,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _LOGGING_CONFIGURED = True


def get_logger(name: str = "extractforms") -> structlog.BoundLogger:
    """Return package logger, configuring logging lazily."""
    if not _LOGGING_CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
