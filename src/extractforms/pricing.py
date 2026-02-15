"""Pricing helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from extractforms.typing.models import PricingCall


def merge_pricing_calls(calls: list[PricingCall]) -> PricingCall | None:
    """Aggregate pricing calls into a single summary.

    Args:
        calls: List of calls.

    Returns:
        PricingCall | None: Aggregated call or None if empty.
    """
    if not calls:
        return None

    accumulator = calls[0]
    for call in calls[1:]:
        accumulator += call

    return accumulator
