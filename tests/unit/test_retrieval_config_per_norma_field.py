"""v0.1.11 — RetrievalConfig.max_chunks_per_norma field unit tests.

Pins the new field's defaults + invariants. Default = None = no cap (backward-
compat with v0.1.10 behaviour; production callers see no change unless they
opt in to the cap explicitly).
"""

from __future__ import annotations

import pytest

from regulaitor.rag.retrieval import RetrievalConfig


def test_default_is_none_for_backward_compat() -> None:
    """RetrievalConfig() default has max_chunks_per_norma=2 (v0.1.21.2 flip) →
    per-norma cap enables cross-corpus diversity. Opt-out via explicit None
    restores v0.1.10 behaviour."""
    cfg = RetrievalConfig()
    assert cfg.max_chunks_per_norma == 2


def test_explicit_int_value_preserved() -> None:
    cfg = RetrievalConfig(max_chunks_per_norma=3)
    assert cfg.max_chunks_per_norma == 3


def test_explicit_none_value_preserved() -> None:
    cfg = RetrievalConfig(max_chunks_per_norma=None)
    assert cfg.max_chunks_per_norma is None


def test_rejects_zero_or_negative() -> None:
    """Capping to 0 (or negative) chunks per norma makes no operational sense
    — it would silently filter everything. Fail loud at construction."""
    with pytest.raises(ValueError, match="max_chunks_per_norma must be >= 1"):
        RetrievalConfig(max_chunks_per_norma=0)
    with pytest.raises(ValueError, match="max_chunks_per_norma must be >= 1"):
        RetrievalConfig(max_chunks_per_norma=-1)


def test_rejects_non_int_non_none() -> None:
    with pytest.raises(TypeError, match="max_chunks_per_norma must be int or None"):
        RetrievalConfig(max_chunks_per_norma=3.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="max_chunks_per_norma must be int or None"):
        RetrievalConfig(max_chunks_per_norma="3")  # type: ignore[arg-type]


def test_can_set_both_caps_simultaneously() -> None:
    """The two caps compose: per-article applies first, then per-norma. Both
    can be set on the same config without interaction at construction."""
    cfg = RetrievalConfig(max_chunks_per_article=2, max_chunks_per_norma=3)
    assert cfg.max_chunks_per_article == 2
    assert cfg.max_chunks_per_norma == 3
