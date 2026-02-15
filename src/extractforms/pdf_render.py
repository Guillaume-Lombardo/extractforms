"""PDF rendering helpers."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

try:
    import fitz
except Exception:  # pragma: no cover - optional dependency at runtime
    fitz: Any
    fitz = None

from extractforms.exceptions import BackendError
from extractforms.logging import get_logger
from extractforms.models import RenderedPage

logger = get_logger(__name__)

_MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
}


def render_pdf_pages(
    pdf_path: Path,
    *,
    dpi: int,
    image_format: str,
    page_start: int | None = None,
    page_end: int | None = None,
    max_pages: int | None = None,
) -> list[RenderedPage]:
    """Render a PDF file into base64 image pages.

    Args:
        pdf_path: PDF file to render.
        dpi: Render DPI.
        image_format: Target format (`png`, `jpeg`, `jpg`).
        page_start: Optional first page (1-based, inclusive).
        page_end: Optional last page (1-based, inclusive).
        max_pages: Optional hard limit on rendered pages.

    Raises:
        BackendError: If PyMuPDF is unavailable or rendering fails.

    Returns:
        list[RenderedPage]: Rendered pages.
    """
    if fitz is None:
        raise BackendError(message="PyMuPDF is required for PDF rendering")

    normalized_format = image_format.lower()
    if normalized_format not in _MIME_BY_FORMAT:
        raise BackendError(message=f"Unsupported image format: {image_format}")

    first = (page_start - 1) if page_start else 0

    try:
        rendered: list[RenderedPage] = []
        with fitz.open(pdf_path) as doc:
            last = (page_end - 1) if page_end else (len(doc) - 1)
            page_indices = range(first, min(last, len(doc) - 1) + 1)

            for idx in page_indices:
                page = doc.load_page(idx)
                pix = page.get_pixmap(dpi=dpi)
                image_bytes = pix.tobytes(output=normalized_format)
                encoded = base64.b64encode(image_bytes).decode("ascii")
                rendered.append(
                    RenderedPage(
                        page_number=idx + 1,
                        mime_type=_MIME_BY_FORMAT[normalized_format],
                        data_base64=encoded,
                    ),
                )
                if max_pages and len(rendered) >= max_pages:
                    break

        logger.info("PDF rendered", extra={"pages": len(rendered), "input_path": str(pdf_path)})
        return rendered
    except Exception as exc:  # pragma: no cover - depends on file and fitz internals
        raise BackendError(message=f"Failed to render PDF: {pdf_path}") from exc
