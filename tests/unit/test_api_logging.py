"""Unit tests for api.logging — IP redaction + chat/doc turn loggers."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from regulaitor.api.logging import (
    _redact_ip,
    log_api_chat_turn,
    log_api_document_turn,
)
from regulaitor.api.schemas import (
    AnalyzeResponse,
    AnswerDTO,
    AskResponse,
    AuditResultDTO,
    CitationDTO,
    FindingDTO,
    SegmentResultDTO,
)
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    DocumentReport,
    Finding,
    Segment,
    SegmentResult,
)
from regulaitor.orchestration.state import ChatState


def test_redact_ipv4_to_24() -> None:
    assert _redact_ip("192.168.1.45") == "192.168.1.0"


def test_redact_ipv6_to_48() -> None:
    redacted = _redact_ip("2001:db8:1234:5678::1")
    assert redacted is not None
    assert redacted.startswith("2001:db8:1234:")


def test_redact_invalid_returns_none() -> None:
    assert _redact_ip("not an ip") is None
    assert _redact_ip(None) is None
    assert _redact_ip("") is None


def _ask_response() -> AskResponse:
    cit = CitationDTO(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    audit = AuditResultDTO(
        citation=cit,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    finding = FindingDTO(text="t", citations=[cit], severity="info")
    answer = AnswerDTO(text="text", findings=[finding])
    return AskResponse(
        case_id="api-ch-1",
        verdict="pass",
        answer=answer,
        audit_results=[audit],
        reason=None,
        response_time_ms=100,
    )


def _chat_state() -> ChatState:
    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    finding = Finding(text="t", citations=[cit], severity="info")
    answer = Answer(query="q", language="es", text="text", findings=[finding])
    audit = AuditResult(
        citation=cit,
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
        case_id="api-ch-1",
        query="q",
        corpus="ai_act",
        language="es",
        answer=answer,
        audited_answer=audited,
    )


def _request() -> SimpleNamespace:
    state = SimpleNamespace(token_hash="a1b2c3d4")
    return SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/ask"),
        state=state,
        client=SimpleNamespace(host="192.168.1.45"),
    )


def test_log_api_chat_turn_emits_record(caplog) -> None:
    caplog.set_level(logging.INFO, logger="regulaitor.api.logging")
    log_api_chat_turn(_request(), _chat_state(), _ask_response())
    assert any("api_chat_turn" in r.message for r in caplog.records)
    record_msg = next(r.message for r in caplog.records if "api_chat_turn" in r.message)
    payload = json.loads(record_msg.split("api_chat_turn: ", 1)[1])
    assert payload["case_id"] == "api-ch-1"
    assert payload["http_status"] == 200
    assert payload["token_hash"] == "a1b2c3d4"
    assert payload["client_ip_redacted"] == "192.168.1.0"
    assert payload["verdict"] == "pass"
    assert payload["tenant_id"] is None  # no tenant in state -> null (legacy/pre-auth)


def test_log_api_chat_turn_includes_tenant_id(caplog) -> None:
    """Fase 4: the structured record carries tenant_id when a tenant is resolved."""
    caplog.set_level(logging.INFO, logger="regulaitor.api.logging")
    request = _request()
    request.state.tenant = SimpleNamespace(tenant_id="acme")
    log_api_chat_turn(request, _chat_state(), _ask_response())
    msg = next(r.message for r in caplog.records if "api_chat_turn" in r.message)
    payload = json.loads(msg.split("api_chat_turn: ", 1)[1])
    assert payload["tenant_id"] == "acme"


def _document_report() -> DocumentReport:
    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    finding = Finding(text="t", citations=[cit], severity="info")
    answer = Answer(query="(seg)", language="es", text="text", findings=[finding])
    audit = AuditResult(
        citation=cit,
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
    seg = Segment(id=1, title=None, text="seg", token_count=1, is_continuation=False)
    seg_res = SegmentResult(
        segment=seg,
        skipped=False,
        skip_reason=None,
        audited_answer=audited,
        latency_ms=10,
        cost_eur=0.001,
    )
    return DocumentReport(
        case_id="api-doc-1",
        document_hash="x" * 64,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[seg_res],
        document_verdict=AuditVerdict.PASS,
        document_reason=None,
        n_segments_total=1,
        n_segments_blocked_by_injection=0,
        n_segments_pass=1,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=10,
        cost_eur_total=0.001,
    )


def _analyze_response() -> AnalyzeResponse:
    cit = CitationDTO(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    audit = AuditResultDTO(
        citation=cit,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    finding = FindingDTO(text="t", citations=[cit], severity="info")
    answer = AnswerDTO(text="text", findings=[finding])
    seg_dto = SegmentResultDTO(
        segment_id=1,
        title=None,
        skipped=False,
        skip_category="clean",
        answer=answer,
        verdict="pass",
        audit_results=[audit],
        latency_ms=10,
        cost_eur=0.001,
    )
    return AnalyzeResponse(
        case_id="api-doc-1",
        document_verdict="pass",
        document_reason=None,
        n_segments_total=1,
        n_segments_pass=1,
        n_segments_block=0,
        n_segments_review=0,
        n_segments_blocked_by_injection=0,
        sanitizer_log=[],
        segments=[seg_dto],
        latency_ms_total=10,
        cost_eur_total=0.001,
        response_time_ms=200,
    )


def test_log_api_document_turn_emits_record(caplog) -> None:
    caplog.set_level(logging.INFO, logger="regulaitor.api.logging")
    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/analyze"),
        state=SimpleNamespace(token_hash="a1b2c3d4"),
        client=SimpleNamespace(host="192.168.1.45"),
    )
    log_api_document_turn(request, _document_report(), _analyze_response())
    assert any("api_document_turn" in r.message for r in caplog.records)
