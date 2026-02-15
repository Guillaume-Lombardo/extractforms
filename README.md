# ExtractForms

`extractforms` is a Python package and CLI to extract key/value fields from PDF forms.

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

## CLI

```bash
extractforms extract --input form.pdf --output results/result.json --passes 2
```

Supported options include:
- `--no-cache`
- `--dpi`, `--image-format`, `--page-start`, `--page-end`, `--max-pages`
- `--chunk-pages`
- `--extra-instructions`
- `--schema-id`, `--schema-path`, `--match-schema`

## Environment

Copy `.env.template` to `.env` and configure:
- logging (`LOG_LEVEL`, `LOG_JSON`, `LOG_FILE`)
- enterprise network/TLS (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `CERT_PATH`)
- model endpoint (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`)

## Project Layout

- `/Users/g1lom/Documents/extractforms/src/extractforms`: package code
- `/Users/g1lom/Documents/extractforms/tests/unit`: fast default tests
- `/Users/g1lom/Documents/extractforms/tests/integration`: component-level tests
- `/Users/g1lom/Documents/extractforms/tests/end2end`: user-facing behavior tests
- `/Users/g1lom/Documents/extractforms/skills`: AI helper skills for coding workflows

## Release

1. Bump `version` in `pyproject.toml`.
2. Create and push a git tag: `vX.Y.Z`.
3. GitHub Action publishes to PyPI.

For manual validation, use workflow dispatch with `publish_target=testpypi`.
