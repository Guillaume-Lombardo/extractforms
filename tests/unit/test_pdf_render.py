from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from extractforms.exceptions import BackendError
from extractforms.pdf_render import render_pdf_pages

if TYPE_CHECKING:
    from pathlib import Path


class _FakePixmap:
    def tobytes(self, output: str) -> bytes:
        assert output == "png"
        return b"abc"


class _FakePage:
    def get_pixmap(self, dpi: int) -> _FakePixmap:
        assert dpi == 120
        return _FakePixmap()


class _FakeDoc:
    def __init__(self, pages: int = 1) -> None:
        self._pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def __len__(self) -> int:
        return self._pages

    def load_page(self, idx: int) -> _FakePage:
        assert 0 <= idx < self._pages
        return _FakePage()


class _FakeFitzModule:
    @staticmethod
    def open(path: Path) -> _FakeDoc:
        assert path.name == "doc.pdf"
        return _FakeDoc()


class _FakeFitzThreePages:
    @staticmethod
    def open(path: Path) -> _FakeDoc:
        assert path.name == "doc.pdf"
        return _FakeDoc(pages=3)


def test_render_pdf_pages_rejects_unknown_image_format(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"pdf")

    with pytest.raises(BackendError, match="Unsupported image format"):
        render_pdf_pages(pdf, dpi=120, image_format="gif")


def test_render_pdf_pages_with_fake_fitz(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"pdf")

    monkeypatch.setattr("extractforms.pdf_render.fitz", _FakeFitzModule)
    pages = render_pdf_pages(pdf, dpi=120, image_format="png")

    assert len(pages) == 1
    assert pages[0].mime_type == "image/png"


def test_render_pdf_pages_includes_page_end_upper_bound(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"pdf")

    monkeypatch.setattr("extractforms.pdf_render.fitz", _FakeFitzThreePages)
    pages = render_pdf_pages(pdf, dpi=120, image_format="png", page_end=3)

    assert [page.page_number for page in pages] == [1, 2, 3]
