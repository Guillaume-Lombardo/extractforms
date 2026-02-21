"""Page rendering and selection models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RenderedPage(BaseModel):
    """Rendered page sent to extraction backends."""

    model_config = ConfigDict(extra="forbid")

    page_number: int
    mime_type: str
    data_base64: str


class PageSelectionRequest(BaseModel):
    """Request payload for selected-page analysis."""

    model_config = ConfigDict(extra="forbid")

    pdf_path: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    max_pages: int | None = Field(default=None, ge=1)
    ink_ratio_threshold: float = Field(ge=0.0)
    near_white_level: int = Field(ge=0, le=255)
    sample_dpi: int = Field(default=72, ge=36, le=300)


class PageSelectionAnalysis(BaseModel):
    """Page analysis for a selected PDF range."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_page_numbers: list[int]
    nonblank_page_numbers: list[int]
