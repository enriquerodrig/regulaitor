"""Unit tests for corpus.schemas: construction, validation, serialization."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulaitor.corpus.schemas import (
    ArticleEntry,
    HttpCacheEntry,
    LanguageEntry,
    Manifest,
    Stats,
)


def _now() -> datetime:
    return datetime(2026, 4, 30, 18, 42, 13, tzinfo=UTC)


def test_language_entry_minimal_construction() -> None:
    le = LanguageEntry(
        hash="sha256:abc",
        tokens=412,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32024R1689",
    )
    assert le.chunks == []
    assert le.embedded_at is None


def test_language_entry_round_trips() -> None:
    le = LanguageEntry(
        hash="sha256:abc",
        tokens=412,
        chunks=["ai_act.6.1.es", "ai_act.6.2.es"],
        embedded_at=_now(),
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32024R1689",
    )
    payload = le.model_dump_json()
    restored = LanguageEntry.model_validate_json(payload)
    assert restored == le


def test_article_entry_requires_at_least_one_language() -> None:
    with pytest.raises(ValidationError):
        ArticleEntry(article_id="ai_act.1", articulo="1", languages={})


def test_manifest_full_round_trip() -> None:
    le_es = LanguageEntry(
        hash="sha256:aa",
        tokens=100,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32024R1689",
    )
    le_en = LanguageEntry(
        hash="sha256:bb",
        tokens=95,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
    )
    article = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        title_es="Objeto",
        title_en="Subject matter",
        languages={"es": le_es, "en": le_en},
    )
    manifest = Manifest(
        corpus="ai_act",
        celex="32024R1689",
        version="2024-07-12",
        source_format="formex4",
        fetched_at=_now(),
        languages=["es", "en"],
        http_cache={
            "es": HttpCacheEntry(etag='W/"abc"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT"),
            "en": HttpCacheEntry(etag='W/"def"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT"),
        },
        stats=Stats(articles_total=1, raw_size_bytes=1024),
        articles=[article],
    )
    payload = manifest.model_dump_json()
    restored = Manifest.model_validate_json(payload)
    assert restored == manifest


def test_manifest_rejects_unknown_corpus() -> None:
    with pytest.raises(ValidationError):
        Manifest(
            corpus="random_law",  # type: ignore[arg-type]
            celex="X",
            version="2024-01-01",
            source_format="formex4",
            fetched_at=_now(),
            languages=["es"],
            http_cache={"es": HttpCacheEntry()},
            stats=Stats(articles_total=0, raw_size_bytes=0),
            articles=[],
        )


def test_http_cache_entry_all_fields_optional() -> None:
    assert HttpCacheEntry().etag is None
    assert HttpCacheEntry().last_modified is None


def test_language_entry_carries_embedding_model_field() -> None:
    """H2 adds embedding_model to track which model produced the vectors."""
    le = LanguageEntry(
        hash="sha256:abc",
        tokens=412,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/x",
        embedding_model="BAAI/bge-m3@v1.0",
    )
    assert le.embedding_model == "BAAI/bge-m3@v1.0"


def test_language_entry_embedding_model_defaults_to_none_for_h1_compat() -> None:
    """Manifests written by H1 (without this field) must still parse."""
    le = LanguageEntry(
        hash="sha256:abc",
        tokens=412,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/x",
    )
    assert le.embedding_model is None
