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


def test_strip_schema_sets_additional_properties_false_recursive_in_defs() -> None:
    """v0.1.22 regression guard: every object-typed subschema (root + $defs + nested
    properties) must have additionalProperties=False. Pre-fix, the function only
    set the root flag; nested $defs (Finding, Citation) shipped without the
    flag, causing Anthropic strict mode (Capa A) to reject the tool with
    ``400 invalid_request_error: For 'object' type, 'additionalProperties' must
    be explicitly set to false``. Shipped silently broken in v0.1.21 (T0 probe
    used a trivial schema; missed nested-object case). See ADR-0029 §22.22.
    """
    # Schema with a $defs entry that is itself an object type.
    schema = {
        "type": "object",
        "properties": {
            "findings": {"type": "array", "items": {"$ref": "#/$defs/Finding"}},
        },
        "$defs": {
            "Finding": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/Citation"},
                    },
                },
            },
            "Citation": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
        },
    }
    result = _strip_unsupported_schema_fields(schema)
    assert result["additionalProperties"] is False
    assert result["$defs"]["Finding"]["additionalProperties"] is False
    assert result["$defs"]["Citation"]["additionalProperties"] is False


def test_strip_schema_does_not_set_on_non_object_subschemas() -> None:
    """The recursive walker must only set additionalProperties on object types;
    array, string, integer, etc. types must remain untouched (additionalProperties
    on a non-object is nonsensical and could confuse downstream validators)."""
    schema = {
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string"}},
            "count": {"type": "integer"},
        },
    }
    result = _strip_unsupported_schema_fields(schema)
    assert result["additionalProperties"] is False
    assert "additionalProperties" not in result["properties"]["tags"]
    assert "additionalProperties" not in result["properties"]["tags"]["items"]
    assert "additionalProperties" not in result["properties"]["count"]


def test_strip_schema_does_not_mutate_input() -> None:
    """The walker returns a deep-copy; the original schema dict must be unchanged
    (defense against shared schema dicts referenced from Pydantic class state)."""
    original = {
        "type": "object",
        "$defs": {"Finding": {"type": "object", "properties": {}}},
    }
    import copy

    snapshot = copy.deepcopy(original)
    _strip_unsupported_schema_fields(original)
    assert original == snapshot


def test_init_rejects_path_traversal() -> None:
    """AnalystAgent must reject prompt_version values that could enable path traversal."""
    with pytest.raises(ValueError):
        AnalystAgent(prompt_version="../../etc/passwd")


# ---------------------------------------------------------------------------
# H8 fix: retry-once on `findings` missing (analyst.py:79 docstring)
# ---------------------------------------------------------------------------


def _make_completion_result_missing_findings() -> CompletionResult:
    """Mock LLM emits tool_use_input WITHOUT the findings field (the H8 bug)."""
    return CompletionResult(
        text=None,
        tool_use_input={
            "query": "alto riesgo",
            "language": "es",
            "text": "El AI Act trata los sistemas de alto riesgo.",
            # findings field omitted (the bug)
        },
        usage=Usage(input_tokens=1000, output_tokens=500),
        model_id="claude-sonnet-4-6",
        latency_ms=2500,
        cost_eur=0.018,
    )


def test_analyze_retries_once_when_findings_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """First response omits `findings` -> retry once with tool_result error -> accept."""
    from regulaitor.agents import analyst

    complete_mock = MagicMock(
        side_effect=[
            _make_completion_result_missing_findings(),
            _make_completion_result_with_answer(),
        ]
    )
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    answer = agent.analyze(query="alto riesgo", context=_make_context())

    assert isinstance(answer, Answer)
    assert len(answer.findings) == 1
    assert complete_mock.call_count == 2

    second_messages = complete_mock.call_args_list[1].kwargs["messages"]
    assert len(second_messages) == 3, "retry should append assistant tool_use + user tool_result"
    assert second_messages[1]["role"] == "assistant"
    assert second_messages[1]["content"][0]["type"] == "tool_use"
    assert second_messages[2]["role"] == "user"
    tool_result = second_messages[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["is_error"] is True
    assert "findings" in tool_result["content"]


def test_analyze_no_retry_when_other_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.21 (Capa C): retry on ANY ValidationError up to MAX_ATTEMPTS=3.

    Pre-v0.1.21 contract: if validation errors included fields other than
    findings, do NOT retry. v0.1.21 contract: catch ANY ValidationError
    (including missing fields beyond findings) and retry with failure-specific
    feedback up to 3 attempts total.
    """
    from regulaitor.agents import analyst

    malformed = CompletionResult(
        text=None,
        tool_use_input={"query": "x"},  # missing language, text, AND findings
        usage=Usage(input_tokens=100, output_tokens=50),
        model_id="claude-sonnet-4-6",
        latency_ms=500,
        cost_eur=0.001,
    )
    complete_mock = MagicMock(return_value=malformed)
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="malformed Answer"):
        agent.analyze(query="q", context=_make_context())

    # v0.1.21: now retries up to 3 times on ANY ValidationError.
    assert complete_mock.call_count == 3, "v0.1.21 retries 3x on any validation error"


def test_analyze_raises_after_two_failed_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """v0.1.21 (Capa C): after 3 attempts, raise RuntimeError with 'after N retries' marker."""
    from regulaitor.agents import analyst

    complete_mock = MagicMock(
        side_effect=[
            _make_completion_result_missing_findings(),
            _make_completion_result_missing_findings(),
            _make_completion_result_missing_findings(),
        ]
    )
    monkeypatch.setattr(analyst.router, "complete", complete_mock)

    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="malformed Answer after 2 retries"):
        agent.analyze(query="q", context=_make_context())

    # v0.1.21: now attempts 3 times before giving up.
    assert complete_mock.call_count == 3
