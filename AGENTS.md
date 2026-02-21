# AGENTS.md

## Mission

Build and maintain a robust Python package, `extractforms` (module `extractforms`), to extract key/value fields from form-like PDF documents with enterprise-ready operational constraints.

## Product Scope

- Primary backend: multimodal LLM extraction through OpenAI-compatible `chat.completions` endpoints (served via LiteLLM proxy).
- Secondary/alternative backend: OCR-based extraction path (Document Intelligence style), initially as MVP stub with explicit interfaces.
- Main user value: reliable form field extraction with reproducible schemas, strict structured outputs, and predictable runtime behavior behind enterprise networks.

## Current Stage

This template includes AI delivery tooling:

- agent governance (`agent.md`)
- execution roadmap (`plan.md`)
- reusable project skills (`skills/*`)
- LLM workflow index (`SKILLS.md`)

## Working Rules

- Use English as the default language for docstrings, README, and core project artifacts.
- Allow French only as a secondary translation or complementary version when needed.
- Keep architecture modular and boundaries explicit.
- Keep runtime dependencies explicit and configurable.
- Do not couple business logic to infrastructure details.
- Prefer typed enums for user-facing choices:
  - use `enum.StrEnum` for single-choice values
  - use `enum.Flag`/`enum.IntFlag` for combinable choices
  - provide explicit conversions from `str` to enum/flag and back
- Write Google-style docstrings with explicit types in `Args` and `Returns` (and `Raises` when relevant).

## Domain Contracts (MVP)

- Core models:
  - `SchemaSpec` (id, name, fingerprint, fields)
  - `SchemaField` (key, label, page, kind, optional type/regex/options)
  - `ExtractionResult` (fields, flat map, schema_fields_count, pricing, metadata)
  - `ExtractRequest` (input/output, mode, cache, render settings, chunking, instructions)
- Null sentinel policy:
  - Missing/empty values must be emitted as a consistent sentinel (`"NULL"` by default).
- Extraction modes:
  - `PassMode.ONE_PASS`
  - `PassMode.TWO_PASS`
  - `PassMode.ONE_SCHEMA_PASS`
- Structured output policy:
  - enforce strict JSON schema responses (`response_format=json_schema`)
  - forbid extra properties and sanitize schemas for provider compatibility.

## Enterprise Runtime Constraints

- Support environment-based network configuration:
  - `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`
  - `CERT_PATH`, `TIMEOUT`, `MAX_CONNECTIONS`
- Build explicit TLS configuration via `ssl.SSLContext` with:
  - internal CA support (`cafile`)
  - certificate verification required
  - minimum TLS 1.2
- Build `httpx` clients with explicit `verify`, proxy, timeout, and connection limits.

## Quality Gates

- Unit tests are the default run target.
- Before closing any PR, run all tests from `tests/unit`, `tests/integration`, and `tests/end2end`.
- Test markers are auto-applied by `tests/conftest.py`.
- Add at least one end-to-end test for each major user-visible flow.
- Add integration tests for boundary behavior when relevant.
- When a bug is reported, write a failing test first, then implement the fix.

## Delivery Workflow

- Implement each run, phase, and feature in a dedicated branch created for that specific scope.
- All future work must start by creating or switching to a dedicated non-`main` branch.
- Do not develop features directly on the main branch.
- End every run, phase, and feature delivery with a GitHub Pull Request.
- Use PR review and CI as mandatory validation before merge.
- For every created PR, wait for CI completion and Copilot review publication before finalizing.
- Poll PR status every 60 seconds (`gh pr checks` + `gh pr view ...reviews/comments`) for up to 20 cycles (20 minutes) until:
  - CI is no longer pending, and
  - at least one Copilot review is present (or Copilot definitively reports no review for this PR).
- Do not stop polling right after CI success if Copilot review is still missing.
- As soon as a review appears, process it immediately (address pertinent comments in code/tests/docs, and justify non-pertinent comments in PR discussion) without waiting for remaining cycles.
- Evaluate review comments for technical relevance; address pertinent comments in code/tests/docs and explicitly justify non-pertinent comments in the PR discussion.
- Before each push/PR, run one explicit dead-code pass and remove unused code/paths/imports no longer referenced.
- Before every push/PR, ensure docs/config bootstrap are synchronized with code changes:
  - update `README.md` when CLI behavior, setup, or workflow changes
  - update `.env.template` when environment variables change
  - update local `.env` accordingly for validation runs
- Before implementation and before merge, review and respect engineering guidance in:
  - `docs/engineering/DEFINITION_OF_DONE.md`
  - `docs/engineering/REVIEW_RUNBOOK.md`
  - `docs/adr/README.md`
- Document architecture decisions in `docs/adr/` whenever a change introduces or modifies a structural/architectural choice.
- Keep unit tests mirrored to package layout under `tests/unit/...` without reintroducing an extra `extractforms` path segment.
- Example: `src/extractforms/backends/multimodal_openai.py` maps to `tests/unit/backends/test_multimodal_openai.py`.
- Do not modify `ruff.toml` unless the user explicitly requests it.

## Pre-PR Checklist

Run locally:

- `uv run ruff format .`
- `uv run ruff check .`
- `uv run ty check src tests`
- `uv run pytest -m unit`
- `uv run pytest -m integration`
- `uv run pytest -m end2end`
- `uv run pre-commit run --all-files`
- Run a dead-code cleanup pass (remove unused code, stale helpers, and obsolete branches).
- Verify Google-style docstrings include explicit types in `Args` and `Returns` for modified code paths.
- Verify `tests/unit` structure still mirrors `src/extractforms` after refactors/moves.
- Confirm documentation/config sync:
  - `README.md` updated if behavior changed
  - `.env.template` updated if env contract changed
  - local `.env` updated for manual/e2e validation
  - `docs/adr/*` updated when architecture decisions changed

## Skills

Project skills live in `skills/`:

- `skills/architecture/SKILL.md`
- `skills/testing/SKILL.md`
- `skills/code-style/SKILL.md`
- `skills/tooling/SKILL.md`
- `skills/review-followup/SKILL.md`
