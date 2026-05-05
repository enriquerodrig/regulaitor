"""Pydantic v2 schemas for the corpus pipeline.

Schemas are stable for H1; H2 extends them by populating `LanguageEntry.chunks`
and `LanguageEntry.embedded_at` rather than adding new fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Norma = Literal["ai_act", "gdpr", "nis2", "dora"]
Language = Literal["es", "en"]
SourceFormat = Literal["formex4", "html", "pdf"]


class HttpCacheEntry(BaseModel):
    """Conditional-request hints captured per (corpus, language) on the last fetch."""

    etag: str | None = None
    last_modified: str | None = None  # raw HTTP date string (RFC 7231)


class LanguageEntry(BaseModel):
    """Per-language metadata for one article. H2 fills `chunks`, `embedded_at`,
    and `embedding_model`. The latter records which model produced the vectors,
    enabling automatic invalidation when the model is upgraded."""

    hash: str  # "sha256:<hex>" — SHA256 of the raw article text
    tokens: int
    chunks: list[str] = Field(default_factory=list)
    embedded_at: datetime | None = None
    embedding_model: str | None = None  # e.g. "BAAI/bge-m3@<sha256>"
    fetched_at: datetime
    # plain str (not HttpUrl): URLs are built internally by eurlex.py;
    # exact-match is required for HTTP cache headers (If-Modified-Since / ETag).
    source_url: str


class ArticleEntry(BaseModel):
    """One article across all available languages."""

    article_id: str  # e.g. "ai_act.6"
    articulo: str
    title_es: str | None = None
    title_en: str | None = None
    languages: dict[Language, LanguageEntry]

    @field_validator("languages")
    @classmethod
    def _at_least_one_language(
        cls, v: dict[Language, LanguageEntry]
    ) -> dict[Language, LanguageEntry]:
        if not v:
            raise ValueError("at least one language entry required")
        return v


class Stats(BaseModel):
    """Per-manifest counters used for diagnostics and the decisions log."""

    articles_total: int
    chunks_total: int = 0
    embedded_total: int = 0
    raw_size_bytes: int


class Manifest(BaseModel):
    """Top-level manifest written to corpus/manifests/<corpus>.json."""

    corpus: Norma
    celex: str
    version: str  # consolidation date YYYY-MM-DD
    source_format: SourceFormat
    fetched_at: datetime
    languages: list[Language]
    http_cache: dict[Language, HttpCacheEntry]
    stats: Stats
    articles: list[ArticleEntry]
