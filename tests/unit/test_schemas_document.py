"""Tests for H5 document schemas: frozen, extra='forbid', invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import (
    Attachment,
    DocumentBlockedError,
    DocumentReport,
    FontInfo,
    OutlineEntry,
    Page,
    PIISummary,
    RawDocument,
    SanitizedDocument,
    SanitizerEvent,
    Segment,
    SegmentResult,
)


def _minimal_report(**overrides: object) -> DocumentReport:
    base: dict[str, object] = {
        "case_id": "doc-20260506-aaaa1111",
        "document_hash": "sha256:f",
        "language": "es",
        "corpus": ["ai_act"],
        "sanitizer_log": [],
        "segments": [],
        "document_verdict": "pass",
        "document_reason": None,
        "n_segments_total": 0,
        "n_segments_blocked_by_injection": 0,
        "n_segments_pass": 0,
        "n_segments_block": 0,
        "n_segments_review": 0,
        "latency_ms_total": 0,
        "cost_eur_total": 0.0,
    }
    base.update(overrides)
    return DocumentReport(**base)  # type: ignore[arg-type]


def test_font_info_frozen():
    f = FontInfo(name="Arial", size_pt=12.0, color_hex="#000000", is_visible_estimated=True)
    with pytest.raises(ValidationError):
        f.name = "Times"  # type: ignore[misc]


def test_font_info_extra_forbid():
    with pytest.raises(ValidationError):
        FontInfo(name="A", size_pt=1.0, color_hex="#000", is_visible_estimated=True, foo="bar")


def test_page_minimum_fields():
    p = Page(
        number=1,
        text="hello",
        fonts=[],
        annotations=[],
        hidden_text_candidates=[],
        likely_scanned=False,
    )
    assert p.number == 1
    assert p.text == "hello"


def test_attachment_required():
    Attachment(name="x.pdf", mime="application/pdf", size_bytes=10, hash="sha256:ab")


def test_outline_entry_levels():
    OutlineEntry(title="Intro", level=1, page_number=1)


def test_raw_document_mime_literal():
    with pytest.raises(ValidationError):
        RawDocument(
            document_hash="sha256:f",
            mime_type="application/exe",  # not in literal
            language="es",
            pages=[],
            metadata={},
            attachments=[],
            outline=None,
            has_javascript=False,
            has_form_actions=False,
            uri_actions=[],
        )


def test_raw_document_valid():
    rd = RawDocument(
        document_hash="sha256:f",
        mime_type="application/pdf",
        language="es",
        pages=[],
        metadata={},
        attachments=[],
        outline=None,
        has_javascript=False,
        has_form_actions=False,
        uri_actions=[],
    )
    assert rd.mime_type == "application/pdf"


def test_sanitizer_event_categories_literal():
    with pytest.raises(ValidationError):
        SanitizerEvent(
            severity="warning",
            category="bogus_cat",  # type: ignore[arg-type]
            location="p1",
            content_hash="ab",
            reason="x",
        )


def test_sanitizer_event_valid():
    e = SanitizerEvent(
        severity="critical",
        category="javascript_blocked",
        location="page=1",
        content_hash="abcd",
        reason="JS embedded",
    )
    assert e.severity == "critical"


def test_sanitized_document_min_length_50():
    with pytest.raises(ValidationError):
        SanitizedDocument(
            document_hash="sha256:f",
            language="es",
            clean_text="too short",
            outline=None,
            sanitizer_log=[],
        )


def test_segment_min_text_and_token_count():
    with pytest.raises(ValidationError):
        Segment(id=1, title=None, text="", token_count=1, is_continuation=False)
    with pytest.raises(ValidationError):
        Segment(id=1, title=None, text="ok", token_count=0, is_continuation=False)


def test_segment_id_ge_1():
    with pytest.raises(ValidationError):
        Segment(id=0, title=None, text="ok", token_count=1, is_continuation=False)


def test_segment_result_skipped_no_audited():
    seg = Segment(id=1, title="T", text="abc", token_count=1, is_continuation=False)
    sr = SegmentResult(
        segment=seg,
        skipped=True,
        skip_reason="document_self_validating",
        audited_answer=None,
        latency_ms=5,
        cost_eur=0.0,
    )
    assert sr.skipped is True


def test_document_report_count_invariants_via_construction():
    rep = DocumentReport(
        case_id="doc-20260506-aaaa1111",
        document_hash="sha256:f",
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[],
        document_verdict="pass",  # type: ignore[arg-type]
        document_reason=None,
        n_segments_total=0,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=0,
        cost_eur_total=0.0,
    )
    assert rep.case_id.startswith("doc-")


# ---------- PIISummary (Fase 2.1, §18.5/§18.8) ----------


def test_pii_summary_valid():
    s = PIISummary(total=3, counts={"email": 2, "dni_nif": 1})
    assert s.total == 3
    assert s.counts == {"email": 2, "dni_nif": 1}


def test_pii_summary_total_must_match_counts():
    with pytest.raises(ValidationError):
        PIISummary(total=5, counts={"email": 2})


def test_pii_summary_rejects_empty_counts():
    """A PIISummary only exists when PII was found — None means no PII."""
    with pytest.raises(ValidationError):
        PIISummary(total=0, counts={})


def test_pii_summary_frozen_and_extra_forbid():
    with pytest.raises(ValidationError):
        PIISummary(total=1, counts={"email": 1}, foo="bar")  # type: ignore[call-arg]
    s = PIISummary(total=1, counts={"email": 1})
    with pytest.raises(ValidationError):
        s.total = 2  # type: ignore[misc]


def test_document_report_pii_summary_defaults_none():
    rep = _minimal_report()
    assert rep.pii_summary is None


def test_document_report_accepts_pii_summary():
    rep = _minimal_report(pii_summary=PIISummary(total=2, counts={"email": 2}))
    assert rep.pii_summary is not None
    assert rep.pii_summary.total == 2


def test_document_blocked_error_carries_log():
    log = [
        SanitizerEvent(
            severity="critical",
            category="javascript_blocked",
            location="catalog",
            content_hash="ab",
            reason="JS",
        )
    ]
    err = DocumentBlockedError("javascript_blocked", log)
    assert err.reason == "javascript_blocked"
    assert err.sanitizer_log == log
