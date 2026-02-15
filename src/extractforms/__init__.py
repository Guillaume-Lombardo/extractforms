"""ExtractForms package."""

from extractforms.async_runner import run_async
from extractforms.exceptions import (
    AsyncExecutionError,
    BackendError,
    DependencyError,
    ExtractionError,
    PackageError,
    SettingsError,
)
from extractforms.logging import configure_logging, get_logger
from extractforms.settings import Settings, get_settings

__version__ = "0.1.0"

# Initialize package logger at import time via `get_logger`.
logger = get_logger("extractforms")

__all__ = [
    "AsyncExecutionError",
    "BackendError",
    "DependencyError",
    "ExtractionError",
    "PackageError",
    "Settings",
    "SettingsError",
    "__version__",
    "configure_logging",
    "get_logger",
    "get_settings",
    "logger",
    "run_async",
]
