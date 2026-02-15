"""OCR backend stub for future Document Intelligence integration."""

from __future__ import annotations

from extractforms.exceptions import BackendError
from extractforms.typing.models import FieldValue, PricingCall, RenderedPage, SchemaSpec


class OCRBackend:
    """Placeholder OCR backend."""

    def infer_schema(self, pages: list[RenderedPage]) -> tuple[SchemaSpec, PricingCall | None]:
        """Infer schema with OCR backend.

        Args:
            pages: Rendered pages.

        Raises:
            BackendError: Always in MVP stub.

        Returns:
            tuple[SchemaSpec, PricingCall | None]: Never returned in MVP.
        """
        raise BackendError(message="OCR backend is not implemented yet")

    def extract_values(
        self,
        pages: list[RenderedPage],
        keys: list[str],
    ) -> tuple[list[FieldValue], PricingCall | None]:
        """Extract values with OCR backend.

        Args:
            pages: Rendered pages.
            keys: Keys to extract.

        Raises:
            BackendError: Always in MVP stub.

        Returns:
            tuple[list[FieldValue], PricingCall | None]: Never returned in MVP.
        """
        raise BackendError(message="OCR backend is not implemented yet")
