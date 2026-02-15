"""Core domain models."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from extractforms.typing.enums import ConfidenceLevel, FieldKind, PassMode


class SchemaField(BaseModel):
    """Single schema field definition."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    page: int | None = None
    kind: FieldKind = FieldKind.UNKNOWN
    expected_type: str | None = None
    regex: str | None = None
    options: list[str] = Field(default_factory=list)


class SchemaSpec(BaseModel):
    """Schema describing an input form."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    fingerprint: str
    fields: list[SchemaField]


class FieldValue(BaseModel):
    """Extracted field value payload."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str
    page: int | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN


class PricingCall(BaseModel):
    """Price accounting for one model call."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None


class ExtractionResult(BaseModel):
    """Extraction result persisted to JSON."""

    model_config = ConfigDict(extra="forbid")

    fields: list[FieldValue]
    flat: dict[str, str]
    schema_fields_count: int
    pricing: PricingCall | None = None


class ExtractRequest(BaseModel):
    """Extraction request settings."""

    model_config = ConfigDict(extra="forbid")

    input_path: Path
    output_path: Path | None = None
    mode: PassMode = PassMode.TWO_PASS
    use_cache: bool = True
    dpi: int = 200
    image_format: str = "png"
    page_start: int | None = None
    page_end: int | None = None
    max_pages: int | None = None
    chunk_pages: int = 1
    schema_id: str | None = None
    schema_path: Path | None = None
    match_schema: bool = False
    extra_instructions: str | None = None


class MatchResult(BaseModel):
    """Schema matching output."""

    model_config = ConfigDict(extra="forbid")

    matched: bool
    schema_id: str | None = None
    score: float | None = None
    reason: str | None = None


class RenderedPage(BaseModel):
    """Rendered page sent to extraction backends."""

    model_config = ConfigDict(extra="forbid")

    page_number: int
    mime_type: str
    data_base64: str


class SanitizedJsonSchema(BaseModel):
    """Schema payload used for strict structured output."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    json_schema: dict[str, Any] = Field(alias="schema")
    strict: bool = True
