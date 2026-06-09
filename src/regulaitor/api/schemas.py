"""H7 — DTOs + converters for the FastAPI surface.

These DTOs explicitly allowlist what gets exposed to API clients. Backend
schemas (ChatState, DocumentReport, etc.) carry internal fields that must
never leak (pattern_name, skip_reason, injection_reason, sanitizer location).
The converters below redact those fields by construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    Citation,
    CouncilReview,
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
    corpus: Literal["ai_act", "gdpr", "nis2", "dora", "auto"]
    language: Literal["es", "en"]
    council: StrictBool | None = None


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


class JudgeVoteDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    model_id: str
    provider: str
    vote: Literal["pass", "block", "requires_human_review"]
    reason: str
    ok: bool
    error_category: str | None


class CouncilReviewDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    triggered: bool
    trigger_reason: Literal["auditor_rhr", "high_severity", "api_override", "not_triggered"]
    judges: list[JudgeVoteDTO]
    council_verdict: Literal["pass", "block", "requires_human_review"]
    agreement: Literal["unanimous", "majority", "split", "degraded"]
    diverges_from_auditor: bool
    reason: str


class AskResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    verdict: Literal["pass", "block", "requires_human_review"]
    answer: AnswerDTO
    audit_results: list[AuditResultDTO]
    reason: str | None
    response_time_ms: int = Field(ge=0)
    council_notice: str | None = None
    council: CouncilReviewDTO | None = None


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
        verdict = audited.verdict.value
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


# SSDLC: JudgeVote.reason and CouncilReview.reason are intentionally exposed as
# auditable Council evidence — this is the H13 advisory record (authenticated
# Bearer API, 500-char truncated upstream in T7, consistent with AuditResult.reason
# and AuditedAnswer.reason already exposed). These strings are LLM-judge rationale
# over corpus text, NOT user PII. If a non-UI / third-party API consumer is ever
# added, revisit whether redaction is appropriate.
def _council_review_to_dto(cr: CouncilReview) -> CouncilReviewDTO:
    return CouncilReviewDTO(
        triggered=cr.triggered,
        trigger_reason=cr.trigger_reason,
        judges=[
            JudgeVoteDTO(
                model_id=j.model_id,
                provider=j.provider,
                vote=j.vote.value,
                reason=j.reason,
                ok=j.ok,
                error_category=j.error_category,
            )
            for j in cr.judges
        ],
        council_verdict=cr.council_verdict.value,
        agreement=cr.agreement,
        diverges_from_auditor=cr.diverges_from_auditor,
        reason=cr.reason,
    )


def _council_notice(
    cr: CouncilReview | None,
    audited: AuditedAnswer | None = None,
) -> str | None:
    """User-facing notice when Council diverges from Auditor.

    v0.1.19 (ADR-0025): when ``audited.reason`` starts with ``"COUNCIL_BIND:"``,
    the Council binding fired and the verdict was promoted from PASS to
    requires_human_review. The notice reflects the promotion. Otherwise the
    legacy advisory notice is emitted (Council diverged but verdict unchanged).

    Backward-compat: callers may pass ``audited=None`` (v0.1.18 single-arg
    callers); in that case the legacy advisory notice is emitted.
    """
    if cr is None or not cr.diverges_from_auditor:
        return None
    # Council unavailable: no judge responded (e.g. no judge API keys in a fully
    # self-hosted / sovereign deploy where the US-hosted judges have no keys).
    # It did NOT diverge — it could not run. Suppress the misleading "judges
    # diverged" notice; the deterministic Auditor verdict stands on its own.
    if not any(j.ok for j in cr.judges):
        return None
    if (
        audited is not None
        and audited.reason is not None
        and audited.reason.startswith("COUNCIL_BIND:")
    ):
        return (
            "Hallazgo marcado por revisión colegiada (Council): los jueces "
            "independientes promovieron el veredicto a requires_human_review "
            "por unanimidad. Se recomienda revisión humana."
        )
    return (
        "Hallazgo marcado por revisión colegiada (Council): los jueces "
        "independientes discreparon de la validación automática. El veredicto "
        "no cambia; se recomienda revisión humana."
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
        verdict=audited.verdict.value,
        answer=_to_answer_dto(audited.answer),
        audit_results=[_to_audit_result_dto(r) for r in audited.audit_results],
        reason=audited.reason,
        response_time_ms=response_time_ms,
        council_notice=_council_notice(state.council_review, state.audited_answer),
        council=(
            _council_review_to_dto(state.council_review)
            if state.council_review is not None
            else None
        ),
    )


def to_analyze_response(report: DocumentReport, response_time_ms: int) -> AnalyzeResponse:
    """Translate DocumentReport to public AnalyzeResponse with SSDLC redaction.

    SSDLC redaction applied:
    - Per-segment skip_reason -> coarse skip_category (never raw)
    - SanitizerEvent.location and reason -> dropped (never serialized)
    """
    return AnalyzeResponse(
        case_id=report.case_id,
        document_verdict=report.document_verdict.value,
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
