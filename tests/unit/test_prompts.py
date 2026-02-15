from __future__ import annotations

from extractforms.models import SchemaField, SchemaSpec
from extractforms.prompts import (
    build_schema_inference_prompt,
    build_values_extraction_prompt,
    sanitize_json_schema,
    schema_response_format,
)


def test_sanitize_json_schema_sets_required_and_forbids_additional_properties() -> None:
    raw = {
        "type": "object",
        "properties": {
            "foo": {"type": "string"},
            "bar": {"type": "number"},
        },
    }

    cleaned = sanitize_json_schema(raw)

    assert cleaned["required"] == ["bar", "foo"]
    assert cleaned["additionalProperties"] is False


def test_schema_response_format_is_strict() -> None:
    result = schema_response_format("x", {"type": "object", "properties": {"k": {"type": "string"}}})

    assert result.strict is True
    assert result.name == "x"


def test_prompt_builders_include_extra_instructions() -> None:
    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A")],
    )

    schema_prompt = build_schema_inference_prompt(extra_instructions="extra")
    value_prompt = build_values_extraction_prompt(schema, extra_instructions="extra")

    assert "extra" in schema_prompt
    assert "extra" in value_prompt
    assert "a" in value_prompt
