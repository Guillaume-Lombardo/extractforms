"""Backend interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from extractforms.typing.models import FieldValue, PricingCall, RenderedPage, SchemaSpec


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

    def infer_schema(self, pages: list[RenderedPage]) -> tuple[SchemaSpec, PricingCall | None]:
        """Infer schema for a document.

        Args:
            pages: Rendered pages.

        Returns:
            tuple[SchemaSpec, PricingCall | None]: Inferred schema and optional pricing.
        """

    def extract_values(
        self,
        pages: list[RenderedPage],
        keys: list[str],
        *,
        extra_instructions: str | None = None,
    ) -> tuple[list[FieldValue], PricingCall | None]:
        """Extract values for selected keys.

        Args:
            pages: Rendered pages.
            keys: Keys to extract.
            extra_instructions: Optional runtime instructions.

        Returns:
            tuple[list[FieldValue], PricingCall | None]: Extracted values and optional pricing.
        """
