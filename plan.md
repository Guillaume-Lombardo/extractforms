# plan.md

## Product

`extractforms` (Python package, module namespace `extractforms`): reusable key/value extraction from form-like PDFs.

## Goals

- Provide stable extraction of form fields with strict structured outputs.
- Support enterprise environments (proxy, internal TLS CA, configurable httpx clients).
- Expose a clear CLI and stable Python API.
- Prepare backend abstraction for multimodal and OCR strategies.

## Scope Baseline

- Primary extraction backend: multimodal LLM via OpenAI-compatible `chat.completions` (LiteLLM proxy path).
- Complementary path: OCR backend interface, MVP stub in first phase.
- Extraction modes:
  - `PassMode.ONE_PASS`
  - `PassMode.TWO_PASS` (recommended default)
  - `PassMode.ONE_SCHEMA_PASS`
- PDF input rendered to images (PyMuPDF/fitz), configurable DPI/format.
- Strict structured JSON output using `response_format=json_schema` plus sanitizer.
- Schema caching by stable fingerprint (`sha256(pdf)`), with `--no-cache` override.

## Target CLI (MVP+)

- `extractforms extract --input <pdf> [--output <json>] [--passes 1|2] [--no-cache]`
- Extra flags:
  - `--dpi`, `--image-format`, `--page-start`, `--page-end`, `--max-pages`
  - `--chunk-pages`
  - `--extra-instructions`
  - `--schema-id`, `--schema-path`
  - `--match-schema`

## Target Python API (stable)

- `infer_schema(request, settings) -> tuple[SchemaSpec, PricingCall | None]`
- `extract_values(schema, request, settings) -> tuple[ExtractionResult, PricingCall | None]`
- `extract_one_pass(request, settings) -> tuple[ExtractionResult, PricingCall | None]`
- `match_schema(pdf, schemas_store, settings) -> MatchResult`
- `persist_result(result, path) -> None`

## Data Contracts

- `SchemaSpec`: `id`, `name`, `fingerprint`, `fields[]`.
- `SchemaField`: `key`, `label`, `page`, `kind`, optional validation/type metadata.
- `ExtractionResult`:
  - `fields`: `{key, value, page, confidence}`[]
  - `flat`: `dict[str, str]`
  - `schema_fields_count`
  - `pricing`
- `ExtractRequest`: input/output/mode/cache/render/chunking/instructions.
- Null sentinel for missing values: default `"NULL"`.

## Architecture Plan

- Package layout target:
  - `src/extractforms/__init__.py`
  - `src/extractforms/settings.py`
  - `src/extractforms/logging.py`
  - `src/extractforms/cli.py`
  - `src/extractforms/enums.py`
  - `src/extractforms/models.py`
  - `src/extractforms/pdf_render.py`
  - `src/extractforms/schema_store.py`
  - `src/extractforms/backends/protocol.py`
  - `src/extractforms/backends/multimodal_openai.py`
  - `src/extractforms/backends/ocr_document_intelligence.py` (stub in MVP)
  - `src/extractforms/prompts.py`
  - `src/extractforms/extractor.py`
  - `src/extractforms/pricing.py`
- Interface boundaries:
  - `PageSource`: `render_images()`, `ocr_pages()`
  - `ExtractorBackend`: `infer_schema(pages)`, `extract_values(pages, keys)`

## Enterprise Runtime Plan

- Settings contract via env + optional `.env`:
  - proxies: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`
  - TLS/network: `CERT_PATH`, `TIMEOUT`, `MAX_CONNECTIONS`
- Build `SSLContext` with:
  - `create_default_context(cafile=...)`
  - `CERT_REQUIRED`
  - minimum `TLSv1_2`
- Build `httpx.Client`/`AsyncClient` with:
  - proxy configuration compatible with selected httpx version
  - `verify=ssl_context`
  - `limits=Limits(max_connections=...)`
- Logging:
  - structlog JSON default
  - optional human-readable rendering
  - controlled configuration for noisy libraries (`httpx`, etc.)

## PR Governance

- Every delivery must go through a PR with CI and Copilot review requested.
- Poll CI and review status every 60 seconds until results are available.
- Apply pertinent review feedback before merge; if feedback is not pertinent, record a short technical rationale in PR discussion.
- Respect engineering and architecture guardrails from:
  - `docs/engineering/DEFINITION_OF_DONE.md`
  - `docs/engineering/REVIEW_RUNBOOK.md`
  - `docs/adr/README.md`

## Iterative Roadmap

### S1 (MVP)

- Implement one-pass and two-pass multimodal extraction flows.
- Add strict response schema handling and sanitization.
- Add schema cache persistence by fingerprint.
- Deliver `extract` CLI and stable API surface.
- Implement enterprise network/TLS settings and httpx client factory.
- Add core unit tests (models/prompts/fingerprint/render/pricing/settings).

### S2

- Implement page-by-page value extraction using `SchemaField.page`.
- Add fallback key-to-page mapping when page metadata is sparse.
- Implement simple schema matching (heuristics + metadata index).
- Support extraction batching (`--chunk-pages`) for larger documents.

### S3

- Implement OCR backend (Document Intelligence integration path).
- Add OCR-to-field reconstruction and optional text-only LLM normalization.
- Harden pricing/finops and extraction metrics.
- Add schema lifecycle management improvements (versioning/migrations).

## Acceptance Criteria (MVP)

- `extractforms extract --passes 2` generates:
  - schema cache file under schema store
  - result JSON with all schema keys present (no key omission)
  - missing values populated with sentinel `"NULL"`
- Extraction works behind proxy with internal CA configuration.
- Local quality checks pass for MVP scope:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run ty check src tests`
  - `uv run pytest -m unit`

## Testing Strategy

- Unit tests:
  - pydantic models and enum parsing/serialization
  - prompt builders and schema sanitizer behavior
  - fingerprint stability and schema cache naming
  - PDF render orchestration with mocks
  - pricing aggregation behavior
- Integration tests:
  - backend orchestration with mocked LLM responses and strict JSON validation
  - schema store read/write + matching flow on fixtures
- End-to-end tests:
  - sample PDF extraction via CLI
  - one-pass and two-pass smoke coverage
  - regression for null sentinel and output contract

## Risks and Mitigations

- Risk: model output drift from strict schema.
  - Mitigation: sanitizer + strict parse validation + deterministic post-processing.
- Risk: enterprise proxy/TLS misconfiguration.
  - Mitigation: explicit settings validation and startup diagnostics.
- Risk: high token/image cost on long documents.
  - Mitigation: page chunking, page-targeted extraction, schema cache reuse.
