# plan.md

## Product

- [x] `extractforms` (Python package, module namespace `extractforms`): reusable key/value extraction from form-like PDFs.

## Goals

- [x] Provide stable extraction of form fields with strict structured outputs.
- [x] Support enterprise environments (proxy, internal TLS CA, configurable httpx clients).
- [x] Expose a clear CLI and stable Python API.
- [x] Prepare backend abstraction for multimodal and OCR strategies.

## Scope Baseline

- [x] Primary extraction backend: multimodal LLM via OpenAI-compatible `chat.completions` (LiteLLM proxy path).
- [x] Complementary path: OCR backend interface, MVP stub in first phase.
- [x] Extraction mode: `PassMode.ONE_PASS`.
- [x] Extraction mode: `PassMode.TWO_PASS` (recommended default).
- [x] Extraction mode: `PassMode.ONE_SCHEMA_PASS`.
- [x] PDF input rendered to images (PyMuPDF/fitz), configurable DPI/format.
- [x] Strict structured JSON output using `response_format=json_schema` plus sanitizer.
- [x] Schema caching by stable fingerprint (`sha256(pdf)`), with `--no-cache` override.

## Target CLI (MVP+)

- [x] `extractforms extract --input <pdf> [--output <json>] [--passes 1|2] [--no-cache]`.
- [x] Flag `--dpi`.
- [x] Flag `--image-format`.
- [x] Flag `--page-start`.
- [x] Flag `--page-end`.
- [x] Flag `--max-pages`.
- [x] Flag `--chunk-pages`.
- [x] Flag `--extra-instructions`.
- [x] Flag `--schema-id`.
- [x] Flag `--schema-path`.
- [x] Flag `--match-schema`.

## Target Python API (stable)

- [x] `infer_schema(request, settings) -> tuple[SchemaSpec, PricingCall | None]`.
- [x] `extract_values(schema, request, settings) -> tuple[ExtractionResult, PricingCall | None]`.
- [x] `extract_one_pass(request, settings) -> tuple[ExtractionResult, PricingCall | None]`.
- [x] `match_schema(pdf, schemas_store, settings) -> MatchResult`.
- [x] `persist_result(result, path) -> None`.

## Data Contracts

- [x] `SchemaSpec`: `id`, `name`, `fingerprint`, `fields[]`.
- [x] `SchemaField`: `key`, `label`, `page`, `kind`, optional validation/type metadata.
- [x] `ExtractionResult.fields`: `{key, value, page, confidence}`[].
- [x] `ExtractionResult.flat`: `dict[str, str]`.
- [x] `ExtractionResult.schema_fields_count`.
- [x] `ExtractionResult.pricing`.
- [x] `ExtractRequest`: input/output/mode/cache/render/chunking/instructions.
- [x] Null sentinel for missing values: default `"NULL"`.

## Architecture Plan

- [x] Package layout includes:
- [x] `src/extractforms/__init__.py`
- [x] `src/extractforms/_bootstrap.py`
- [x] `src/extractforms/settings.py`
- [x] `src/extractforms/logging.py`
- [x] `src/extractforms/cli.py`
- [x] `src/extractforms/pdf_render.py`
- [x] `src/extractforms/schema_store.py`
- [x] `src/extractforms/backends/protocol.py`
- [x] `src/extractforms/backends/multimodal_openai.py`
- [x] `src/extractforms/backends/ocr_document_intelligence.py` (stub)
- [x] `src/extractforms/prompts.py`
- [x] `src/extractforms/extractor.py`
- [x] `src/extractforms/pricing.py`
- [x] `src/extractforms/typing/enums.py`
- [x] `src/extractforms/typing/models.py`
- [x] `src/extractforms/typing/protocol.py`
- [x] Interface boundary `PageSource`: `render_images()`, `ocr_pages()`.
- [x] Interface boundary `ExtractorBackend`: `infer_schema(pages)`, `extract_values(pages, keys)`.

## Enterprise Runtime Plan

- [x] Settings contract via env + optional `.env`.
- [x] Proxies: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`.
- [x] TLS/network: `CERT_PATH`, `TIMEOUT`, `MAX_CONNECTIONS`.
- [x] `SSLContext` uses `create_default_context(cafile=...)`.
- [x] `SSLContext` uses `CERT_REQUIRED`.
- [x] `SSLContext` enforces minimum `TLSv1_2`.
- [x] `httpx` clients get proxy configuration compatible with the selected httpx version.
- [x] `httpx` clients use `verify=ssl_context`.
- [x] `httpx` clients use `limits=Limits(max_connections=...)`.
- [x] Logging defaults to structlog JSON.
- [x] Optional human-readable log rendering.
- [x] Noisy-library log levels can be controlled (`httpx`, etc.).

## PR Governance

- [x] Every delivery must go through a PR with CI and Copilot review requested.
- [x] Poll CI and review status every 60 seconds until results are available.
- [x] Apply pertinent review feedback before merge.
- [x] If feedback is not pertinent, record a short technical rationale in PR discussion.
- [x] Respect guardrails from `docs/engineering/DEFINITION_OF_DONE.md`.
- [x] Respect guardrails from `docs/engineering/REVIEW_RUNBOOK.md`.
- [x] Respect guardrails from `docs/adr/README.md`.

## Iterative Roadmap

### S1 (MVP)

- [x] Implement one-pass and two-pass multimodal extraction flows.
- [x] Add strict response schema handling and sanitization.
- [x] Add schema cache persistence by fingerprint.
- [x] Deliver `extract` CLI and stable API surface.
- [x] Implement enterprise network/TLS settings and httpx client factory.
- [x] Add core unit tests (models/prompts/fingerprint/render/pricing/settings).

### S2

- [x] Implement page-by-page value extraction using `SchemaField.page`.
- [ ] Add fallback key-to-page mapping when page metadata is sparse.
- [x] Implement simple schema matching (heuristics + metadata index).
- [x] Support extraction batching (`--chunk-pages`) for larger documents.
- [x] Detect and filter near-blank PDF pages (recto/verso scan artifacts) before extraction.
- [x] Build logical-to-physical page mapping so schema page numbers remain reliable when blank pages exist.
- [x] Add explicit page markers to multimodal prompts to anchor page numbering in PDF order.
- [x] Extend schema typing with richer semantic field types (phone, address, amount, etc.).
- [x] Add typed-field normalization hooks (phone, amount, address) and validation-friendly metadata.

### S3

- [ ] Implement OCR backend (Document Intelligence integration path).
- [ ] Add OCR-to-field reconstruction and optional text-only LLM normalization.
- [ ] Harden pricing/finops and extraction metrics.
- [ ] Add schema lifecycle management improvements (versioning/migrations).

## Acceptance Criteria (MVP)

- [x] `extractforms extract --passes 2` generates a schema cache file under schema store.
- [x] `extractforms extract --passes 2` generates result JSON with all schema keys present (no key omission).
- [x] Missing values are populated with sentinel `"NULL"`.
- [x] Extraction works behind proxy with internal CA configuration.
- [x] Local quality checks pass for MVP scope.
- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check src tests`
- [x] `uv run pytest -m unit`

## Testing Strategy

- [x] Unit tests: pydantic models and enum parsing/serialization.
- [x] Unit tests: prompt builders and schema sanitizer behavior.
- [x] Unit tests: fingerprint stability and schema cache naming.
- [x] Unit tests: PDF render orchestration with mocks.
- [x] Unit tests: pricing aggregation behavior.
- [x] Integration tests: backend orchestration with mocked LLM responses and strict JSON validation.
- [x] Integration tests: schema store read/write + matching flow on fixtures.
- [x] End-to-end tests: sample PDF extraction via CLI.
- [x] End-to-end tests: one-pass and two-pass smoke coverage.
- [x] End-to-end tests: regression for null sentinel and output contract.
- [ ] Unit tests: blank-page detector and page-map heuristics.
- [ ] Integration tests: extraction behavior with interleaved blank pages and schema page routing.
- [ ] End-to-end tests: typed-field extraction flow (`phone`, `address`, `amount`) with null-sentinel invariants.

## Risks and Mitigations

- [x] Risk: model output drift from strict schema.
- [x] Mitigation: sanitizer + strict parse validation + deterministic post-processing.
- [x] Risk: enterprise proxy/TLS misconfiguration.
- [x] Mitigation: explicit settings validation and startup diagnostics.
- [x] Risk: high token/image cost on long documents.
- [x] Mitigation: page chunking, page-targeted extraction, schema cache reuse.
