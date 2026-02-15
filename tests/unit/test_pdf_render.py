from __future__ import annotations

from pathlib import Path

import pytest

from extractforms.exceptions import BackendError
from extractforms.pdf_render import render_pdf_pages


class _FakePixmap:
    def tobytes(self, output: str) -> bytes:
        assert output == "png"
        return b"abc"


class _FakePage:
    def get_pixmap(self, dpi: int) -> _FakePixmap:
        assert dpi == 120
        return _FakePixmap()


class _FakeDoc:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        return None

    def __len__(self) -> int:
        return 1

    def load_page(self, idx: int) -> _FakePage:
        assert idx == 0
        return _FakePage()


class _FakeFitzModule:
    @staticmethod
    def open(path: Path) -> _FakeDoc:
        assert path.name == "doc.pdf"
        return _FakeDoc()


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
