from __future__ import annotations

from extractforms.typing.models import MatchResult, SchemaField, SchemaSpec
from extractforms.schema_store import SchemaStore, build_schema_with_generated_id


def test_fingerprint_pdf_is_stable(tmp_path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"test-content")

    fp1 = SchemaStore.fingerprint_pdf(pdf)
    fp2 = SchemaStore.fingerprint_pdf(pdf)

    assert fp1 == fp2


def test_save_load_and_match_schema(tmp_path) -> None:
    store = SchemaStore(root=tmp_path)
    schema = SchemaSpec(
        id="schema-1",
        name="Demo",
        fingerprint="abc",
        fields=[SchemaField(key="x", label="X")],
    )

    path = store.save(schema)
    loaded = store.load(path)

    assert loaded.id == "schema-1"
    assert store.list_schemas() == [path]

    match = store.match_schema("abc")
    assert match == MatchResult(matched=True, schema_id="schema-1", score=1.0, reason="fingerprint_match")


def test_build_schema_with_generated_id() -> None:
    schema = build_schema_with_generated_id("Name", "fp", [SchemaField(key="a", label="A")])
    assert schema.id
    assert schema.name == "Name"
