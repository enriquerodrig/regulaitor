"""v0.1.12 — RetrievalConfig.top_k_auto field unit tests.

Pins the new field's defaults + invariants. Default `None` = use `cfg.top_k`
(backward-compat with v0.1.11). When set, `run_auto` uses this value INSTEAD
of `cfg.top_k` for the purity gate window + final output size. The explicit-
corpus `run()` path ignores this field entirely (continues using `top_k`),
preserving the T6 byte-identical invariant for the explicit path.

The motivation (v0.1.11 deeper ceiling carried to v0.1.12): per-norma cap=2
surfaced GDPR 33 (2/3 expected) but NIS2 35 still missed because the reranker
scores it below DORA 19/22. Raising `top_k_auto` to 12 gives the gate more
slots so NIS2 35 might fit if the per-norma cap is also relaxed accordingly.
"""

from __future__ import annotations

import pytest

from regulaitor.rag.retrieval import RetrievalConfig


def test_default_is_none_for_backward_compat() -> None:
    """RetrievalConfig() default has top_k_auto=None → auto path uses cfg.top_k
    (= 5 default) → v0.1.11 behaviour preserved."""
    cfg = RetrievalConfig()
    assert cfg.top_k_auto is None


def test_explicit_int_value_preserved() -> None:
    cfg = RetrievalConfig(top_k_auto=12)
    assert cfg.top_k_auto == 12


def test_explicit_none_value_preserved() -> None:
    cfg = RetrievalConfig(top_k_auto=None)
    assert cfg.top_k_auto is None


def test_rejects_zero_or_negative() -> None:
    """Capping to 0 (or negative) makes no operational sense — fail loud."""
    with pytest.raises(ValueError, match="top_k_auto must be >= 1"):
        RetrievalConfig(top_k_auto=0)
    with pytest.raises(ValueError, match="top_k_auto must be >= 1"):
        RetrievalConfig(top_k_auto=-1)


def test_rejects_non_int_non_none() -> None:
    """Type discipline: int or None only, not float or string."""
    with pytest.raises(TypeError, match="top_k_auto must be int or None"):
        RetrievalConfig(top_k_auto=12.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="top_k_auto must be int or None"):
        RetrievalConfig(top_k_auto="12")  # type: ignore[arg-type]


def test_composes_with_other_caps_and_top_k() -> None:
    """All four levers can be set on the same config without interaction at
    construction. The composition semantics are tested in
    test_top_k_auto_in_run_auto.py (integration of the wiring in run_auto)."""
    cfg = RetrievalConfig(
        top_k=5,
        top_k_auto=12,
        max_chunks_per_article=2,
        max_chunks_per_norma=3,
    )
    assert cfg.top_k == 5
    assert cfg.top_k_auto == 12
    assert cfg.max_chunks_per_article == 2
    assert cfg.max_chunks_per_norma == 3
