"""Unit tests for agents/retriever.py — RetrieverAgent adapter producing Context."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.citation.schemas import Context, RetrievedChunk


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.9,
        version="32024R1689",
        source_url="https://example.com",
    )


def test_retriever_agent_returns_context(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk = _make_chunk()
    run_mock = MagicMock(return_value=[chunk])
    model_id_mock = MagicMock(return_value="BAAI/bge-m3")

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(retriever.embeddings, "model_identifier", model_id_mock)

    agent = RetrieverAgent()
    ctx = agent.retrieve("alto riesgo", "ai_act", "es", top_k=3)

    assert isinstance(ctx, Context)
    assert ctx.query == "alto riesgo"
    assert ctx.corpus == "ai_act"
    assert ctx.language == "es"
    assert ctx.chunks == [chunk]
    assert ctx.embedding_model == "BAAI/bge-m3"
    assert ctx.retrieved_at.tzinfo == UTC


def test_retriever_agent_delegates_with_correct_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock(return_value=[])

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    agent.retrieve("q", "gdpr", "en", top_k=10)

    run_mock.assert_called_once_with("q", "gdpr", "en", top_k=10)


def test_retriever_agent_default_top_k_passes_none_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H15.2: the RetrieverAgent's default `top_k` is `None` (pass-through);
    `rag_retrieval.run()` resolves None -> DEFAULT_CONFIG.top_k at call time
    (= 5 when REGULAITOR_RETRIEVAL_CONFIG is unset, production-byte-identical).
    The wrapper no longer hardcodes 5 — that invariant moved into DEFAULT_CONFIG
    where the env-override can reach it (ADR-0018, closes §22.22 design-defect)."""
    run_mock = MagicMock(return_value=[])

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    agent.retrieve("q", "ai_act", "es")

    run_mock.assert_called_once_with("q", "ai_act", "es", top_k=None)


def test_retrieved_at_is_close_to_now(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", MagicMock(return_value=[]))
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    before = datetime.now(tz=UTC)
    ctx = agent.retrieve("q", "ai_act", "es")
    after = datetime.now(tz=UTC)

    assert before <= ctx.retrieved_at <= after
