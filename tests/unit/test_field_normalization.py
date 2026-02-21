from __future__ import annotations

from extractforms.field_normalization import normalize_typed_value
from extractforms.typing.enums import FieldKind, FieldSemanticType
from extractforms.typing.models import SchemaField


def test_normalize_phone_value() -> None:
    schema_field = SchemaField(
        key="phone",
        label="Phone",
        kind=FieldKind.PHONE,
        semantic_type=FieldSemanticType.PHONE,
    )

    normalized = normalize_typed_value(
        value="00 33 6 12 34 56 78",
        schema_field=schema_field,
        null_sentinel="NULL",
    )

    assert normalized == "+33612345678"


def test_normalize_amount_value() -> None:
    schema_field = SchemaField(
        key="amount",
        label="Amount",
        kind=FieldKind.AMOUNT,
        semantic_type=FieldSemanticType.AMOUNT,
    )

    normalized = normalize_typed_value(value="1 234,50", schema_field=schema_field, null_sentinel="NULL")

    assert normalized == "1234.5"


def test_normalize_address_value() -> None:
    schema_field = SchemaField(
        key="address",
        label="Address",
        kind=FieldKind.ADDRESS,
        semantic_type=FieldSemanticType.ADDRESS,
    )

    normalized = normalize_typed_value(
        value=" 10   rue   de la Paix ",
        schema_field=schema_field,
        null_sentinel="NULL",
    )

    assert normalized == "10 rue de la Paix"


def test_normalize_email_value() -> None:
    schema_field = SchemaField(
        key="email",
        label="Email",
        kind=FieldKind.EMAIL,
        semantic_type=FieldSemanticType.EMAIL,
    )

    normalized = normalize_typed_value(
        value="John.DOE@Example.org",
        schema_field=schema_field,
        null_sentinel="NULL",
    )

    assert normalized == "john.doe@example.org"


def test_normalize_percentage_value() -> None:
    schema_field = SchemaField(
        key="rate",
        label="Rate",
        semantic_type=FieldSemanticType.PERCENTAGE,
    )

    normalized = normalize_typed_value(
        value="12,5 %",
        schema_field=schema_field,
        null_sentinel="NULL",
    )

    assert normalized == "12.5%"
