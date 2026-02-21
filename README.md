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
- `--backend` (`multimodal` or `ocr`)
- `--drop-blank-pages`, `--blank-page-ink-threshold`, `--blank-page-near-white-level`
- `--extra-instructions`
- `--schema-id`, `--schema-path` (expects `*.schema.json`), `--match-schema`

Schema fields support both `kind` and optional `semantic_type` metadata for richer typing
(for example: phone, address, amount, iban, postal code).

## Environment

Copy `.env.template` to `.env` and configure:
- logging (`LOG_LEVEL`, `LOG_JSON`, `LOG_FILE`)
- enterprise network/TLS (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `CERT_PATH`)
- model endpoint (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`)
- backend selection (`EXTRACTION_BACKEND`, `OCR_PROVIDER_FACTORY`, `OCR_ENABLE_TEXT_NORMALIZATION`)
- extraction behavior (`DROP_BLANK_PAGES`, `BLANK_PAGE_INK_THRESHOLD`, `BLANK_PAGE_NEAR_WHITE_LEVEL`)

Security notes:
- `OPENAI_BASE_URL` must use `https://` in non-local environments (`http://` is accepted for localhost/loopback only).
- `--schema-path` accepts only schema cache files with `.schema.json` suffix.

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
