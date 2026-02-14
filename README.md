# ExtractForms

A python project to turn scanned forms into a list of key-value pairs.

## Quickstart

```bash
uv sync --group dev
uv run pre-commit install
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run pytest
uv run pre-commit run --all-files
```

## First Commit

```bash
git add .
git commit -m "initial commit"
git push -u origin main
```

## Project Layout

- `src/extractforms`: package code
- `tests/unit`: fast default tests
- `tests/integration`: component-level tests
- `tests/end2end`: user-facing behavior tests
- `skills`: AI helper skills for coding workflows

## Release

1. Bump `version` in `pyproject.toml`.
2. Create and push a git tag: `vX.Y.Z`.
3. GitHub Action publishes to PyPI.

For manual validation, use workflow dispatch with `publish_target=testpypi`.
