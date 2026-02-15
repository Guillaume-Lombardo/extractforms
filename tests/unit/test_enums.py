from __future__ import annotations

import pytest

from extractforms.typing.enums import ConfidenceLevel


def test_confidence_level_from_str() -> None:
    assert ConfidenceLevel.from_str("high") == ConfidenceLevel.HIGH


def test_confidence_level_from_str_raises_on_invalid_value() -> None:
    with pytest.raises(ValueError):
        ConfidenceLevel.from_str("very-high")
