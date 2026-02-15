"""Pricing helpers."""

from __future__ import annotations

from extractforms.models import PricingCall


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
    input_tokens = sum(call.input_tokens or 0 for call in calls)
    output_tokens = sum(call.output_tokens or 0 for call in calls)
    total_cost = sum(call.total_cost_usd or 0.0 for call in calls)

    return PricingCall(
        provider=first.provider,
        model=first.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost_usd=total_cost,
    )
