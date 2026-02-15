from __future__ import annotations

import pytest

from extractforms.dependencies import ensure_cli_dependencies_for_extract
from extractforms.exceptions import DependencyError


def test_ensure_cli_dependencies_for_extract_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("extractforms.dependencies._is_module_available", lambda module_name: True)
    ensure_cli_dependencies_for_extract()


def test_ensure_cli_dependencies_for_extract_raises(monkeypatch) -> None:
    monkeypatch.setattr("extractforms.dependencies._is_module_available", lambda module_name: False)
    with pytest.raises(DependencyError, match="Missing runtime dependencies"):
        ensure_cli_dependencies_for_extract()
