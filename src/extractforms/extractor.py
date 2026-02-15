"""Extraction orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from extractforms.backends.multimodal_openai import MultimodalLLMBackend
from extractforms.exceptions import ExtractionError
from extractforms.pdf_render import render_pdf_pages
from extractforms.pricing import merge_pricing_calls
from extractforms.schema_store import SchemaStore
from extractforms.typing.enums import ConfidenceLevel, PassMode
from extractforms.typing.models import (
    ExtractionResult,
    ExtractRequest,
    FieldValue,
    MatchResult,
    PricingCall,
    SchemaSpec,
)

if TYPE_CHECKING:
    from extractforms.settings import Settings


def _confidence_rank(confidence: ConfidenceLevel) -> int:
    """Return a comparable rank for confidence values.

    Args:
        confidence: Confidence label.

    Returns:
        int: Comparable rank where higher is more confident.
    """
    rank = {
        ConfidenceLevel.UNKNOWN: 0,
        ConfidenceLevel.LOW: 1,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.HIGH: 3,
    }
    return rank[confidence]


def _select_better_value(current: FieldValue | None, candidate: FieldValue) -> FieldValue:
    """Select the better field value between current and candidate.

    Args:
        current: Currently selected value for the key.
        candidate: New candidate value.

    Returns:
        FieldValue: Selected value.
    """
    if current is None:
        return candidate

    current_blank = not current.value.strip()
    candidate_blank = not candidate.value.strip()
    if current_blank and not candidate_blank:
        return candidate
    if not current_blank and candidate_blank:
        return current
    if _confidence_rank(candidate.confidence) > _confidence_rank(current.confidence):
        return candidate
    return current


def _extract_values_for_keys(
    *,
    backend: MultimodalLLMBackend,
    pages: list,
    keys: list[str],
    chunk_pages: int,
    extra_instructions: str | None,
) -> tuple[list[FieldValue], list[PricingCall]]:
    """Extract values for a key set with optional page chunking.

    Args:
        backend: Extraction backend.
        pages: Rendered pages.
        keys: Keys to extract.
        chunk_pages: Requested chunk size.
        extra_instructions: Additional prompt instructions.

    Returns:
        tuple[list[FieldValue], list[PricingCall]]: Extracted values and pricing calls.
    """
    if not keys:
        return [], []

    normalized_chunk = max(chunk_pages, 1)
    page_batches: list[list] = []
    if normalized_chunk == 1 or normalized_chunk >= len(pages):
        page_batches = [pages]
    else:
        for start in range(0, len(pages), normalized_chunk):
            page_batches.append(pages[start : start + normalized_chunk])

    by_key: dict[str, FieldValue] = {}
    pricing_calls: list[PricingCall] = []
    for batch in page_batches:
        batch_values, call = backend.extract_values(
            batch,
            keys,
            extra_instructions=extra_instructions,
        )
        for value in batch_values:
            by_key[value.key] = _select_better_value(by_key.get(value.key), value)
        if call:
            pricing_calls.append(call)

    return list(by_key.values()), pricing_calls


def _build_result(
    *,
    schema: SchemaSpec,
    values: list[FieldValue],
    null_sentinel: str,
    pricing: PricingCall | None,
) -> ExtractionResult:
    """Build normalized extraction result.

    Args:
        schema: Reference schema.
        values: Extracted values from backend.
        null_sentinel: Null fallback value.
        pricing: Aggregated pricing.

    Returns:
        ExtractionResult: Normalized result.
    """
    by_key = {field.key: field for field in values}

    normalized: list[FieldValue] = []
    flat: dict[str, str] = {}

    for schema_field in schema.fields:
        field_value = by_key.get(schema_field.key)
        if field_value is None or not field_value.value.strip():
            value = null_sentinel
            confidence = field_value.confidence if field_value else ConfidenceLevel.UNKNOWN
            page = field_value.page if field_value else schema_field.page
            normalized_value = FieldValue(
                key=schema_field.key,
                value=value,
                page=page,
                confidence=confidence,
            )
        else:
            normalized_value = field_value

        normalized.append(normalized_value)
        flat[normalized_value.key] = normalized_value.value

    return ExtractionResult(
        fields=normalized,
        flat=flat,
        schema_fields_count=len(schema.fields),
        pricing=pricing,
    )


def infer_schema(request: ExtractRequest, settings: Settings) -> tuple[SchemaSpec, PricingCall | None]:
    """Infer schema from a document.

    Args:
        request: Extraction request.
        settings: Runtime settings.

    Returns:
        tuple[SchemaSpec, PricingCall | None]: Inferred schema and pricing.
    """
    fingerprint = SchemaStore.fingerprint_pdf(request.input_path)
    pages = render_pdf_pages(
        request.input_path,
        dpi=request.dpi,
        image_format=request.image_format,
        page_start=request.page_start,
        page_end=request.page_end,
        max_pages=request.max_pages,
    )

    backend = MultimodalLLMBackend(settings)
    schema, pricing = backend.infer_schema(pages)
    schema_with_identity = SchemaSpec(
        id=str(uuid4()),
        name=schema.name or request.input_path.stem,
        fingerprint=fingerprint,
        fields=schema.fields,
    )
    return schema_with_identity, pricing


def _group_keys_by_page(schema: SchemaSpec) -> dict[int, list[str]]:
    """Group schema keys by page.

    Args:
        schema: Schema to group.

    Returns:
        dict[int, list[str]]: Keys by page.
    """
    keys_by_page: dict[int, list[str]] = {}
    for field in schema.fields:
        if field.page is None:
            continue
        keys_by_page.setdefault(field.page, []).append(field.key)
    return keys_by_page


def extract_values(  # noqa: PLR0914
    schema: SchemaSpec,
    request: ExtractRequest,
    settings: Settings,
) -> tuple[ExtractionResult, PricingCall | None]:
    """Extract values using an existing schema.

    Args:
        schema: Schema used for extraction.
        request: Extraction request.
        settings: Runtime settings.

    Returns:
        tuple[ExtractionResult, PricingCall | None]: Result and pricing.
    """
    pages = render_pdf_pages(
        request.input_path,
        dpi=request.dpi,
        image_format=request.image_format,
        page_start=request.page_start,
        page_end=request.page_end,
        max_pages=request.max_pages,
    )
    backend = MultimodalLLMBackend(settings)

    calls: list[PricingCall] = []
    extracted_values: list[FieldValue] = []

    keys_by_page = _group_keys_by_page(schema)
    non_paged_keys = [field.key for field in schema.fields if field.page is None]

    if keys_by_page:
        pages_by_number = {page.page_number: page for page in pages}
        for page_number, keys in sorted(keys_by_page.items()):
            page = pages_by_number.get(page_number)
            if not page:
                continue
            page_values, call = backend.extract_values(
                [page],
                keys,
                extra_instructions=request.extra_instructions,
            )
            extracted_values.extend(page_values)
            if call:
                calls.append(call)
        non_paged_values, non_paged_calls = _extract_values_for_keys(
            backend=backend,
            pages=pages,
            keys=non_paged_keys,
            chunk_pages=request.chunk_pages,
            extra_instructions=request.extra_instructions,
        )
        extracted_values.extend(non_paged_values)
        calls.extend(non_paged_calls)
    else:
        keys = [field.key for field in schema.fields]
        extracted_values, chunk_calls = _extract_values_for_keys(
            backend=backend,
            pages=pages,
            keys=keys,
            chunk_pages=request.chunk_pages,
            extra_instructions=request.extra_instructions,
        )
        calls.extend(chunk_calls)

    pricing = merge_pricing_calls(calls)
    result = _build_result(
        schema=schema,
        values=extracted_values,
        null_sentinel=settings.null_sentinel,
        pricing=pricing,
    )
    return result, pricing


def extract_one_pass(
    request: ExtractRequest,
    settings: Settings,
) -> tuple[ExtractionResult, PricingCall | None]:
    """Run one-pass extraction.

    Args:
        request: Extraction request.
        settings: Runtime settings.

    Returns:
        tuple[ExtractionResult, PricingCall | None]: Result and pricing.
    """
    schema, schema_pricing = infer_schema(request, settings)
    result, values_pricing = extract_values(schema, request, settings)

    merged_pricing = merge_pricing_calls([
        call for call in [schema_pricing, values_pricing] if call is not None
    ])
    result_with_pricing = result.model_copy(update={"pricing": merged_pricing})
    return result_with_pricing, merged_pricing


def match_schema(pdf: Path, schemas_store: SchemaStore, _settings: Settings) -> MatchResult:
    """Match document against schema cache.

    Args:
        pdf: PDF to match.
        schemas_store: Schema storage.
        _settings: Runtime settings (currently unused; reserved for future matching configuration).

    Returns:
        MatchResult: Match payload.
    """
    fingerprint = SchemaStore.fingerprint_pdf(pdf)
    return schemas_store.match_schema(fingerprint)


def _extract_for_schema_id(
    store: SchemaStore,
    schema_id: str,
    request: ExtractRequest,
    settings: Settings,
) -> ExtractionResult | None:
    """Load and extract values for a schema id if found.

    Args:
        store: Schema store.
        schema_id: Candidate schema id.
        request: Extraction request.
        settings: Runtime settings.

    Returns:
        ExtractionResult | None: Extraction result when found, otherwise None.
    """
    for schema_path in store.list_schemas():
        candidate = store.load(schema_path)
        if candidate.id == schema_id:
            result, _ = extract_values(candidate, request, settings)
            return result
    return None


def persist_result(result: ExtractionResult, path: Path) -> None:
    """Persist extraction result as JSON.

    Args:
        result: Result payload.
        path: Output path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def run_extract(request: ExtractRequest, settings: Settings) -> ExtractionResult:  # noqa: C901
    """Top-level extraction flow used by CLI.

    Args:
        request: Extraction request.
        settings: Runtime settings.

    Raises:
        ExtractionError: If request mode is unsupported.

    Returns:
        ExtractionResult: Extraction output.
    """
    store = SchemaStore(root=Path(settings.schema_cache_dir))

    if request.schema_path:
        schema = store.load(request.schema_path)
        result, _ = extract_values(schema, request, settings)
        return result

    if request.mode == PassMode.ONE_PASS:
        result, _ = extract_one_pass(request, settings)
        return result

    if request.mode == PassMode.ONE_SCHEMA_PASS:
        if not request.schema_id:
            raise ExtractionError(message="ONE_SCHEMA_PASS requires --schema-id or --schema-path")

        result = _extract_for_schema_id(store, request.schema_id, request, settings)
        if result is not None:
            return result
        raise ExtractionError(message=f"Schema id not found: {request.schema_id}")

    if request.mode == PassMode.TWO_PASS:
        fingerprint = SchemaStore.fingerprint_pdf(request.input_path)

        if request.match_schema or request.use_cache:
            matched = store.match_schema(fingerprint)
            if matched.matched and matched.schema_id:
                result = _extract_for_schema_id(store, matched.schema_id, request, settings)
                if result is not None:
                    return result

        schema, _ = infer_schema(request, settings)
        if request.use_cache:
            store.save(schema)

        result, _ = extract_values(schema, request, settings)
        return result

    raise ExtractionError(message=f"Unsupported mode: {request.mode}")


def result_to_json_dict(result: ExtractionResult) -> dict[str, object]:
    """Return result payload for custom serialization paths.

    Args:
        result: Extraction result.

    Returns:
        dict[str, object]: JSON-serializable dictionary.
    """
    return json.loads(result.model_dump_json())
