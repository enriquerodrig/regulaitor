"""Unit tests for citation/schemas.py — Pydantic v2 contracts for H3."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    Context,
    FetchedArticle,
    RetrievedChunk,
)


def test_citation_minimum_valid() -> None:
    c = Citation(norma="ai_act", articulo="6", language="es", text="some text")
    assert c.apartado is None


def test_citation_with_apartado() -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    assert c.apartado == "1"


def test_citation_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        Citation(norma="ai_act", articulo="6", language="es", text="")


def test_citation_rejects_empty_articulo() -> None:
    with pytest.raises(ValidationError):
        Citation(norma="ai_act", articulo="", language="es", text="text")


def test_citation_is_frozen() -> None:
    c = Citation(norma="ai_act", articulo="6", language="es", text="text")
    with pytest.raises(ValidationError):
        c.text = "other"  # type: ignore[misc]


def test_audit_result_validated_true() -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    r = AuditResult(
        citation=c,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    assert r.validated is True


def test_audit_result_validated_false_with_reason() -> None:
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = AuditResult(
        citation=c,
        validated=False,
        article_exists=False,
        apartado_exists=None,
        text_normalized_match=False,
        reason="article_not_found: ai_act has no articulo 999",
    )
    assert r.reason is not None


def test_retrieved_chunk_score_in_range() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.95,
        version="32024R1689",
        source_url="https://eur-lex.europa.eu/...",
    )
    assert rc.score == 0.95


def test_retrieved_chunk_rejects_score_above_one() -> None:
    with pytest.raises(ValidationError):
        RetrievedChunk(
            chunk_id="ai_act.6.1.es",
            norma="ai_act",
            articulo="6",
            apartado="1",
            language="es",
            text="text",
            score=1.5,
            version="32024R1689",
            source_url="https://example.com",
        )


def test_retrieved_chunk_is_frozen() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.5,
        version="v",
        source_url="https://example.com",
    )
    with pytest.raises(ValidationError):
        rc.text = "other"  # type: ignore[misc]


def test_context_holds_chunks_with_metadata() -> None:
    rc = RetrievedChunk(
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
    ctx = Context(
        query="alto riesgo",
        corpus="ai_act",
        language="es",
        chunks=[rc],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3",
    )
    assert ctx.query == "alto riesgo"
    assert len(ctx.chunks) == 1


def test_fetched_article_apartado_optional() -> None:
    fa = FetchedArticle(
        norma="ai_act",
        articulo="6",
        apartado=None,
        language="es",
        text="full article text",
        version="v",
        source_url="https://example.com",
    )
    assert fa.apartado is None
