"""v0.1.10 — per-article dedup helper unit tests.

Motivated by v0.1.9 xcorpus-002 diagnostic (see `docs/xcorpus_002_investigation.md`):
the standard bge-reranker-v2-m3 scored 5 different paragraphs of NIS2 art 23
higher than NIS2 art 35 or GDPR art 33 on a personal-data-breach cross-corpus
query (single-article dominance failure mode).

The dedup helper is a pure function that caps the number of chunks per
`(norma, article)` key in a reranked list, preserving best-first order.
Intended to be called BEFORE `_apply_purity_gate` in `run_auto` when the new
`RetrievalConfig.max_chunks_per_article` field is set.

These tests pin the contract; the integration test
`tests/integration/test_xcorpus_002_diagnostic.py` measures the actual impact
on xcorpus-002 with cap=2 (the v0.1.10 follow-up question).
"""

from __future__ import annotations

from regulaitor.rag.retrieval import _apply_per_article_dedup


def _triples(items: list[tuple[str, str]]) -> list[tuple[str, str, int]]:
    """Build (norma, article, payload) triples best-first; payload = opaque int id."""
    return [(n, a, i) for i, (n, a) in enumerate(items)]


def test_cap_two_keeps_at_most_two_per_article_preserving_order() -> None:
    """Five chunks of NIS2 art 23 + one of GDPR art 33: cap=2 keeps top-2 NIS2 23
    and the GDPR 33, dropping NIS2 23 positions 3-5."""
    triples = _triples(
        [
            ("nis2", "23"),
            ("nis2", "23"),
            ("nis2", "23"),
            ("nis2", "23"),
            ("nis2", "23"),
            ("gdpr", "33"),
        ]
    )
    out = _apply_per_article_dedup(triples, max_per_article=2)
    assert list(out) == [
        ("nis2", 0),
        ("nis2", 1),
        ("gdpr", 5),
    ]


def test_cap_one_keeps_exactly_one_per_article() -> None:
    """Strict deduplication: cap=1 keeps the first chunk per (norma, article)."""
    triples = _triples(
        [
            ("nis2", "23"),
            ("nis2", "23"),
            ("nis2", "35"),
            ("gdpr", "33"),
            ("gdpr", "33"),
        ]
    )
    out = _apply_per_article_dedup(triples, max_per_article=1)
    # Position 0 (nis2.23), position 2 (nis2.35), position 3 (gdpr.33)
    assert list(out) == [
        ("nis2", 0),
        ("nis2", 2),
        ("gdpr", 3),
    ]


def test_cap_unchanged_when_no_duplicates_exist() -> None:
    """All distinct (norma, article) → output identical to input (just payload drop)."""
    triples = _triples([("nis2", "23"), ("nis2", "35"), ("gdpr", "33"), ("dora", "1")])
    out = _apply_per_article_dedup(triples, max_per_article=2)
    assert list(out) == [
        ("nis2", 0),
        ("nis2", 1),
        ("gdpr", 2),
        ("dora", 3),
    ]


def test_empty_input_returns_empty() -> None:
    assert _apply_per_article_dedup([], max_per_article=2) == []


def test_same_article_in_different_normas_treated_as_distinct_keys() -> None:
    """`(norma, article)` is the dedup key — NIS2 art 23 and GDPR art 23 are
    different chunks even though the article number coincides."""
    triples = _triples([("nis2", "23"), ("gdpr", "23"), ("nis2", "23"), ("gdpr", "23")])
    out = _apply_per_article_dedup(triples, max_per_article=1)
    assert list(out) == [
        ("nis2", 0),
        ("gdpr", 1),
    ]


def test_cap_larger_than_any_article_count_is_no_op() -> None:
    """If `max_per_article` exceeds the highest per-article count in input,
    the output is identical to the input (with payload extracted)."""
    triples = _triples([("nis2", "23"), ("nis2", "23"), ("nis2", "35"), ("gdpr", "33")])
    out = _apply_per_article_dedup(triples, max_per_article=10)
    assert list(out) == [
        ("nis2", 0),
        ("nis2", 1),
        ("nis2", 2),
        ("gdpr", 3),
    ]
