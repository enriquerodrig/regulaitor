"""Model identifiers and pricing for the router (H4).

H4 wires only Anthropic Sonnet 4.6. H12 will extend with cost/evaluation/fallback
modes (Llama Groq, GPT-4o, GPT-4o-mini).
"""

from __future__ import annotations

from typing import NamedTuple


class ModelPricing(NamedTuple):
    input_per_million: float  # USD per 1M input tokens
    output_per_million: float  # USD per 1M output tokens


# Model IDs (H4 default; H12 adds more)
ANTHROPIC_SONNET_4_6 = "claude-sonnet-4-6"

PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_SONNET_4_6: ModelPricing(input_per_million=3.0, output_per_million=15.0),
}

# Rough USD->EUR rate; H17 cost analysis pins exact rate per snapshot date.
USD_TO_EUR = 0.93


def cost_eur(*, model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in EUR for a completion. Raises KeyError if model_id unknown."""
    pricing = PRICING[model_id]
    cost_usd = (
        input_tokens / 1_000_000 * pricing.input_per_million
        + output_tokens / 1_000_000 * pricing.output_per_million
    )
    return cost_usd * USD_TO_EUR
