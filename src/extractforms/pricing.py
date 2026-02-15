"""Pricing helpers."""

from __future__ import annotations

from extractforms.typing.models import PricingCall


def _sum_optional_int(values: list[int | None]) -> int | None:
    """Sum integer values while preserving unknown state.

    Args:
        values: Optional integer values.

    Returns:
        int | None: Sum when at least one value is known, else None.
    """
    known_values = [value for value in values if value is not None]
    if not known_values:
        return None
    return sum(known_values)


def _sum_optional_float(values: list[float | None]) -> float | None:
    """Sum float values while preserving unknown state.

    Args:
        values: Optional float values.

    Returns:
        float | None: Sum when at least one value is known, else None.
    """
    known_values = [value for value in values if value is not None]
    if not known_values:
        return None
    return sum(known_values)


def merge_pricing_calls(calls: list[PricingCall]) -> PricingCall | None:
    """Aggregate pricing calls into a single summary.

    Args:
        calls: List of calls.

    Returns:
        PricingCall | None: Aggregated call or None if empty.
    """
    if not calls:
        return None

    first = calls[0]
    input_tokens = _sum_optional_int([call.input_tokens for call in calls])
    output_tokens = _sum_optional_int([call.output_tokens for call in calls])
    total_cost = _sum_optional_float([call.total_cost_usd for call in calls])

    return PricingCall(
        provider=first.provider,
        model=first.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost_usd=total_cost,
    )
