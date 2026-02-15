"""Backend interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from extractforms.typing.models import FieldValue, RenderedPage, SchemaSpec


class PageSource(Protocol):
    """Source abstraction for pages consumed by extractors."""

    def render_images(self, pdf_path: Path) -> list[RenderedPage]:
        """Render pages into image payloads.

        Args:
            pdf_path: Source PDF path.

        Returns:
            list[RenderedPage]: Rendered pages.
        """

    def ocr_pages(self, pdf_path: Path) -> list[dict[str, object]]:
        """Run OCR and return raw OCR structures.

        Args:
            pdf_path: Source PDF path.

        Returns:
            list[dict[str, object]]: OCR payloads.
        """


class ExtractorBackend(Protocol):
    """Extraction backend interface."""

    def infer_schema(self, pages: list[RenderedPage]) -> SchemaSpec:
        """Infer schema for a document.

        Args:
            pages: Rendered pages.

        Returns:
            SchemaSpec: Inferred schema.
        """

    def extract_values(self, pages: list[RenderedPage], keys: list[str]) -> list[FieldValue]:
        """Extract values for selected keys.

        Args:
            pages: Rendered pages.
            keys: Keys to extract.

        Returns:
            list[FieldValue]: Extracted key/value entries.
        """
