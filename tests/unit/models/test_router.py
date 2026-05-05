"""Unit tests for models/router.py — single entry point with Anthropic backend."""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from regulaitor.models import router
from regulaitor.models.config import ANTHROPIC_SONNET_4_6
from regulaitor.models.router import CompletionResult


def _make_anthropic_error(cls: type[anthropic.APIStatusError], status: int) -> Exception:
    """Construct an anthropic APIStatusError subclass with a stub httpx.Response."""
    response = httpx.Response(
        status_code=status,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return cls(message=f"stub {status}", response=response, body=None)


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


def test_complete_raises_on_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Important 2: fail-fast at client construction when ANTHROPIC_API_KEY is unset."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
        router._anthropic_client()


def test_complete_concatenates_multiple_text_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Important 3: thinking + final answer text blocks must both be returned."""
    response = MagicMock()
    response.content = [
        MagicMock(type="text", text="thinking..."),
        MagicMock(type="text", text="answer"),
    ]
    response.usage = MagicMock(input_tokens=10, output_tokens=5)
    response.model = ANTHROPIC_SONNET_4_6

    client_mock = MagicMock()
    client_mock.messages.create.return_value = response
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    result = router.complete(messages=[{"role": "user", "content": "hi"}], system="s")

    assert result.text == "thinking...\nanswer"
    assert result.tool_use_input is None


def test_complete_no_retry_on_bad_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Important 1: BadRequestError (400) is NOT transient, must not retry."""
    err = _make_anthropic_error(anthropic.BadRequestError, status=400)
    client_mock = MagicMock()
    client_mock.messages.create.side_effect = err
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    with pytest.raises(anthropic.BadRequestError):
        router.complete(messages=[{"role": "user", "content": "hi"}], system="s")

    # No retry: filter rejects BadRequestError, so exactly 1 call.
    assert client_mock.messages.create.call_count == 1


def test_complete_retries_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch, mock_anthropic_response: MagicMock
) -> None:
    """Important 1 (positive): RateLimitError (429) IS transient, retry path runs."""
    # Patch sleep so wait_exponential does not slow the test.
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)

    err = _make_anthropic_error(anthropic.RateLimitError, status=429)
    client_mock = MagicMock()
    # First call raises RateLimitError, second call succeeds.
    client_mock.messages.create.side_effect = [err, mock_anthropic_response]
    monkeypatch.setattr(router, "_anthropic_client", lambda: client_mock)

    result = router.complete(messages=[{"role": "user", "content": "hi"}], system="s")

    assert isinstance(result, CompletionResult)
    assert client_mock.messages.create.call_count == 2
