from __future__ import annotations

import json

from extractforms.typing.models import MatchResult, SchemaField, SchemaSpec
from extractforms.schema_store import (
    SchemaStore,
    build_schema_revision,
    build_schema_with_generated_id,
)


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
    assert schema.version == 1
    assert schema.schema_family_id == schema.id


def test_schema_store_load_migrates_legacy_payload(tmp_path) -> None:
    store = SchemaStore(root=tmp_path)
    legacy = {
        "id": "legacy-1",
        "name": "Legacy",
        "fingerprint": "fp",
        "fields": [{"key": "a", "label": "A"}],
    }
    path = tmp_path / "legacy.schema.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = store.load(path)

    assert loaded.version == 1
    assert loaded.schema_family_id == "legacy-1"


def test_schema_store_save_uses_versioned_envelope(tmp_path) -> None:
    store = SchemaStore(root=tmp_path)
    schema = SchemaSpec(
        id="schema-1",
        name="Demo",
        fingerprint="abc",
        version=2,
        schema_family_id="family-1",
        fields=[SchemaField(key="x", label="X")],
    )

    path = store.save(schema)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_file_version"] == 2
    assert payload["schema"]["version"] == 2
    assert payload["schema"]["schema_family_id"] == "family-1"


def test_build_schema_revision_increments_version_and_family() -> None:
    previous = SchemaSpec(
        id="schema-1",
        name="Demo",
        fingerprint="fp",
        version=2,
        schema_family_id="family-1",
        fields=[SchemaField(key="a", label="A")],
    )
    revised = build_schema_revision(previous, fields=[SchemaField(key="b", label="B")])

    assert revised.version == 3
    assert revised.schema_family_id == "family-1"
    assert revised.id != previous.id
