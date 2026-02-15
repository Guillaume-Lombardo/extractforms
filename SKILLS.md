# SKILLS.md

## Purpose

This file maps project delivery skills to the `extractforms` roadmap and clarifies when each skill should be applied during implementation and review cycles.

## Core Skills (Project Local)

- `skills/architecture/SKILL.md`
  - Use for module boundaries, backend abstraction design, and orchestration layering (`extractor`, `backends`, `schema_store`).
- `skills/testing/SKILL.md`
  - Use for test strategy across unit/integration/end2end and when adding regression tests for bugs.
- `skills/code-style/SKILL.md`
  - Use for style/lint/type consistency, docstring format, and enum/model conventions.
- `skills/tooling/SKILL.md`
  - Use for local tooling workflow (`uv`, `ruff`, `ty`, `pytest`, `pre-commit`) and dev setup reliability.
- `skills/review-followup/SKILL.md`
  - Use to close review comments and ensure PR feedback is fully addressed.

## Skill Usage by Roadmap Phase

- S1 (MVP)
  - Prioritize: architecture + testing + tooling.
  - Focus: strict contracts, multimodal extraction flow, enterprise network settings, and baseline CLI/API behavior.
- S2
  - Prioritize: architecture + testing.
  - Focus: page-by-page extraction, key-to-page mapping, schema matching heuristics and validations.
- S3
  - Prioritize: architecture + testing + review-followup.
  - Focus: OCR backend implementation, schema lifecycle hardening, and robust metrics/pricing observability.

## Operating Rules

- Prefer the smallest skill set that fully covers the task.
- Keep artifacts in English by default (French as complementary only if needed).
- Update this file if new project-local skills are added or if roadmap ownership changes significantly.
