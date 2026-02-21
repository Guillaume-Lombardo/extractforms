"""Blank-page detection and page-number mapping helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import fitz
from pydantic import BaseModel, ConfigDict, Field

from extractforms import logger

if TYPE_CHECKING:
    from extractforms.typing.models import RenderedPage, SchemaSpec


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


def analyze_page_selection(request: PageSelectionRequest) -> PageSelectionAnalysis | None:
    """Analyze selected pages and detect near-blank pages.

    Args:
        request (PageSelectionRequest): Selected-page analysis request.

    Returns:
        PageSelectionAnalysis | None: Selection analysis, or None on analysis failure.
    """
    try:
        with fitz.open(request.pdf_path) as doc:
            selected_page_numbers = _compute_selected_page_numbers(doc, request)
            nonblank_page_numbers = [
                page_number
                for page_number in selected_page_numbers
                if _is_nonblank_page(
                    doc=doc,
                    page_number=page_number,
                    near_white_level=request.near_white_level,
                    ink_ratio_threshold=request.ink_ratio_threshold,
                    sample_dpi=request.sample_dpi,
                )
            ]
    except Exception:
        logger.warning("Failed to analyze blank pages", extra={"input_path": str(request.pdf_path)})
        return None

    return PageSelectionAnalysis(
        selected_page_numbers=selected_page_numbers,
        nonblank_page_numbers=nonblank_page_numbers,
    )


def _compute_selected_page_numbers(
    doc: fitz.Document,
    request: PageSelectionRequest,
) -> list[int]:
    """Compute selected page numbers for a PDF document.

    Args:
        doc (fitz.Document): Open PDF document.
        request (PageSelectionRequest): Selection request.

    Returns:
        list[int]: Selected page numbers in ascending order.
    """
    total_pages = len(doc)
    if total_pages <= 0:
        return []

    first_page = max(1, request.page_start or 1)
    last_page = min(request.page_end or total_pages, total_pages)
    if first_page > last_page:
        return []

    selected = list(range(first_page, last_page + 1))
    if request.max_pages is not None:
        selected = selected[: request.max_pages]
    return selected


def _is_nonblank_page(
    *,
    doc: fitz.Document,
    page_number: int,
    near_white_level: int,
    ink_ratio_threshold: float,
    sample_dpi: int,
) -> bool:
    """Return whether a page has enough ink to be treated as non-blank.

    Args:
        doc (fitz.Document): Open PDF document.
        page_number (int): Page number (1-based).
        near_white_level (int): Near-white threshold.
        ink_ratio_threshold (float): Non-white ratio threshold.
        sample_dpi (int): Sampling DPI.

    Returns:
        bool: True if page is non-blank.
    """
    zoom = float(sample_dpi) / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    page = doc.load_page(page_number - 1)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    if not pix.samples:
        return False

    ink = _count_ink_pixels(pix.samples, near_white_level)
    total_px = max(1, pix.width * pix.height)
    return (ink / total_px) >= ink_ratio_threshold


def _count_ink_pixels(rgb_samples: bytes, near_white_level: int) -> int:
    """Count non-near-white pixels in RGB samples.

    Args:
        rgb_samples (bytes): RGB pixel bytes.
        near_white_level (int): Near-white threshold per RGB channel.

    Returns:
        int: Number of non-near-white pixels.
    """
    view = memoryview(rgb_samples)
    ink = 0
    for idx in range(0, len(view), 3):
        red = view[idx]
        green = view[idx + 1]
        blue = view[idx + 2]
        if red < near_white_level or green < near_white_level or blue < near_white_level:
            ink += 1
    return ink


def filter_rendered_pages_to_nonblank(
    pages: list[RenderedPage],
    *,
    nonblank_page_numbers: list[int],
) -> list[RenderedPage]:
    """Filter rendered pages to keep only non-blank page numbers.

    Args:
        pages (list[RenderedPage]): Rendered pages.
        nonblank_page_numbers (list[int]): Non-blank page numbers (1-based).

    Returns:
        list[RenderedPage]: Filtered page list.
    """
    if not nonblank_page_numbers:
        return pages
    nonblank_set = set(nonblank_page_numbers)
    return [page for page in pages if page.page_number in nonblank_set]


def build_schema_page_mapping(
    *,
    schema: SchemaSpec,
    analysis: PageSelectionAnalysis | None,
) -> dict[int, int]:
    """Build schema logical-page to physical PDF page mapping.

    Args:
        schema (SchemaSpec): Extraction schema.
        analysis (PageSelectionAnalysis | None): Selected page analysis.

    Returns:
        dict[int, int]: Mapping from schema page numbers to PDF page numbers.
    """
    schema_pages = sorted({field.page for field in schema.fields if field.page is not None})
    if not schema_pages:
        return {}

    max_schema_page = max(schema_pages)
    if analysis is None:
        return {page_number: page_number for page_number in range(1, max_schema_page + 1)}

    selected = analysis.selected_page_numbers
    nonblank = analysis.nonblank_page_numbers
    if not selected:
        return {page_number: page_number for page_number in range(1, max_schema_page + 1)}

    has_blank_pages = bool(nonblank) and len(nonblank) < len(selected)
    if has_blank_pages and max_schema_page <= len(nonblank):
        return {page_number: nonblank[page_number - 1] for page_number in range(1, max_schema_page + 1)}

    return {page_number: page_number for page_number in range(1, max_schema_page + 1)}
