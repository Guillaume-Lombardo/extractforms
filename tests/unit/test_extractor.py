from __future__ import annotations

from pathlib import Path
from typing import cast

from extractforms.enums import ConfidenceLevel, PassMode
from extractforms.extractor import extract_values, persist_result, result_to_json_dict, run_extract
from extractforms.models import ExtractRequest, ExtractionResult, FieldValue, SchemaField, SchemaSpec
from extractforms.settings import Settings


def _request(pdf: Path, mode: PassMode = PassMode.TWO_PASS) -> ExtractRequest:
    return ExtractRequest(
        input_path=pdf,
        output_path=pdf.parent / "result.json",
        mode=mode,
        dpi=120,
        image_format="png",
    )


def test_extract_values_fills_missing_with_null(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A", page=1), SchemaField(key="b", label="B", page=1)],
    )

    class _FakeBackend:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):  # noqa: ANN001
            return [FieldValue(key="a", value="x", page=1, confidence=ConfidenceLevel.HIGH)], None

    page = type("Page", (), {"page_number": 1})()

    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page])
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)

    result, _ = extract_values(schema, _request(pdf), Settings(null_sentinel="NULL"))

    assert result.flat["a"] == "x"
    assert result.flat["b"] == "NULL"


def test_run_extract_two_pass_with_cached_schema(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="abc",
        fields=[SchemaField(key="a", label="A")],
    )

    class _FakeStore:
        def __init__(self, root: Path) -> None:
            self.root = root

        @staticmethod
        def fingerprint_pdf(path: Path) -> str:
            return "abc"

        def match_schema(self, fingerprint: str):
            class _Match:
                matched = True
                schema_id = "id"

            return _Match()

        def list_schemas(self):
            return [pdf.parent / "schema.json"]

        def load(self, path: Path) -> SchemaSpec:
            return schema

        def save(self, schema_obj: SchemaSpec) -> Path:
            return pdf.parent / "saved.json"

    monkeypatch.setattr("extractforms.extractor.SchemaStore", _FakeStore)
    monkeypatch.setattr(
        "extractforms.extractor.extract_values",
        lambda schema_obj, request, settings: (
            ExtractionResult(
                fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
                flat={"a": "v"},
                schema_fields_count=1,
                pricing=None,
            ),
            None,
        ),
    )

    result = run_extract(_request(pdf, PassMode.TWO_PASS), Settings(schema_cache_dir=str(tmp_path)))
    assert result.flat["a"] == "v"


def test_persist_and_result_to_json_dict(tmp_path: Path) -> None:
    result = ExtractionResult(
        fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
        flat={"a": "v"},
        schema_fields_count=1,
        pricing=None,
    )

    output = tmp_path / "result.json"
    persist_result(result, output)

    data = result_to_json_dict(result)
    flat = cast(dict[str, str], data["flat"])

    assert output.exists()
    assert flat["a"] == "v"


def test_run_extract_one_pass(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    expected = ExtractionResult(
        fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
        flat={"a": "v"},
        schema_fields_count=1,
        pricing=None,
    )

    monkeypatch.setattr("extractforms.extractor.extract_one_pass", lambda request, settings: (expected, None))
    result = run_extract(_request(pdf, PassMode.ONE_PASS), Settings(schema_cache_dir=str(tmp_path)))

    assert result.flat["a"] == "v"


def test_run_extract_one_schema_pass_errors_without_schema_id(tmp_path: Path) -> None:
    from extractforms.exceptions import ExtractionError

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    request = _request(pdf, PassMode.ONE_SCHEMA_PASS)
    try:
        run_extract(request, Settings(schema_cache_dir=str(tmp_path)))
    except ExtractionError as exc:
        assert "requires --schema-id" in str(exc)
    else:
        raise AssertionError("Expected ExtractionError")


def test_run_extract_two_pass_infers_and_saves(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="abc",
        fields=[SchemaField(key="a", label="A")],
    )

    class _NoMatchStore:
        def __init__(self, root: Path) -> None:
            self.root = root
            self.saved = False

        @staticmethod
        def fingerprint_pdf(path: Path) -> str:
            return "abc"

        def match_schema(self, fingerprint: str):
            class _Match:
                matched = False
                schema_id = None

            return _Match()

        def list_schemas(self):
            return []

        def load(self, path: Path) -> SchemaSpec:
            return schema

        def save(self, schema_obj: SchemaSpec) -> Path:
            self.saved = True
            return self.root / "saved.json"

    monkeypatch.setattr("extractforms.extractor.SchemaStore", _NoMatchStore)
    monkeypatch.setattr("extractforms.extractor.infer_schema", lambda request, settings: (schema, None))
    monkeypatch.setattr(
        "extractforms.extractor.extract_values",
        lambda schema_obj, request, settings: (
            ExtractionResult(
                fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
                flat={"a": "v"},
                schema_fields_count=1,
                pricing=None,
            ),
            None,
        ),
    )

    result = run_extract(_request(pdf, PassMode.TWO_PASS), Settings(schema_cache_dir=str(tmp_path)))
    assert result.schema_fields_count == 1
