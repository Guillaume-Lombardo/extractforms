"""Runtime dependency checks for CLI commands."""

from __future__ import annotations

import importlib.util

from extractforms.exceptions import DependencyError


def _is_module_available(module_name: str) -> bool:
    """Check whether a module can be imported.

    Args:
        module_name (str): Python module name.

    Returns:
        bool: True if import spec exists.
    """
    return importlib.util.find_spec(module_name) is not None


def _collect_missing_dependencies(modules_by_package: dict[str, str]) -> list[str]:
    """Collect missing packages for a module mapping.

    Args:
        modules_by_package (Mapping[str, str]): Mapping of package name -> import module.

    Returns:
        list[str]: Missing package names.
    """
    return [package for package, module in modules_by_package.items() if not _is_module_available(module)]


def ensure_package_dependencies() -> None:
    """Validate required dependencies at package import time.

    Raises:
        DependencyError: If required runtime dependencies are missing.
    """
    missing = _collect_missing_dependencies(
        {
            "httpx": "httpx",
            "openai": "openai",
            "certifi": "certifi",
        },
    )
    if missing:
        raise DependencyError(missing_package=missing, message="package import")


def ensure_cli_dependencies_for_extract() -> None:
    """Validate required runtime dependencies for `extractforms extract`.

    Raises:
        DependencyError: If one or more required modules are missing.
    """
    missing = _collect_missing_dependencies(
        {
            "pymupdf": "fitz",
            "httpx": "httpx",
            "openai": "openai",
        },
    )

    if missing:
        raise DependencyError(missing_package=missing, message="extract")
