"""Pydantic v2 schemas for H3: Citation, AuditResult, RetrievedChunk, Context, FetchedArticle.

Defer Finding and Answer to H4 (decisions log 2026-05-05 entry "Schemas Pydantic en H3").
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from regulaitor.corpus.schemas import CorpusSelector, Language, Norma


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
    corpus: CorpusSelector
    language: Language
    chunks: list[RetrievedChunk]
    retrieved_at: datetime
    embedding_model: str
    resolved_normas: list[Norma] = Field(default_factory=list)


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
    # v0.1.21 (ADR-0027 D3, Capa B): server-side defense-in-depth.
    # `findings=[]` is now invalid at the schema layer; the Analyst's
    # Capa C retry loop catches the resulting ValidationError and
    # re-prompts Sonnet with failure-specific feedback. Capa A
    # (Anthropic strict mode + minItems) is the API-level guarantee
    # upstream; Capa B is the post-API defense.
    findings: list[Finding] = Field(min_length=1)


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


class JudgeVote(BaseModel):
    """One Council judge's vote (H13). Frozen; immutable evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    vote: AuditVerdict
    reason: str
    ok: bool
    error_category: str | None


class CouncilReview(BaseModel):
    """Aggregated Council outcome (H13). Advisory: never mutates the verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    triggered: bool
    trigger_reason: Literal["auditor_rhr", "high_severity", "api_override", "not_triggered"]
    judges: list[JudgeVote]
    council_verdict: AuditVerdict
    agreement: Literal["unanimous", "majority", "split", "degraded"]
    diverges_from_auditor: bool
    reason: str

    @model_validator(mode="after")
    def _triggered_matches_reason(self) -> CouncilReview:
        if self.triggered != (self.trigger_reason != "not_triggered"):
            raise ValueError("triggered must equal (trigger_reason != 'not_triggered')")
        return self


# ---------------------------------------------------------------------------
# H5 — Document pipeline schemas
# ---------------------------------------------------------------------------


class FontInfo(BaseModel):
    """Font metadata captured per text run for invisible-text heuristics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    size_pt: float
    color_hex: str
    is_visible_estimated: bool


class Page(BaseModel):
    """One page of an extracted document; pre-sanitization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int
    text: str
    fonts: list[FontInfo]
    annotations: list[str]
    hidden_text_candidates: list[str]
    likely_scanned: bool


class Attachment(BaseModel):
    """Embedded file declared inside the document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    mime: str
    size_bytes: int
    hash: str


class OutlineEntry(BaseModel):
    """One bookmark / outline entry, used by the segmenter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    level: int
    page_number: int


class RawDocument(BaseModel):
    """Output of extractor.extract; pre-sanitization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_hash: str
    mime_type: Literal["application/pdf", "text/markdown"]
    language: Language
    pages: list[Page]
    metadata: dict[str, str]
    attachments: list[Attachment]
    outline: list[OutlineEntry] | None
    has_javascript: bool
    has_form_actions: bool
    uri_actions: list[str]


class SanitizerEvent(BaseModel):
    """One audit-trail entry recording a sanitizer decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["info", "warning", "critical"]
    category: Literal[
        "metadata_stripped",
        "annotation_stripped",
        "invisible_text_stripped",
        "javascript_blocked",
        "attachment_blocked",
        "form_action_blocked",
        "uri_action_blocked",
        "hidden_layer_stripped",
        "unicode_trick_stripped",
        "encrypted_with_password",
        "outline_extracted",
        "large_document_warning",
    ]
    location: str
    content_hash: str  # sha256[:12]; never plain text (CLAUDE.md §18.8)
    reason: str


class SanitizedDocument(BaseModel):
    """Output of sanitizer.sanitize; safe to pass to segmenter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_hash: str
    language: Language
    clean_text: str = Field(min_length=50)
    outline: list[OutlineEntry] | None
    sanitizer_log: list[SanitizerEvent]


class Segment(BaseModel):
    """One unit of analysis produced by segmenter.segment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int = Field(ge=1)
    title: str | None
    text: str = Field(min_length=1)
    token_count: int = Field(ge=1)
    is_continuation: bool


class SegmentResult(BaseModel):
    """Per-segment outcome wrapping AuditedAnswer or skip reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    segment: Segment
    skipped: bool
    skip_reason: str | None
    audited_answer: AuditedAnswer | None
    latency_ms: int = Field(ge=0)
    cost_eur: float = Field(ge=0)


class DocumentReport(BaseModel):
    """End-to-end output of orchestration.document_graph.run_document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    document_hash: str
    language: Language
    corpus: list[str]
    sanitizer_log: list[SanitizerEvent]
    segments: list[SegmentResult]
    document_verdict: AuditVerdict
    document_reason: str | None
    n_segments_total: int = Field(ge=0)
    n_segments_blocked_by_injection: int = Field(ge=0)
    n_segments_pass: int = Field(ge=0)
    n_segments_block: int = Field(ge=0)
    n_segments_review: int = Field(ge=0)
    latency_ms_total: int = Field(ge=0)
    cost_eur_total: float = Field(ge=0)


class DocumentBlockedError(Exception):
    """Raised by sanitizer when a critical-block category is hit.

    Carries the partial sanitizer_log so the caller can build a
    DocumentReport with verdict=REQUIRES_HUMAN_REVIEW and segments=[].
    """

    def __init__(self, reason: str, sanitizer_log: list[SanitizerEvent]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.sanitizer_log = sanitizer_log
