from __future__ import annotations

import pytest

from extractforms.typing.enums import ConfidenceLevel, FieldSemanticType


def test_confidence_level_from_str() -> None:
    assert ConfidenceLevel.from_str("high") == ConfidenceLevel.HIGH


def test_confidence_level_from_str_raises_on_invalid_value() -> None:
    with pytest.raises(ValueError, match="Unsupported ConfidenceLevel value"):
        ConfidenceLevel.from_str("very-high")


def test_field_semantic_type_from_str() -> None:
    assert FieldSemanticType.from_str("phone") == FieldSemanticType.PHONE
