"""Pydantic v2 schemas for H3: Citation, AuditResult, RetrievedChunk, Context, FetchedArticle.

Defer Finding and Answer to H4 (decisions log 2026-05-05 entry "Schemas Pydantic en H3").
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

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


class Finding(BaseModel):
    """One assertion within an Answer; >=1 Citation required (H4 schema for Analyst output).

    Frozen and immutable. Per the lean Auditor (decisions log 2026-05-05 entry
    "Auditor lean en H4"), Field(min_length=1) on citations enforces "no Finding
    without citation" at schema level.
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)
    severity: Literal["info", "low", "medium", "high"] = "info"


class Answer(BaseModel):
    """Analyst output: human-readable summary + structured findings (H4).

    Frozen. The Auditor wraps this in AuditedAnswer; Answer itself is never mutated.
    `query` and `language` echo the input for downstream invariant checks.
    """

    model_config = ConfigDict(frozen=True)

    query: str
    language: Language
    text: str = Field(min_length=1)
    findings: list[Finding]


class AuditVerdict(StrEnum):
    """Three-state verdict for the Lenient-strict aggregation policy (H4)."""

    PASS = "pass"  # nosec B105 -- enum value, not a password
    BLOCK = "block"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AuditedAnswer(BaseModel):
    """Auditor wrapper composed over the immutable Analyst Answer (H4).

    Carries per-citation audit_results and an aggregated verdict + reason.
    """

    answer: Answer
    verdict: AuditVerdict
    audit_results: list[AuditResult]
    reason: str | None
