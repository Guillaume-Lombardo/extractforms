from __future__ import annotations

import pytest

from extractforms.typing.models import PricingCall
from extractforms.pricing import merge_pricing_calls


def test_merge_pricing_calls_returns_none_on_empty() -> None:
    assert merge_pricing_calls([]) is None


def test_merge_pricing_calls_aggregates_values() -> None:
    calls = [
        PricingCall(provider="x", model="m", input_tokens=10, output_tokens=5, total_cost_usd=0.1),
        PricingCall(provider="x", model="m", input_tokens=3, output_tokens=2, total_cost_usd=0.05),
    ]

    merged = merge_pricing_calls(calls)

    assert merged is not None
    assert merged.input_tokens == 13
    assert merged.output_tokens == 7
    assert merged.total_cost_usd == pytest.approx(0.15)
