"""Unit tests for models/_translate.py (Anthropic<->OpenAI tool/msg)."""

from __future__ import annotations

import json

from regulaitor.models import _translate as t


def test_tools_anthropic_to_openai() -> None:
    anthropic = [{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}]
    out = t.tools_to_openai(anthropic)
    assert out == [
        {
            "type": "function",
            "function": {
                "name": "emit_answer",
                "description": "d",
                "parameters": {"type": "object"},
            },
        }
    ]


def test_tool_choice_anthropic_to_openai() -> None:
    assert t.tool_choice_to_openai({"type": "tool", "name": "emit_answer"}) == {
        "type": "function",
        "function": {"name": "emit_answer"},
    }
    assert t.tool_choice_to_openai(None) is None


def test_messages_plain_text() -> None:
    msgs = [{"role": "user", "content": "hello"}]
    assert t.messages_to_openai(msgs, system="sys") == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]


def test_messages_h8_retry_blocks_round_trip() -> None:
    msgs = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tid", "name": "emit_answer", "input": {"a": 1}}
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tid",
                    "content": "missing findings",
                    "is_error": True,
                }
            ],
        },
    ]
    out = t.messages_to_openai(msgs, system="sys")
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1] == {"role": "user", "content": "q"}
    assert out[2]["role"] == "assistant"
    assert out[2]["tool_calls"][0]["id"] == "tid"
    assert out[2]["tool_calls"][0]["type"] == "function"
    assert out[2]["tool_calls"][0]["function"]["name"] == "emit_answer"
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"a": 1}
    assert out[3] == {"role": "tool", "tool_call_id": "tid", "content": "missing findings"}


def test_extract_tool_use_input_from_openai_response() -> None:
    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": []}'

    class _TC:
        id = "tid"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    text, tui = t.extract_openai_tool_use(_Resp())
    assert text is None
    assert tui == {"findings": []}


def test_extract_text_when_no_tool_call() -> None:
    class _Msg:
        content = "plain answer"
        tool_calls = None

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    text, tui = t.extract_openai_tool_use(_Resp())
    assert text == "plain answer"
    assert tui is None


def test_messages_unrecognized_block_type_raises() -> None:
    """Security-critical: an unknown block type must NOT be silently dropped."""
    import pytest

    msgs = [{"role": "user", "content": [{"type": "image", "data": "x"}]}]
    with pytest.raises(ValueError, match="unrecognized Anthropic block type"):
        t.messages_to_openai(msgs, system="sys")
