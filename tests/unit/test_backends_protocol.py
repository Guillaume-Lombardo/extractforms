from __future__ import annotations

from extractforms.backends import protocol


def test_protocols_are_importable() -> None:
    assert protocol.PageSource is not None
    assert protocol.ExtractorBackend is not None
