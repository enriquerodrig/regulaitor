# tests/unit/test_retrieval_run_branches.py
from __future__ import annotations

import pytest

from regulaitor.rag import retrieval


class _FakeSearch:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.where_clause: str | None = None

    def where(self, clause: str) -> _FakeSearch:
        self.where_clause = clause
        return self

    def limit(self, _n: int) -> _FakeSearch:
        return self

    def to_list(self) -> list[dict]:
        return self._rows


class _FakeTable:
    def __init__(self, rows: list[dict]) -> None:
        self.search_obj = _FakeSearch(rows)

    def search(self, _vec: object) -> _FakeSearch:
        return self.search_obj


def _row(norma: str, art: str) -> dict:
    return {
        "chunk_id": f"{norma}-{art}",
        "norma": norma,
        "articulo": art,
        "apartado": None,
        "language": "es",
        "text": f"text-{norma}-{art}",
    }


@pytest.fixture
def _patch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(
        retrieval.loader,
        "get_manifest_meta",
        lambda _c: {"version": "v", "source_url": "u"},
    )

    def _factory(rows: list[dict]):
        table = _FakeTable(rows)
        monkeypatch.setattr(retrieval.store, "connect", lambda _p: table)
        return table

    return _factory


def test_explicit_corpus_uses_single_norma_where_clause(_patch, monkeypatch) -> None:
    rows = [_row("gdpr", "5"), _row("gdpr", "6")]
    table = _patch(rows)
    monkeypatch.setattr(retrieval.reranker, "rerank", lambda _q, _p, top_n: [(0, 0.9), (1, 0.8)])
    out = retrieval.run("q", "gdpr", "es", top_k=5)
    assert table.search_obj.where_clause == "norma = 'gdpr' AND language = 'es'"
    assert [c.norma for c in out] == ["gdpr", "gdpr"]


def test_auto_drops_norma_filter_and_applies_gate(_patch, monkeypatch) -> None:
    # 4 gdpr + 1 nis2 in rerank order -> 4/5 = 0.8 >= 0.6 -> collapse to gdpr.
    rows = [
        _row("gdpr", "1"),
        _row("gdpr", "2"),
        _row("gdpr", "3"),
        _row("gdpr", "4"),
        _row("nis2", "9"),
    ]
    table = _patch(rows)
    monkeypatch.setattr(
        retrieval.reranker,
        "rerank",
        lambda _q, _p, top_n: [(0, 0.9), (1, 0.85), (2, 0.8), (3, 0.75), (4, 0.5)],
    )
    out, resolved = retrieval.run_auto("q", "es", retrieval.RetrievalConfig())
    assert "norma" not in (table.search_obj.where_clause or "")
    assert table.search_obj.where_clause == "language = 'es'"
    assert resolved == ["gdpr"]
    assert all(c.norma == "gdpr" for c in out)


def test_auto_multi_corpus_non_collapse_returns_per_norma_meta(monkeypatch) -> None:
    # 2 nis2 + 2 dora interleaved, top_k default 5 -> max share 2/5 = 0.4 < 0.6
    # -> NO collapse -> genuine multi-corpus result. Each chunk must carry ITS
    # OWN norma's version/source_url (the _enrich per-chunk correctness claim).
    rows = [
        _row("nis2", "21"),
        _row("dora", "5"),
        _row("nis2", "23"),
        _row("dora", "9"),
    ]
    table = _FakeTable(rows)
    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: table)
    monkeypatch.setattr(
        retrieval.reranker,
        "rerank",
        lambda _q, _p, top_n: [(0, 0.9), (1, 0.85), (2, 0.8), (3, 0.75)],
    )
    # norma-distinct meta: version == source_url == the norma itself.
    monkeypatch.setattr(
        retrieval.loader,
        "get_manifest_meta",
        lambda n: {"version": n, "source_url": n},
    )
    out, resolved = retrieval.run_auto("q", "es", retrieval.RetrievalConfig())
    assert sorted(resolved) == ["dora", "nis2"]  # genuine multi-corpus
    assert sorted(c.norma for c in out) == ["dora", "dora", "nis2", "nis2"]
    # the per-chunk-meta correctness claim: every chunk's version/source_url
    # equals ITS OWN norma (would fail if _enrich resolved meta once by a
    # single corpus arg instead of per chunk).
    for c in out:
        assert c.version == c.norma
        assert c.source_url == c.norma


def test_auto_empty_rerank_returns_empty_tuple(monkeypatch) -> None:
    table = _FakeTable([])
    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: table)
    monkeypatch.setattr(retrieval.reranker, "rerank", lambda _q, _p, top_n: [])
    result = retrieval.run_auto("q", "es", retrieval.RetrievalConfig())
    assert result == ([], [])
