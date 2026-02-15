# agent.md

## Role

Pragmatic software agent for the `extractforms` package (`extractforms` module).

## Objective

Deliver high-quality, maintainable increments for a Python package and its CLI/API to extract key/value form fields from PDFs through multimodal LLM first, with OCR-ready backend abstractions.

## Key Principles

- Keep contracts explicit (CLI, API, config, outputs).
- Preserve reproducibility with explicit configuration.
- Keep strict boundaries between domain orchestration and backend/infrastructure adapters.
- Keep tests and docs aligned with behavior.
- Build enterprise-ready network behavior (proxy + internal TLS CA) into settings and HTTP clients.

## Collaboration Contract

- Clarify unclear scope before coding critical parts.
- Surface assumptions explicitly when requirements are incomplete.
- Prefer small, testable increments aligned with `plan.md` phases.
- Keep docs, skills, and plan synchronized with implementation.
- Never implement on `main`; all subsequent work must happen on a dedicated feature branch.
- For each PR, monitor CI and Copilot review by polling every 60 seconds until:
  - CI is finished (not pending), and
  - Copilot review has been posted (or is explicitly absent for this PR).
- Do not stop at CI success when Copilot review is still pending.
- Address technically relevant review comments with code/test/doc updates; document rationale when comments are not applicable.
- Always align decisions with `docs/engineering/*` and `docs/adr/*` guidance before considering work done.
- Record architecture decisions in `docs/adr/` when introducing or changing architecture/structure choices.
- Enforce unit-test layout parity under `tests/unit/...` without adding an extra `extractforms` directory segment.
- Example: `src/extractforms/backends/multimodal_openai.py` maps to `tests/unit/backends/test_multimodal_openai.py`.
- Never modify `ruff.toml` unless explicitly requested by the user.

## Extraction Strategy Guardrails

- Default recommendation: `TWO_PASS` extraction.
  - Pass 1 infers stable schema and metadata.
  - Pass 2 extracts values using schema constraints.
- Support `ONE_PASS` for simplicity and `ONE_SCHEMA_PASS` when user provides schema input.
- Ensure strict JSON structured outputs with schema sanitization and `extra="forbid"` semantics.
- Enforce null sentinel behavior (`"NULL"` unless configured otherwise) for missing values.

## Definition Of Done (feature level)

A feature is done only if:

- implementation is complete and typed
- tests exist at relevant levels (unit/integration/end2end as needed)
- lint/format/type checks pass
- dead code pass is completed and unused code is removed
- docs/plan updates are applied when architecture or behavior changes
- `docs/adr/*` is updated when architecture decisions are introduced or revised
- `README.md` is synchronized with user-facing behavior and commands
- `.env.template` is synchronized with the environment variable contract
- local `.env` is updated for validation before push/PR
- modified code uses Google-style docstrings with explicit argument/return types
- `tests/unit` structure mirrors `src/extractforms`

## Non-Goals (for now)

- Do not introduce unrelated features in the same change.
- Do not add hidden runtime dependencies without explicit documentation.
- Long-term, avoid hardwiring one extraction backend into the domain layer.
- Current MVP intentionally wires `MultimodalLLMBackend` in the orchestrator and should migrate to protocol/factory-based backend selection as OCR support matures.
