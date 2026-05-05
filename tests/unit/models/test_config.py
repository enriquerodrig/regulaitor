"""Unit tests for models/config.py — pricing table + constants."""

from __future__ import annotations

from regulaitor.models.config import (
    ANTHROPIC_SONNET_4_6,
    PRICING,
    USD_TO_EUR,
    cost_eur,
)


def test_anthropic_sonnet_4_6_constant() -> None:
    assert ANTHROPIC_SONNET_4_6 == "claude-sonnet-4-6"


def test_pricing_includes_sonnet() -> None:
    assert ANTHROPIC_SONNET_4_6 in PRICING
    pricing = PRICING[ANTHROPIC_SONNET_4_6]
    assert pricing.input_per_million == 3.0
    assert pricing.output_per_million == 15.0


def test_usd_to_eur_in_range() -> None:
    assert 0.7 < USD_TO_EUR < 1.2  # sanity check on the rate


def test_cost_eur_calculation() -> None:
    # 1000 input + 500 output tokens at sonnet pricing
    # input: 1000/1M * $3 = $0.003
    # output: 500/1M * $15 = $0.0075
    # total USD: $0.0105
    # EUR: $0.0105 * USD_TO_EUR
    cost = cost_eur(model_id=ANTHROPIC_SONNET_4_6, input_tokens=1000, output_tokens=500)
    expected = (1000 / 1_000_000 * 3.0 + 500 / 1_000_000 * 15.0) * USD_TO_EUR
    assert abs(cost - expected) < 1e-9
