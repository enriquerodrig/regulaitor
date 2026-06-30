"""Schemathesis contract test fixtures with backend fakes."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    DocumentReport,
    Finding,
)
from regulaitor.orchestration.state import ChatState


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "test_token_at_least_16_chars_long")
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")

    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    finding = Finding(text="f", citations=[cit], severity="info")
    answer = Answer(query="q", language="es", text="a", findings=[finding])
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

    def fake_run(**kw: object) -> ChatState:
        return ChatState(
            case_id=kw.get("case_id", "api-ch-1"),
            query=kw.get("query", "q"),
            corpus=kw.get("corpus", "ai_act"),
            language=kw.get("language", "es"),
            answer=answer,
            audited_answer=audited,
        )

    def fake_run_document(**kw: object) -> DocumentReport:
        return DocumentReport(
            case_id=kw.get("case_id", "api-doc-1"),
            document_hash="d" * 64,
            language=kw.get("language", "es"),
            corpus=kw.get("corpus", ["ai_act"]),
            sanitizer_log=[],
            segments=[],
            document_verdict=AuditVerdict.PASS,
            document_reason=None,
            n_segments_total=0,
            n_segments_blocked_by_injection=0,
            n_segments_pass=0,
            n_segments_block=0,
            n_segments_review=0,
            latency_ms_total=10,
            cost_eur_total=0.0,
        )

    monkeypatch.setattr("regulaitor.api.routes_ask.run", fake_run)
    monkeypatch.setattr("regulaitor.api.routes_analyze.run_document", fake_run_document)

    # Stub LanceDB so /health doesn't require a real vector store.
    class _FakeTable:
        def count_rows(self) -> int:
            return 1011

    monkeypatch.setattr("regulaitor.api.routes_health.connect", lambda **_: _FakeTable())

    # Reset rate-limit counters accumulated by earlier tests.
    from regulaitor.security.rate_limit import limiter

    limiter.reset()

    yield
