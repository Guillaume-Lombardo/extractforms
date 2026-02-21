"""Schema cache and matching utilities."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from extractforms import logger
from extractforms.exceptions import SchemaStoreError
from extractforms.typing.models import MatchResult, SchemaField, SchemaSpec

_SCHEMA_FILE_VERSION = 2


class SchemaStore(BaseModel):
    """Filesystem-based schema cache."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    root: Path = Field(description="Cache directory root.")

    def model_post_init(self, __context: object, /) -> None:
        """Ensure the cache directory exists after model initialization.

        Args:
            __context (object): Pydantic model context.
        """
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def fingerprint_pdf(pdf_path: Path) -> str:
        """Compute stable PDF fingerprint.

        Args:
            pdf_path (Path): Input PDF path.

        Returns:
            str: SHA-256 hex digest.
        """
        digest = hashlib.sha256()
        with pdf_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def schema_path(
        self,
        *,
        schema_name: str,
        schema_id: str,
        fingerprint: str,
    ) -> Path:
        """Build schema cache path.

        Args:
            schema_name (str): Schema name.
            schema_id (str): Schema identifier.
            fingerprint (str): PDF fingerprint.

        Returns:
            Path: Cache path.
        """
        safe_name = re.sub(r"[^a-z0-9._-]+", "-", schema_name.lower()).strip("-")
        if not safe_name:
            safe_name = "schema"
        return self.root / f"{safe_name}-{schema_id}-{fingerprint}.schema.json"

    @staticmethod
    def load(path: Path) -> SchemaSpec:
        """Load schema from path.

        Args:
            path (Path): Schema file path.

        Returns:
            SchemaSpec: Loaded schema.
        """
        _validate_schema_file_path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        migrated = _migrate_schema_payload(payload)
        return SchemaSpec.model_validate(migrated)

    def save(self, schema: SchemaSpec) -> Path:
        """Persist schema to store.

        Args:
            schema (SchemaSpec): Schema payload.

        Returns:
            Path: Written file path.
        """
        path = self.schema_path(
            schema_name=schema.name,
            schema_id=schema.id,
            fingerprint=schema.fingerprint,
        )
        envelope = {
            "schema_file_version": _SCHEMA_FILE_VERSION,
            "schema": schema.model_dump(mode="json"),
        }
        path.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")
        logger.info("Schema cached", extra={"schema_path": str(path)})
        return path

    def list_schemas(self) -> list[Path]:
        """List cached schema files.

        Returns:
            list[Path]: Schema files.
        """
        return sorted(self.root.glob("*.schema.json"))

    def match_schema(self, fingerprint: str) -> MatchResult:
        """Try finding an existing schema by fingerprint.

        Args:
            fingerprint (str): PDF fingerprint.

        Returns:
            MatchResult: Match details.
        """
        for path in self.list_schemas():
            schema = self.load(path)
            if schema.fingerprint == fingerprint:
                return MatchResult(
                    matched=True,
                    schema_id=schema.id,
                    score=1.0,
                    reason="fingerprint_match",
                )

        return MatchResult(matched=False, reason="no_match")


def build_schema_with_generated_id(name: str, fingerprint: str, fields: list[SchemaField]) -> SchemaSpec:
    """Create schema with generated UUID id.

    Args:
        name (str): Schema name.
        fingerprint (str): Source document fingerprint.
        fields (list[SchemaField]): Schema fields.

    Returns:
        SchemaSpec: Generated schema.
    """
    schema_id = str(uuid4())
    return SchemaSpec(
        id=schema_id,
        name=name,
        fingerprint=fingerprint,
        version=1,
        schema_family_id=schema_id,
        fields=fields,
    )


def build_schema_revision(
    previous: SchemaSpec,
    *,
    fields: list[SchemaField],
    name: str | None = None,
) -> SchemaSpec:
    """Create a new schema revision from an existing schema.

    Args:
        previous (SchemaSpec): Existing schema.
        fields (list[SchemaField]): Revised fields payload.
        name (str | None): Optional revised schema name.

    Returns:
        SchemaSpec: New schema revision.
    """
    family_id = previous.schema_family_id or previous.id
    return SchemaSpec(
        id=str(uuid4()),
        name=name or previous.name,
        fingerprint=previous.fingerprint,
        version=previous.version + 1,
        schema_family_id=family_id,
        fields=fields,
    )


def _migrate_schema_payload(payload: object) -> dict[str, object]:
    """Migrate schema payload from file format versions to current model format.

    Args:
        payload (object): Raw JSON payload.

    Raises:
        SchemaStoreError: If payload is not a JSON object.

    Returns:
        dict[str, object]: Migrated schema object payload.
    """
    if not isinstance(payload, dict):
        raise SchemaStoreError(message="Schema payload must be a JSON object")

    payload_obj = cast("dict[str, object]", payload)
    schema_object = payload_obj
    embedded_schema = payload_obj.get("schema")
    if isinstance(embedded_schema, dict):
        schema_object = cast("dict[str, object]", embedded_schema)

    migrated = dict(schema_object)
    if "version" not in migrated:
        migrated["version"] = 1
    if "schema_family_id" not in migrated:
        schema_id = migrated.get("id")
        migrated["schema_family_id"] = schema_id if isinstance(schema_id, str) else None
    return migrated


def _validate_schema_file_path(path: Path) -> None:
    """Validate schema file path before loading.

    Args:
        path (Path): Schema file path.

    Raises:
        SchemaStoreError: If path is not a `pathlib.Path` or not a readable schema JSON file.
    """
    if not isinstance(path, Path):
        raise SchemaStoreError(message=f"Schema path must be a pathlib.Path instance, got: {type(path)!r}")
    if not path.is_file():
        raise SchemaStoreError(message=f"Schema path is not a file: {path}")
    if not path.name.endswith(".schema.json"):
        raise SchemaStoreError(message=f"Schema path must end with '.schema.json': {path}")
