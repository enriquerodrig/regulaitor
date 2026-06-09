"""Unit tests for the self-hosted / open-model additions to models/config.py
(probe R1): MISTRAL_SMALL constant + PRICING entry + cost_eur tolerance for
unknown (open/self-hosted) model ids."""

from __future__ import annotations

import logging

from regulaitor.models import config
from regulaitor.models.config import MISTRAL_SMALL, PRICING, cost_eur


def test_mistral_small_constant() -> None:
    assert MISTRAL_SMALL == "mistral-small-latest"


def test_mistral_small_in_pricing() -> None:
    assert MISTRAL_SMALL in PRICING
    pricing = PRICING[MISTRAL_SMALL]
    assert pricing.input_per_million > 0
    assert pricing.output_per_million > 0
    # Cheaper than Sonnet on both legs (sanity, not exact).
    sonnet = PRICING[config.ANTHROPIC_SONNET_4_6]
    assert pricing.input_per_million < sonnet.input_per_million
    assert pricing.output_per_million < sonnet.output_per_million


def test_cost_eur_known_mistral_small_positive() -> None:
    c = cost_eur(model_id=MISTRAL_SMALL, input_tokens=1000, output_tokens=500)
    assert c > 0.0


def test_cost_eur_unknown_model_returns_zero_with_warning(caplog) -> None:
    """Self-hosted/open model ids absent from PRICING must NOT raise (would crash
    the cost accumulator mid-run); they report 0.0 + a WARNING."""
    with caplog.at_level(logging.WARNING, logger="regulaitor.models.config"):
        c = cost_eur(model_id="some-unknown-open-model", input_tokens=1000, output_tokens=500)
    assert c == 0.0
    assert "some-unknown-open-model" in caplog.text


def test_cost_eur_known_models_unaffected() -> None:
    """Regression: the tolerant lookup keeps exact list-price for known models."""
    from regulaitor.models.config import USD_TO_EUR

    c = cost_eur(model_id=config.ANTHROPIC_SONNET_4_6, input_tokens=1000, output_tokens=500)
    expected = (1000 / 1_000_000 * 3.0 + 500 / 1_000_000 * 15.0) * USD_TO_EUR
    assert abs(c - expected) < 1e-9
