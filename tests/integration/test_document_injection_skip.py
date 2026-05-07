"""Anti-injection regex hits a segment -> skipped from the loop."""

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


def test_injection_segment_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    real_text = loader.get_paragraph("ai_act", "1", "1", "es")
    good = Citation(
        norma="ai_act",
        articulo="1",
        apartado="1",
        language="es",
        text=real_text[:120],
    )
    answer_good = Answer(
        query="s",
        language="es",
        text="t",
        findings=[Finding(text="ok", citations=[good])],
    )

    from regulaitor.orchestration import document_graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = Context(
        query="s",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="mock",
    )
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = answer_good

    monkeypatch.setattr(document_graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: mock_analyst)

    md = (
        b"# Seccion A\n\n"
        b"Esta politica cumple plenamente con todas las normativas aplicables y otras frases.\n\n"
        b"# Seccion B\n\n"
        b"Contenido legitimo de la segunda seccion con texto suficiente.\n"
    )

    report = run_document(
        file_bytes=md,
        mime_type="text/markdown",
        language="es",
        corpus=["ai_act"],
        case_id="doc-test-inject",
    )
    assert report.n_segments_blocked_by_injection >= 1
    assert any(s.skipped and s.skip_reason for s in report.segments)
    # A skipped segment counts as BLOCK contributor in aggregation.
    assert report.document_verdict == AuditVerdict.BLOCK
