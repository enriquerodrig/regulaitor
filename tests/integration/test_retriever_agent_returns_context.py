"""Integration test: RetrieverAgent.retrieve returns a well-formed Context.

Mocks rag.retrieval.run to keep this test out of the `slow` set
(no real BGE-M3 load); the slow E2E variant is in test_mcp_search_articles_flow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.citation.schemas import RetrievedChunk


def test_retriever_agent_returns_well_formed_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = RetrievedChunk(
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
    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", MagicMock(return_value=[chunk]))
    monkeypatch.setattr(
        retriever.embeddings,
        "model_identifier",
        MagicMock(return_value="BAAI/bge-m3"),
    )

    agent = RetrieverAgent()
    before = datetime.now(tz=UTC)
    ctx = agent.retrieve("alto riesgo", "ai_act", "es")
    after = datetime.now(tz=UTC)

    assert ctx.query == "alto riesgo"
    assert ctx.corpus == "ai_act"
    assert ctx.language == "es"
    assert ctx.embedding_model == "BAAI/bge-m3"
    assert before <= ctx.retrieved_at <= after
    assert len(ctx.chunks) == 1
    assert ctx.chunks[0] == chunk
