"""Integration test: chat E2E with mocked Analyst producing real-corpus citations -> PASS.

Both Analyst AND Retriever are mocked to keep this in CI fast suite (no BGE-M3 load).
The Retriever's actual output is not used by the mocked Analyst, but the LangGraph wiring
runs the Retriever node anyway. Real Auditor + real validator + real corpus exercise the
"no citation, no answer" rule end-to-end.
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
    """Empty Context — the mocked Analyst ignores it."""
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3-mock",
    )


def test_chat_pass_with_real_corpus_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Analyst to produce Answer with citation literally extracted from real corpus.

    Real Auditor + real validator + real loader + real corpus -> verdict PASS.
    """
    # Pull a real apartado text from the corpus
    real_text = loader.get_paragraph(norma="ai_act", articulo="1", apartado="1", language="es")

    citation = Citation(
        norma="ai_act",
        articulo="1",
        apartado="1",
        language="es",
        text=real_text[:120],  # use first 120 chars; substring after _normalize will match
    )
    finding = Finding(text="El AI Act define su objeto en el articulo 1.", citations=[citation])
    mocked_answer = Answer(
        query="Que dice el AI Act sobre su objeto?",
        language="es",
        text="El AI Act establece su objeto en el Articulo 1.",
        findings=[finding],
    )

    from regulaitor.orchestration import graph

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = _mock_context()
    mock_analyst = MagicMock()
    mock_analyst.analyze.return_value = mocked_answer
    monkeypatch.setattr(graph, "_retriever", lambda: mock_retriever)
    monkeypatch.setattr(graph, "_analyst", lambda: mock_analyst)

    state = run(
        query="Que dice el AI Act sobre su objeto?",
        corpus="ai_act",
        language="es",
        case_id="ch-pass",
    )

    assert state.injection_blocked is False
    assert state.audited_answer is not None
    assert state.audited_answer.verdict == AuditVerdict.PASS
    assert state.audited_answer.reason is None
