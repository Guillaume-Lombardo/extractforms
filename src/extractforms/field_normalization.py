"""Typed field value normalization helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from extractforms.typing.enums import FieldKind, FieldSemanticType

if TYPE_CHECKING:
    from extractforms.typing.models import SchemaField


def normalize_typed_value(
    *,
    value: str,
    schema_field: SchemaField,
    null_sentinel: str,
) -> str:
    """Normalize field values based on schema typing metadata.

    Args:
        value (str): Raw extracted value.
        schema_field (SchemaField): Schema field descriptor.
        null_sentinel (str): Null sentinel value.

    Returns:
        str: Normalized value.
    """
    stripped = value.strip()
    if not stripped or stripped == null_sentinel:
        return null_sentinel

    semantic_type = schema_field.semantic_type
    kind = schema_field.kind
    normalized = stripped

    if semantic_type == FieldSemanticType.PHONE or kind == FieldKind.PHONE:
        normalized = _normalize_phone(stripped)
    elif semantic_type == FieldSemanticType.AMOUNT or kind == FieldKind.AMOUNT:
        normalized = _normalize_decimal(stripped)
    elif semantic_type == FieldSemanticType.PERCENTAGE:
        normalized = _normalize_percentage(stripped)
    elif semantic_type == FieldSemanticType.ADDRESS or kind == FieldKind.ADDRESS:
        normalized = " ".join(stripped.split())
    elif semantic_type == FieldSemanticType.EMAIL or kind == FieldKind.EMAIL:
        normalized = stripped.lower()

    return normalized


def _normalize_phone(value: str) -> str:
    compact = "".join(ch for ch in value if ch.isdigit() or ch == "+")
    if compact.startswith("00"):
        return "+" + compact[2:]
    if compact.count("+") > 1:
        return compact.replace("+", "")
    return compact


def _normalize_decimal(value: str) -> str:
    compact = value.replace(" ", "").replace(",", ".")
    try:
        number = Decimal(compact)
    except InvalidOperation:
        return value
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _normalize_percentage(value: str) -> str:
    compact = value.replace("%", "").strip()
    normalized = _normalize_decimal(compact)
    return f"{normalized}%"
