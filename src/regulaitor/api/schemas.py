"""H7 — DTOs + converters for the FastAPI surface.

These DTOs explicitly allowlist what gets exposed to API clients. Backend
schemas (ChatState, DocumentReport, etc.) carry internal fields that must
never leak (pattern_name, skip_reason, injection_reason, sanitizer location).
The converters below redact those fields by construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    Citation,
    DocumentReport,
    Finding,
    SanitizerEvent,
    SegmentResult,
)
from regulaitor.orchestration.state import ChatState

# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """Body for POST /ask.

    Mutable (no frozen=True) because FastAPI mutates request models during
    validation. Response/data DTOs are frozen.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    corpus: Literal["ai_act", "gdpr"]
    language: Literal["es", "en"]


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class CitationDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    norma: str
    articulo: str
    apartado: str | None
    language: str
    text: str


class AuditResultDTO(BaseModel):
    """Subset of AuditResult: validated + 3 sub-flags + reason. No internal Citation echo."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    citation: CitationDTO
    validated: bool
    article_exists: bool
    apartado_exists: bool | None
    text_normalized_match: bool
    reason: str | None


class FindingDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    citations: list[CitationDTO]
    severity: Literal["info", "low", "medium", "high"]


class AnswerDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    findings: list[FindingDTO]


class AskResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    verdict: Literal["pass", "block", "requires_human_review"]
    answer: AnswerDTO
    audit_results: list[AuditResultDTO]
    reason: str | None
    response_time_ms: int = Field(ge=0)


SanitizerCategory = Literal[
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


class SanitizerEventDTO(BaseModel):
    """Subset of SanitizerEvent. Excludes location and raw reason (SSDLC redaction)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    severity: Literal["info", "warning", "critical"]
    category: SanitizerCategory
    content_hash: str


class SegmentResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    segment_id: int
    title: str | None
    skipped: bool
    skip_category: Literal["clean", "injection_blocked", "internal_error"]
    answer: AnswerDTO | None
    verdict: Literal["pass", "block", "requires_human_review"] | None
    audit_results: list[AuditResultDTO]
    latency_ms: int = Field(ge=0)
    cost_eur: float = Field(ge=0)


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    document_verdict: Literal["pass", "block", "requires_human_review"]
    document_reason: str | None
    n_segments_total: int = Field(ge=0)
    n_segments_pass: int = Field(ge=0)
    n_segments_block: int = Field(ge=0)
    n_segments_review: int = Field(ge=0)
    n_segments_blocked_by_injection: int = Field(ge=0)
    sanitizer_log: list[SanitizerEventDTO]
    segments: list[SegmentResultDTO]
    latency_ms_total: int = Field(ge=0)
    cost_eur_total: float = Field(ge=0)
    response_time_ms: int = Field(ge=0)


class HealthCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    status: Literal["ok", "present", "missing", "unreachable", "degraded"]
    detail: str | None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["ok", "degraded"]
    version: str
    checks: list[HealthCheck]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    error_code: str
    message: str
    case_id: str | None


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------


def _to_citation_dto(c: Citation) -> CitationDTO:
    return CitationDTO(
        norma=str(c.norma),
        articulo=c.articulo,
        apartado=c.apartado,
        language=str(c.language),
        text=c.text,
    )


def _to_audit_result_dto(r: AuditResult) -> AuditResultDTO:
    return AuditResultDTO(
        citation=_to_citation_dto(r.citation),
        validated=r.validated,
        article_exists=r.article_exists,
        apartado_exists=r.apartado_exists,
        text_normalized_match=r.text_normalized_match,
        reason=r.reason,
    )


def _to_finding_dto(f: Finding) -> FindingDTO:
    return FindingDTO(
        text=f.text,
        citations=[_to_citation_dto(c) for c in f.citations],
        severity=f.severity,
    )


def _to_answer_dto(a: Answer) -> AnswerDTO:
    return AnswerDTO(
        text=a.text,
        findings=[_to_finding_dto(f) for f in a.findings],
    )


def _to_sanitizer_event_dto(e: SanitizerEvent) -> SanitizerEventDTO:
    """SSDLC: location and reason are NOT propagated."""
    return SanitizerEventDTO(
        severity=e.severity,
        category=e.category,
        content_hash=e.content_hash,
    )


def _classify_skip_category(
    seg_result: SegmentResult,
) -> Literal["clean", "injection_blocked", "internal_error"]:
    """Map skip_reason to coarse category. SSDLC: NEVER expose raw reason."""
    if not seg_result.skipped:
        return "clean"
    reason = (seg_result.skip_reason or "").lower()
    if "injection" in reason:
        return "injection_blocked"
    return "internal_error"


def _segment_result_to_dto(seg_result: SegmentResult) -> SegmentResultDTO:
    audited: AuditedAnswer | None = seg_result.audited_answer
    answer_dto: AnswerDTO | None = None
    audit_dtos: list[AuditResultDTO] = []
    verdict: Literal["pass", "block", "requires_human_review"] | None = None
    if audited is not None:
        answer_dto = _to_answer_dto(audited.answer)
        audit_dtos = [_to_audit_result_dto(r) for r in audited.audit_results]
        verdict = audited.verdict.value  # type: ignore[assignment]
    return SegmentResultDTO(
        segment_id=seg_result.segment.id,
        title=seg_result.segment.title,
        skipped=seg_result.skipped,
        skip_category=_classify_skip_category(seg_result),
        answer=answer_dto,
        verdict=verdict,
        audit_results=audit_dtos,
        latency_ms=seg_result.latency_ms,
        cost_eur=seg_result.cost_eur,
    )


def to_ask_response(state: ChatState, response_time_ms: int) -> AskResponse:
    """Translate ChatState (with audited_answer set) to public AskResponse.

    Caller MUST handle injection_blocked and errors states BEFORE calling this:
    InjectionDetected and BackendError exceptions are raised in the route, not here.
    """
    audited = state.audited_answer
    if audited is None:
        raise ValueError("to_ask_response requires state.audited_answer to be set")
    return AskResponse(
        case_id=state.case_id,
        verdict=audited.verdict.value,  # type: ignore[arg-type]
        answer=_to_answer_dto(audited.answer),
        audit_results=[_to_audit_result_dto(r) for r in audited.audit_results],
        reason=audited.reason,
        response_time_ms=response_time_ms,
    )


def to_analyze_response(report: DocumentReport, response_time_ms: int) -> AnalyzeResponse:
    """Translate DocumentReport to public AnalyzeResponse with SSDLC redaction.

    SSDLC redaction applied:
    - Per-segment skip_reason -> coarse skip_category (never raw)
    - SanitizerEvent.location and reason -> dropped (never serialized)
    """
    return AnalyzeResponse(
        case_id=report.case_id,
        document_verdict=report.document_verdict.value,  # type: ignore[arg-type]
        document_reason=report.document_reason,
        n_segments_total=report.n_segments_total,
        n_segments_pass=report.n_segments_pass,
        n_segments_block=report.n_segments_block,
        n_segments_review=report.n_segments_review,
        n_segments_blocked_by_injection=report.n_segments_blocked_by_injection,
        sanitizer_log=[_to_sanitizer_event_dto(e) for e in report.sanitizer_log],
        segments=[_segment_result_to_dto(s) for s in report.segments],
        latency_ms_total=report.latency_ms_total,
        cost_eur_total=report.cost_eur_total,
        response_time_ms=response_time_ms,
    )
