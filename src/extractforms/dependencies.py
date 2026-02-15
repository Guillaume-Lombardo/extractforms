"""Runtime dependency checks for CLI commands."""

from __future__ import annotations

import importlib.util

from extractforms.exceptions import DependencyError


def _is_module_available(module_name: str) -> bool:
    """Check whether a module can be imported.

    Args:
        module_name: Python module name.

    Returns:
        bool: True if import spec exists.
    """
    return importlib.util.find_spec(module_name) is not None


def ensure_cli_dependencies_for_extract() -> None:
    """Validate required runtime dependencies for `extractforms extract`.

    Raises:
        DependencyError: If one or more required modules are missing.
    """
    missing: list[str] = []

    if not _is_module_available("fitz"):
        missing.append("pymupdf")

    if not _is_module_available("httpx"):
        missing.append("httpx")

    if missing:
        raise DependencyError(missing_package=missing, message="extract")
