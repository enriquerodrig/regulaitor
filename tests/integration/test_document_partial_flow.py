"""One segment PASS + another REQUIRES_HUMAN_REVIEW -> document REQUIRES_HUMAN_REVIEW."""

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


def test_partial_flow_yields_review(monkeypatch: pytest.MonkeyPatch) -> None:
    real_text = loader.get_paragraph("ai_act", "1", "1", "es")
    good = Citation(
        norma="ai_act",
        articulo="1",
        apartado="1",
        language="es",
        text=real_text[:120],
    )
    bad = Citation(
        norma="ai_act",
        articulo="999",
        apartado=None,
        language="es",
        text="fab",
    )

    answer_good = Answer(
        query="s",
        language="es",
        text="t",
        findings=[Finding(text="ok", citations=[good])],
    )
    answer_mixed = Answer(
        query="s",
        language="es",
        text="t",
        findings=[
            Finding(text="ok", citations=[good]),
            Finding(text="ko2", citations=[bad]),
        ],
    )

    from regulaitor.orchestration import document_graph

    answers = iter([answer_good, answer_mixed])
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
    mock_analyst.analyze.side_effect = lambda *args, **kwargs: next(answers)

    monkeypatch.setattr(document_graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: mock_analyst)

    md = (
        b"# Seccion A\n\n"
        b"Primera seccion con contenido suficiente para procesarse correctamente.\n\n"
        b"# Seccion B\n\n"
        b"Segunda seccion con contenido suficiente para procesarse correctamente.\n"
    )

    report = run_document(
        file_bytes=md,
        mime_type="text/markdown",
        language="es",
        corpus=["ai_act"],
        case_id="doc-test-partial",
    )
    # Bad segment has 1 valid + 1 fabricated -> REQUIRES_HUMAN_REVIEW per H4 lenient.
    # Good segment is PASS. Mix without BLOCK -> document REQUIRES_HUMAN_REVIEW.
    assert report.document_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
