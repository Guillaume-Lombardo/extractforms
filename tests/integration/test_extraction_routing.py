from __future__ import annotations

from typing import TYPE_CHECKING

from extractforms.extractor import extract_values
from extractforms.settings import Settings
from extractforms.typing.enums import ConfidenceLevel, PassMode
from extractforms.typing.models import (
    ExtractRequest,
    FieldValue,
    RenderedPage,
    SchemaField,
    SchemaSpec,
)

if TYPE_CHECKING:
    from pathlib import Path


def _rendered_page(page_number: int) -> RenderedPage:
    return RenderedPage(page_number=page_number, mime_type="image/png", data_base64="AA==")


def test_extract_values_routes_schema_pages_with_interleaved_blank_pages(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[
            SchemaField(key="a", label="A", page=1),
            SchemaField(key="sparse_x", label="Sparse"),
            SchemaField(key="b", label="B", page=2),
        ],
    )

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = extra_instructions
            page_numbers = tuple(page.page_number for page in pages)
            calls.append((page_numbers, tuple(keys)))
            if keys == ["a", "sparse_x"]:
                return [
                    FieldValue(key="a", value="value-a", page=1, confidence=ConfidenceLevel.HIGH),
                    FieldValue(key="sparse_x", value="value-x", page=1, confidence=ConfidenceLevel.MEDIUM),
                ], None
            if keys == ["b"]:
                return [FieldValue(key="b", value="value-b", page=3, confidence=ConfidenceLevel.HIGH)], None
            return [], None

    calls: list[tuple[tuple[int, ...], tuple[str, ...]]] = []
    page1 = _rendered_page(1)
    page2 = _rendered_page(2)
    page3 = _rendered_page(3)
    page4 = _rendered_page(4)
    monkeypatch.setattr(
        "extractforms.extractor.render_pdf_pages",
        lambda *args, **kwargs: [page1, page2, page3, page4],
    )
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)
    monkeypatch.setattr(
        "extractforms.extractor.analyze_page_selection",
        lambda *args, **kwargs: type(
            "Analysis",
            (),
            {"selected_page_numbers": [1, 2, 3, 4], "nonblank_page_numbers": [1, 3]},
        )(),
    )

    request = ExtractRequest(
        input_path=pdf,
        output_path=tmp_path / "result.json",
        mode=PassMode.TWO_PASS,
        chunk_pages=2,
    )
    result, _ = extract_values(schema=schema, request=request, settings=Settings(null_sentinel="NULL"))

    assert result.flat["a"] == "value-a"
    assert result.flat["sparse_x"] == "value-x"
    assert result.flat["b"] == "value-b"
    assert calls == [((1,), ("a", "sparse_x")), ((3,), ("b",))]
