# tests/unit/test_purity_gate.py
from __future__ import annotations

from regulaitor.rag.retrieval import RetrievalConfig, _apply_purity_gate


def _pairs(normas: list[str]) -> list[tuple[str, int]]:
    # (norma, payload) ordered best-first; payload is an opaque int id.
    return [(n, i) for i, n in enumerate(normas)]


def test_single_corpus_dominant_collapses_to_that_norma() -> None:
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    pairs = _pairs(["gdpr", "gdpr", "gdpr", "gdpr", "nis2"])  # 4/5 = 0.8 >= 0.6
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["gdpr"]
    assert all(n == "gdpr" for n, _ in kept)
    assert len(kept) == 4


def test_genuine_multi_corpus_returns_top_k_unfiltered() -> None:
    cfg = RetrievalConfig(top_k=4, purity_threshold=0.6)
    pairs = _pairs(["nis2", "dora", "nis2", "dora", "gdpr"])  # max share 2/4 = 0.5 < 0.6
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert [n for n, _ in kept] == ["nis2", "dora", "nis2", "dora"]
    assert sorted(resolved) == ["dora", "nis2"]


def test_threshold_is_inclusive_boundary() -> None:
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    pairs = _pairs(["dora", "dora", "dora", "nis2", "gdpr"])  # 3/5 = 0.6 == threshold
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["dora"]  # >= is inclusive


def test_empty_rerank_returns_empty() -> None:
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    kept, resolved = _apply_purity_gate([], cfg)
    assert kept == []
    assert resolved == []


def test_share_window_is_top_k_not_full_list() -> None:
    # 10 items, top_k=4: only the first 4 count toward the share.
    cfg = RetrievalConfig(top_k=4, purity_threshold=0.75)
    pairs = _pairs(["gdpr", "gdpr", "gdpr", "gdpr", "nis2", "nis2", "nis2", "nis2", "nis2", "nis2"])
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["gdpr"]  # top-4 are all gdpr (4/4 = 1.0)
    assert len(kept) == 4


def test_tie_no_corpus_reaches_threshold_returns_multi() -> None:
    cfg = RetrievalConfig(top_k=4, purity_threshold=0.6)
    pairs = _pairs(["ai_act", "gdpr", "nis2", "dora"])  # each 1/4 = 0.25
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert len(kept) == 4
    assert sorted(resolved) == ["ai_act", "dora", "gdpr", "nis2"]


def test_fewer_candidates_than_top_k_uses_top_k_denominator() -> None:
    # Only 3 candidates, all gdpr, but top_k=5 -> share = 3/5 = 0.6 (not 3/3=1.0).
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    pairs = _pairs(["gdpr", "gdpr", "gdpr"])
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["gdpr"]  # 3/5 == 0.6 >= 0.6 -> collapses
    assert len(kept) == 3


def test_fewer_candidates_below_top_k_denominator_stays_multi() -> None:
    # 2 of 2 gdpr but top_k=5 -> 2/5 = 0.4 < 0.6 -> NOT collapsed despite 100% one corpus.
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    pairs = _pairs(["gdpr", "gdpr"])
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["gdpr"]  # sorted(counts) over the single norma present
    assert len(kept) == 2


def test_retrievalconfig_rejects_top_k_below_one() -> None:
    import pytest

    with pytest.raises(ValueError, match="top_k must be >= 1"):
        RetrievalConfig(top_k=0)
