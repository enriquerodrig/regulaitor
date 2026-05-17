"""Model identifiers and pricing for the router (H4+H12).

H4 wires Anthropic Sonnet 4.6. H12 extends with OpenAI GPT-4o / GPT-4o-mini and
Groq Llama-3.3-70B for cost/quality/fallback modes.
"""

from __future__ import annotations

from typing import NamedTuple


class ModelPricing(NamedTuple):
    input_per_million: float  # USD per 1M input tokens
    output_per_million: float  # USD per 1M output tokens


# Model IDs
ANTHROPIC_SONNET_4_6 = "claude-sonnet-4-6"
OPENAI_GPT_4O = "gpt-4o"
OPENAI_GPT_4O_MINI = "gpt-4o-mini"
# Groq's exact 70B id is verified against the live catalog in a later task
# (3.1-70B may be served as llama-3.3-70b-versatile); update this constant +
# the PRICING key together if it differs.
GROQ_LLAMA_70B = "llama-3.3-70b-versatile"

# Published list prices, USD per 1M tokens. VERIFY against each provider's
# pricing page; pin PRICING_SNAPSHOT_DATE. If a number differs, use the
# verified value.
PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_SONNET_4_6: ModelPricing(input_per_million=3.0, output_per_million=15.0),
    OPENAI_GPT_4O: ModelPricing(input_per_million=2.50, output_per_million=10.0),
    OPENAI_GPT_4O_MINI: ModelPricing(input_per_million=0.15, output_per_million=0.60),
    GROQ_LLAMA_70B: ModelPricing(input_per_million=0.59, output_per_million=0.79),
}

PRICING_SNAPSHOT_DATE = "2026-05-16"

# Rough USD->EUR rate; cost_analysis.md pins exact rate per snapshot date.
USD_TO_EUR = 0.93


def cost_eur(*, model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in EUR for a completion. Raises KeyError if model_id unknown."""
    pricing = PRICING[model_id]
    cost_usd = (
        input_tokens / 1_000_000 * pricing.input_per_million
        + output_tokens / 1_000_000 * pricing.output_per_million
    )
    return cost_usd * USD_TO_EUR
