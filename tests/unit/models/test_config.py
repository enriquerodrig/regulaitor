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


# --- H12 multi-provider pricing tests ---


def test_pricing_snapshot_date_present() -> None:
    from regulaitor.models import config

    assert isinstance(config.PRICING_SNAPSHOT_DATE, str)
    assert config.PRICING_SNAPSHOT_DATE  # non-empty


def test_cost_eur_known_for_all_h12_models() -> None:
    from regulaitor.models import config

    for mid in (
        config.ANTHROPIC_SONNET_4_6,
        config.ANTHROPIC_HAIKU_4_5,
        config.OPENAI_GPT_4O,
        config.OPENAI_GPT_4O_MINI,
        config.GROQ_LLAMA_70B,
    ):
        c = config.cost_eur(model_id=mid, input_tokens=1000, output_tokens=500)
        assert c > 0.0


def test_cost_eur_gpt_4o_value() -> None:
    from regulaitor.models import config

    # 1M in @2.50 + 1M out @10.00 = 12.50 USD * 0.93 = 11.625 EUR
    c = config.cost_eur(
        model_id=config.OPENAI_GPT_4O,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert abs(c - 11.625) < 1e-6


# --- H13 judge mode pricing ---


def test_haiku_45_pricing_present() -> None:
    from regulaitor.models import config

    assert config.ANTHROPIC_HAIKU_4_5 == "claude-haiku-4-5-20251001"
    assert config.ANTHROPIC_HAIKU_4_5 in config.PRICING
    pricing = config.PRICING[config.ANTHROPIC_HAIKU_4_5]
    in_usd, out_usd = pricing.input_per_million, pricing.output_per_million
    assert in_usd > 0 and out_usd > 0
    # Haiku is cheaper than Sonnet on both legs (sanity, not exact).
    s_in, s_out = (
        config.PRICING[config.ANTHROPIC_SONNET_4_6].input_per_million,
        config.PRICING[config.ANTHROPIC_SONNET_4_6].output_per_million,
    )
    assert in_usd < s_in and out_usd < s_out
