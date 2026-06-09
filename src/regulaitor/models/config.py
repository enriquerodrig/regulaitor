"""Model identifiers and pricing for the router (H4+H12+H13).

H4 wires Anthropic Sonnet 4.6. H12 extends with OpenAI GPT-4o / GPT-4o-mini and
Groq Llama-3.3-70B for cost/quality/fallback modes. H13 adds Haiku 4.5 (judge mode).
"""

from __future__ import annotations

import logging
from typing import NamedTuple

logger = logging.getLogger("regulaitor.models.config")


class ModelPricing(NamedTuple):
    input_per_million: float  # USD per 1M input tokens
    output_per_million: float  # USD per 1M output tokens


# Model IDs
ANTHROPIC_SONNET_4_6 = "claude-sonnet-4-6"
ANTHROPIC_HAIKU_4_5 = "claude-haiku-4-5-20251001"
OPENAI_GPT_4O = "gpt-4o"
OPENAI_GPT_4O_MINI = "gpt-4o-mini"
# Groq's exact 70B id is verified against the live catalog in a later task
# (3.1-70B may be served as llama-3.3-70b-versatile); update this constant +
# the PRICING key together if it differs.
GROQ_LLAMA_70B = "llama-3.3-70b-versatile"
# Open-source self-hosted candidate (probe R1). The Mistral La Plateforme API
# id; the same Apache-2.0 weights can later be served on OVH/Scaleway/vLLM.
MISTRAL_SMALL = "mistral-small-latest"

# Published list prices, USD per 1M tokens. VERIFY against each provider's
# pricing page; pin PRICING_SNAPSHOT_DATE. If a number differs, use the
# verified value.
PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_SONNET_4_6: ModelPricing(input_per_million=3.0, output_per_million=15.0),
    ANTHROPIC_HAIKU_4_5: ModelPricing(input_per_million=1.0, output_per_million=5.0),
    OPENAI_GPT_4O: ModelPricing(input_per_million=2.50, output_per_million=10.0),
    OPENAI_GPT_4O_MINI: ModelPricing(input_per_million=0.15, output_per_million=0.60),
    GROQ_LLAMA_70B: ModelPricing(input_per_million=0.59, output_per_million=0.79),
    # Mistral Small list price [verificar] — notional only when run on the free
    # tier (actual spend $0). Self-hosted on own GPU the marginal token cost is
    # ~0; this number is a placeholder so the cost accumulator has a value.
    MISTRAL_SMALL: ModelPricing(input_per_million=0.10, output_per_million=0.30),
}

PRICING_SNAPSHOT_DATE = "2026-05-16"

# Rough USD->EUR rate; cost_analysis.md pins exact rate per snapshot date.
USD_TO_EUR = 0.93


def cost_eur(*, model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in EUR for a completion.

    Self-hosted / open-model ids may not be in PRICING (their list price is $0
    or unknown). For an unknown model_id, log a WARNING and return 0.0 instead
    of raising, so the process-level cost accumulator never crashes mid-run on a
    self-hosted probe. Known models keep their exact list-price computation.
    """
    pricing = PRICING.get(model_id)
    if pricing is None:
        logger.warning(
            "cost_eur: no PRICING entry for model_id=%r; reporting 0.0 "
            "(self-hosted / open model?).",
            model_id,
        )
        return 0.0
    cost_usd = (
        input_tokens / 1_000_000 * pricing.input_per_million
        + output_tokens / 1_000_000 * pricing.output_per_million
    )
    return cost_usd * USD_TO_EUR
