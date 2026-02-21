# 0001 - Modular typing models and schema load hardening

## Context

`extractforms` reached a stage where `typing/models.py` was aggregating unrelated domains
(schema, extraction runtime, page selection, structured output). This made refactors harder,
increased import churn, and complicated reviewability.

At the same time, schema loading accepted arbitrary JSON file names and endpoint URL validation
allowed plain HTTP for non-local targets.

## Decision

- Split Pydantic models into a dedicated package:
  - `typing/models/schema.py`
  - `typing/models/extraction.py`
  - `typing/models/page_selection.py`
  - `typing/models/json_schema.py`
  - Re-export through `typing/models/__init__.py` to preserve public imports.
- Harden schema loading constraints:
  - enforce `.schema.json` suffix on schema files
  - reject non-object JSON schema payloads explicitly
- Harden endpoint configuration:
  - require `https://` for `OPENAI_BASE_URL` outside localhost/loopback.

## Alternatives considered

- Keep a single `typing/models.py` and add sections/comments only.
- Introduce a fully separate `domain/` package and move models + orchestration in one large migration.

## Consequences

- Positives:
  - clearer model boundaries, easier targeted reviews/tests
  - safer schema loading path and endpoint defaults
  - public import stability preserved (`extractforms.typing.models`)
- Negatives:
  - more files to navigate
  - slight maintenance overhead for re-export indexes
- Risks:
  - accidental internal import path drift during future refactors
