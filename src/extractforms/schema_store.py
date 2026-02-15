"""Schema cache and matching utilities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from extractforms.logging import get_logger
from extractforms.models import MatchResult, SchemaField, SchemaSpec

logger = get_logger(__name__)


class SchemaStore(BaseModel):
    """Filesystem-based schema cache."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    root: Path = Field(description="Cache directory root.")

    def model_post_init(self, __context: object, /) -> None:
        """Ensure the cache directory exists after model initialization.

        Args:
            __context: Pydantic model context.
        """
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def fingerprint_pdf(pdf_path: Path) -> str:
        """Compute stable PDF fingerprint.

        Args:
            pdf_path: Input PDF path.

        Returns:
            str: SHA-256 hex digest.
        """
        digest = hashlib.sha256()
        with pdf_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def schema_path(self, *, schema_name: str, schema_id: str, fingerprint: str) -> Path:
        """Build schema cache path.

        Args:
            schema_name: Schema name.
            schema_id: Schema identifier.
            fingerprint: PDF fingerprint.

        Returns:
            Path: Cache path.
        """
        safe_name = schema_name.replace(" ", "-").lower()
        return self.root / f"{safe_name}-{schema_id}-{fingerprint}.schema.json"

    def load(self, path: Path) -> SchemaSpec:
        """Load schema from path.

        Args:
            path: Schema file path.

        Returns:
            SchemaSpec: Loaded schema.
        """
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SchemaSpec.model_validate(payload)

    def save(self, schema: SchemaSpec) -> Path:
        """Persist schema to store.

        Args:
            schema: Schema payload.

        Returns:
            Path: Written file path.
        """
        path = self.schema_path(
            schema_name=schema.name,
            schema_id=schema.id,
            fingerprint=schema.fingerprint,
        )
        path.write_text(schema.model_dump_json(indent=2), encoding="utf-8")
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
            fingerprint: PDF fingerprint.

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
        name: Schema name.
        fingerprint: Source document fingerprint.
        fields: Schema fields.

    Returns:
        SchemaSpec: Generated schema.
    """
    return SchemaSpec(id=str(uuid4()), name=name, fingerprint=fingerprint, fields=fields)
