"""OCR backend stub for future Document Intelligence integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from extractforms.exceptions import BackendError

if TYPE_CHECKING:
    from extractforms.typing.models import FieldValue, PricingCall, RenderedPage, SchemaSpec


class OCRBackend:
    """Placeholder OCR backend."""

    @staticmethod
    def infer_schema(
        pages: list[RenderedPage],
    ) -> tuple[SchemaSpec, PricingCall | None]:
        """Infer schema with OCR backend.

        Args:
            pages (list[RenderedPage]): Rendered pages.

        Raises:
            BackendError: Always in MVP stub.

        """
        _ = pages
        raise BackendError(message="OCR backend is not implemented yet")

    @staticmethod
    def extract_values(
        pages: list[RenderedPage],
        keys: list[str],
    ) -> tuple[list[FieldValue], PricingCall | None]:
        """Extract values with OCR backend.

        Args:
            pages (list[RenderedPage]): Rendered pages.
            keys (list[str]): Keys to extract.

        Raises:
            BackendError: Always in MVP stub.

        """
        _ = (pages, keys)
        raise BackendError(message="OCR backend is not implemented yet")
