from __future__ import annotations

from typing import TYPE_CHECKING, Self

from extractforms.processing.page_selection import (
    analyze_page_selection,
    build_schema_page_mapping,
    filter_rendered_pages_to_nonblank,
)
from extractforms.typing.models import (
    PageSelectionAnalysis,
    PageSelectionRequest,
    RenderedPage,
    SchemaField,
    SchemaSpec,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_filter_rendered_pages_to_nonblank() -> None:
    pages = [
        RenderedPage(page_number=1, mime_type="image/png", data_base64="AA=="),
        RenderedPage(page_number=2, mime_type="image/png", data_base64="AA=="),
        RenderedPage(page_number=3, mime_type="image/png", data_base64="AA=="),
    ]

    filtered = filter_rendered_pages_to_nonblank(pages, nonblank_page_numbers=[1, 3])

    assert [page.page_number for page in filtered] == [1, 3]


def test_build_schema_page_mapping_uses_nonblank_when_blank_pages_are_present() -> None:
    schema = SchemaSpec(
        id="id",
        name="n",
        fingerprint="fp",
        fields=[
            SchemaField(key="a", label="A", page=1),
            SchemaField(key="b", label="B", page=2),
        ],
    )
    analysis = PageSelectionAnalysis(selected_page_numbers=[1, 2, 3, 4], nonblank_page_numbers=[1, 3])

    mapping = build_schema_page_mapping(schema=schema, analysis=analysis)

    assert mapping == {1: 1, 2: 3}


def test_build_schema_page_mapping_defaults_to_identity_without_analysis() -> None:
    schema = SchemaSpec(
        id="id",
        name="n",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A", page=2)],
    )

    mapping = build_schema_page_mapping(schema=schema, analysis=None)

    assert mapping == {1: 1, 2: 2}


def test_analyze_page_selection_detects_nonblank_pages(  # noqa: C901
    monkeypatch,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"pdf")

    class _FakePixmap:
        def __init__(self, samples: bytes) -> None:
            self.width = 1
            self.height = 1
            self.samples = samples

    class _FakePage:
        def __init__(self, index: int) -> None:
            self.index = index

        def get_pixmap(self, matrix=None, alpha: bool = False):  # noqa: FBT001, FBT002
            _ = (matrix, alpha)
            if self.index == 0:
                return _FakePixmap(bytes([0, 0, 0]))
            return _FakePixmap(bytes([255, 255, 255]))

    class _FakeDoc:
        def __len__(self) -> int:
            return 2

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = (exc_type, exc, tb)

        def load_page(self, idx: int) -> _FakePage:
            return _FakePage(idx)

    class _FakeFitz:
        class Matrix:
            def __init__(self, x: float, y: float) -> None:
                _ = (x, y)

        @staticmethod
        def open(path: Path) -> _FakeDoc:
            _ = path
            return _FakeDoc()

    monkeypatch.setattr("extractforms.processing.page_selection.fitz", _FakeFitz)

    analysis = analyze_page_selection(
        PageSelectionRequest(
            pdf_path=pdf.as_posix(),
            page_start=1,
            page_end=2,
            max_pages=None,
            ink_ratio_threshold=0.1,
            near_white_level=245,
        ),
    )

    assert analysis is not None
    assert analysis.selected_page_numbers == [1, 2]
    assert analysis.nonblank_page_numbers == [1]
