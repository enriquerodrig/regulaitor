"""Integration test: clean Markdown -> document_verdict=PASS.

Mocks Retriever + Document Analyst to keep this fast (no BGE-M3 / no LLM).
Real Auditor + real validator + real corpus exercise the per-Finding lenient
+ per-Document strict aggregation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import (
    Answer,
    AuditVerdict,
    Citation,
    Context,
    Finding,
)
from regulaitor.corpus import loader
from regulaitor.orchestration.document_graph import run_document


@pytest.fixture(scope="module", autouse=True)
def _warmup_loader():
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def _mock_context() -> Context:
    return Context(
        query="seg",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3-mock",
    )


def test_pass_flow_with_clean_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    real_text = loader.get_paragraph("ai_act", "1", "1", "es")
    citation = Citation(
        norma="ai_act",
        articulo="1",
        apartado="1",
        language="es",
        text=real_text[:120],
    )
    finding = Finding(text="Observacion valida", citations=[citation])
    mocked_answer = Answer(
        query="seg",
        language="es",
        text="resumen",
        findings=[finding],
    )

    from regulaitor.orchestration import document_graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = _mock_context()
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = mocked_answer

    monkeypatch.setattr(document_graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: mock_analyst)

    md = (
        b"# Politica de IA\n\n"
        b"Esta politica describe el uso de IA en la empresa Acme y cubre datos personales.\n"
    )

    report = run_document(
        file_bytes=md,
        mime_type="text/markdown",
        language="es",
        corpus=["ai_act"],
        case_id="doc-test-pass",
    )
    assert report.document_verdict == AuditVerdict.PASS
    assert report.n_segments_total >= 1
    assert report.n_segments_pass == report.n_segments_total
    # Clean (PII-free) body -> no PII summary (the wiring's None branch).
    assert report.pii_summary is None


def test_pii_summary_populated_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fase 2.1: a document whose sanitized text carries PII must surface a
    populated pii_summary through the real run_document wiring (the
    `pii_summary=_summarize_pii(sanitized.clean_text)` line), not just via the
    unit-tested helper. Guards against a wiring regression (wrong field /
    dropped kwarg) that every mock-injected test would miss."""
    real_text = loader.get_paragraph("ai_act", "1", "1", "es")
    citation = Citation(
        norma="ai_act", articulo="1", apartado="1", language="es", text=real_text[:120]
    )
    mocked_answer = Answer(
        query="seg",
        language="es",
        text="resumen",
        findings=[Finding(text="Observacion valida", citations=[citation])],
    )

    from regulaitor.orchestration import document_graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = _mock_context()
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = mocked_answer
    monkeypatch.setattr(document_graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: mock_analyst)

    # Body embeds an email + a DNI in visible prose; both survive sanitization.
    md = (
        b"# Politica de privacidad\n\n"
        b"El responsable de datos es ana.lopez@empresa.es y su DNI es 12345678Z, "
        b"segun el registro interno de la empresa Acme para sistemas de IA.\n"
    )

    report = run_document(
        file_bytes=md,
        mime_type="text/markdown",
        language="es",
        corpus=["ai_act"],
        case_id="doc-test-pii",
    )
    assert report.pii_summary is not None
    assert report.pii_summary.counts.get("email") == 1
    assert report.pii_summary.counts.get("dni_nif") == 1
    assert report.pii_summary.total == report.pii_summary.counts["email"] + (
        report.pii_summary.counts["dni_nif"]
    )
