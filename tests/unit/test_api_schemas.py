"""Unit tests for api.schemas — DTOs + converters with SSDLC redaction."""

from regulaitor.api.schemas import (
    # smoke imports: ensure the public types are exposed by the schemas module.
    AnalyzeResponse,  # noqa: F401
    AskRequest,
    AskResponse,  # noqa: F401
    ErrorResponse,
    HealthCheck,  # noqa: F401
    HealthResponse,
    to_analyze_response,
    to_ask_response,
)
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    DocumentReport,
    Finding,
    SanitizerEvent,
    Segment,
    SegmentResult,
)
from regulaitor.orchestration.state import ChatState


def _make_chat_state(*, blocked: bool = False) -> ChatState:
    citation = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="Los sistemas de alto riesgo...",
    )
    finding = Finding(text="Requiere evaluación", citations=[citation], severity="info")
    answer = Answer(
        query="¿Qué dice el AI Act?",
        language="es",
        text="El AI Act regula...",
        findings=[finding],
    )
    audit = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    audited = AuditedAnswer(
        answer=answer,
        verdict=AuditVerdict.PASS,
        audit_results=[audit],
        reason=None,
    )
    return ChatState(
        case_id="api-ch-20260508-abc12345",
        query="¿Qué dice el AI Act?",
        corpus="ai_act",
        language="es",
        answer=answer,
        audited_answer=audited,
        injection_blocked=blocked,
        injection_reason="injection_pattern_X" if blocked else None,
    )


def test_ask_request_validates_query_length() -> None:
    AskRequest(query="x", corpus="ai_act", language="es")  # min OK
    AskRequest(query="x" * 2000, corpus="ai_act", language="es")  # max OK


def test_ask_request_rejects_empty_query() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AskRequest(query="", corpus="ai_act", language="es")


def test_ask_request_rejects_oversize_query() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AskRequest(query="x" * 2001, corpus="ai_act", language="es")


def test_ask_request_rejects_unknown_corpus() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AskRequest(query="hi", corpus="nis2", language="es")  # type: ignore[arg-type]


def test_ask_request_rejects_unknown_language() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AskRequest(query="hi", corpus="ai_act", language="fr")  # type: ignore[arg-type]


def test_to_ask_response_translates_pass_state() -> None:
    state = _make_chat_state(blocked=False)
    response = to_ask_response(state, response_time_ms=1234)
    assert response.case_id == state.case_id
    assert response.verdict == "pass"
    assert state.audited_answer is not None
    assert response.answer.text == state.audited_answer.answer.text
    assert len(response.audit_results) == 1
    assert response.response_time_ms == 1234


def test_to_ask_response_does_not_leak_injection_reason() -> None:
    """SSDLC: injection_reason from ChatState must NEVER appear in serialized response."""
    state = _make_chat_state(blocked=False)
    response = to_ask_response(state, response_time_ms=0)
    serialized = response.model_dump_json()
    assert "injection_pattern_X" not in serialized
    assert "injection_reason" not in serialized


def test_to_ask_response_raises_if_audited_answer_is_none() -> None:
    """Defensive: caller must handle injection_blocked/errors before calling converter."""
    import pytest

    state = ChatState(
        case_id="api-ch-x",
        query="q",
        corpus="ai_act",
        language="es",
    )
    assert state.audited_answer is None
    with pytest.raises(ValueError, match="audited_answer"):
        to_ask_response(state, response_time_ms=0)


def _make_document_report(*, with_skip: bool = False) -> DocumentReport:
    citation = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="Los sistemas de alto riesgo...",
    )
    finding = Finding(text="Requiere evaluación", citations=[citation], severity="info")
    answer = Answer(
        query="(segment)",
        language="es",
        text="El segmento dice...",
        findings=[finding],
    )
    audit = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    audited = AuditedAnswer(
        answer=answer,
        verdict=AuditVerdict.PASS,
        audit_results=[audit],
        reason=None,
    )
    seg = Segment(
        id=1,
        title="Sec 1",
        text="Texto del segmento.",
        token_count=10,
        is_continuation=False,
    )
    if with_skip:
        seg_result = SegmentResult(
            segment=seg,
            skipped=True,
            skip_reason="injection_pattern_X",
            audited_answer=None,
            latency_ms=5,
            cost_eur=0.0,
        )
    else:
        seg_result = SegmentResult(
            segment=seg,
            skipped=False,
            skip_reason=None,
            audited_answer=audited,
            latency_ms=120,
            cost_eur=0.001,
        )
    sanitizer_event = SanitizerEvent(
        severity="info",
        category="metadata_stripped",
        location="page 1 / metadata.author",
        content_hash="a1b2c3d4e5f6",
        reason="raw author string contained PII",
    )
    return DocumentReport(
        case_id="api-doc-20260508-xyz98765",
        document_hash="deadbeef" * 8,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[sanitizer_event],
        segments=[seg_result],
        document_verdict=(
            AuditVerdict.PASS if not with_skip else AuditVerdict.REQUIRES_HUMAN_REVIEW
        ),
        document_reason=None if not with_skip else "1 segment skipped",
        n_segments_total=1,
        n_segments_blocked_by_injection=1 if with_skip else 0,
        n_segments_pass=0 if with_skip else 1,
        n_segments_block=0,
        n_segments_review=1 if with_skip else 0,
        latency_ms_total=120,
        cost_eur_total=0.001,
    )


def test_to_analyze_response_translates_pass() -> None:
    report = _make_document_report(with_skip=False)
    response = to_analyze_response(report, response_time_ms=999)
    assert response.case_id == report.case_id
    assert response.document_verdict == "pass"
    assert len(response.segments) == 1
    assert response.segments[0].skip_category == "clean"
    assert response.response_time_ms == 999


def test_to_analyze_response_redacts_skip_reason_to_injection_blocked() -> None:
    """SSDLC: injection skip_reason must map to coarse category, never literal."""
    report = _make_document_report(with_skip=True)
    response = to_analyze_response(report, response_time_ms=0)
    serialized = response.model_dump_json()
    assert "injection_pattern_X" not in serialized
    assert "skip_reason" not in serialized
    assert response.segments[0].skip_category == "injection_blocked"


def test_to_analyze_response_redacts_sanitizer_location_and_reason() -> None:
    """SSDLC: SanitizerEvent.location and reason MUST NOT appear in API response."""
    report = _make_document_report(with_skip=False)
    response = to_analyze_response(report, response_time_ms=0)
    serialized = response.model_dump_json()
    assert "page 1 / metadata.author" not in serialized
    assert "raw author string" not in serialized
    # category and content_hash are exposed
    assert "metadata_stripped" in serialized
    assert "a1b2c3d4e5f6" in serialized


def test_to_analyze_response_classifies_non_injection_skip_as_internal_error() -> None:
    """SSDLC: a non-injection skip_reason maps to internal_error and the raw text is redacted."""
    seg = Segment(id=1, title=None, text="text", token_count=5, is_continuation=False)
    seg_result = SegmentResult(
        segment=seg,
        skipped=True,
        skip_reason="parse_error_at_offset_42",
        audited_answer=None,
        latency_ms=2,
        cost_eur=0.0,
    )
    report = DocumentReport(
        case_id="api-doc-x",
        document_hash="d" * 64,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[seg_result],
        document_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        document_reason="1 segment skipped",
        n_segments_total=1,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=1,
        latency_ms_total=2,
        cost_eur_total=0.0,
    )
    response = to_analyze_response(report, response_time_ms=0)
    serialized = response.model_dump_json()
    assert response.segments[0].skip_category == "internal_error"
    assert "parse_error_at_offset_42" not in serialized
    assert "skip_reason" not in serialized


def test_to_analyze_response_handles_skip_reason_none() -> None:
    """A skipped segment with skip_reason=None falls into internal_error without leaking 'None'."""
    seg = Segment(id=1, title=None, text="text", token_count=5, is_continuation=False)
    seg_result = SegmentResult(
        segment=seg,
        skipped=True,
        skip_reason=None,
        audited_answer=None,
        latency_ms=1,
        cost_eur=0.0,
    )
    report = DocumentReport(
        case_id="api-doc-x",
        document_hash="d" * 64,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[seg_result],
        document_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        document_reason=None,
        n_segments_total=1,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=1,
        latency_ms_total=1,
        cost_eur_total=0.0,
    )
    response = to_analyze_response(report, response_time_ms=0)
    assert response.segments[0].skip_category == "internal_error"


def test_error_response_shape() -> None:
    err = ErrorResponse(
        error_code="injection_blocked",
        message="Input rejected",
        case_id="api-ch-20260508-abc12345",
    )
    dumped = err.model_dump()
    assert dumped == {
        "error_code": "injection_blocked",
        "message": "Input rejected",
        "case_id": "api-ch-20260508-abc12345",
    }


def test_health_response_status_literal() -> None:
    import pytest
    from pydantic import ValidationError

    HealthResponse(status="ok", version="0.0.8", checks=[])  # OK
    HealthResponse(status="degraded", version="0.0.8", checks=[])  # OK
    with pytest.raises(ValidationError):
        HealthResponse(status="broken", version="0.0.8", checks=[])  # type: ignore[arg-type]
