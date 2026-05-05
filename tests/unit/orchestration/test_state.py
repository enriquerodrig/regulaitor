"""Unit tests for orchestration/state.py — ChatState Pydantic BaseModel."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulaitor.orchestration.state import ChatState


def test_chat_state_minimum_valid() -> None:
    state = ChatState(case_id="ch-1", query="q", corpus="ai_act", language="es")
    assert state.case_id == "ch-1"
    assert state.context is None
    assert state.answer is None
    assert state.audited_answer is None
    assert state.injection_blocked is False
    assert state.injection_reason is None
    assert state.errors == []


def test_chat_state_rejects_empty_case_id() -> None:
    with pytest.raises(ValidationError):
        ChatState(case_id="", query="q", corpus="ai_act", language="es")


def test_chat_state_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        ChatState(case_id="ch-1", query="", corpus="ai_act", language="es")


def test_chat_state_serializable() -> None:
    state = ChatState(case_id="ch-1", query="q", corpus="ai_act", language="es")
    json_str = state.model_dump_json()
    parsed = ChatState.model_validate_json(json_str)
    assert parsed == state
