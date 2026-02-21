"""OCR backend MVP with injectable OCR provider integration path."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from extractforms.exceptions import BackendError
from extractforms.typing.enums import ConfidenceLevel
from extractforms.typing.models import FieldValue, SchemaField, SchemaSpec

if TYPE_CHECKING:
    from extractforms.typing.models import PricingCall, RenderedPage


class OCRPageProvider(Protocol):
    """Provider protocol for OCR payload extraction."""

    def extract_pages(self, pages: list[RenderedPage]) -> list[dict[str, object]]:
        """Extract OCR payloads for rendered pages.

        Args:
            pages (list[RenderedPage]): Rendered pages.

        Returns:
            list[dict[str, object]]: OCR payload per page.
        """


class OCRBackend:
    """OCR backend with pluggable page OCR provider.

    The provider bridge is intentionally separated so this backend can host
    a Document Intelligence client without coupling extraction orchestration
    to a specific provider SDK.
    """

    def __init__(
        self,
        *,
        provider: OCRPageProvider | None = None,
        null_sentinel: str = "NULL",
    ) -> None:
        """Initialize OCR backend.

        Args:
            provider (OCRPageProvider | None): OCR page provider bridge.
            null_sentinel (str): Null sentinel for missing values.
        """
        self._provider = provider
        self._null_sentinel = null_sentinel

    def infer_schema(
        self,
        pages: list[RenderedPage],
    ) -> tuple[SchemaSpec, PricingCall | None]:
        """Infer schema from OCR text patterns.

        Args:
            pages (list[RenderedPage]): Rendered pages.

        Returns:
            tuple[SchemaSpec, PricingCall | None]: Inferred schema and no pricing.
        """
        ocr_pages = self._ocr_pages(pages)
        fields: list[SchemaField] = []
        seen_keys: set[str] = set()

        for page_number, lines in self._iter_page_lines(ocr_pages):
            for line in lines:
                key, _ = _parse_key_value_line(line)
                if key is None or key in seen_keys:
                    continue
                seen_keys.add(key)
                fields.append(
                    SchemaField(
                        key=key,
                        label=key.replace("_", " ").title(),
                        page=page_number,
                    ),
                )

        return SchemaSpec(
            id="ocr-schema",
            name="OCR Inferred Schema",
            fingerprint="ocr",
            fields=fields,
        ), None

    def extract_values(
        self,
        pages: list[RenderedPage],
        keys: list[str],
    ) -> tuple[list[FieldValue], PricingCall | None]:
        """Extract key/value pairs from OCR text.

        Args:
            pages (list[RenderedPage]): Rendered pages.
            keys (list[str]): Keys to extract.

        Returns:
            tuple[list[FieldValue], PricingCall | None]: Extracted values and no pricing.
        """
        requested_keys = {key.strip().lower(): key for key in keys}
        if not requested_keys:
            return [], None

        values: list[FieldValue] = []
        found: set[str] = set()

        for page_number, lines in self._iter_page_lines(self._ocr_pages(pages)):
            for line in lines:
                parsed_key, parsed_value = _parse_key_value_line(line)
                if parsed_key is None or parsed_value is None:
                    continue
                requested_key = requested_keys.get(parsed_key)
                if requested_key is None or requested_key in found:
                    continue
                found.add(requested_key)
                values.append(
                    FieldValue(
                        key=requested_key,
                        value=parsed_value.strip() or self._null_sentinel,
                        page=page_number,
                        confidence=ConfidenceLevel.MEDIUM,
                    ),
                )

        return values, None

    def _ocr_pages(self, pages: list[RenderedPage]) -> list[dict[str, object]]:
        """Load OCR payload through provider.

        Args:
            pages (list[RenderedPage]): Rendered pages.

        Raises:
            BackendError: If provider is not configured.

        Returns:
            list[dict[str, object]]: OCR payload per page.
        """
        if self._provider is None:
            raise BackendError(
                message=(
                    "OCR backend requires an OCR provider bridge. "
                    "Configure a Document Intelligence page provider before use."
                ),
            )
        return self._provider.extract_pages(pages)

    @staticmethod
    def _iter_page_lines(ocr_pages: list[dict[str, object]]) -> list[tuple[int, list[str]]]:
        """Normalize OCR payload into page-numbered lines.

        Args:
            ocr_pages (list[dict[str, object]]): OCR payloads.

        Returns:
            list[tuple[int, list[str]]]: Page number and associated text lines.
        """
        pages: list[tuple[int, list[str]]] = []
        for index, payload in enumerate(ocr_pages, start=1):
            raw_page = payload.get("page_number")
            page_number = raw_page if isinstance(raw_page, int) else index
            raw_lines = payload.get("lines")
            if not isinstance(raw_lines, list):
                pages.append((page_number, []))
                continue
            lines = [line for line in raw_lines if isinstance(line, str)]
            pages.append((page_number, lines))
        return pages


def _parse_key_value_line(line: str) -> tuple[str | None, str | None]:
    """Parse one OCR line into a key/value pair.

    Args:
        line (str): OCR line content.

    Returns:
        tuple[str | None, str | None]: Parsed key and value.
    """
    if ":" not in line:
        return None, None
    left, right = line.split(":", maxsplit=1)
    key = _normalize_key(left)
    value = right.strip()
    if not key:
        return None, None
    return key, value


def _normalize_key(raw_key: str) -> str:
    """Normalize key text from OCR line labels.

    Args:
        raw_key (str): OCR raw key label.

    Returns:
        str: Snake_case key.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "_", raw_key.strip().lower()).strip("_")
