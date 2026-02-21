"""Strict structured-output schema models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SanitizedJsonSchema(BaseModel):
    """Schema payload used for strict structured output."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    json_schema: dict[str, Any] = Field(alias="schema")
    strict: bool = True
