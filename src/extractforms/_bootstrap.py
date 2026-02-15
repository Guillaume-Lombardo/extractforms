"""Package bootstrap helpers."""

from extractforms.dependencies import ensure_package_dependencies
from extractforms.logging import get_logger

ensure_package_dependencies()

logger = get_logger("extractforms")

__all__ = ["logger"]
