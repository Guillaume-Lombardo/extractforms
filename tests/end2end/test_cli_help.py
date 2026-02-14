from __future__ import annotations

import sys
from subprocess import run as subprocess_run  # noqa: S404


def test_cli_help() -> None:
    result = subprocess_run(  # noqa: S603
        [sys.executable, "-m", "extractforms.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
