"""v0.1.21 — Tier 2 Capa C: Analyst aggressive retry with failure-specific feedback.

3 attempts max; on Pydantic ValidationError (e.g. Capa B `findings=[]` rejection),
the next attempt's tool_result message includes the failing text + actionable
instruction. After 3 failed attempts -> RuntimeError (preserves current behavior).

ADR-0027 / spec D4.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from regulaitor.agents.analyst import AnalystAgent
from regulaitor.citation.schemas import Context, RetrievedChunk


def _ctx() -> Context:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="High-risk AI systems shall comply with...",
        score=0.9,
        version="v",
        source_url="https://example.com",
    )
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[rc],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3",
    )


class _StubResult:
    def __init__(self, tool_use_input: dict[str, Any] | None) -> None:
        self.tool_use_input = tool_use_input


def test_retry_aggressive_three_attempts_max(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock router.complete to return empty `findings` 3 times -> RuntimeError."""
    from regulaitor.agents import analyst

    bad_input = {"query": "q", "language": "es", "text": "claim with no findings", "findings": []}
    complete_mock = MagicMock(
        side_effect=[
            _StubResult(bad_input),
            _StubResult(bad_input),
            _StubResult(bad_input),
        ]
    )
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="Analyst emitted malformed Answer"):
        agent.analyze("q", _ctx())

    # 3 attempts consumed (the 3rd raises after the loop ends).
    assert complete_mock.call_count == 3


def test_retry_aggressive_succeeds_on_second_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock 1 bad + 1 good response -> returns the valid Answer."""
    from regulaitor.agents import analyst

    bad_input = {"query": "q", "language": "es", "text": "claim", "findings": []}
    good_input = {
        "query": "q",
        "language": "es",
        "text": "claim",
        "findings": [
            {
                "text": "rule applies",
                "citations": [
                    {
                        "norma": "ai_act",
                        "articulo": "6",
                        "apartado": "1",
                        "language": "es",
                        "text": "High-risk AI systems shall comply",
                    }
                ],
                "severity": "info",
            }
        ],
    }
    complete_mock = MagicMock(side_effect=[_StubResult(bad_input), _StubResult(good_input)])
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    answer = agent.analyze("q", _ctx())
    assert len(answer.findings) == 1
    assert complete_mock.call_count == 2


def test_retry_aggressive_feedback_message_contains_failure_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On findings=[] failure the retry tool_result includes 'findings' + a quoted
    excerpt of the offending text so Sonnet can self-correct (spec D4 verbatim)."""
    from regulaitor.agents import analyst

    bad_input = {
        "query": "q",
        "language": "es",
        "text": "The processing of personal data must comply with art 5",
        "findings": [],
    }
    good_input = {
        "query": "q",
        "language": "es",
        "text": "ok",
        "findings": [
            {
                "text": "rule applies",
                "citations": [
                    {
                        "norma": "ai_act",
                        "articulo": "6",
                        "apartado": "1",
                        "language": "es",
                        "text": "High-risk AI systems shall comply",
                    }
                ],
                "severity": "info",
            }
        ],
    }

    captured_messages: list[list[dict[str, Any]]] = []

    def fake_complete(**kwargs: Any) -> _StubResult:
        captured_messages.append(list(kwargs["messages"]))
        # Attempt 1: return bad; Attempt 2: return good.
        return _StubResult(bad_input if len(captured_messages) == 1 else good_input)

    monkeypatch.setattr(analyst.router, "complete", MagicMock(side_effect=fake_complete))

    agent = AnalystAgent()
    agent.analyze("q", _ctx())

    # Inspect the messages passed on attempt 2: must contain a tool_result with
    # the failure-specific feedback per spec D4.
    assert len(captured_messages) == 2
    attempt2_messages = captured_messages[1]
    # The last user message on attempt 2 carries the tool_result feedback.
    last_user_msg = attempt2_messages[-1]
    assert last_user_msg["role"] == "user"
    content_blocks = last_user_msg["content"]
    assert isinstance(content_blocks, list)
    tool_result = next(b for b in content_blocks if b.get("type") == "tool_result")
    feedback_text = tool_result["content"]
    # Spec D4 verbatim contract:
    assert "findings" in feedback_text
    assert "your text" in feedback_text.lower() or "Your text" in feedback_text
    # Excerpt of the offending text appears in feedback (first 200 chars).
    assert "processing of personal data" in feedback_text
