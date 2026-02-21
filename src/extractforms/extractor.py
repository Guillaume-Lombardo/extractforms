"""Extraction orchestration."""

from __future__ import annotations

import asyncio
import importlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from extractforms.async_runner import run_async
from extractforms.backends.multimodal_openai import MultimodalLLMBackend
from extractforms.backends.ocr_document_intelligence import OCRBackend
from extractforms.backends.ocr_text_normalizer import OCRTextLLMNormalizer
from extractforms.exceptions import ExtractionError
from extractforms.pdf_render import render_pdf_pages
from extractforms.pricing import merge_pricing_calls
from extractforms.processing.normalization import normalize_typed_value
from extractforms.processing.page_selection import (
    analyze_page_selection,
    build_schema_page_mapping,
    filter_rendered_pages_to_nonblank,
)
from extractforms.schema_store import SchemaStore
from extractforms.typing.enums import ConfidenceLevel, ExtractionBackendType, PassMode
from extractforms.typing.models import (
    CollectSchemaValuesInput,
    ExtractionResult,
    ExtractRequest,
    FieldValue,
    MatchResult,
    PageSelectionAnalysis,
    PageSelectionRequest,
    PricingCall,
    RenderedPage,
    SchemaSpec,
)

if TYPE_CHECKING:
    from extractforms.backends.ocr_document_intelligence import OCRPageProvider
    from extractforms.settings import Settings
    from extractforms.typing.protocol import ExtractorBackend


def _confidence_rank(confidence: ConfidenceLevel) -> int:
    """Return a comparable rank for confidence values.

    Args:
        confidence (ConfidenceLevel): Confidence label.

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
        current (FieldValue | None): Currently selected value for the key.
        candidate (FieldValue): New candidate value.

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


def _backend_concurrency(backend: object) -> int:
    """Resolve backend concurrency setting with a safe fallback.

    Args:
        backend (object): Backend instance.

    Returns:
        int: Effective concurrency (minimum 1).
    """
    settings_obj = getattr(backend, "settings", None)
    if settings_obj is None:
        settings_obj = getattr(backend, "_settings", None)

    raw_value = getattr(settings_obj, "openai_concurrency", 8)
    try:
        concurrency = int(raw_value)
    except (TypeError, ValueError):
        concurrency = 8
    return max(concurrency, 1)


def _backend_null_sentinel(backend: object) -> str:
    """Resolve backend null sentinel with a safe fallback.

    Args:
        backend (object): Backend instance.

    Returns:
        str: Null sentinel.
    """
    settings_obj = getattr(backend, "settings", None)
    if settings_obj is None:
        settings_obj = getattr(backend, "_settings", None)

    sentinel = getattr(settings_obj, "null_sentinel", None)
    if isinstance(sentinel, str) and sentinel:
        return sentinel
    return "NULL"


async def _extract_values_for_keys(
    *,
    backend: ExtractorBackend,
    pages: list[RenderedPage],
    keys: list[str],
    chunk_pages: int,
    extra_instructions: str | None,
) -> tuple[list[FieldValue], list[PricingCall]]:
    """Extract values for a key set with optional page chunking.

    Args:
        backend (Any): Extraction backend.
        pages (list[RenderedPage]): Rendered pages.
        keys (list[str]): Keys to extract.
        chunk_pages (int): Requested chunk size.
        extra_instructions (str | None): Additional prompt instructions.

    Returns:
        tuple[list[FieldValue], list[PricingCall]]: Extracted values and pricing calls.
    """
    if not keys:
        return [], []

    normalized_chunk = max(chunk_pages, 1)
    page_batches: list[list[RenderedPage]] = []
    if normalized_chunk >= len(pages):
        page_batches = [pages]
    else:
        for start in range(0, len(pages), normalized_chunk):
            page_batches.append(pages[start : start + normalized_chunk])

    semaphore = asyncio.Semaphore(_backend_concurrency(backend))

    async def _extract_batch(batch: list[RenderedPage]) -> tuple[list[FieldValue], PricingCall | None]:
        async with semaphore:
            extract_async = getattr(backend, "aextract_values", None)
            if extract_async is not None:
                return await extract_async(
                    batch,
                    keys,
                    extra_instructions=extra_instructions,
                )
            return backend.extract_values(
                batch,
                keys,
                extra_instructions=extra_instructions,
            )

    batch_results = await asyncio.gather(*[_extract_batch(batch) for batch in page_batches])

    by_key: dict[str, FieldValue] = {}
    pricing_calls: list[PricingCall] = []
    for batch_values, call in batch_results:
        for value in batch_values:
            by_key[value.key] = _select_better_value(by_key.get(value.key), value)
        if call:
            pricing_calls.append(call)

    return list(by_key.values()), pricing_calls


async def _extract_values_for_page_groups(
    *,
    backend: ExtractorBackend,
    pages: list[RenderedPage],
    keys_by_page: dict[int, list[str]],
    extra_instructions: str | None,
) -> tuple[list[FieldValue], list[PricingCall]]:
    """Extract values for page-scoped key groups.

    Args:
        backend (Any): Extraction backend.
        pages (list[RenderedPage]): Rendered pages.
        keys_by_page (dict[int, list[str]]): Keys grouped by page number.
        extra_instructions (str | None): Additional prompt instructions.

    Returns:
        tuple[list[FieldValue], list[PricingCall]]: Extracted values and pricing calls.
    """
    pages_by_number = {page.page_number: page for page in pages}
    semaphore = asyncio.Semaphore(_backend_concurrency(backend))

    async def _extract_one(page_number: int, keys: list[str]) -> tuple[list[FieldValue], PricingCall | None]:
        page = pages_by_number.get(page_number)
        if page is None:
            return [], None
        async with semaphore:
            extract_async = getattr(backend, "aextract_values", None)
            if extract_async is not None:
                return await extract_async(
                    [page],
                    keys,
                    extra_instructions=extra_instructions,
                )
            return backend.extract_values(
                [page],
                keys,
                extra_instructions=extra_instructions,
            )

    tasks = []
    for page_number, keys in sorted(keys_by_page.items()):
        tasks.append(_extract_one(page_number, keys))
    results = await asyncio.gather(*tasks)

    extracted_values: list[FieldValue] = []
    calls: list[PricingCall] = []
    for page_values, call in results:
        extracted_values.extend(page_values)
        if call:
            calls.append(call)
    return extracted_values, calls


async def _collect_schema_values(
    payload: CollectSchemaValuesInput,
) -> tuple[list[FieldValue], list[PricingCall]]:
    """Collect extracted values and pricing calls for a schema.

    Args:
        payload (CollectSchemaValuesInput): Collection input payload.

    Returns:
        tuple[list[FieldValue], list[PricingCall]]: Extracted values and pricing calls.
    """
    backend = cast("ExtractorBackend", payload.backend)
    pages = cast("list[RenderedPage]", payload.pages)

    keys_by_page = _build_routed_keys_by_page(
        payload.schema_spec,
        page_map=payload.schema_page_map,
    )
    unresolved_non_paged = _unresolved_sparse_keys(
        payload.schema_spec,
        page_map=payload.schema_page_map,
    )

    if not keys_by_page or not payload.use_page_groups:
        keys = [field.key for field in payload.schema_spec.fields]
        return await _extract_values_for_keys(
            backend=backend,
            pages=pages,
            keys=keys,
            chunk_pages=payload.request.chunk_pages,
            extra_instructions=payload.request.extra_instructions,
        )

    paged_values, paged_calls = await _extract_values_for_page_groups(
        backend=backend,
        pages=pages,
        keys_by_page=keys_by_page,
        extra_instructions=payload.request.extra_instructions,
    )
    non_paged_values, non_paged_calls = await _extract_values_for_keys(
        backend=backend,
        pages=pages,
        keys=unresolved_non_paged,
        chunk_pages=payload.request.chunk_pages,
        extra_instructions=payload.request.extra_instructions,
    )

    extracted_values = paged_values + non_paged_values
    missing_paged_keys = _missing_paged_keys(
        extracted_values=extracted_values,
        keys_by_page=keys_by_page,
        backend=backend,
    )

    if not missing_paged_keys:
        return extracted_values, paged_calls + non_paged_calls

    fallback = await _extract_values_for_keys(
        backend=backend,
        pages=pages,
        keys=missing_paged_keys,
        chunk_pages=payload.request.chunk_pages,
        extra_instructions=payload.request.extra_instructions,
    )
    return (
        extracted_values + fallback[0],
        paged_calls + non_paged_calls + fallback[1],
    )


def _build_routed_keys_by_page(
    schema: SchemaSpec,
    *,
    page_map: dict[int, int] | None = None,
) -> dict[int, list[str]]:
    """Build page-key routing from explicit and inferred schema page metadata.

    Args:
        schema (SchemaSpec): Schema to route.
        page_map (dict[int, int] | None): Optional mapping from schema page numbers to PDF page numbers.

    Returns:
        dict[int, list[str]]: Routed keys by PDF page number.
    """
    keys_by_page = _group_keys_by_page(schema, page_map=page_map)
    inferred_by_page, _ = _infer_sparse_keys_by_page(schema, page_map=page_map)
    for page_number, keys in inferred_by_page.items():
        keys_by_page.setdefault(page_number, [])
        for key in keys:
            if key not in keys_by_page[page_number]:
                keys_by_page[page_number].append(key)
    return keys_by_page


def _unresolved_sparse_keys(
    schema: SchemaSpec,
    *,
    page_map: dict[int, int] | None = None,
) -> list[str]:
    """Return sparse keys that cannot be attached to a page.

    Args:
        schema (SchemaSpec): Schema to inspect.
        page_map (dict[int, int] | None): Optional mapping from schema page numbers to PDF page numbers.

    Returns:
        list[str]: Keys that remain non-routable by page metadata.
    """
    _, unresolved = _infer_sparse_keys_by_page(schema, page_map=page_map)
    return unresolved


def _missing_paged_keys(
    *,
    extracted_values: list[FieldValue],
    keys_by_page: dict[int, list[str]],
    backend: object,
) -> list[str]:
    """Return page-routed keys still unresolved after page-scoped extraction.

    Args:
        extracted_values (list[FieldValue]): Values gathered so far.
        keys_by_page (dict[int, list[str]]): Keys that were attempted with page routing.
        backend (object): Backend instance for null-sentinel resolution.

    Returns:
        list[str]: Routed keys still missing usable values.
    """
    extracted_non_blank = {
        value.key
        for value in extracted_values
        if value.value.strip() and value.value.strip() not in {_backend_null_sentinel(backend), "NULL"}
    }
    paged_keys = {key for keys in keys_by_page.values() for key in keys}
    return sorted(paged_keys - extracted_non_blank)


def _build_result(
    *,
    schema: SchemaSpec,
    values: list[FieldValue],
    null_sentinel: str,
    pricing: PricingCall | None,
) -> ExtractionResult:
    """Build normalized extraction result.

    Args:
        schema (SchemaSpec): Reference schema.
        values (list[FieldValue]): Extracted values from backend.
        null_sentinel (str): Null fallback value.
        pricing (PricingCall | None): Aggregated pricing.

    Returns:
        ExtractionResult: Normalized result.
    """
    by_key: dict[str, FieldValue] = {}
    for value in values:
        by_key[value.key] = _select_better_value(by_key.get(value.key), value)

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
            normalized_value = field_value.model_copy(
                update={
                    "value": normalize_typed_value(
                        value=field_value.value,
                        schema_field=schema_field,
                        null_sentinel=null_sentinel,
                    ),
                },
            )

        normalized.append(normalized_value)
        flat[normalized_value.key] = normalized_value.value

    return ExtractionResult(
        fields=normalized,
        flat=flat,
        schema_fields_count=len(schema.fields),
        pricing=pricing,
    )


def _resolve_backend_type(request: ExtractRequest, settings: Settings) -> ExtractionBackendType:
    """Resolve effective backend type from request override or settings default.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Returns:
        ExtractionBackendType: Effective backend selection.
    """
    if request.backend is not None:
        return request.backend
    return settings.extraction_backend


def _load_dotted_object(dotted_path: str) -> object:
    """Load object from a dotted path.

    Args:
        dotted_path (str): Dotted object path (`module.attr`).

    Raises:
        ExtractionError: If path cannot be imported.

    Returns:
        object: Imported object.
    """
    if "." not in dotted_path:
        raise ExtractionError(message=f"OCR_PROVIDER_FACTORY must be dotted path, got: {dotted_path}")
    module_name, attr_name = dotted_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ExtractionError(message=f"Cannot import OCR provider module: {module_name}") from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise ExtractionError(message=f"Cannot resolve OCR provider factory: {dotted_path}") from exc


def _build_ocr_provider(*, request: ExtractRequest, settings: Settings) -> OCRPageProvider:
    """Build OCR provider using configured factory.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Raises:
        ExtractionError: If factory is not configured or callable.

    Returns:
        OCRPageProvider: OCR provider instance.
    """
    dotted_path = settings.ocr_provider_factory
    if not dotted_path:
        raise ExtractionError(
            message=(
                "OCR backend selected but OCR_PROVIDER_FACTORY is not configured. "
                "Set a dotted factory path returning an OCR page provider."
            ),
        )
    factory = _load_dotted_object(dotted_path)
    if not callable(factory):
        raise ExtractionError(message=f"OCR provider factory is not callable: {dotted_path}")
    typed_factory = cast("Any", factory)

    try:
        try:
            provider = typed_factory(settings=settings, request=request)
        except TypeError:
            try:
                provider = typed_factory(settings)
            except TypeError:
                provider = typed_factory()
    except Exception as exc:
        raise ExtractionError(
            message=f"OCR provider factory call failed: {dotted_path}",
        ) from exc
    return cast("OCRPageProvider", provider)


def _build_extraction_backend(
    *,
    request: ExtractRequest,
    settings: Settings,
) -> tuple[ExtractorBackend, ExtractionBackendType]:
    """Build extraction backend according to runtime selection.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Returns:
        tuple[ExtractorBackend, ExtractionBackendType]: Backend instance and selected backend type.
    """
    backend_type = _resolve_backend_type(request, settings)
    if backend_type == ExtractionBackendType.MULTIMODAL:
        return MultimodalLLMBackend(settings), backend_type

    text_normalizer = OCRTextLLMNormalizer(settings) if settings.ocr_enable_text_normalization else None
    backend = OCRBackend(
        provider=_build_ocr_provider(request=request, settings=settings),
        null_sentinel=settings.null_sentinel,
        text_normalizer=text_normalizer,
    )
    return backend, backend_type


def _augment_result_metadata(result: ExtractionResult, updates: dict[str, object]) -> ExtractionResult:
    """Merge metadata updates into result.

    Args:
        result (ExtractionResult): Base result.
        updates (dict[str, object]): Metadata updates.

    Returns:
        ExtractionResult: Result with merged metadata.
    """
    metadata = dict(result.metadata)
    metadata.update(updates)
    return result.model_copy(update={"metadata": metadata})


def infer_schema(request: ExtractRequest, settings: Settings) -> tuple[SchemaSpec, PricingCall | None]:
    """Infer schema from a document.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

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
    pages = _filter_blank_pages_if_requested(pages=pages, request=request, settings=settings)

    backend, _ = _build_extraction_backend(request=request, settings=settings)
    schema, pricing = backend.infer_schema(pages)
    schema_id = str(uuid4())
    schema_with_identity = SchemaSpec(
        id=schema_id,
        name=schema.name or request.input_path.stem,
        fingerprint=fingerprint,
        version=schema.version,
        schema_family_id=schema.schema_family_id or schema_id,
        fields=schema.fields,
    )
    return schema_with_identity, pricing


def _group_keys_by_page(
    schema: SchemaSpec,
    *,
    page_map: dict[int, int] | None = None,
) -> dict[int, list[str]]:
    """Group schema keys by page.

    Args:
        schema (SchemaSpec): Schema to group.
        page_map (dict[int, int] | None): Optional mapping from schema page numbers to PDF page numbers.

    Returns:
        dict[int, list[str]]: Keys by page.
    """
    keys_by_page: dict[int, list[str]] = {}
    for field in schema.fields:
        if field.page is None:
            continue
        mapped_page = field.page
        if page_map is not None:
            mapped_page = page_map.get(field.page, field.page)
        keys_by_page.setdefault(mapped_page, []).append(field.key)
    return keys_by_page


def _infer_sparse_keys_by_page(
    schema: SchemaSpec,
    *,
    page_map: dict[int, int] | None = None,
) -> tuple[dict[int, list[str]], list[str]]:
    """Infer page routing for fields without explicit page metadata.

    Fields with no `page` are attached to the nearest field that has page metadata
    based on schema order. Remaining keys are returned when no anchor page exists.

    Args:
        schema (SchemaSpec): Schema to inspect.
        page_map (dict[int, int] | None): Optional mapping from schema page numbers to PDF page numbers.

    Returns:
        tuple[dict[int, list[str]], list[str]]: Inferred keys by page and unresolved keys.
    """
    anchored_positions: list[tuple[int, int]] = []
    for index, field in enumerate(schema.fields):
        if field.page is None:
            continue
        mapped_page = page_map.get(field.page, field.page) if page_map is not None else field.page
        anchored_positions.append((index, mapped_page))

    unresolved: list[str] = []
    inferred_by_page: dict[int, list[str]] = {}
    if not anchored_positions:
        return inferred_by_page, [field.key for field in schema.fields if field.page is None]

    for index, field in enumerate(schema.fields):
        if field.page is not None:
            continue

        nearest_index, nearest_page = min(
            anchored_positions,
            key=lambda anchored: abs(anchored[0] - index),
        )
        _ = nearest_index
        inferred_by_page.setdefault(nearest_page, []).append(field.key)

    return inferred_by_page, unresolved


def extract_values(
    schema: SchemaSpec,
    request: ExtractRequest,
    settings: Settings,
    *,
    use_page_groups: bool = True,
) -> tuple[ExtractionResult, PricingCall | None]:
    """Extract values using an existing schema.

    Args:
        schema (SchemaSpec): Schema used for extraction.
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.
        use_page_groups (bool): Whether to route paged keys to page-specific calls.

    Returns:
        tuple[ExtractionResult, PricingCall | None]: Result and pricing.
    """
    started_at = time.perf_counter()
    pages = render_pdf_pages(
        request.input_path,
        dpi=request.dpi,
        image_format=request.image_format,
        page_start=request.page_start,
        page_end=request.page_end,
        max_pages=request.max_pages,
    )
    analysis = _analyze_page_selection(request=request, settings=settings)
    pages = _filter_blank_pages_if_requested(
        pages=pages,
        request=request,
        settings=settings,
        analysis=analysis,
    )
    backend, backend_type = _build_extraction_backend(request=request, settings=settings)
    schema_page_map = build_schema_page_mapping(schema=schema, analysis=analysis)

    extracted_values, calls = run_async(
        _collect_schema_values(
            CollectSchemaValuesInput(
                schema_spec=schema,
                request=request,
                backend=backend,
                pages=pages,
                use_page_groups=use_page_groups,
                schema_page_map=schema_page_map,
            ),
        ),
    )

    pricing = merge_pricing_calls(calls)
    result = _build_result(
        schema=schema,
        values=extracted_values,
        null_sentinel=settings.null_sentinel,
        pricing=pricing,
    )
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    result = _augment_result_metadata(
        result,
        {
            "backend": backend_type.value,
            "pages_processed": len(pages),
            "model_calls": len(calls),
            "schema_version": schema.version,
            "schema_family_id": schema.schema_family_id,
            "duration_ms": elapsed_ms,
            "pricing": {
                "provider": pricing.provider if pricing else None,
                "model": pricing.model if pricing else None,
                "input_tokens": pricing.input_tokens if pricing else None,
                "output_tokens": pricing.output_tokens if pricing else None,
                "total_cost_usd": pricing.total_cost_usd if pricing else None,
            },
        },
    )
    return result, pricing


def extract_one_pass(
    request: ExtractRequest,
    settings: Settings,
) -> tuple[ExtractionResult, PricingCall | None]:
    """Run one-pass extraction.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Returns:
        tuple[ExtractionResult, PricingCall | None]: Result and pricing.
    """
    schema, schema_pricing = infer_schema(request, settings)
    result, values_pricing = extract_values(schema, request, settings, use_page_groups=False)

    merged_pricing = merge_pricing_calls([
        call for call in [schema_pricing, values_pricing] if call is not None
    ])
    result_with_pricing = result.model_copy(update={"pricing": merged_pricing})
    return result_with_pricing, merged_pricing


def _analyze_page_selection(
    *,
    request: ExtractRequest,
    settings: Settings,
) -> PageSelectionAnalysis | None:
    """Analyze selected pages to detect non-blank pages.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Returns:
        PageSelectionAnalysis | None: Page analysis payload when available.
    """
    ink_threshold = (
        request.blank_page_ink_threshold
        if request.blank_page_ink_threshold is not None
        else settings.blank_page_ink_threshold
    )
    near_white_level = (
        request.blank_page_near_white_level
        if request.blank_page_near_white_level is not None
        else settings.blank_page_near_white_level
    )
    return analyze_page_selection(
        PageSelectionRequest(
            pdf_path=request.input_path.as_posix(),
            page_start=request.page_start,
            page_end=request.page_end,
            max_pages=request.max_pages,
            ink_ratio_threshold=ink_threshold,
            near_white_level=near_white_level,
        ),
    )


def _filter_blank_pages_if_requested(
    *,
    pages: list[RenderedPage],
    request: ExtractRequest,
    settings: Settings,
    analysis: PageSelectionAnalysis | None = None,
) -> list[RenderedPage]:
    """Filter rendered pages when blank-page filtering is enabled.

    Args:
        pages (list[RenderedPage]): Rendered pages.
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.
        analysis (PageSelectionAnalysis | None): Optional precomputed page analysis.

    Returns:
        list[RenderedPage]: Filtered or original pages.
    """
    drop_blank = (
        request.drop_blank_pages if request.drop_blank_pages is not None else settings.drop_blank_pages
    )
    if not drop_blank:
        return pages

    computed = (
        analysis if analysis is not None else _analyze_page_selection(request=request, settings=settings)
    )
    if computed is None:
        return pages
    return filter_rendered_pages_to_nonblank(
        pages,
        nonblank_page_numbers=computed.nonblank_page_numbers,
    )


def match_schema(pdf: Path, schemas_store: SchemaStore, _settings: Settings) -> MatchResult:
    """Match document against schema cache.

    Args:
        pdf (Path): PDF to match.
        schemas_store (SchemaStore): Schema storage.
        _settings (Settings): Runtime settings (currently unused; reserved for future matching configuration).

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
        store (SchemaStore): Schema store.
        schema_id (str): Candidate schema id.
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Returns:
        ExtractionResult | None: Extraction result when found, otherwise None.
    """
    for schema_path in store.list_schemas():
        candidate = store.load(schema_path)
        if candidate.id == schema_id:
            result, _ = extract_values(candidate, request, settings)
            return result
    return None


def _extract_with_schema(schema: SchemaSpec, request: ExtractRequest, settings: Settings) -> ExtractionResult:
    """Extract values with a pre-loaded schema.

    Args:
        schema (SchemaSpec): Pre-loaded schema.
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Returns:
        ExtractionResult: Extraction result.
    """
    result, _ = extract_values(schema, request, settings)
    return result


def _run_one_schema_pass(
    request: ExtractRequest,
    settings: Settings,
    store: SchemaStore,
) -> ExtractionResult:
    """Handle ONE_SCHEMA_PASS extraction mode.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.
        store (SchemaStore): Schema store.

    Raises:
        ExtractionError: If schema identifier is missing or unknown.

    Returns:
        ExtractionResult: Extraction result.
    """
    if not request.schema_id:
        raise ExtractionError(message="ONE_SCHEMA_PASS requires --schema-id or --schema-path")

    result = _extract_for_schema_id(store, request.schema_id, request, settings)
    if result is None:
        raise ExtractionError(message=f"Schema id not found: {request.schema_id}")
    return result


def _run_two_pass(
    request: ExtractRequest,
    settings: Settings,
    store: SchemaStore,
) -> tuple[ExtractionResult, bool]:
    """Handle TWO_PASS extraction mode.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.
        store (SchemaStore): Schema store.

    Returns:
        tuple[ExtractionResult, bool]: Extraction result and cache-hit flag.
    """
    if request.match_schema or request.use_cache:
        fingerprint = SchemaStore.fingerprint_pdf(request.input_path)
        matched = store.match_schema(fingerprint)
        if matched.matched and matched.schema_id:
            cached = _extract_for_schema_id(store, matched.schema_id, request, settings)
            if cached is not None:
                return cached, True

    schema, _ = infer_schema(request, settings)
    if request.use_cache:
        store.save(schema)
    return _extract_with_schema(schema, request, settings), False


def persist_result(result: ExtractionResult, path: Path) -> None:
    """Persist extraction result as JSON.

    Args:
        result (ExtractionResult): Result payload.
        path (Path): Output path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def run_extract(request: ExtractRequest, settings: Settings) -> ExtractionResult:
    """Top-level extraction flow used by CLI.

    Args:
        request (ExtractRequest): Extraction request.
        settings (Settings): Runtime settings.

    Raises:
        ExtractionError: If request mode is unsupported.

    Returns:
        ExtractionResult: Extraction output.
    """
    store = SchemaStore(root=Path(settings.schema_cache_dir))

    if request.schema_path:
        schema = store.load(request.schema_path)
        result = _extract_with_schema(schema, request, settings)
        return _augment_result_metadata(result, {"mode": request.mode.value, "cache_hit": False})

    if request.mode == PassMode.ONE_PASS:
        result, _ = extract_one_pass(request, settings)
        return _augment_result_metadata(result, {"mode": request.mode.value, "cache_hit": False})

    if request.mode == PassMode.ONE_SCHEMA_PASS:
        result = _run_one_schema_pass(request, settings, store)
        return _augment_result_metadata(result, {"mode": request.mode.value, "cache_hit": False})

    if request.mode == PassMode.TWO_PASS:
        result, cache_hit = _run_two_pass(request, settings, store)
        return _augment_result_metadata(result, {"mode": request.mode.value, "cache_hit": cache_hit})

    raise ExtractionError(message=f"Unsupported mode: {request.mode}")


def result_to_json_dict(result: ExtractionResult) -> dict[str, object]:
    """Return result payload for custom serialization paths.

    Args:
        result (ExtractionResult): Extraction result.

    Returns:
        dict[str, object]: JSON-serializable dictionary.
    """
    return json.loads(result.model_dump_json())
