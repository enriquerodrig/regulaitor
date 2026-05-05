"""Single LLM entry point. H4 routes 'default'/'quality' to Anthropic Sonnet 4.6.

H12 extends to 'cost' (Llama Groq), 'evaluation' (GPT-4o), 'fallback' (GPT-4o-mini).
Per-tool error semantics + cost tracking + retries via tenacity.
Decisions log 2026-05-05 entry "models/router.py arquitectura: thin router con un backend en H4".
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Literal

from anthropic import Anthropic
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from regulaitor.models.config import ANTHROPIC_SONNET_4_6, cost_eur

logger = logging.getLogger("regulaitor.models.router")

ModelChoice = Literal["default", "quality"]  # H12 adds: "cost", "evaluation", "fallback"


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class CompletionResult(BaseModel):
    """Router output abstraction. Same shape regardless of provider."""

    text: str | None
    tool_use_input: dict[str, Any] | None
    usage: Usage
    model_id: str
    latency_ms: int
    cost_eur: float


def _anthropic_client() -> Anthropic:
    """Construct an Anthropic client. Reads ANTHROPIC_API_KEY from env.

    Wrapped in a function so tests can monkeypatch this attribute.
    """
    return Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def complete(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    model_choice: ModelChoice = "default",
    max_tokens: int = 2000,
) -> CompletionResult:
    """Single entry. H4 routes 'default'/'quality' -> Anthropic Sonnet."""
    if model_choice not in {"default", "quality"}:
        raise NotImplementedError(f"model_choice={model_choice!r} added in H12 router expansion")
    return _call_anthropic_sonnet(
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _call_anthropic_sonnet(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """Wrap Anthropic SDK with timing, cost calc, structured logging.

    Retries on transient errors via tenacity (3 attempts, exponential backoff).
    """
    client = _anthropic_client()
    kwargs: dict[str, Any] = {
        "model": ANTHROPIC_SONNET_4_6,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    t0 = time.monotonic()
    response = client.messages.create(**kwargs)
    latency_ms = int((time.monotonic() - t0) * 1000)

    # Extract first text block + first tool_use block (if present)
    text: str | None = None
    tool_use_input: dict[str, Any] | None = None
    for block in response.content:
        if block.type == "text" and text is None:
            text = block.text
        elif block.type == "tool_use" and tool_use_input is None:
            tool_use_input = dict(block.input)

    usage = Usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    cost = cost_eur(
        model_id=ANTHROPIC_SONNET_4_6,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )

    logger.info(
        "anthropic completion: model=%s tokens=%d/%d cost_eur=%.4f latency_ms=%d",
        ANTHROPIC_SONNET_4_6,
        usage.input_tokens,
        usage.output_tokens,
        cost,
        latency_ms,
    )

    return CompletionResult(
        text=text,
        tool_use_input=tool_use_input,
        usage=usage,
        model_id=ANTHROPIC_SONNET_4_6,
        latency_ms=latency_ms,
        cost_eur=cost,
    )
