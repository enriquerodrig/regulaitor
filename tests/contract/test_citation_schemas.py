"""Hypothesis round-trip contract tests for citation schemas (H3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    Context,
    FetchedArticle,
    RetrievedChunk,
)

pytestmark = pytest.mark.contract


_NORMA = st.sampled_from(["ai_act", "gdpr", "nis2", "dora"])
_LANG = st.sampled_from(["es", "en"])
_NON_EMPTY = st.text(min_size=1, max_size=200)


@given(
    norma=_NORMA,
    articulo=_NON_EMPTY,
    apartado=st.one_of(st.none(), _NON_EMPTY),
    language=_LANG,
    text=_NON_EMPTY,
)
@settings(max_examples=50)
def test_citation_round_trip(
    norma: str, articulo: str, apartado: str | None, language: str, text: str
) -> None:
    c = Citation(
        norma=norma,  # type: ignore[arg-type]
        articulo=articulo,
        apartado=apartado,
        language=language,  # type: ignore[arg-type]
        text=text,
    )
    parsed = Citation.model_validate_json(c.model_dump_json())
    assert parsed == c


@given(
    chunk_id=_NON_EMPTY,
    norma=_NORMA,
    articulo=_NON_EMPTY,
    apartado=st.one_of(st.none(), _NON_EMPTY),
    language=_LANG,
    text=_NON_EMPTY,
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    version=_NON_EMPTY,
    source_url=_NON_EMPTY,
)
@settings(max_examples=50)
def test_retrieved_chunk_round_trip(
    chunk_id: str,
    norma: str,
    articulo: str,
    apartado: str | None,
    language: str,
    text: str,
    score: float,
    version: str,
    source_url: str,
) -> None:
    rc = RetrievedChunk(
        chunk_id=chunk_id,
        norma=norma,  # type: ignore[arg-type]
        articulo=articulo,
        apartado=apartado,
        language=language,  # type: ignore[arg-type]
        text=text,
        score=score,
        version=version,
        source_url=source_url,
    )
    parsed = RetrievedChunk.model_validate_json(rc.model_dump_json())
    assert parsed == rc


def test_audit_result_round_trip_minimal() -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    r = AuditResult(
        citation=c,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    parsed = AuditResult.model_validate_json(r.model_dump_json())
    assert parsed == r


def test_context_round_trip_minimal() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="t",
        score=0.5,
        version="v",
        source_url="https://example.com",
    )
    ctx = Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[rc],
        retrieved_at=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
        embedding_model="BAAI/bge-m3",
    )
    parsed = Context.model_validate_json(ctx.model_dump_json())
    assert parsed == ctx


def test_fetched_article_round_trip_minimal() -> None:
    fa = FetchedArticle(
        norma="ai_act",
        articulo="6",
        apartado=None,
        language="es",
        text="text",
        version="v",
        source_url="https://example.com",
    )
    parsed = FetchedArticle.model_validate_json(fa.model_dump_json())
    assert parsed == fa
