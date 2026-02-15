from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from extractforms.typing.models import ExtractRequest

if TYPE_CHECKING:
    from pathlib import Path


def test_extract_request_rejects_missing_input_path(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing.pdf"

    with pytest.raises(ValidationError, match="does not exist"):
        ExtractRequest(input_path=missing_pdf)


def test_extract_request_accepts_existing_input_file(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    request = ExtractRequest(input_path=pdf)

    assert request.input_path == pdf
