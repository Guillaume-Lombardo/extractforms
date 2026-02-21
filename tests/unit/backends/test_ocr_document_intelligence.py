from __future__ import annotations

import pytest

from extractforms.backends.ocr_document_intelligence import OCRBackend
from extractforms.exceptions import BackendError
from extractforms.typing.enums import ConfidenceLevel
from extractforms.typing.models import RenderedPage


class _FakeOCRProvider:
    def extract_pages(self, pages: list[RenderedPage]) -> list[dict[str, object]]:
        _ = pages
        return [
            {
                "page_number": 1,
                "lines": [
                    "Phone: +33 6 12 34 56 78",
                    "Address: 12 Rue de la Paix",
                    "Amount: 1 234,50",
                ],
            },
            {"page_number": 2, "lines": ["Comment: N/A"]},
        ]


def test_ocr_backend_requires_provider() -> None:
    backend = OCRBackend()
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")
    with pytest.raises(BackendError, match="requires an OCR provider bridge"):
        backend.infer_schema([page])


def test_ocr_backend_rejects_empty_pages_for_infer_schema() -> None:
    backend = OCRBackend(provider=_FakeOCRProvider())

    with pytest.raises(BackendError, match="requires at least one rendered page"):
        backend.infer_schema([])


def test_ocr_backend_infer_schema_from_ocr_lines() -> None:
    backend = OCRBackend(provider=_FakeOCRProvider())
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")

    schema, pricing = backend.infer_schema([page])

    assert pricing is None
    assert [field.key for field in schema.fields] == ["phone", "address", "amount", "comment"]
    assert [field.page for field in schema.fields] == [1, 1, 1, 2]


def test_ocr_backend_extract_values_from_requested_keys() -> None:
    backend = OCRBackend(provider=_FakeOCRProvider())
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")

    values, pricing = backend.extract_values([page], ["address", "amount"])

    assert pricing is None
    assert [(value.key, value.value, value.page, value.confidence) for value in values] == [
        ("address", "12 Rue de la Paix", 1, ConfidenceLevel.MEDIUM),
        ("amount", "1 234,50", 1, ConfidenceLevel.MEDIUM),
    ]


def test_ocr_backend_rejects_empty_pages_for_extract_values() -> None:
    backend = OCRBackend(provider=_FakeOCRProvider())

    with pytest.raises(BackendError, match="requires at least one rendered page"):
        backend.extract_values([], ["address"])


def test_ocr_backend_extract_values_handles_malformed_and_empty_lines() -> None:
    class _MalformedProvider:
        def extract_pages(self, pages: list[RenderedPage]) -> list[dict[str, object]]:
            _ = pages
            return [
                {"page_number": 1},
                {"page_number": 2, "lines": ["No delimiter line", "Email:"]},
            ]

    backend = OCRBackend(provider=_MalformedProvider())
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")
    values, pricing = backend.extract_values([page], ["email", "address"])

    assert pricing is None
    assert [(value.key, value.value, value.page) for value in values] == [("email", "NULL", 2)]


def test_ocr_backend_prefers_first_duplicate_key_across_pages() -> None:
    class _DuplicateProvider:
        def extract_pages(self, pages: list[RenderedPage]) -> list[dict[str, object]]:
            _ = pages
            return [
                {"page_number": 1, "lines": ["Address: First value"]},
                {"page_number": 2, "lines": ["Address: Second value"]},
            ]

    backend = OCRBackend(provider=_DuplicateProvider())
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")
    values, _ = backend.extract_values([page], ["address"])

    assert [(value.key, value.value, value.page) for value in values] == [("address", "First value", 1)]


def test_ocr_backend_returns_empty_when_requested_keys_not_found() -> None:
    backend = OCRBackend(provider=_FakeOCRProvider())
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")

    values, pricing = backend.extract_values([page], ["iban"])

    assert pricing is None
    assert values == []
