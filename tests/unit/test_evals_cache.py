"""Unit tests for evals.cache — hash-keyed LLM response cache."""

from __future__ import annotations

from pathlib import Path

import pytest
from evals import cache


def test_cache_key_deterministic() -> None:
    k1 = cache.cache_key(model="claude-sonnet-4-6", prompt="hello", temperature=0.0)
    k2 = cache.cache_key(model="claude-sonnet-4-6", prompt="hello", temperature=0.0)
    assert k1 == k2
    assert len(k1) == 64  # sha256 hex


def test_cache_key_differs_for_different_inputs() -> None:
    k_a = cache.cache_key(model="claude-sonnet-4-6", prompt="a", temperature=0.0)
    k_b = cache.cache_key(model="claude-sonnet-4-6", prompt="b", temperature=0.0)
    k_t = cache.cache_key(model="claude-sonnet-4-6", prompt="a", temperature=0.5)
    k_m = cache.cache_key(model="claude-haiku-4-5", prompt="a", temperature=0.0)
    assert len({k_a, k_b, k_t, k_m}) == 4


def test_cache_call_persists_on_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)

    calls: list[dict] = []

    def fake_invoke(
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, int, int]:
        calls.append({"model": model, "user": user})
        return ("response_text", 100, 50)  # text, tokens_in, tokens_out

    # Use a known model so cost > 0 (unknown models return 0.0 by design)
    text, cost = cache.cache_call(
        model="claude-sonnet-4-6",
        system="s",
        user="u",
        temperature=0.0,
        max_tokens=1000,
        invoke=fake_invoke,
        cache_only=False,
    )
    assert text == "response_text"
    assert cost > 0
    assert len(calls) == 1
    # Persisted file exists
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1


def test_cache_call_hit_skips_invoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)
    calls: list[dict] = []

    def fake_invoke(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return ("first", 100, 50)

    cache.cache_call(
        model="m",
        system="s",
        user="u",
        temperature=0.0,
        max_tokens=1000,
        invoke=fake_invoke,
        cache_only=False,
    )
    cache.cache_call(
        model="m",
        system="s",
        user="u",
        temperature=0.0,
        max_tokens=1000,
        invoke=fake_invoke,
        cache_only=False,
    )
    assert len(calls) == 1  # second call hit cache


def test_cache_only_raises_on_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="cache miss"):
        cache.cache_call(
            model="m",
            system="s",
            user="u",
            temperature=0.0,
            max_tokens=1000,
            invoke=lambda **kw: ("x", 0, 0),
            cache_only=True,
        )


def test_estimate_cost_eur_known_models() -> None:
    cost = cache.estimate_cost_eur(model="claude-sonnet-4-6", tokens_in=1_000_000, tokens_out=0)
    assert cost == pytest.approx(2.76, rel=0.01)
    cost = cache.estimate_cost_eur(
        model="claude-haiku-4-5-20251001", tokens_in=1_000_000, tokens_out=0
    )
    assert cost == pytest.approx(0.92, rel=0.01)


def test_estimate_cost_eur_unknown_model_returns_zero() -> None:
    assert cache.estimate_cost_eur(model="some-other-model", tokens_in=1000, tokens_out=1000) == 0.0
