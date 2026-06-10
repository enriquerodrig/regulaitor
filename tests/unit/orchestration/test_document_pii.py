"""Fase 2.1 — document-pipeline PII summary: node helper, structured log,
and langfuse trace-record allowlist safety (§18.5 / §18.8)."""

from __future__ import annotations

import json
import logging

from regulaitor.citation.schemas import AuditVerdict, DocumentReport, PIISummary
from regulaitor.observability.langfuse_client import _assert_safe_keys
from regulaitor.orchestration.document_graph import (
    _doc_trace_record,
    _log_document_turn,
    _summarize_pii,
)


def _report(pii: PIISummary | None) -> DocumentReport:
    return DocumentReport(
        case_id="doc-20260610-aaaa1111",
        document_hash="sha256:" + "f" * 58,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[],
        document_verdict=AuditVerdict.PASS,
        document_reason=None,
        n_segments_total=0,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=0,
        cost_eur_total=0.0,
        pii_summary=pii,
    )


def test_summarize_pii_returns_summary_for_text_with_pii() -> None:
    summary = _summarize_pii("Contacto ana@empresa.es y DNI 12345678Z en el registro.")
    assert summary is not None
    assert summary.total == 2
    assert summary.counts == {"dni_nif": 1, "email": 1}


def test_summarize_pii_returns_none_for_clean_text() -> None:
    assert _summarize_pii("La política de IA describe el sistema de alto riesgo.") is None


def test_log_document_turn_includes_pii_counts(caplog) -> None:
    """§18.8: structured log carries counts/kinds only (no raw values)."""
    report = _report(PIISummary(total=2, counts={"email": 1, "dni_nif": 1}))
    with caplog.at_level(logging.INFO, logger="regulaitor.orchestration.document_graph"):
        _log_document_turn(report)
    line = next(m for m in caplog.messages if "document_turn" in m)
    payload = json.loads(line.split("document_turn: ", 1)[1])
    assert payload["pii_total"] == 2
    assert payload["pii_kinds"] == {"email": 1, "dni_nif": 1}


def test_log_document_turn_pii_zero_when_absent(caplog) -> None:
    report = _report(None)
    with caplog.at_level(logging.INFO, logger="regulaitor.orchestration.document_graph"):
        _log_document_turn(report)
    line = next(m for m in caplog.messages if "document_turn" in m)
    payload = json.loads(line.split("document_turn: ", 1)[1])
    assert payload["pii_total"] == 0
    assert payload["pii_kinds"] == {}


def test_doc_trace_record_pii_total_passes_allowlist() -> None:
    """The trace record must include n_pii_total AND stay allowlist-safe
    (no raw text reaches the 3rd-party egress; counts only)."""
    record = _doc_trace_record(_report(PIISummary(total=4, counts={"email": 4})))
    assert record["n_pii_total"] == 4
    _assert_safe_keys(record)  # raises if any key is not allowlisted


def test_doc_trace_record_pii_total_zero_when_absent() -> None:
    record = _doc_trace_record(_report(None))
    assert record["n_pii_total"] == 0
    _assert_safe_keys(record)
