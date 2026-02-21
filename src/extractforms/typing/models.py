"""Core domain models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from extractforms.exceptions import ModelMismatchError
from extractforms.typing.enums import ConfidenceLevel, FieldKind, FieldSemanticType, PassMode

_ = Path


class SchemaField(BaseModel):
    """Single schema field definition."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    page: int | None = None
    kind: FieldKind = FieldKind.UNKNOWN
    semantic_type: FieldSemanticType | None = None
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
    input_tokens: int | None = Field(default=None)
    output_tokens: int | None = Field(default=None)
    total_cost_usd: float | None = Field(default=None)

    def __add__(self, other: PricingCall) -> PricingCall:
        """Combine two PricingCall instances by summing token counts and costs.

        Args:
            other: Another PricingCall instance to combine with.

        Raises:
            NotImplementedError: If the other object is not a PricingCall instance.
            ModelMismatchError: If the provider or model of the two calls do not match.

        Returns:
            PricingCall: A new instance with combined values.
        """
        if not isinstance(other, PricingCall):
            raise NotImplementedError("Cannot add PricingCall with non-PricingCall instance")

        if self.provider != other.provider or self.model != other.model:
            raise ModelMismatchError(self.provider, self.model, other.provider, other.model)

        return PricingCall(
            provider=self.provider,
            model=self.model,
            input_tokens=_sum_optional_int(self.input_tokens, other.input_tokens),
            output_tokens=_sum_optional_int(self.output_tokens, other.output_tokens),
            total_cost_usd=_sum_optional_float(self.total_cost_usd, other.total_cost_usd),
        )


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
    drop_blank_pages: bool | None = None
    blank_page_ink_threshold: float | None = None
    blank_page_near_white_level: int | None = None
    schema_id: str | None = None
    schema_path: Path | None = None
    match_schema: bool = False
    extra_instructions: str | None = None

    @field_validator("input_path")
    @classmethod
    def _validate_input_path(cls, value: Path) -> Path:
        """Ensure input path exists and points to a file.

        Args:
            value (Path): Input path.

        Raises:
            ValueError: If the path does not exist or is not a file.

        Returns:
            Path: Validated input path.
        """
        if not value.exists():
            raise ValueError("Input path does not exist")  # noqa: TRY003
        if not value.is_file():
            raise ValueError("Input path is not a file")  # noqa: TRY003
        return value


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


def _sum_optional_int(value1: int | None, value2: int | None) -> int | None:
    """Sum optional int values while preserving unknown state.

    Args:
        value1 (int|None): Optional int value.
        value2 (int|None): Optional int value.

    Returns:
        int | None: Sum when at least one value is known, else None.
    """
    if value1 is None:
        return value2
    if value2 is None:
        return value1
    return value1 + value2


def _sum_optional_float(value1: float | None, value2: float | None) -> float | None:
    """Sum optional float values while preserving unknown state.

    Args:
        value1 (float|None): Optional float value.
        value2 (float|None): Optional float value.

    Returns:
        float | None: Sum when at least one value is known, else None.
    """
    if value1 is None:
        return value2
    if value2 is None:
        return value1
    return value1 + value2
