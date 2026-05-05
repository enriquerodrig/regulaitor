"""Unit tests for rag.chunking. Stubs token_count to avoid loading BGE-M3."""

from __future__ import annotations

import pytest

from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph
from regulaitor.rag import chunking


@pytest.fixture(autouse=True)
def stub_token_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make token_count count whitespace-split words for predictable tests."""
    monkeypatch.setattr(
        chunking.embeddings,
        "token_count",
        lambda text: len(text.split()),
    )


def _article(
    articulo: str = "1",
    paragraphs: list[ParsedParagraph] | None = None,
    title: str | None = "Title",
    text: str = "x",
) -> ParsedArticle:
    return ParsedArticle(
        articulo=articulo,
        title=title,
        text=text,
        paragraphs=paragraphs or [],
    )


def _kwargs() -> dict:
    return {
        "norma": "ai_act",
        "language": "es",
        "celex": "32024R1689",
        "version": "2024-07-12",
        "source_format": "pdf",
        "source_url": "file:///x",
        "hash": "sha256:abc",
    }


def test_normalize_lowercases_and_strips_accents() -> None:
    out = chunking._normalize("ÁRTICULO Único — La normativa, dice:  Esto.")
    assert "á" not in out
    assert "ó" not in out  # but "Único" -> "unico", checking accent strip
    assert "ARTICULO" not in out
    assert "  " not in out  # whitespace collapsed


def test_normalize_unifies_typographic_dashes() -> None:
    """Per spec §12.2, all dash variants collapse to ASCII '-' so quotes from
    the PDF (which often use em-dash) match the corpus."""
    assert chunking._normalize("artículo 1—del") == "articulo 1-del"  # em-dash
    assert chunking._normalize("artículo 1–del") == "articulo 1-del"  # en-dash
    assert chunking._normalize("artículo 1−del") == "articulo 1-del"  # minus
    assert chunking._normalize("artículo 1―del") == "articulo 1-del"  # horizontal bar
    # ASCII hyphen passes through unchanged
    assert chunking._normalize("artículo 1-del") == "articulo 1-del"


def test_short_article_yields_single_chunk() -> None:
    article = _article(text="palabra " * 100)  # 100 tokens, well below 1000
    chunks = chunking.chunk_article(article, **_kwargs())
    assert len(chunks) == 1
    assert chunks[0].apartado is None
    assert chunks[0].chunk_id == "ai_act.1.es"
    assert chunks[0].article_id == "ai_act.1"


def test_long_article_with_paragraphs_splits_by_apartado() -> None:
    paragraphs = [
        ParsedParagraph(apartado="1", text="palabra " * 200),  # 200 tokens
        ParsedParagraph(apartado="2", text="palabra " * 600),  # 600 tokens
        ParsedParagraph(apartado="3", text="palabra " * 400),  # 400 tokens
    ]
    article = _article(text="palabra " * 1200, paragraphs=paragraphs)  # full > 1000
    chunks = chunking.chunk_article(article, **_kwargs())
    assert len(chunks) == 3
    assert [c.apartado for c in chunks] == ["1", "2", "3"]
    assert [c.chunk_id for c in chunks] == [
        "ai_act.1.1.es",
        "ai_act.1.2.es",
        "ai_act.1.3.es",
    ]
    # token_count is computed per-apartado, not the article-level total
    assert chunks[0].token_count == 200
    assert chunks[1].token_count == 600
    assert chunks[2].token_count == 400


def test_long_article_without_paragraphs_yields_single_chunk_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If an article exceeds threshold but has no PARAG structure, we cannot
    split it. We emit a single oversized chunk and log a warning."""
    import logging

    caplog.set_level(logging.WARNING, logger="regulaitor.rag.chunking")
    article = _article(text="palabra " * 1500, paragraphs=[])
    chunks = chunking.chunk_article(article, **_kwargs())
    assert len(chunks) == 1
    assert chunks[0].apartado is None
    # Verify the warning actually fired
    assert any("exceeds threshold" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "WARNING" for rec in caplog.records)


def test_chunk_token_count_matches_text() -> None:
    article = _article(text="alpha beta gamma delta")
    chunks = chunking.chunk_article(article, **_kwargs())
    assert chunks[0].token_count == 4


def test_chunk_text_normalized_strips_accents() -> None:
    article = _article(text="Éste es el TEXTO con ácidos.")
    chunks = chunking.chunk_article(article, **_kwargs())
    assert chunks[0].text_normalized == "este es el texto con acidos."


def test_chunk_carries_metadata_from_kwargs() -> None:
    article = _article(text="x")
    chunks = chunking.chunk_article(article, **_kwargs())
    assert chunks[0].celex == "32024R1689"
    assert chunks[0].version == "2024-07-12"
    assert chunks[0].source_format == "pdf"
    assert chunks[0].hash == "sha256:abc"


def test_threshold_constant_is_1000() -> None:
    assert chunking.THRESHOLD_TOKENS == 1000
