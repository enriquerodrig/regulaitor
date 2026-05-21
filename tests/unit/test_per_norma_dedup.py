"""v0.1.11 — per-norma dedup helper unit tests.

Motivated by v0.1.10 measurement: the per-ARTICLE cap (v0.1.10) recovered
article diversity within a single norma (5×nis2.23 → 4 distinct NIS2 articles)
but did NOT fix xcorpus-002 because top-5 was still 5/5 NIS2 (just diversified
articles within NIS2) and the purity gate still collapsed to NIS2-only,
starving NIS2 art 35 and GDPR art 33.

v0.1.11 adds a SECOND-axis cap: at most N chunks per `norma` key, regardless
of article. With per-norma cap=3 on top_k=5, at least 2 of top-5 MUST come
from a non-dominant norma → cross-corpus diversity guaranteed → purity gate
cannot collapse if dominant share = 3/5 = 0.6 (exactly at threshold; with
cap=2 the share = 2/5 = 0.4 < 0.6 → guaranteed multi-corpus emission).

The two caps compose: per-article applies first (each (norma, article) ≤N1),
then per-norma applies (each norma ≤N2) — both pure, both deterministic.

These tests pin the contract of the new pure helper `_apply_per_norma_dedup`;
the integration test `tests/integration/test_xcorpus_002_diagnostic.py`
measures the actual cap=3 impact on xcorpus-002 (the v0.1.11 success question).
"""

from __future__ import annotations

from regulaitor.rag.retrieval import _apply_per_norma_dedup


def _pairs(normas: list[str]) -> list[tuple[str, int]]:
    """(norma, payload) best-first; payload = opaque int id (position)."""
    return [(n, i) for i, n in enumerate(normas)]


def test_cap_three_keeps_at_most_three_per_norma_preserving_order() -> None:
    """Five NIS2 + two GDPR in best-first order: cap=3 keeps top-3 NIS2 and
    both GDPR, dropping NIS2 positions 4-5."""
    pairs = _pairs(["nis2", "nis2", "nis2", "nis2", "nis2", "gdpr", "gdpr"])
    out = _apply_per_norma_dedup(pairs, max_per_norma=3)
    assert out == [
        ("nis2", 0),
        ("nis2", 1),
        ("nis2", 2),
        ("gdpr", 5),
        ("gdpr", 6),
    ]


def test_cap_two_forces_minimum_multi_corpus_in_top_five() -> None:
    """Five NIS2 + three GDPR: cap=2 keeps top-2 NIS2 + top-2 GDPR. The point:
    in a top_k=5 window this guarantees max-share = 2/5 = 0.4 < 0.6 threshold
    → purity gate stays multi-corpus."""
    pairs = _pairs(["nis2", "nis2", "nis2", "nis2", "nis2", "gdpr", "gdpr", "gdpr"])
    out = _apply_per_norma_dedup(pairs, max_per_norma=2)
    assert out == [
        ("nis2", 0),
        ("nis2", 1),
        ("gdpr", 5),
        ("gdpr", 6),
    ]


def test_cap_one_strict_round_robin_first_wins() -> None:
    """cap=1 keeps the best chunk of each norma in best-first encounter order."""
    pairs = _pairs(["nis2", "nis2", "gdpr", "dora", "gdpr", "ai_act"])
    out = _apply_per_norma_dedup(pairs, max_per_norma=1)
    assert out == [
        ("nis2", 0),
        ("gdpr", 2),
        ("dora", 3),
        ("ai_act", 5),
    ]


def test_cap_unchanged_when_no_duplicates_exist() -> None:
    """All distinct normas: output identical to input (no chunks dropped)."""
    pairs = _pairs(["nis2", "gdpr", "dora", "ai_act"])
    out = _apply_per_norma_dedup(pairs, max_per_norma=3)
    assert out == pairs


def test_empty_input_returns_empty() -> None:
    assert _apply_per_norma_dedup([], max_per_norma=3) == []


def test_cap_larger_than_any_norma_count_is_no_op() -> None:
    """If max_per_norma exceeds the highest per-norma count, output = input."""
    pairs = _pairs(["nis2", "nis2", "nis2", "gdpr"])
    out = _apply_per_norma_dedup(pairs, max_per_norma=10)
    assert out == pairs
