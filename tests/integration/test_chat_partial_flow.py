"""Integration test: 1 valid + 1 fabricated Finding -> REQUIRES_HUMAN_REVIEW.

Both Analyst AND Retriever are mocked to keep this in CI fast suite (no BGE-M3 load).
Real Auditor + real validator + real corpus exercise the Lenient-strict aggregation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import Answer, AuditVerdict, Citation, Context, Finding
from regulaitor.corpus import loader
from regulaitor.orchestration.graph import run


@pytest.fixture(scope="module", autouse=True)
def _warmup_loader() -> None:
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def _mock_context() -> Context:
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3-mock",
    )


def test_chat_partial_returns_human_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """1 Finding all-valid + 1 Finding all-invalid -> REQUIRES_HUMAN_REVIEW."""
    real_text = loader.get_paragraph("ai_act", "1", "1", "es")

    good = Citation(norma="ai_act", articulo="1", apartado="1", language="es", text=real_text[:120])
    bad = Citation(norma="ai_act", articulo="999", apartado=None, language="es", text="fab")

    finding_good = Finding(text="Afirmacion valida", citations=[good])
    finding_bad = Finding(text="Afirmacion falsa", citations=[bad])
    mocked_answer = Answer(
        query="q",
        language="es",
        text="response",
        findings=[finding_good, finding_bad],
    )

    from regulaitor.orchestration import graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = _mock_context()
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = mocked_answer
    monkeypatch.setattr(graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(graph, "_analyst", lambda: mock_analyst)

    state = run(query="q", corpus="ai_act", language="es", case_id="ch-partial")

    assert state.audited_answer is not None
    assert state.audited_answer.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert state.audited_answer.reason is not None
    assert "REQUIRES_HUMAN_REVIEW" in state.audited_answer.reason
