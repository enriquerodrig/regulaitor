"""Tests for ui_streamlit._render — pure-ish functions that call Streamlit primitives.

We monkeypatch streamlit primitives to capture calls and verify the right
ones fire with the expected arguments. Coverage focus: branching on
verdict, severity, exception type.
"""

from __future__ import annotations

import pytest

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
from regulaitor.ui_streamlit import _render


@pytest.fixture
def streamlit_recorder(monkeypatch):
    """Capture all streamlit calls into a list of (method, args, kwargs)."""
    calls: list[tuple[str, tuple, dict]] = []

    class _Expander:
        def __init__(self, label, expanded=False):
            calls.append(("expander_open", (label,), {"expanded": expanded}))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append(("expander_close", (), {}))

    def _expander(label, *, expanded=False):
        return _Expander(label, expanded=expanded)

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _columns(n):
        calls.append(("columns", (n,), {}))
        return [_Col() for _ in range(n)]

    for method in (
        "success",
        "error",
        "warning",
        "info",
        "markdown",
        "metric",
        "dataframe",
        "caption",
    ):
        monkeypatch.setattr(
            f"streamlit.{method}",
            lambda *a, _m=method, **kw: calls.append((_m, a, kw)),
        )
    monkeypatch.setattr("streamlit.expander", _expander)
    monkeypatch.setattr("streamlit.columns", _columns)
    return calls


def _citation() -> Citation:
    return Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto literal del corpus",
    )


def _finding(text: str = "hallazgo X", sev: str = "medium") -> Finding:
    return Finding(text=text, citations=[_citation()], severity=sev)


def _answer() -> Answer:
    return Answer(query="q", language="es", text="resumen", findings=[_finding()])


def _audited(verdict: AuditVerdict = AuditVerdict.PASS) -> AuditedAnswer:
    return AuditedAnswer(
        answer=_answer(),
        verdict=verdict,
        audit_results=[
            AuditResult(
                citation=_citation(),
                validated=True,
                article_exists=True,
                apartado_exists=True,
                text_normalized_match=True,
                reason=None,
            )
        ],
        reason=None,
    )


def _chat_state(verdict: AuditVerdict = AuditVerdict.PASS, blocked: bool = False) -> ChatState:
    return ChatState(
        case_id="ch-test",
        query="q",
        corpus="ai_act",
        language="es",
        injection_blocked=blocked,
        injection_reason="ignore-previous" if blocked else None,
        context=None,
        answer=None if blocked else _answer(),
        audited_answer=None if blocked else _audited(verdict),
        errors=[],
    )


# ---------- verdict_badge ----------


def test_verdict_badge_pass(streamlit_recorder):
    _render.verdict_badge(AuditVerdict.PASS)
    methods = [c[0] for c in streamlit_recorder]
    # R3 polish: verdict_badge now emits subtle pill via st.markdown (HTML),
    # NOT st.success/error/warning. No emojis. Color encoded via inline style.
    assert "markdown" in methods
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "markdown")
    assert "PASS" in msg
    assert "✓" not in msg  # no-emoji guarantee
    assert "aria-live" in msg  # accessibility — async status update


def test_verdict_badge_block_with_reason(streamlit_recorder):
    _render.verdict_badge(AuditVerdict.BLOCK, reason="block_in_segments:[2]")
    methods = [c[0] for c in streamlit_recorder]
    assert "markdown" in methods
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "markdown")
    assert "BLOCK" in msg
    assert "block_in_segments" in msg
    assert "✗" not in msg


def test_verdict_badge_review(streamlit_recorder):
    _render.verdict_badge(AuditVerdict.REQUIRES_HUMAN_REVIEW)
    methods = [c[0] for c in streamlit_recorder]
    assert "markdown" in methods
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "markdown")
    assert "REQUIRES HUMAN REVIEW" in msg
    assert "⚠" not in msg


# ---------- finding ----------


def test_finding_renders_text_severity_and_citations(streamlit_recorder):
    f = _finding(text="hallazgo X", sev="medium")
    _render.finding(f)
    md_calls = [args[0] for m, args, _ in streamlit_recorder if m == "markdown"]
    assert len(md_calls) == 2
    assert "hallazgo X" in md_calls[0]
    assert "MEDIUM" in md_calls[0].upper()
    assert "texto literal del corpus" in md_calls[1]
    assert "ai_act art. 6.1" in md_calls[1]


def test_finding_with_multiple_citations(streamlit_recorder):
    citations = [_citation(), _citation()]
    f = Finding(text="x", citations=citations, severity="info")
    _render.finding(f)
    md_calls = [args[0] for m, args, _ in streamlit_recorder if m == "markdown"]
    assert len(md_calls) == 1 + len(citations)


# ---------- error_message ----------


def test_error_message_authentication_error(streamlit_recorder):
    # Use real anthropic SDK exception class to avoid __name__ setattr issues.
    from anthropic import AuthenticationError

    # AuthenticationError requires response object; substitute via a stub.
    # If the constructor signature changes, fall back to type(...) with __name__.
    try:
        exc: Exception = AuthenticationError(message="bad", response=None, body=None)
    except (TypeError, AttributeError):
        # API surface differs across versions; create generic with right __name__.
        class _AuthError(Exception):  # noqa: N818 - name overridden below
            pass

        _AuthError.__name__ = "AuthenticationError"
        _AuthError.__module__ = "anthropic"
        exc = _AuthError("bad")
    _render.error_message(exc)
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    assert "Anthropic" in msg
    assert "inválida" in msg.lower() or "invalida" in msg.lower()


def test_error_message_credit_balance(streamlit_recorder):
    from anthropic import BadRequestError

    try:
        exc: Exception = BadRequestError(
            message="Your credit balance is too low",
            response=None,
            body=None,
        )
    except (TypeError, AttributeError):

        class _BadReqError(Exception):
            pass

        _BadReqError.__name__ = "BadRequestError"
        _BadReqError.__module__ = "anthropic"
        exc = _BadReqError("Your credit balance is too low")
    _render.error_message(exc)
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    assert "crédito" in msg.lower() or "credito" in msg.lower() or "billing" in msg.lower()


def test_error_message_generic(streamlit_recorder):
    _render.error_message(RuntimeError("boom"))
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    # No stack trace, no exception type name, no raw message
    assert "RuntimeError" not in msg
    assert "boom" not in msg
    assert "inesperado" in msg.lower()


# ---------- sanitizer_log_expander ----------


def test_sanitizer_log_expander_renders_table(streamlit_recorder):
    log = [
        SanitizerEvent(
            severity="warning",
            category="metadata_stripped",
            location="metadata.Author",
            content_hash="abc123",
            reason="metadata field stripped",
        ),
        SanitizerEvent(
            severity="info",
            category="outline_extracted",
            location="document.outline",
            content_hash="def456",
            reason="outline has 7 entries",
        ),
    ]
    _render.sanitizer_log_expander(log)
    methods = [c[0] for c in streamlit_recorder]
    assert "expander_open" in methods
    assert "dataframe" in methods


def test_sanitizer_log_expander_skipped_when_empty(streamlit_recorder):
    _render.sanitizer_log_expander([])
    methods = [c[0] for c in streamlit_recorder]
    assert "expander_open" not in methods
    assert "dataframe" not in methods


# ---------- chat_state (top-level) ----------


def test_chat_state_pass_renders_full_output(streamlit_recorder):
    state = _chat_state(AuditVerdict.PASS)
    _render.chat_state(state)
    methods = [c[0] for c in streamlit_recorder]
    # R3 polish: verdict_badge uses st.markdown (not st.success); so check that
    # PASS appears somewhere in any markdown call rather than checking for st.success.
    assert "markdown" in methods
    pass_in_markdown = any(
        m == "markdown" and "PASS" in str(args[0]) for m, args, _ in streamlit_recorder
    )
    assert pass_in_markdown, "expected PASS badge rendered via st.markdown"
    assert "expander_open" in methods


def test_chat_state_injection_blocked_shows_user_friendly_msg(streamlit_recorder):
    state = _chat_state(blocked=True)
    _render.chat_state(state)
    err_msgs = [args[0] for m, args, _ in streamlit_recorder if m == "error"]
    assert any("bloqueada" in m.lower() for m in err_msgs)
    # pattern_name MUST NOT appear in any user-visible text
    all_msgs = [
        args[0]
        for m, args, _ in streamlit_recorder
        if m in ("error", "warning", "info", "success", "markdown")
    ]
    assert not any("ignore-previous" in m for m in all_msgs)


# ---------- document_report (top-level) ----------


def _document_report(
    verdict: AuditVerdict = AuditVerdict.PASS,
    reason: str | None = None,
    skipped_segments: int = 0,
) -> DocumentReport:
    seg = Segment(id=1, title="§1 Intro", text="x", token_count=1, is_continuation=False)
    sr = SegmentResult(
        segment=seg,
        skipped=False,
        skip_reason=None,
        audited_answer=_audited(AuditVerdict.PASS),
        latency_ms=100,
        cost_eur=0.01,
    )
    segs = [sr]
    for i in range(skipped_segments):
        skip_seg = Segment(
            id=2 + i,
            title=f"§{2+i} bad",
            text="x",
            token_count=1,
            is_continuation=False,
        )
        segs.append(
            SegmentResult(
                segment=skip_seg,
                skipped=True,
                skip_reason="document_self_validating",
                audited_answer=None,
                latency_ms=10,
                cost_eur=0.0,
            )
        )
    return DocumentReport(
        case_id="doc-test",
        document_hash="sha256:test",
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=segs,
        document_verdict=verdict,
        document_reason=reason,
        n_segments_total=len(segs),
        n_segments_blocked_by_injection=skipped_segments,
        n_segments_pass=1 if verdict == AuditVerdict.PASS else 0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=200,
        cost_eur_total=0.02,
    )


def test_document_report_pass_renders_metrics_and_segments(streamlit_recorder):
    report = _document_report(AuditVerdict.PASS)
    _render.document_report(report)
    methods = [c[0] for c in streamlit_recorder]
    # R3 polish: verdict_badge → st.markdown. document_report still uses
    # st.metric for the top-of-page metric strip + st.expander for segments.
    assert "markdown" in methods
    pass_in_markdown = any(
        m == "markdown" and "PASS" in str(args[0]) for m, args, _ in streamlit_recorder
    )
    assert pass_in_markdown, "expected PASS badge rendered via st.markdown"
    assert "metric" in methods
    assert "expander_open" in methods


def test_document_report_sanitizer_critical_short_circuits(streamlit_recorder):
    report = _document_report(
        AuditVerdict.REQUIRES_HUMAN_REVIEW,
        reason="sanitizer_critical:javascript_blocked",
    )
    _render.document_report(report)
    err_or_warn = [args[0] for m, args, _ in streamlit_recorder if m in ("error", "warning")]
    assert any(
        "javascript" in m.lower() or "bloqueado" in m.lower() or "revisión" in m.lower()
        for m in err_or_warn
    )


def test_document_report_skipped_segment_user_friendly(streamlit_recorder):
    report = _document_report(AuditVerdict.BLOCK, skipped_segments=1)
    _render.document_report(report)
    all_text = []
    for _m, args, _ in streamlit_recorder:
        if args and isinstance(args[0], str):
            all_text.append(args[0])
        elif args and isinstance(args[0], list):
            all_text.append(repr(args[0]))
    full = " ".join(all_text)
    # skip_reason (= pattern_name) MUST NOT appear in UI
    assert "document_self_validating" not in full
    # User-friendly message about "saltado" / "sospechoso" should appear
    assert "sospech" in full.lower() or "saltado" in full.lower()
