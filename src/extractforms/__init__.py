"""ExtractForms package."""

from extractforms._bootstrap import logger
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

__version__ = "0.2.0"

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
