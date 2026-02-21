from __future__ import annotations

from typing import TYPE_CHECKING

from extractforms.extractor import run_extract
from extractforms.settings import Settings
from extractforms.typing.enums import ConfidenceLevel, FieldKind, FieldSemanticType, PassMode
from extractforms.typing.models import ExtractRequest, FieldValue, SchemaField, SchemaSpec

if TYPE_CHECKING:
    from pathlib import Path


def test_typed_fields_extraction_flow_applies_normalization_and_null_sentinel(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")
    schema_path = tmp_path / "schema.json"

    schema = SchemaSpec(
        id="typed-schema",
        name="Typed Schema",
        fingerprint="fp",
        fields=[
            SchemaField(
                key="phone",
                label="Phone",
                page=1,
                kind=FieldKind.PHONE,
                semantic_type=FieldSemanticType.PHONE,
            ),
            SchemaField(
                key="address",
                label="Address",
                page=1,
                kind=FieldKind.ADDRESS,
                semantic_type=FieldSemanticType.ADDRESS,
            ),
            SchemaField(
                key="amount",
                label="Amount",
                page=1,
                kind=FieldKind.AMOUNT,
                semantic_type=FieldSemanticType.AMOUNT,
            ),
            SchemaField(
                key="amount_missing",
                label="Amount Missing",
                page=1,
                kind=FieldKind.AMOUNT,
                semantic_type=FieldSemanticType.AMOUNT,
            ),
        ],
    )
    schema_path.write_text(schema.model_dump_json(indent=2), encoding="utf-8")

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = (pages, keys, extra_instructions)
            return [
                FieldValue(key="phone", value="06 12 34 56 78", page=1, confidence=ConfidenceLevel.HIGH),
                FieldValue(
                    key="address",
                    value="  12,   Rue de la Paix\n\t75002  Paris  ",
                    page=1,
                    confidence=ConfidenceLevel.MEDIUM,
                ),
                FieldValue(key="amount", value="1 234,50", page=1, confidence=ConfidenceLevel.HIGH),
            ], None

    page = type("Page", (), {"page_number": 1})()
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page])
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)
    monkeypatch.setattr(
        "extractforms.extractor.analyze_page_selection",
        lambda *args, **kwargs: type(
            "Analysis",
            (),
            {"selected_page_numbers": [1], "nonblank_page_numbers": [1]},
        )(),
    )

    request = ExtractRequest(
        input_path=pdf,
        output_path=tmp_path / "result.json",
        mode=PassMode.ONE_SCHEMA_PASS,
        schema_path=schema_path,
        chunk_pages=1,
    )
    result = run_extract(request=request, settings=Settings(null_sentinel="NULL"))

    assert result.flat["phone"] == "0612345678"
    assert result.flat["address"] == "12, Rue de la Paix 75002 Paris"
    assert result.flat["amount"] == "1234.5"
    assert result.flat["amount_missing"] == "NULL"
