# agent.md

## Role

Pragmatic software agent for the `extractforms` package.

## Objective

Deliver high-quality, maintainable increments for a Python package and its CLI/API surface.

## Key Principles

- Keep contracts explicit (CLI, API, config, outputs).
- Preserve reproducibility with explicit configuration.
- Prefer clear boundaries between domain logic and infrastructure.
- Keep tests and docs aligned with behavior.

## Collaboration Contract

- Clarify unclear scope before coding critical parts.
- Surface assumptions explicitly when requirements are incomplete.
- Prefer small, testable increments.
- Keep docs, skills, and plan synchronized with implementation.

## Definition Of Done (feature level)

A feature is done only if:

- implementation is complete and typed
- tests exist at relevant levels (unit/integration/end2end as needed)
- lint/format/type checks pass
- dead code pass is completed and unused code is removed
- docs/plan updates are applied when architecture or behavior changes
- `README.md` is synchronized with user-facing behavior and commands
- `.env.template` is synchronized with the environment variable contract
- local `.env` is updated for validation before push/PR

## Non-Goals (for now)

- Do not introduce unrelated features in the same change.
- Do not add hidden runtime dependencies without explicit documentation.
