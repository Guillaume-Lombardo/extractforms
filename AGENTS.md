# AGENTS.md

## Mission
Build and maintain a robust Python package with clear contracts, high code quality, and reliable delivery workflows.

## Current Stage
This template includes AI delivery tooling:
- agent governance (`agent.md`)
- execution roadmap (`plan.md`)
- reusable project skills (`skills/*`)

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

## Quality Gates
- Unit tests are the default run target.
- Before closing any PR, run all tests from `tests/unit`, `tests/integration`, and `tests/end2end`.
- Test markers are auto-applied by `tests/conftest.py`.
- Add at least one end-to-end test for each major user-visible flow.
- Add integration tests for boundary behavior when relevant.
- When a bug is reported, write a failing test first, then implement the fix.

## Delivery Workflow
- Implement each run, phase, and feature in a dedicated branch created for that specific scope.
- Do not develop features directly on the main branch.
- End every run, phase, and feature delivery with a GitHub Pull Request.
- Use PR review and CI as mandatory validation before merge.
- Before each push/PR, run one explicit dead-code pass and remove unused code/paths/imports no longer referenced.
- Before every push/PR, ensure docs/config bootstrap are synchronized with code changes:
  - update `README.md` when CLI behavior, setup, or workflow changes
  - update `.env.template` when environment variables change
  - update local `.env` accordingly for validation runs

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
- Confirm documentation/config sync:
  - `README.md` updated if behavior changed
  - `.env.template` updated if env contract changed
  - local `.env` updated for manual/e2e validation

## Skills
Project skills live in `skills/`:
- `skills/architecture/SKILL.md`
- `skills/testing/SKILL.md`
- `skills/code-style/SKILL.md`
- `skills/tooling/SKILL.md`
- `skills/review-followup/SKILL.md`
