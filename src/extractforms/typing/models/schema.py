"""Schema-centric domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from extractforms.typing.enums import FieldKind, FieldSemanticType


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
    version: int = 1
    schema_family_id: str | None = None
    fields: list[SchemaField]


class MatchResult(BaseModel):
    """Schema matching output."""

    model_config = ConfigDict(extra="forbid")

    matched: bool
    schema_id: str | None = None
    score: float | None = None
    reason: str | None = None
