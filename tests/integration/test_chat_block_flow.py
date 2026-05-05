"""Integration test: mock Analyst with fabricated citation -> real Auditor -> BLOCK.

Both Analyst AND Retriever are mocked to keep this in CI fast suite (no BGE-M3 load).
Real Auditor + real validator + real corpus exercise the "no citation, no answer" rule.
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


def test_chat_block_with_fabricated_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Analyst mocked to fabricate non-existent article 999 -> Auditor BLOCK."""
    citation = Citation(
        norma="ai_act",
        articulo="999",
        apartado=None,
        language="es",
        text="texto fabricado",
    )
    finding = Finding(text="Afirmacion falsa", citations=[citation])
    mocked_answer = Answer(
        query="q",
        language="es",
        text="response",
        findings=[finding],
    )

    from regulaitor.orchestration import graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = _mock_context()
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = mocked_answer
    monkeypatch.setattr(graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(graph, "_analyst", lambda: mock_analyst)

    state = run(query="q", corpus="ai_act", language="es", case_id="ch-block")

    assert state.audited_answer is not None
    assert state.audited_answer.verdict == AuditVerdict.BLOCK
    assert state.audited_answer.reason is not None
    assert "BLOCK" in state.audited_answer.reason
    assert "article_not_found" in state.audited_answer.reason
