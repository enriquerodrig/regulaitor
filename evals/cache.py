"""H8 — Hash-keyed filesystem cache for LLM responses.

The harness wraps every LLM call through `cache_call`. On hit, returns the
cached response without API contact. On miss, calls `invoke` (the live API
function), persists the response with cost estimation, and returns it.

`cache_only=True` mode refuses to call `invoke` on miss — useful for
regenerating the report from cached responses without spending credit
(`make eval-from-cache`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

# Filesystem location for the cache. Tests monkeypatch this to tmp_path.
_CACHE_DIR = Path(__file__).resolve().parent / "cache"

# Separator joining (system, user) into the canonical prompt before hashing.
# A future caller computing cache_key() manually must use this same separator.
_PROMPT_SEP = "\n---\n"

# Anthropic prices per 1M tokens (USD), converted to EUR at ~0.92.
# Rates as of 2026-Q1: Sonnet 4.6 $3/M in, $15/M out; Haiku 4.5 $1/M in, $5/M out.
_PRICE_EUR_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (2.76, 13.80),  # input, output
    "claude-haiku-4-5-20251001": (0.92, 4.60),
}


def cache_key(*, model: str, prompt: str, temperature: float) -> str:
    """SHA256 hex digest of (model, prompt, temperature). 64 chars."""
    payload = f"{model}|{prompt}|{temperature}".encode()
    return hashlib.sha256(payload).hexdigest()


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


# Still live: used by cache_call for judge-layer cost
# (H15 removed only the harness production-cost use).
def estimate_cost_eur(*, model: str, tokens_in: int, tokens_out: int) -> float:
    """Approximate cost in EUR using static price table. Unknown model -> 0.0."""
    rates = _PRICE_EUR_PER_M_TOKENS.get(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    return (tokens_in / 1_000_000) * in_rate + (tokens_out / 1_000_000) * out_rate


# Type of the live-API invocation function: returns (response_text, tokens_in, tokens_out).
InvokeFn = Callable[..., tuple[str, int, int]]


def cache_call(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    invoke: InvokeFn,
    cache_only: bool,
) -> tuple[str, float]:
    """Cached LLM invocation. Returns (response_text, cost_eur).

    On hit: zero-cost; on miss with cache_only=False: live API + persist;
    on miss with cache_only=True: raises RuntimeError.
    """
    prompt = f"{system}{_PROMPT_SEP}{user}"
    key = cache_key(model=model, prompt=prompt, temperature=temperature)
    path = _cache_path(key)

    if path.exists():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            return record["response"], 0.0  # cache hit -> zero marginal cost
        except (json.JSONDecodeError, KeyError):
            # Corrupt or partial cache entry (e.g. process killed mid-write).
            # Treat as miss so the live API call rebuilds it.
            pass

    if cache_only:
        raise RuntimeError(f"cache miss for {key} in --cache-only mode")

    text, tokens_in, tokens_out = invoke(
        model=model,
        system=system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    cost = estimate_cost_eur(model=model, tokens_in=tokens_in, tokens_out=tokens_out)

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "request": {"model": model, "system": system, "user": user, "temperature": temperature},
        "response": text,
        "timestamp": datetime.now(UTC).isoformat(),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_eur": cost,
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return text, cost
