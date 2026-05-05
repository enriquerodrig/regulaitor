"""Unit tests for mcp_server/tools.py — 3 adapters + error mapping."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    FetchedArticle,
    RetrievedChunk,
)
from regulaitor.mcp_server import tools
from regulaitor.mcp_server.errors import NotFoundError


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.9,
        version="v",
        source_url="https://example.com",
    )


def test_search_articles_delegates_to_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _make_chunk()
    run_mock = MagicMock(return_value=[chunk])
    monkeypatch.setattr(tools.rag_retrieval, "run", run_mock)

    result = tools.search_articles(query="q", corpus="ai_act", language="es", top_k=3)

    run_mock.assert_called_once_with("q", "ai_act", "es", top_k=3)
    assert result == [chunk]


def test_search_articles_returns_empty_on_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools.rag_retrieval, "run", MagicMock(return_value=[]))

    result = tools.search_articles(query="q", corpus="ai_act", language="es")

    assert result == []


def test_fetch_article_with_apartado(monkeypatch: pytest.MonkeyPatch) -> None:
    paragraph_mock = MagicMock(return_value="apartado text")
    meta_mock = MagicMock(
        return_value={"version": "32024R1689", "source_url": "https://example.com"}
    )
    monkeypatch.setattr(tools.loader, "get_paragraph", paragraph_mock)
    monkeypatch.setattr(tools.loader, "get_manifest_meta", meta_mock)

    fa = tools.fetch_article(norma="ai_act", articulo="6", language="es", apartado="1")

    assert isinstance(fa, FetchedArticle)
    assert fa.text == "apartado text"
    assert fa.apartado == "1"
    assert fa.version == "32024R1689"


def test_fetch_article_without_apartado(monkeypatch: pytest.MonkeyPatch) -> None:
    article_text_mock = MagicMock(return_value="full article text")
    meta_mock = MagicMock(return_value={"version": "v", "source_url": "https://example.com"})
    monkeypatch.setattr(tools.loader, "get_article_text", article_text_mock)
    monkeypatch.setattr(tools.loader, "get_manifest_meta", meta_mock)

    fa = tools.fetch_article(norma="ai_act", articulo="6", language="es")

    assert fa.apartado is None
    assert fa.text == "full article text"


def test_fetch_article_apartado_missing_raises_notfound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paragraph_mock = MagicMock(side_effect=KeyError("no apartado 99"))
    monkeypatch.setattr(tools.loader, "get_paragraph", paragraph_mock)

    with pytest.raises(NotFoundError, match="apartado"):
        tools.fetch_article(norma="ai_act", articulo="6", language="es", apartado="99")


def test_fetch_article_article_missing_raises_notfound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools.loader,
        "get_article_text",
        MagicMock(side_effect=KeyError("no article 999")),
    )

    with pytest.raises(NotFoundError, match="article"):
        tools.fetch_article(norma="ai_act", articulo="999", language="es")


def test_validate_citation_returns_audit_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    expected = AuditResult(
        citation=c,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    validate_mock = MagicMock(return_value=expected)
    monkeypatch.setattr(tools.validator_mod, "validate", validate_mock)

    result = tools.validate_citation(c)

    assert result == expected
    validate_mock.assert_called_once_with(c)
