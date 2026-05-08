"""Mock analyst with fabricated citation -> real Auditor -> document BLOCK."""

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


def test_block_flow_with_fabricated_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    citation = Citation(
        norma="ai_act",
        articulo="999",
        apartado=None,
        language="es",
        text="texto fabricado",
    )
    finding = Finding(text="Afirmacion falsa", citations=[citation])
    mocked_answer = Answer(
        query="seg",
        language="es",
        text="resumen",
        findings=[finding],
    )

    from regulaitor.orchestration import document_graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = Context(
        query="seg",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="mock",
    )
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = mocked_answer

    monkeypatch.setattr(document_graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: mock_analyst)

    md = (
        b"# Politica\n\n"
        b"Texto suficiente para superar el minimo de 50 caracteres en clean_text.\n"
    )

    report = run_document(
        file_bytes=md,
        mime_type="text/markdown",
        language="es",
        corpus=["ai_act"],
        case_id="doc-test-block",
    )
    assert report.document_verdict == AuditVerdict.BLOCK
    assert report.n_segments_block >= 1
    assert "BLOCK" in (report.document_reason or "") or "block" in (report.document_reason or "")
