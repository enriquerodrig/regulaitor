"""Single LLM entry point. H4 routes 'default'/'quality' to Anthropic Sonnet 4.6.

H12 extends to 'cost' (Llama Groq), 'evaluation' (GPT-4o), 'fallback' (GPT-4o-mini).
H13 adds 'judge' (Haiku 4.5).
Per-tool error semantics + cost tracking + retries via tenacity.
Decisions log 2026-05-05 entry "models/router.py arquitectura: thin router con un backend en H4".
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Literal, NamedTuple, get_args

import groq
import openai
from anthropic import (
    Anthropic,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from groq import APIConnectionError as GroqConnErr
from groq import APITimeoutError as GroqTimeoutErr
from groq import InternalServerError as GroqServerErr
from groq import RateLimitError as GroqRateErr
from openai import APIConnectionError as OpenAIConnErr
from openai import APITimeoutError as OpenAITimeoutErr
from openai import InternalServerError as OpenAIServerErr
from openai import RateLimitError as OpenAIRateErr
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from regulaitor.models import _translate
from regulaitor.models.config import (
    ANTHROPIC_HAIKU_4_5,
    ANTHROPIC_SONNET_4_6,
    GROQ_LLAMA_70B,
    MISTRAL_SMALL,
    OPENAI_GPT_4O,
    OPENAI_GPT_4O_MINI,
    cost_eur,
)

logger = logging.getLogger("regulaitor.models.router")

# "self_hosted" (probe R1) routes the Analyst to an open-source model served on
# an OpenAI-compatible endpoint (Mistral La Plateforme now; OVH/Scaleway/vLLM
# later) via REGULAITOR_SELFHOST_BASE_URL. It is NOT a controlled-fallback
# target and never falls back to a US model (see _NO_FALLBACK_MODES).
ModelChoice = Literal[
    "default", "quality", "cost", "evaluation", "fallback", "judge", "self_hosted"
]
# Single source of truth: derived from the Literal (no duplicated string set).
_VALID_MODES: frozenset[str] = frozenset(get_args(ModelChoice))


class ProviderModel(NamedTuple):
    """A routing target. Named (mirrors config.ModelPricing) so downstream
    dispatch reads `.provider`/`.model_id`, not positional [0]/[1]."""

    provider: str
    model_id: str


# Provider keys — single source of truth. Used by _MODE_MAP, the complete()
# dispatch branch, and provider_label, so a typo can't silently misroute
# (Task 7 fans out more provider branches; constants keep them type-greppable).
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"
PROVIDER_GROQ = "groq"
PROVIDER_SELFHOST = "selfhost"

# Controlled fallback fires ONLY on a true transport/availability failure that
# survived a provider's own tenacity retries (spec §3/§4/§5: "terminal
# transport failure post-retry"). Deterministic app errors — anthropic
# BadRequestError, or the I1/I2 RuntimeError for malformed/non-object tool
# args — must propagate LOUDLY: silently re-routing them to GPT-4o-mini would
# mask bugs and corrupt the Task-10 A/B measurement (a Llama/GPT-4o malformed
# response would be misattributed to GPT-4o-mini).
_FALLBACKABLE_ERRORS: tuple[type[BaseException], ...] = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAIRateErr,
    OpenAIConnErr,
    OpenAITimeoutErr,
    OpenAIServerErr,
    GroqRateErr,
    GroqConnErr,
    GroqTimeoutErr,
    GroqServerErr,
)

# mode -> routing target. "fallback" is also the controlled-fallback target.
# self_hosted's model_id is the DEFAULT; _call_selfhost lets
# REGULAITOR_SELFHOST_MODEL override it at call time.
_MODE_MAP: dict[str, ProviderModel] = {
    "default": ProviderModel(PROVIDER_ANTHROPIC, ANTHROPIC_SONNET_4_6),
    "quality": ProviderModel(PROVIDER_ANTHROPIC, ANTHROPIC_SONNET_4_6),
    "cost": ProviderModel(PROVIDER_GROQ, GROQ_LLAMA_70B),
    "evaluation": ProviderModel(PROVIDER_OPENAI, OPENAI_GPT_4O),
    "fallback": ProviderModel(PROVIDER_OPENAI, OPENAI_GPT_4O_MINI),
    "judge": ProviderModel(PROVIDER_ANTHROPIC, ANTHROPIC_HAIKU_4_5),
    "self_hosted": ProviderModel(PROVIDER_SELFHOST, MISTRAL_SMALL),
}

# Modes that must NEVER fall back to the (US-hosted) GPT-4o-mini fallback model.
# "fallback" because it IS the fallback (no recursion); "self_hosted" because a
# sovereign run must surface its own failure, not be silently answered by a US
# model — that would both contaminate the probe and break the sovereignty
# guarantee the mode exists to provide.
_NO_FALLBACK_MODES: frozenset[str] = frozenset({"fallback", "self_hosted"})


def _resolve_mode(model_choice: ModelChoice) -> str:
    """Apply the optional eval-only env override.

    REGULAITOR_ROUTER_MODE, when set to a valid mode, overrides the caller's
    model_choice (used by the A/B harness). An invalid value is ignored with a
    WARNING so a bad env never breaks production. Unset => caller's choice.
    """
    override = os.environ.get("REGULAITOR_ROUTER_MODE")
    if override is None:
        return model_choice
    if override in _VALID_MODES:
        return override
    logger.warning(
        "REGULAITOR_ROUTER_MODE=%r is not a valid mode %s; ignoring (using %r)",
        override,
        sorted(_VALID_MODES),
        model_choice,
    )
    return model_choice


# Provider -> API-key env var. Single source of truth for "is this provider
# configured" checks; mirrors the fail-fast key reads in each _<provider>_client().
_PROVIDER_KEY_ENV: dict[str, str] = {
    PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    PROVIDER_OPENAI: "OPENAI_API_KEY",
    PROVIDER_GROQ: "GROQ_API_KEY",
    PROVIDER_SELFHOST: "REGULAITOR_SELFHOST_API_KEY",
}


def effective_provider(model_choice: ModelChoice) -> str:
    """The provider a ``complete(model_choice)`` call would actually hit, after
    the REGULAITOR_ROUTER_MODE override. Override-aware so a sovereign global
    override (every mode -> self_hosted) reports ``selfhost``, not the nominal US
    provider — the Council uses this to decide whether a judge is reachable."""
    return _MODE_MAP[_resolve_mode(model_choice)].provider


def provider_key_present(provider: str) -> bool:
    """True if the API-key env for ``provider`` is set (non-empty). An unknown
    provider fails OPEN (True) so a future provider is never silently skipped."""
    env = _PROVIDER_KEY_ENV.get(provider)
    if env is None:
        return True
    return bool(os.environ.get(env, "").strip())


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


# H15 / ADR 0016 — process-level real-cost accumulator.
# Every router.complete() provider branch already computes the real per-call
# cost_eur from real token usage; previously only the CompletionResult carried
# it and the eval harness discarded it (the H12/H13 "cost estimated, not
# measured" gap). This accumulator lets the harness reset-before / read-after
# each case so spend becomes MEASURED. Localized observability side-effect:
# complete()'s return value & contract are byte-identical (§22.18).
_cost_lock = threading.Lock()
_accumulated_cost_eur: float = 0.0


def _record_cost_eur(cost: float) -> None:
    """Accumulate real per-call cost. Called by complete() in every provider branch."""
    global _accumulated_cost_eur
    with _cost_lock:
        _accumulated_cost_eur += cost


def reset_cost_accumulator() -> None:
    """Zero the accumulator. The eval harness calls this before each case.

    NOTE: correct only when cases run sequentially in one process/thread. If the
    harness is ever parallelized (ThreadPoolExecutor, multiprocessing,
    pytest-xdist), this process-global pattern must be replaced with a per-case
    context or per-thread accumulator (the lock guards the +=, not run isolation).
    """
    global _accumulated_cost_eur
    with _cost_lock:
        _accumulated_cost_eur = 0.0


def get_accumulated_cost_eur() -> float:
    """Real EUR spent via router.complete() since the last reset."""
    with _cost_lock:
        return _accumulated_cost_eur


def _anthropic_client() -> Anthropic:
    """Construct an Anthropic client. Reads ANTHROPIC_API_KEY from env.

    Fails fast at construction time if key is missing (rather than waiting for
    the SDK to fail at request time inside the retry decorator).
    Wrapped in a function so tests can monkeypatch this attribute.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set; required for router.complete(). "
            "Set the environment variable or use a mocked router in tests."
        )
    return Anthropic(api_key=key)


def complete(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    model_choice: ModelChoice = "default",
    max_tokens: int = 2000,
) -> CompletionResult:
    """Resolve env override -> (provider, model_id) -> dispatch.

    Controlled fallback: if the active provider fails terminally (after its
    own tenacity retries) AND we are not already on the 'fallback' model,
    retry exactly once on the 'fallback' model. If that also fails, the
    ORIGINAL exception propagates (bounded — no loop, no recursion).
    """
    mode = _resolve_mode(model_choice)
    try:
        return _dispatch(
            mode,
            messages=messages,
            system=system,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
        )
    except _FALLBACKABLE_ERRORS as primary_exc:
        if mode in _NO_FALLBACK_MODES:
            raise
        logger.warning("router fallback_triggered=true primary_mode=%s error=%s", mode, primary_exc)
        try:
            result = _dispatch(
                "fallback",
                messages=messages,
                system=system,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens,
            )
        except Exception as fallback_exc:  # noqa: BLE001 — logged; original surfaced below
            logger.warning("router fallback also failed (surfacing primary): %s", fallback_exc)
            raise primary_exc from None
        logger.info(
            "router fallback_used=true primary_mode=%s fallback_model=%s",
            mode,
            result.model_id,
        )
        return result


def _dispatch(
    mode: str,
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """mode -> provider call fn (each fn carries its own SDK tenacity retry)."""
    target = _MODE_MAP[mode]
    # Function-local (not module-level): late-binds _call_* so tests that
    # monkeypatch.setattr(router, "_call_openai", ...) take effect here.
    fn = {
        PROVIDER_ANTHROPIC: _call_anthropic,
        PROVIDER_OPENAI: _call_openai,
        PROVIDER_GROQ: _call_groq,
        PROVIDER_SELFHOST: _call_selfhost,
    }[target.provider]
    return fn(
        model_id=target.model_id,
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
    ),
    reraise=True,
)
def _call_anthropic(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """Wrap Anthropic SDK with timing, cost calc, structured logging.

    Bespoke — deliberately NOT routed through _call_openai_compatible: the
    Anthropic SDK uses client.messages.create + `system=` kwarg + a
    response.content block list, and returns tool input already parsed as a
    dict (dict(block.input)), so the OpenAI-compatible I1/I2 JSON-string
    guards are structurally inapplicable here. Do not "unify" this.

    Retries on transient errors via tenacity (3 attempts, exponential backoff).
    model_id is passed explicitly so all Anthropic-backed modes share this function.
    """
    client = _anthropic_client()
    kwargs: dict[str, Any] = {
        "model": model_id,
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

    # Extract: concatenate all text blocks (handles thinking + final response);
    # keep first tool_use block (tool_choice="any"/specific guarantees <=1).
    text_parts: list[str] = []
    tool_use_input: dict[str, Any] | None = None
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use" and tool_use_input is None:
            tool_use_input = dict(block.input)
    text: str | None = "\n".join(text_parts) if text_parts else None

    usage = Usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    cost = cost_eur(
        model_id=model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    _record_cost_eur(cost)

    logger.info(
        "anthropic completion: model=%s tokens=%d/%d cost_eur=%.4f latency_ms=%d",
        model_id,
        usage.input_tokens,
        usage.output_tokens,
        cost,
        latency_ms,
    )

    return CompletionResult(
        text=text,
        tool_use_input=tool_use_input,
        usage=usage,
        model_id=model_id,
        latency_ms=latency_ms,
        cost_eur=cost,
    )


def _openai_client() -> openai.OpenAI:
    """OpenAI client. Fail-fast if OPENAI_API_KEY missing (only constructed
    when an openai-backed mode is actually used; prod default never calls it)."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY not set; required for router 'evaluation'/'fallback' "
            "modes. Add it to .env or use a mocked router in tests."
        )
    return openai.OpenAI(api_key=key)


def _groq_client() -> groq.Groq:
    """Groq client. Fail-fast if GROQ_API_KEY missing (only constructed when
    the 'cost' mode is actually used)."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY not set; required for router 'cost' mode. "
            "Add it to .env or use a mocked router in tests."
        )
    return groq.Groq(api_key=key)


def _call_openai_compatible(
    *,
    client: Any,
    provider_label: str,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """Shared call path for OpenAI-compatible SDKs (OpenAI, Groq).

    `client` is a pre-constructed SDK client exposing
    `chat.completions.create(**kwargs)` with OpenAI response shape.
    `provider_label` is only used in the structured log line.
    """
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": _translate.messages_to_openai(messages, system=system),
        "max_tokens": max_tokens,
    }
    otools = _translate.tools_to_openai(tools)
    if otools is not None:
        kwargs["tools"] = otools
    otc = _translate.tool_choice_to_openai(tool_choice)
    if otc is not None:
        kwargs["tool_choice"] = otc

    t0 = time.monotonic()
    response = client.chat.completions.create(**kwargs)
    latency_ms = int((time.monotonic() - t0) * 1000)

    # I2: OpenAI-compatible SDKs return tool-call `arguments` as a JSON *string*.
    # Malformed JSON -> clear terminal RuntimeError (NOT retried — same bad response
    # on every attempt; tenacity here only handles transport errors).
    try:
        text, tool_use_input = _translate.extract_openai_tool_use(response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{provider_label} ({model_id}) returned malformed tool-call JSON arguments: {exc}"
        ) from exc
    # I1: JSON-valid-but-non-object args -> RuntimeError (mirrors analyst.py idiom so
    # the Analyst gets a clear failure, not a confusing pydantic ValidationError).
    if tool_use_input is not None and not isinstance(tool_use_input, dict):
        raise RuntimeError(
            f"{provider_label} ({model_id}) tool-call arguments were not a JSON object "
            f"(got {type(tool_use_input).__name__}); cannot build Answer."
        )

    usage = Usage(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
    cost = cost_eur(
        model_id=model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    _record_cost_eur(cost)
    logger.info(
        "%s completion: model=%s tokens=%d/%d cost_eur=%.4f latency_ms=%d",
        provider_label,
        model_id,
        usage.input_tokens,
        usage.output_tokens,
        cost,
        latency_ms,
    )
    return CompletionResult(
        text=text,
        tool_use_input=tool_use_input,
        usage=usage,
        model_id=model_id,
        latency_ms=latency_ms,
        cost_eur=cost,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (OpenAIRateErr, OpenAIConnErr, OpenAITimeoutErr, OpenAIServerErr)
    ),
    reraise=True,
)
def _call_openai(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """OpenAI (GPT-4o / GPT-4o-mini) via the shared OpenAI-compatible path."""
    return _call_openai_compatible(
        client=_openai_client(),
        provider_label=PROVIDER_OPENAI,
        model_id=model_id,
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((GroqRateErr, GroqConnErr, GroqTimeoutErr, GroqServerErr)),
    reraise=True,
)
def _call_groq(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """Groq (Llama-70B, OpenAI-compatible API) via the shared path."""
    return _call_openai_compatible(
        client=_groq_client(),
        provider_label=PROVIDER_GROQ,
        model_id=model_id,
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )


def _selfhost_client() -> openai.OpenAI:
    """OpenAI-compatible client for the self-hosted / open-model endpoint.

    Reads REGULAITOR_SELFHOST_BASE_URL (e.g. https://api.mistral.ai/v1 now, an
    OVH/Scaleway/vLLM URL later) and REGULAITOR_SELFHOST_API_KEY from env.
    Fail-fast at construction if either is missing (prod default never calls
    this — only the 'self_hosted' mode does). Uses the openai SDK because the
    endpoint is OpenAI-compatible; this reuses _call_openai_compatible verbatim.
    """
    base_url = os.environ.get("REGULAITOR_SELFHOST_BASE_URL")
    if not base_url:
        raise RuntimeError(
            "REGULAITOR_SELFHOST_BASE_URL not set; required for router "
            "'self_hosted' mode. Set it to an OpenAI-compatible endpoint."
        )
    key = os.environ.get("REGULAITOR_SELFHOST_API_KEY")
    if not key:
        raise RuntimeError(
            "REGULAITOR_SELFHOST_API_KEY not set; required for router " "'self_hosted' mode."
        )
    return openai.OpenAI(base_url=base_url, api_key=key)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (OpenAIRateErr, OpenAIConnErr, OpenAITimeoutErr, OpenAIServerErr)
    ),
    reraise=True,
)
def _call_selfhost(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """Self-hosted / open model via the shared OpenAI-compatible path.

    REGULAITOR_SELFHOST_MODEL overrides the served model id at call time
    (default = the _MODE_MAP target, MISTRAL_SMALL). cost_eur reports 0.0 for a
    model id absent from PRICING (open/self-hosted list price unknown), so the
    cost accumulator never crashes. The shared path carries the I1/I2 malformed
    tool-call guards — exactly the structured-output failures probe R1 measures.
    """
    resolved_model = os.environ.get("REGULAITOR_SELFHOST_MODEL") or model_id
    return _call_openai_compatible(
        client=_selfhost_client(),
        provider_label=PROVIDER_SELFHOST,
        model_id=resolved_model,
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )
