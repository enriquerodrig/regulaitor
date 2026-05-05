"""Pydantic v2 schemas for H3: Citation, AuditResult, RetrievedChunk, Context, FetchedArticle.

Defer Finding and Answer to H4 (decisions log 2026-05-05 entry "Schemas Pydantic en H3").
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from regulaitor.corpus.schemas import Language, Norma


class Citation(BaseModel):
    """A claim that a piece of text exists in a specific corpus location."""

    model_config = ConfigDict(frozen=True)

    norma: Norma
    articulo: str = Field(min_length=1)
    apartado: str | None = None
    language: Language
    text: str = Field(min_length=1)


class AuditResult(BaseModel):
    """Output of citation/validator.validate(). Three independent diagnostics + verdict."""

    citation: Citation
    validated: bool
    article_exists: bool
    apartado_exists: bool | None
    text_normalized_match: bool
    reason: str | None


class RetrievedChunk(BaseModel):
    """One result of rag/retrieval.run(). Citable in one MCP call (carries version + url)."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    norma: Norma
    articulo: str
    apartado: str | None
    language: Language
    text: str
    score: float = Field(ge=0.0, le=1.0)
    version: str
    source_url: str


class Context(BaseModel):
    """Wrapper produced by RetrieverAgent for downstream H4 LangGraph state."""

    query: str
    corpus: Norma
    language: Language
    chunks: list[RetrievedChunk]
    retrieved_at: datetime
    embedding_model: str


class FetchedArticle(BaseModel):
    """Output of fetch_article MCP tool. Text + minimal documentary metadata."""

    norma: Norma
    articulo: str
    apartado: str | None
    language: Language
    text: str
    version: str
    source_url: str
