"""Unit tests for models/router.py — single entry point with Anthropic backend."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.models import router
from regulaitor.models.config import ANTHROPIC_SONNET_4_6
from regulaitor.models.router import CompletionResult


@pytest.fixture
def mock_anthropic_response() -> MagicMock:
    """Mock an Anthropic Message response with one tool_use block."""
    response = MagicMock()
    response.content = [
        MagicMock(type="tool_use", input={"key": "value"}, name="emit_answer"),
    ]
    response.usage = MagicMock(input_tokens=1000, output_tokens=500)
    response.model = ANTHROPIC_SONNET_4_6
    return response


@pytest.fixture
def mock_anthropic_text_response() -> MagicMock:
    """Mock an Anthropic Message response with one text block (no tool)."""
    response = MagicMock()
    text_block = MagicMock(type="text", text="hello")
    response.content = [text_block]
    response.usage = MagicMock(input_tokens=100, output_tokens=50)
    response.model = ANTHROPIC_SONNET_4_6
    return response


def test_complete_with_tool_use_returns_tool_input(
    monkeypatch: pytest.MonkeyPatch, mock_anthropic_response: MagicMock
) -> None:
    client_mock = MagicMock()
    client_mock.messages.create.return_value = mock_anthropic_response
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    result = router.complete(
        messages=[{"role": "user", "content": "hi"}],
        system="you are helpful",
        tools=[{"name": "emit_answer", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
    )

    assert isinstance(result, CompletionResult)
    assert result.tool_use_input == {"key": "value"}
    assert result.text is None
    assert result.usage.input_tokens == 1000
    assert result.usage.output_tokens == 500
    assert result.model_id == ANTHROPIC_SONNET_4_6
    assert result.cost_eur > 0
    assert result.latency_ms >= 0


def test_complete_with_text_response(
    monkeypatch: pytest.MonkeyPatch, mock_anthropic_text_response: MagicMock
) -> None:
    client_mock = MagicMock()
    client_mock.messages.create.return_value = mock_anthropic_text_response
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    result = router.complete(
        messages=[{"role": "user", "content": "hi"}],
        system="you are helpful",
    )

    assert result.text == "hello"
    assert result.tool_use_input is None


def test_complete_unsupported_model_choice_raises() -> None:
    with pytest.raises(NotImplementedError, match="model_choice="):
        router.complete(
            messages=[{"role": "user", "content": "hi"}],
            system="s",
            model_choice="cost",  # type: ignore[arg-type]
        )


def test_complete_forwards_tool_choice(
    monkeypatch: pytest.MonkeyPatch, mock_anthropic_response: MagicMock
) -> None:
    client_mock = MagicMock()
    client_mock.messages.create.return_value = mock_anthropic_response
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    router.complete(
        messages=[{"role": "user", "content": "hi"}],
        system="s",
        tools=[{"name": "emit_answer", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
    )

    call_kwargs = client_mock.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "emit_answer"}


def test_complete_max_tokens_default_2000(
    monkeypatch: pytest.MonkeyPatch, mock_anthropic_response: MagicMock
) -> None:
    client_mock = MagicMock()
    client_mock.messages.create.return_value = mock_anthropic_response
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    router.complete(messages=[{"role": "user", "content": "hi"}], system="s")

    call_kwargs = client_mock.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 2000


def test_complete_max_tokens_overridable(
    monkeypatch: pytest.MonkeyPatch, mock_anthropic_response: MagicMock
) -> None:
    client_mock = MagicMock()
    client_mock.messages.create.return_value = mock_anthropic_response
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    router.complete(messages=[{"role": "user", "content": "hi"}], system="s", max_tokens=500)

    call_kwargs = client_mock.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 500
