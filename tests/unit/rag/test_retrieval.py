"""Unit tests for rag/retrieval.py - canonical helper used by both
the MCP search_articles tool and the RetrieverAgent."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import RetrievedChunk
from regulaitor.rag import retrieval


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace the heavy dependencies with mocks; return them for assertions."""
    embed_mock = MagicMock(return_value=[[0.1] * 1024])
    search_mock = MagicMock()
    rerank_mock = MagicMock()
    meta_mock = MagicMock(
        return_value={"version": "32024R1689", "source_url": "https://example.com"}
    )
    connect_mock = MagicMock()

    monkeypatch.setattr(retrieval.embeddings, "embed", embed_mock)
    monkeypatch.setattr(retrieval.store, "connect", connect_mock)
    monkeypatch.setattr(retrieval.reranker, "rerank", rerank_mock)
    monkeypatch.setattr(retrieval.loader, "get_manifest_meta", meta_mock)

    return {
        "embed": embed_mock,
        "search": search_mock,
        "rerank": rerank_mock,
        "connect": connect_mock,
        "meta": meta_mock,
    }


def _make_chain(rows: list[dict[str, Any]]) -> MagicMock:
    """Build a mock that chains .search().where().limit().to_list() returning rows."""
    chain = MagicMock()
    chain.search.return_value.where.return_value.limit.return_value.to_list.return_value = rows
    return chain


def test_run_calls_embed_with_query(_patch_dependencies: dict[str, MagicMock]) -> None:
    _patch_dependencies["connect"].return_value = _make_chain([])
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("alto riesgo", "ai_act", "es", top_k=5)

    _patch_dependencies["embed"].assert_called_once_with(["alto riesgo"])


def test_run_uses_pre_rerank_50(_patch_dependencies: dict[str, MagicMock]) -> None:
    chain = _make_chain([])
    _patch_dependencies["connect"].return_value = chain
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("q", "ai_act", "es", top_k=5)

    # Verify .limit(50) was called on the search chain
    chain.search.return_value.where.return_value.limit.assert_called_once_with(50)


def test_run_filter_by_corpus_and_language(
    _patch_dependencies: dict[str, MagicMock],
) -> None:
    chain = _make_chain([])
    _patch_dependencies["connect"].return_value = chain
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("q", "ai_act", "es", top_k=5)

    where_call = chain.search.return_value.where.call_args
    where_clause = where_call.args[0]
    assert "norma = 'ai_act'" in where_clause
    assert "language = 'es'" in where_clause


def test_run_empty_store_returns_empty(_patch_dependencies: dict[str, MagicMock]) -> None:
    _patch_dependencies["connect"].return_value = _make_chain([])
    _patch_dependencies["rerank"].return_value = []

    result = retrieval.run("q", "ai_act", "es", top_k=5)

    assert result == []


def test_run_returns_chunks_with_meta(
    _patch_dependencies: dict[str, MagicMock],
) -> None:
    rows = [
        {
            "chunk_id": "ai_act.6.1.es",
            "norma": "ai_act",
            "articulo": "6",
            "apartado": "1",
            "language": "es",
            "text": "first chunk text",
        },
        {
            "chunk_id": "ai_act.7.es",
            "norma": "ai_act",
            "articulo": "7",
            "apartado": None,
            "language": "es",
            "text": "second chunk text",
        },
    ]
    _patch_dependencies["connect"].return_value = _make_chain(rows)
    _patch_dependencies["rerank"].return_value = [(0, 0.9), (1, 0.7)]

    result = retrieval.run("q", "ai_act", "es", top_k=2)

    assert len(result) == 2
    assert isinstance(result[0], RetrievedChunk)
    assert result[0].chunk_id == "ai_act.6.1.es"
    assert result[0].score == 0.9
    assert result[0].version == "32024R1689"
    assert result[0].source_url == "https://example.com"
    assert result[1].chunk_id == "ai_act.7.es"
    assert result[1].score == 0.7


def test_run_top_k_default_is_5(_patch_dependencies: dict[str, MagicMock]) -> None:
    _patch_dependencies["connect"].return_value = _make_chain([])
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("q", "ai_act", "es")  # no top_k

    rerank_kwargs = _patch_dependencies["rerank"].call_args.kwargs
    assert rerank_kwargs["top_n"] == 5
