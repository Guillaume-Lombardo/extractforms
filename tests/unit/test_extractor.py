from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from extractforms import extractor
from extractforms.exceptions import ExtractionError
from extractforms.typing.enums import (
    ConfidenceLevel,
    ExtractionBackendType,
    FieldKind,
    FieldSemanticType,
    PassMode,
)
from extractforms.extractor import (
    extract_one_pass,
    extract_values,
    persist_result,
    result_to_json_dict,
    run_extract,
)
from extractforms.settings import Settings
from extractforms.typing.models import ExtractRequest, ExtractionResult, FieldValue, SchemaField, SchemaSpec

if TYPE_CHECKING:
    from pathlib import Path


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
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
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
    flat = cast("dict[str, str]", data["flat"])

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


def test_extract_one_pass_disables_page_groups(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A", page=1)],
    )
    expected = ExtractionResult(
        fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
        flat={"a": "v"},
        schema_fields_count=1,
        pricing=None,
    )

    monkeypatch.setattr("extractforms.extractor.infer_schema", lambda request, settings: (schema, None))

    observed: dict[str, object] = {}

    def _fake_extract_values(schema_obj, request, settings, *, use_page_groups=True):
        _ = (schema_obj, request, settings)
        observed["use_page_groups"] = use_page_groups
        return expected, None

    monkeypatch.setattr("extractforms.extractor.extract_values", _fake_extract_values)
    result, _ = extract_one_pass(_request(pdf, PassMode.ONE_PASS), Settings(schema_cache_dir=str(tmp_path)))

    assert observed["use_page_groups"] is False
    assert result.flat["a"] == "v"


def test_run_extract_one_schema_pass_errors_without_schema_id(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    request = _request(pdf, PassMode.ONE_SCHEMA_PASS)
    with pytest.raises(ExtractionError, match="requires --schema-id"):
        run_extract(request, Settings(schema_cache_dir=str(tmp_path)))


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


def test_run_extract_with_schema_path(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    schema_path = tmp_path / "schema.json"
    pdf.write_bytes(b"doc")
    schema_path.write_text("{}", encoding="utf-8")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A")],
    )

    request = ExtractRequest(
        input_path=pdf,
        output_path=tmp_path / "result.json",
        schema_path=schema_path,
    )

    class _Store:
        def __init__(self, root: Path) -> None:
            self.root = root

        def load(self, path: Path) -> SchemaSpec:
            assert path == schema_path
            return schema

    monkeypatch.setattr("extractforms.extractor.SchemaStore", _Store)
    monkeypatch.setattr(
        "extractforms.extractor.extract_values",
        lambda schema_obj, req, settings: (
            ExtractionResult(
                fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
                flat={"a": "v"},
                schema_fields_count=1,
                pricing=None,
            ),
            None,
        ),
    )

    result = run_extract(request, Settings(schema_cache_dir=str(tmp_path)))
    assert result.flat["a"] == "v"


def test_extract_values_handles_mixed_paged_and_non_paged_keys(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[
            SchemaField(key="paged_key", label="Paged", page=1),
            SchemaField(key="free_key", label="Free", page=None),
        ],
    )

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = (pages, extra_instructions)
            values: list[FieldValue] = []
            if "paged_key" in keys:
                values.append(
                    FieldValue(key="paged_key", value="paged", page=1, confidence=ConfidenceLevel.HIGH),
                )
            if "free_key" in keys:
                values.append(
                    FieldValue(key="free_key", value="free", page=1, confidence=ConfidenceLevel.MEDIUM),
                )
            return values, None

    page1 = type("Page", (), {"page_number": 1})()
    page2 = type("Page", (), {"page_number": 2})()
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page1, page2])
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)

    request = _request(pdf, PassMode.TWO_PASS)
    request.chunk_pages = 2
    result, _ = extract_values(schema, request, Settings(null_sentinel="NULL"))

    assert result.flat["paged_key"] == "paged"
    assert result.flat["free_key"] == "free"


def test_infer_sparse_keys_by_page_uses_nearest_anchored_field() -> None:
    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[
            SchemaField(key="a", label="A", page=1),
            SchemaField(key="x", label="X"),
            SchemaField(key="y", label="Y"),
            SchemaField(key="b", label="B", page=3),
        ],
    )

    inferred, unresolved = extractor._infer_sparse_keys_by_page(schema)

    assert inferred == {1: ["x"], 3: ["y"]}
    assert unresolved == []


def test_extract_values_uses_chunk_pages_for_non_paged_keys(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A"), SchemaField(key="b", label="B")],
    )

    calls: list[int] = []

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            calls.append(len(pages))
            return [
                FieldValue(key="a", value="value-a", page=1, confidence=ConfidenceLevel.MEDIUM),
                FieldValue(key="b", value="", page=1, confidence=ConfidenceLevel.UNKNOWN),
            ], None

    pages = [type("Page", (), {"page_number": idx})() for idx in [1, 2, 3]]
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: pages)
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)

    request = _request(pdf, PassMode.TWO_PASS)
    request.chunk_pages = 2
    result, _ = extract_values(schema, request, Settings(null_sentinel="NULL"))

    assert calls == [2, 1]
    assert result.flat["a"] == "value-a"


def test_extract_values_retries_missing_paged_keys_on_all_pages(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A", page=2)],
    )

    calls: list[tuple[int, tuple[str, ...]]] = []

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = extra_instructions
            calls.append((len(pages), tuple(keys)))
            if len(pages) == 1:
                return [FieldValue(key="a", value="", page=2, confidence=ConfidenceLevel.UNKNOWN)], None
            return [FieldValue(key="a", value="found", page=1, confidence=ConfidenceLevel.HIGH)], None

    page1 = type("Page", (), {"page_number": 1})()
    page2 = type("Page", (), {"page_number": 2})()
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page1, page2])
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)

    request = _request(pdf, PassMode.TWO_PASS)
    request.chunk_pages = 2
    result, _ = extract_values(schema, request, Settings(null_sentinel="NULL"))

    assert result.flat["a"] == "found"
    assert calls == [(1, ("a",)), (2, ("a",))]


def test_extract_values_retries_when_paged_value_is_null_sentinel(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A", page=2)],
    )

    calls: list[tuple[int, tuple[str, ...]]] = []

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = extra_instructions
            calls.append((len(pages), tuple(keys)))
            if len(pages) == 1:
                return [FieldValue(key="a", value="NULL", page=2, confidence=ConfidenceLevel.UNKNOWN)], None
            return [FieldValue(key="a", value="found", page=1, confidence=ConfidenceLevel.HIGH)], None

    page1 = type("Page", (), {"page_number": 1})()
    page2 = type("Page", (), {"page_number": 2})()
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page1, page2])
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)

    request = _request(pdf, PassMode.TWO_PASS)
    request.chunk_pages = 2
    result, _ = extract_values(schema, request, Settings(null_sentinel="NULL"))

    assert result.flat["a"] == "found"
    assert calls == [(1, ("a",)), (2, ("a",))]


def test_extract_values_maps_logical_schema_pages_to_nonblank_pdf_pages(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[SchemaField(key="a", label="A", page=2)],
    )
    routed_pages: list[int] = []

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = (keys, extra_instructions)
            routed_pages.extend([page.page_number for page in pages])
            return [FieldValue(key="a", value="found", page=3, confidence=ConfidenceLevel.HIGH)], None

    page1 = type("Page", (), {"page_number": 1})()
    page2 = type("Page", (), {"page_number": 2})()
    page3 = type("Page", (), {"page_number": 3})()
    monkeypatch.setattr(
        "extractforms.extractor.render_pdf_pages",
        lambda *args, **kwargs: [page1, page2, page3],
    )
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)
    monkeypatch.setattr(
        "extractforms.extractor.analyze_page_selection",
        lambda *args, **kwargs: type(
            "Analysis",
            (),
            {"selected_page_numbers": [1, 2, 3], "nonblank_page_numbers": [1, 3]},
        )(),
    )

    request = _request(pdf, PassMode.TWO_PASS)
    result, _ = extract_values(schema, request, Settings(null_sentinel="NULL"))

    assert result.flat["a"] == "found"
    assert routed_pages == [3]


def test_extract_values_applies_typed_value_normalization(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        fields=[
            SchemaField(
                key="phone",
                label="Phone",
                page=1,
                kind=FieldKind.PHONE,
                semantic_type=FieldSemanticType.PHONE,
            ),
        ],
    )

    class _FakeBackend:
        def __init__(self, settings) -> None:
            self.settings = settings

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = (pages, keys, extra_instructions)
            return [
                FieldValue(
                    key="phone",
                    value="00 33 6 12 34 56 78",
                    page=1,
                    confidence=ConfidenceLevel.HIGH,
                ),
            ], None

    page1 = type("Page", (), {"page_number": 1})()
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page1])
    monkeypatch.setattr("extractforms.extractor.MultimodalLLMBackend", _FakeBackend)

    request = _request(pdf, PassMode.TWO_PASS)
    result, _ = extract_values(schema, request, Settings(null_sentinel="NULL"))

    assert result.flat["phone"] == "+33612345678"


def test_extract_values_uses_ocr_backend_from_settings(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")
    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="fp",
        version=1,
        schema_family_id="family",
        fields=[SchemaField(key="a", label="A", page=1)],
    )

    class _FakeOCRBackend:
        def __init__(self, provider=None, null_sentinel="NULL", text_normalizer=None) -> None:
            _ = (provider, null_sentinel, text_normalizer)

        def extract_values(self, pages, keys, extra_instructions=None):
            _ = (pages, keys, extra_instructions)
            return [FieldValue(key="a", value="ocr", page=1, confidence=ConfidenceLevel.HIGH)], None

    page = type("Page", (), {"page_number": 1})()
    monkeypatch.setattr("extractforms.extractor.render_pdf_pages", lambda *args, **kwargs: [page])
    monkeypatch.setattr("extractforms.extractor.OCRBackend", _FakeOCRBackend)
    monkeypatch.setattr("extractforms.extractor._build_ocr_provider", lambda **kwargs: object())

    settings = Settings(null_sentinel="NULL")
    settings.extraction_backend = ExtractionBackendType.OCR
    result, _ = extract_values(schema, _request(pdf), settings)

    assert result.flat["a"] == "ocr"
    assert result.metadata["backend"] == "ocr"


def test_run_extract_two_pass_sets_cache_hit_metadata(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"doc")

    schema = SchemaSpec(
        id="id",
        name="name",
        fingerprint="abc",
        version=1,
        schema_family_id="id",
        fields=[SchemaField(key="a", label="A")],
    )

    class _Store:
        def __init__(self, root: Path) -> None:
            self.root = root

        @staticmethod
        def fingerprint_pdf(path: Path) -> str:
            _ = path
            return "abc"

        def match_schema(self, fingerprint: str):
            _ = fingerprint
            return type("Match", (), {"matched": True, "schema_id": "id"})()

        def list_schemas(self):
            return [self.root / "schema.json"]

        def load(self, path: Path) -> SchemaSpec:
            _ = path
            return schema

    monkeypatch.setattr("extractforms.extractor.SchemaStore", _Store)
    monkeypatch.setattr(
        "extractforms.extractor.extract_values",
        lambda *args, **kwargs: (
            ExtractionResult(
                fields=[FieldValue(key="a", value="v", confidence=ConfidenceLevel.HIGH)],
                flat={"a": "v"},
                schema_fields_count=1,
                pricing=None,
                metadata={},
            ),
            None,
        ),
    )
    result = run_extract(_request(pdf, PassMode.TWO_PASS), Settings(schema_cache_dir=str(tmp_path)))
    assert result.metadata["cache_hit"] is True
