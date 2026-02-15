"""Pytest marker auto-assignment by folder."""

from __future__ import annotations
from extractforms import logger

from pathlib import Path

import pytest


def _mark_tests_by_directory(
    config: pytest.Config,
    items: list[pytest.Item],
    marker: str,
) -> None:
    """Mark collected tests located under tests/<marker>/."""
    target_dir = Path(config.rootpath) / "tests" / marker
    target_dir = target_dir.resolve()

    for item in items:
        try:
            path = Path(str(item.fspath)).resolve()
        except Exception:
            logger.warning(
                f"Could not resolve path for test item {item.name!s}; skipping {marker!s} marker assignment",
            )
            continue

        if path == target_dir or target_dir in path.parents:
            item.add_marker(getattr(pytest.mark, marker))


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Apply directory-based markers to test items."""
    _mark_tests_by_directory(config, items, "unit")
    _mark_tests_by_directory(config, items, "integration")
    _mark_tests_by_directory(config, items, "end2end")
