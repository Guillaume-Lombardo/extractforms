"""Prompt builders and response schema helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from extractforms.typing.models import SanitizedJsonSchema, SchemaSpec


def sanitize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a JSON schema to maximize strict compatibility.

    Args:
        schema (dict[str, Any]): Raw JSON schema.

    Returns:
        dict[str, Any]: Sanitized JSON schema.
    """
    cleaned = deepcopy(schema)

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            node_dict = cast("dict[str, Any]", node)
            if "properties" in node_dict:
                node_dict.setdefault("type", "object")
                props = node_dict["properties"]
                if isinstance(props, dict):
                    props_dict = cast("dict[str, Any]", props)
                    node_dict["required"] = sorted(str(key) for key in props_dict)
                    node_dict["additionalProperties"] = False
            if "$ref" in node_dict and "default" in node_dict:
                node_dict.pop("default", None)
            for value in node_dict.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(cleaned)
    return cleaned


def schema_response_format(name: str, schema: dict[str, Any]) -> SanitizedJsonSchema:
    """Build strict response format payload.

    Args:
        name (str): Schema name in response format.
        schema (dict[str, Any]): Raw schema payload.

    Returns:
        SanitizedJsonSchema: Strict response schema wrapper.
    """
    return SanitizedJsonSchema(
        name=name,
        schema=sanitize_json_schema(schema),
        strict=True,
    )


def build_schema_inference_prompt(*, extra_instructions: str | None = None) -> str:
    """Build prompt used to infer a document schema.

    Args:
        extra_instructions (str | None): Optional user instructions.

    Returns:
        str: Prompt text.
    """
    base = (
        "Infer a stable schema for this form document. Return fields with key, label, page, and field kind."
    )
    if extra_instructions:
        return f"{base}\nAdditional instructions: {extra_instructions}"
    return base


def build_values_extraction_prompt(schema: SchemaSpec, *, extra_instructions: str | None = None) -> str:
    """Build prompt used to extract values with a known schema.

    Args:
        schema (SchemaSpec): Input schema.
        extra_instructions (str | None): Optional user instructions.

    Returns:
        str: Prompt text.
    """
    keys = ", ".join(field.key for field in schema.fields)
    base = (
        "Extract values for the following keys. "
        "When a value is missing return the NULL sentinel. "
        f"Keys: {keys}."
    )
    if extra_instructions:
        return f"{base}\nAdditional instructions: {extra_instructions}"
    return base
