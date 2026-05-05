"""Unit tests for agents/analyst.py — LLM-backed Analyst with tool use."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.agents.analyst import AnalystAgent, _strip_unsupported_schema_fields
from regulaitor.citation.schemas import Answer, Context, RetrievedChunk
from regulaitor.models.router import CompletionResult, Usage


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="Un sistema de IA se considerará de alto riesgo cuando...",
        score=0.95,
        version="32024R1689",
        source_url="https://eur-lex.europa.eu/...",
    )


def _make_context() -> Context:
    from datetime import UTC, datetime

    return Context(
        query="alto riesgo",
        corpus="ai_act",
        language="es",
        chunks=[_make_chunk()],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3",
    )


def _make_completion_result_with_answer() -> CompletionResult:
    """Mock LLM emits a valid Answer via tool_use."""
    citation = {
        "norma": "ai_act",
        "articulo": "6",
        "apartado": "1",
        "language": "es",
        "text": "Un sistema de IA se considerará de alto riesgo cuando...",
    }
    finding = {"text": "El AI Act define alto riesgo.", "citations": [citation], "severity": "info"}
    answer_dict = {
        "query": "alto riesgo",
        "language": "es",
        "text": "El AI Act trata los sistemas de alto riesgo en el Art. 6.",
        "findings": [finding],
    }
    return CompletionResult(
        text=None,
        tool_use_input=answer_dict,
        usage=Usage(input_tokens=1000, output_tokens=500),
        model_id="claude-sonnet-4-6",
        latency_ms=2500,
        cost_eur=0.018,
    )


def test_analyze_returns_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.agents import analyst

    complete_mock = MagicMock(return_value=_make_completion_result_with_answer())
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    answer = agent.analyze(query="alto riesgo", context=_make_context())

    assert isinstance(answer, Answer)
    assert answer.query == "alto riesgo"
    assert answer.language == "es"
    assert len(answer.findings) == 1
    assert answer.findings[0].citations[0].norma == "ai_act"


def test_analyze_calls_router_with_tool_use_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from regulaitor.agents import analyst

    complete_mock = MagicMock(return_value=_make_completion_result_with_answer())
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    agent.analyze(query="alto riesgo", context=_make_context())

    call_kwargs = complete_mock.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "emit_answer"}
    assert call_kwargs["tools"][0]["name"] == "emit_answer"
    assert "input_schema" in call_kwargs["tools"][0]


def test_analyze_raises_when_no_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.agents import analyst

    no_tool_result = CompletionResult(
        text="prose response",
        tool_use_input=None,
        usage=Usage(input_tokens=100, output_tokens=50),
        model_id="claude-sonnet-4-6",
        latency_ms=500,
        cost_eur=0.001,
    )
    monkeypatch.setattr(analyst.router, "complete", MagicMock(return_value=no_tool_result))

    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="emit_answer"):
        agent.analyze(query="q", context=_make_context())


def test_analyze_loads_versioned_prompt() -> None:
    """AnalystAgent should load the prompt file matching prompt_version."""
    agent = AnalystAgent(prompt_version="v1.0")
    assert "RegulAItor's Analyst" in agent._system_prompt
    assert (
        "no citation, no answer" in agent._system_prompt.lower()
        or "Hard rules" in agent._system_prompt
    )


def test_analyze_raises_on_malformed_tool_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """If LLM emits tool_use_input missing required fields, raise RuntimeError with context."""
    from regulaitor.agents import analyst

    malformed_result = CompletionResult(
        text=None,
        tool_use_input={"query": "x"},  # missing language, text, findings
        usage=Usage(input_tokens=100, output_tokens=50),
        model_id="claude-sonnet-4-6",
        latency_ms=500,
        cost_eur=0.001,
    )
    monkeypatch.setattr(analyst.router, "complete", MagicMock(return_value=malformed_result))

    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="malformed"):
        agent.analyze(query="q", context=_make_context())


def test_strip_schema_hard_sets_additional_properties_false() -> None:
    """_strip_unsupported_schema_fields must hard-set additionalProperties=False, even if True."""
    result = _strip_unsupported_schema_fields({"additionalProperties": True, "type": "object"})
    assert result["additionalProperties"] is False


def test_init_rejects_path_traversal() -> None:
    """AnalystAgent must reject prompt_version values that could enable path traversal."""
    with pytest.raises(ValueError):
        AnalystAgent(prompt_version="../../etc/passwd")
