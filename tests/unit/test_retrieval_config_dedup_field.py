"""v0.1.10 — RetrievalConfig.max_chunks_per_article field unit tests.

Pins the new field's defaults + invariants. Default = None = no cap (backward-
compat with v0.1.9 behaviour; production callers see no change unless they
explicitly opt in to a cap or set REGULAITOR_RETRIEVAL_CONFIG with the field).
"""

from __future__ import annotations

import pytest

from regulaitor.rag.retrieval import RetrievalConfig


def test_default_is_none_for_backward_compat() -> None:
    """RetrievalConfig() default has max_chunks_per_article=None → no cap →
    v0.1.9 behaviour preserved for any caller that doesn't set the field."""
    cfg = RetrievalConfig()
    assert cfg.max_chunks_per_article is None


def test_explicit_int_value_preserved() -> None:
    cfg = RetrievalConfig(max_chunks_per_article=2)
    assert cfg.max_chunks_per_article == 2


def test_explicit_none_value_preserved() -> None:
    cfg = RetrievalConfig(max_chunks_per_article=None)
    assert cfg.max_chunks_per_article is None


def test_rejects_zero_or_negative() -> None:
    """Capping to 0 (or negative) chunks per article makes no operational sense
    — that would silently filter everything. Fail loud at construction."""
    with pytest.raises(ValueError, match="max_chunks_per_article must be >= 1"):
        RetrievalConfig(max_chunks_per_article=0)
    with pytest.raises(ValueError, match="max_chunks_per_article must be >= 1"):
        RetrievalConfig(max_chunks_per_article=-1)


def test_rejects_non_int_non_none() -> None:
    """Type discipline: must be int or None, not float or string."""
    with pytest.raises(TypeError, match="max_chunks_per_article must be int or None"):
        RetrievalConfig(max_chunks_per_article=2.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="max_chunks_per_article must be int or None"):
        RetrievalConfig(max_chunks_per_article="2")  # type: ignore[arg-type]
