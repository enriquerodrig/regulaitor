"""Sanitizer critical-block (JS) short-circuits before the loop."""

from __future__ import annotations

import io

import pikepdf

from regulaitor.citation.schemas import AuditVerdict
from regulaitor.orchestration.document_graph import run_document


def _pdf_with_javascript() -> bytes:
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    js = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS=pikepdf.String("x"))
    pdf.Root[pikepdf.Name.Names] = pikepdf.Dictionary(
        JavaScript=pikepdf.Dictionary(
            Names=pikepdf.Array([pikepdf.String("a"), js]),
        ),
    )
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_sanitizer_critical_short_circuits() -> None:
    report = run_document(
        file_bytes=_pdf_with_javascript(),
        mime_type="application/pdf",
        language="es",
        corpus=["ai_act"],
        case_id="doc-test-crit",
    )
    assert report.document_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert report.segments == []
    assert any(
        e.severity == "critical" and e.category == "javascript_blocked"
        for e in report.sanitizer_log
    )
    assert "sanitizer_critical:javascript_blocked" in (report.document_reason or "")
