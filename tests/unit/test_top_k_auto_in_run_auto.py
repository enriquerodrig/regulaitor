"""v0.1.12 — top_k_auto wiring in run_auto unit tests.

Pins the integration contract: when `cfg.top_k_auto is None` (the backward-
compat default), `run_auto` uses `cfg.top_k` exactly as v0.1.11 did. When set,
`run_auto` uses `cfg.top_k_auto` as the purity-gate window AND final output
size, while `cfg.top_k` itself remains unchanged (preserving the explicit-
corpus `run()` path's byte-identical guarantee).

Tested via mocking the dense+rerank infrastructure: we only care about the
gate decision + output size, not real LanceDB / BGE behaviour (covered in
integration tests).
"""

from __future__ import annotations

from typing import Any

import pytest

from regulaitor.rag import retrieval


def _mock_dense_and_rerank(
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[dict[str, Any]],
    rerank_order: list[int],
) -> None:
    """Mock embed/store/reranker so run_auto sees the given candidates ranked
    in the given order. Each candidate dict must have `norma`, `articulo`,
    `chunk_id`, `text`, `apartado`, `language` keys plus whatever `_enrich`
    pulls. Manifest meta is mocked separately."""

    class _Search:
        def __init__(self, cands: list[dict[str, Any]]) -> None:
            self._cands = cands

        def where(self, _: str):  # type: ignore[no-untyped-def]
            return self

        def limit(self, _: int):  # type: ignore[no-untyped-def]
            return self

        def to_list(self):  # type: ignore[no-untyped-def]
            return self._cands

    class _Table:
        def __init__(self, cands: list[dict[str, Any]]) -> None:
            self._cands = cands

        def search(self, _: list[float]):  # type: ignore[no-untyped-def]
            return _Search(self._cands)

    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: _Table(candidates))
    monkeypatch.setattr(
        retrieval.reranker,
        "rerank",
        lambda _q, _ps, top_n=None: [(idx, 1.0 - i * 0.01) for i, idx in enumerate(rerank_order)],
    )
    # Mock manifest meta so _enrich doesn't hit the real loader.
    monkeypatch.setattr(
        retrieval.loader,
        "get_manifest_meta",
        lambda _n: {"version": "v1", "source_url": "https://example.com"},
    )


def _make_candidate(norma: str, articulo: str, idx: int) -> dict[str, Any]:
    return {
        "chunk_id": f"{norma}.{articulo}.{idx}.es",
        "norma": norma,
        "articulo": articulo,
        "apartado": str(idx),
        "language": "es",
        "text": f"text {norma}.{articulo}.{idx}",
    }


def test_top_k_auto_none_uses_cfg_top_k_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_k_auto=None → uses cfg.top_k=5 → emits 5 chunks (or less if reranker
    returns fewer). Backward-compat with v0.1.11."""
    # 10 NIS2 candidates, reranker keeps them in order.
    cands = [_make_candidate("nis2", "23", i) for i in range(10)]
    _mock_dense_and_rerank(monkeypatch, cands, list(range(10)))

    cfg = retrieval.RetrievalConfig()  # top_k=5, top_k_auto=None
    chunks, resolved = retrieval.run_auto("q", "es", cfg)

    # All 10 are NIS2 23 → gate sees 5/5 = 1.0 ≥ 0.6 → collapses to NIS2 → kept
    # = up to 5 NIS2 chunks (top_k=5 limit).
    assert len(chunks) == 5
    assert list(resolved) == ["nis2"]


def test_top_k_auto_12_uses_12_for_gate_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_k_auto=12 → gate computes share over top-12, kept up to 12. The
    explicit cfg.top_k=5 is IGNORED for the auto path when override is set."""
    # 15 NIS2 candidates so we have plenty for top-12.
    cands = [_make_candidate("nis2", "23", i) for i in range(15)]
    _mock_dense_and_rerank(monkeypatch, cands, list(range(15)))

    cfg = retrieval.RetrievalConfig(top_k=5, top_k_auto=12)
    chunks, resolved = retrieval.run_auto("q", "es", cfg)

    # 15 NIS2 → gate sees top-12 = 12/12 = 1.0 ≥ 0.6 → collapses to NIS2 →
    # kept = up to 12 NIS2 (top_k_auto=12).
    assert len(chunks) == 12
    assert list(resolved) == ["nis2"]


def test_top_k_auto_with_per_norma_cap_composes(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_k_auto=12 + max_chunks_per_norma=3: per-norma cap applies first (limits
    each norma to 3), then gate computes share over top-12 → max-share with 4
    normas equally distributed = 3/12 = 0.25 < 0.6 → multi-corpus output."""
    # 4 normas × 5 candidates each = 20 candidates; reranker interleaves them.
    cands = []
    rerank_order = []
    for i in range(5):
        for norma in ["nis2", "dora", "gdpr", "ai_act"]:
            idx = len(cands)
            cands.append(_make_candidate(norma, f"art{i}", idx))
            rerank_order.append(idx)
    _mock_dense_and_rerank(monkeypatch, cands, rerank_order)

    cfg = retrieval.RetrievalConfig(top_k=5, top_k_auto=12, max_chunks_per_norma=3)
    chunks, resolved = retrieval.run_auto("q", "es", cfg)

    # cap=3 per norma applied first → 3 per norma × 4 normas = 12 chunks.
    # Gate sees max-share = 3/12 = 0.25 < 0.6 → multi-corpus.
    assert len(chunks) == 12
    assert sorted(resolved) == ["ai_act", "dora", "gdpr", "nis2"]
