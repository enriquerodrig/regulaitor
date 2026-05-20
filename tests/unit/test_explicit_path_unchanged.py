# tests/unit/test_explicit_path_unchanged.py
"""HARD guard: the explicit-corpus retrieval path WHERE-CLAUSE must remain
"norma = '<norma>' AND language = '<lang>'" (single-norma, no purity gate).
This is the no-leakage-critical line (§22.18 / H14). The full _enrich path
and RetrievedChunk construction are covered by test_retrieval_run_branches.py
and tests/unit/rag/test_retrieval.py."""
from __future__ import annotations

from regulaitor.rag import retrieval


def test_explicit_where_clause_is_exactly_single_norma(monkeypatch) -> None:
    captured = {}

    class _S:
        def where(self, c):
            captured["w"] = c
            return self

        def limit(self, _n):
            return self

        def to_list(self):
            return []

    class _T:
        def search(self, _v):
            return _S()

    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: _T())
    monkeypatch.setattr(retrieval.reranker, "rerank", lambda *a, **k: [])
    out = retrieval.run("q", "nis2", "en", top_k=5)
    assert out == []
    assert captured["w"] == "norma = 'nis2' AND language = 'en'"
