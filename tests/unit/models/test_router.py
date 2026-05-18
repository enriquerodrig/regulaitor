"""Unit tests for models/router.py — single entry point with Anthropic backend."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from regulaitor.models import router
from regulaitor.models.config import ANTHROPIC_SONNET_4_6, GROQ_LLAMA_70B, OPENAI_GPT_4O
from regulaitor.models.router import CompletionResult


def _client_returning(resp: object) -> object:
    """Minimal OpenAI-compatible client stub returning *resp* from create().

    One helper for both providers: the production seam (_call_openai_compatible)
    is itself OpenAI-compatible, so a single stub mirrors it for OpenAI and Groq
    (the call site picks which via monkeypatch of _openai_client/_groq_client)."""

    class _Client:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**_kwargs: object) -> object:
                    return resp

    return _Client()


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


def test_resolve_mode_passthrough_when_env_unset(monkeypatch) -> None:
    from regulaitor.models import router as r

    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    assert r._resolve_mode("default") == "default"
    assert r._resolve_mode("quality") == "quality"


def test_resolve_mode_env_override(monkeypatch) -> None:
    from regulaitor.models import router as r

    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "evaluation")
    assert r._resolve_mode("default") == "evaluation"


def test_resolve_mode_invalid_env_ignored_with_warning(monkeypatch, caplog) -> None:
    import logging

    from regulaitor.models import router as r

    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "bogus")
    with caplog.at_level(logging.WARNING, logger="regulaitor.models.router"):
        assert r._resolve_mode("default") == "default"
    assert "REGULAITOR_ROUTER_MODE" in caplog.text


def test_default_still_routes_to_anthropic_sonnet(monkeypatch) -> None:
    """Regression-zero: env unset + default => Anthropic Sonnet, unchanged."""
    from regulaitor.models import router as r
    from regulaitor.models.config import ANTHROPIC_SONNET_4_6

    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    captured: dict = {}

    def _fake_anthropic(*, model_id, messages, system, tools, tool_choice, max_tokens):
        captured["model_id"] = model_id
        return r.CompletionResult(
            text="ok",
            tool_use_input=None,
            usage=r.Usage(input_tokens=1, output_tokens=1),
            model_id=model_id,
            latency_ms=1,
            cost_eur=0.0,
        )

    monkeypatch.setattr(r, "_call_anthropic", _fake_anthropic)
    out = r.complete(messages=[{"role": "user", "content": "x"}], system="s")
    assert captured["model_id"] == ANTHROPIC_SONNET_4_6
    assert out.text == "ok"


def test_call_openai_returns_completion_result(monkeypatch) -> None:
    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": []}'

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 4

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(router, "_openai_client", lambda: _client_returning(_Resp()))
    out = router._call_openai(
        model_id=OPENAI_GPT_4O,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=[{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
        max_tokens=100,
    )
    assert out.model_id == OPENAI_GPT_4O
    assert out.tool_use_input == {"findings": []}
    assert out.usage.input_tokens == 10
    assert out.usage.output_tokens == 4
    assert out.cost_eur > 0.0


def test_openai_client_missing_key_fails_fast(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        router._openai_client()


def test_call_openai_non_dict_tool_args_raises(monkeypatch) -> None:
    """I1 guard: model returning JSON-valid but non-object tool args (e.g.
    '[]') must raise a clear router-level RuntimeError, not silently pass a
    list to the Analyst (the Anthropic path's dict(block.input) can't do this)."""

    class _Fn:
        name = "emit_answer"
        arguments = "[]"  # valid JSON, not an object

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 1
        completion_tokens = 1

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(router, "_openai_client", lambda: _client_returning(_Resp()))
    with pytest.raises(RuntimeError, match="tool-call arguments"):
        router._call_openai(
            model_id=OPENAI_GPT_4O,
            messages=[{"role": "user", "content": "q"}],
            system="s",
            tools=None,
            tool_choice=None,
            max_tokens=10,
        )


def test_call_openai_malformed_json_args_raises(monkeypatch) -> None:
    """I2 guard: malformed/truncated tool-call JSON -> clear terminal
    RuntimeError (NOT a raw json.JSONDecodeError, NOT retried)."""

    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": ['  # truncated, invalid JSON

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Usage:
        prompt_tokens = 1
        completion_tokens = 1

    class _Resp:
        choices = [type("Ch", (), {"message": _Msg()})()]
        usage = _Usage()

    monkeypatch.setattr(router, "_openai_client", lambda: _client_returning(_Resp()))
    with pytest.raises(RuntimeError, match="malformed"):
        router._call_openai(
            model_id=OPENAI_GPT_4O,
            messages=[{"role": "user", "content": "q"}],
            system="s",
            tools=None,
            tool_choice=None,
            max_tokens=10,
        )


# ---------------------------------------------------------------------------
# Groq tests (symmetric to OpenAI; exercise _call_groq + shared _call_openai_compatible)
# ---------------------------------------------------------------------------


def test_call_groq_returns_completion_result(monkeypatch) -> None:
    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": []}'

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 4

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(router, "_groq_client", lambda: _client_returning(_Resp()))
    out = router._call_groq(
        model_id=GROQ_LLAMA_70B,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=[{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
        max_tokens=100,
    )
    assert out.model_id == GROQ_LLAMA_70B
    assert out.tool_use_input == {"findings": []}
    assert out.usage.input_tokens == 10
    assert out.usage.output_tokens == 4
    assert out.cost_eur > 0.0


def test_groq_client_missing_key_fails_fast(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        router._groq_client()


def test_call_groq_non_dict_tool_args_raises(monkeypatch) -> None:
    """I1 guard inherited via shared helper: Groq returning '[]' -> clear RuntimeError."""

    class _Fn:
        name = "emit_answer"
        arguments = "[]"  # valid JSON, not an object

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 1
        completion_tokens = 1

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(router, "_groq_client", lambda: _client_returning(_Resp()))
    with pytest.raises(RuntimeError, match="tool-call arguments"):
        router._call_groq(
            model_id=GROQ_LLAMA_70B,
            messages=[{"role": "user", "content": "q"}],
            system="s",
            tools=None,
            tool_choice=None,
            max_tokens=10,
        )


def test_call_groq_malformed_json_args_raises(monkeypatch) -> None:
    """I2 guard inherited via shared helper: Groq returning truncated JSON -> clear RuntimeError."""

    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": ['  # truncated, invalid JSON

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Usage:
        prompt_tokens = 1
        completion_tokens = 1

    class _Resp:
        choices = [type("Ch", (), {"message": _Msg()})()]
        usage = _Usage()

    monkeypatch.setattr(router, "_groq_client", lambda: _client_returning(_Resp()))
    with pytest.raises(RuntimeError, match="malformed"):
        router._call_groq(
            model_id=GROQ_LLAMA_70B,
            messages=[{"role": "user", "content": "q"}],
            system="s",
            tools=None,
            tool_choice=None,
            max_tokens=10,
        )


# ---------------------------------------------------------------------------
# Task 7 — 5-mode dispatch + controlled one-hop fallback
# ---------------------------------------------------------------------------


def _stub_result(model_id: str) -> router.CompletionResult:
    return router.CompletionResult(
        text="ok",
        tool_use_input=None,
        usage=router.Usage(input_tokens=1, output_tokens=1),
        model_id=model_id,
        latency_ms=1,
        cost_eur=0.0,
    )


def test_each_mode_dispatches_to_right_provider(monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        router,
        "_call_anthropic",
        lambda **k: (seen.append("anthropic"), _stub_result(k["model_id"]))[1],
    )
    monkeypatch.setattr(
        router,
        "_call_openai",
        lambda **k: (seen.append("openai"), _stub_result(k["model_id"]))[1],
    )
    monkeypatch.setattr(
        router,
        "_call_groq",
        lambda **k: (seen.append("groq"), _stub_result(k["model_id"]))[1],
    )
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    for mc, prov in [
        ("default", "anthropic"),
        ("quality", "anthropic"),
        ("cost", "groq"),
        ("evaluation", "openai"),
        ("fallback", "openai"),
    ]:
        seen.clear()
        router.complete(
            messages=[{"role": "user", "content": "x"}],
            system="s",
            model_choice=mc,  # type: ignore[arg-type]
        )
        assert seen == [prov], mc


def _make_groq_conn_err() -> Exception:
    """Construct a GroqConnErr (transport error) for fallback-path tests."""
    from regulaitor.models.router import GroqConnErr

    return GroqConnErr(
        message="stub connection error",
        request=httpx.Request("POST", "https://api.groq.com/v1/chat/completions"),
    )


def test_controlled_fallback_one_hop(monkeypatch, caplog) -> None:
    from regulaitor.models.config import OPENAI_GPT_4O_MINI

    calls: list[str] = []
    transport_err = _make_groq_conn_err()

    def _boom(**k):
        calls.append("primary")
        raise transport_err

    def _fallback(**k):
        calls.append("fallback")
        return _stub_result(k["model_id"])

    monkeypatch.setattr(router, "_call_groq", _boom)  # 'cost' primary
    monkeypatch.setattr(router, "_call_openai", _fallback)  # 'fallback' target
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    with caplog.at_level(logging.INFO, logger="regulaitor.models.router"):
        out = router.complete(
            messages=[{"role": "user", "content": "x"}],
            system="s",
            model_choice="cost",
        )
    assert calls == ["primary", "fallback"]
    assert out.model_id == OPENAI_GPT_4O_MINI
    assert "fallback_used=true" in caplog.text


def test_fallback_also_fails_raises_original(monkeypatch) -> None:
    transport_err = _make_groq_conn_err()

    def _boom(**k):
        raise transport_err

    def _boom2(**k):
        raise RuntimeError("fallback down too")

    monkeypatch.setattr(router, "_call_groq", _boom)
    monkeypatch.setattr(router, "_call_openai", _boom2)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    # Original (primary) transport error must surface, not the fallback one.
    with pytest.raises(type(transport_err)):
        router.complete(
            messages=[{"role": "user", "content": "x"}],
            system="s",
            model_choice="cost",
        )


def test_fallback_mode_failure_not_recursed(monkeypatch) -> None:
    """If the caller's mode IS 'fallback' and it fails, do NOT recurse into
    another fallback hop — the original error propagates.

    With the narrowed _FALLBACKABLE_ERRORS catch, a RuntimeError from the
    'fallback' mode is NOT caught by the except clause at all (it's not in
    _FALLBACKABLE_ERRORS), so it propagates directly without entering the guard.
    The test still passes with the same assertion.
    """

    def _boom(**k):
        raise RuntimeError("fallback provider down")

    monkeypatch.setattr(router, "_call_openai", _boom)  # 'fallback' -> openai
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    with pytest.raises(RuntimeError, match="fallback provider down"):
        router.complete(
            messages=[{"role": "user", "content": "x"}],
            system="s",
            model_choice="fallback",
        )


# ---------------------------------------------------------------------------
# I-1 narrowing: new pinning tests (post-review)
# ---------------------------------------------------------------------------


def test_fallback_not_triggered_on_bad_request(monkeypatch) -> None:
    """I-1: anthropic.BadRequestError (400) is deterministic — must NOT trigger
    the controlled fallback. It must propagate, and _call_openai (fallback target)
    must never be called."""
    err = _make_anthropic_error(anthropic.BadRequestError, status=400)
    openai_calls: list[str] = []

    def _raise_bad_request(**k):
        raise err

    def _record_openai(**k):
        openai_calls.append("called")
        return _stub_result(k["model_id"])

    monkeypatch.setattr(router, "_call_anthropic", _raise_bad_request)
    monkeypatch.setattr(router, "_call_openai", _record_openai)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)

    with pytest.raises(anthropic.BadRequestError):
        router.complete(
            messages=[{"role": "user", "content": "x"}],
            system="s",
            model_choice="default",  # Anthropic primary
        )
    # Fallback (OpenAI) must not have been called.
    assert openai_calls == [], "fallback must NOT fire on a deterministic BadRequestError"


def test_fallback_triggered_on_transport_error(monkeypatch) -> None:
    """I-1 positive: a genuine transport error (GroqRateErr) surviving tenacity
    MUST still trigger the one-hop fallback to GPT-4o-mini."""
    from regulaitor.models.config import OPENAI_GPT_4O_MINI
    from regulaitor.models.router import GroqRateErr

    transport_err = GroqRateErr(
        message="stub rate limit",
        response=httpx.Response(
            status_code=429,
            request=httpx.Request("POST", "https://api.groq.com/v1/chat/completions"),
        ),
        body=None,
    )
    openai_calls: list[str] = []

    def _raise_groq(**k):
        raise transport_err

    def _record_openai(**k):
        openai_calls.append("called")
        return _stub_result(k["model_id"])

    monkeypatch.setattr(router, "_call_groq", _raise_groq)  # 'cost' -> groq
    monkeypatch.setattr(router, "_call_openai", _record_openai)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)

    out = router.complete(
        messages=[{"role": "user", "content": "x"}],
        system="s",
        model_choice="cost",
    )
    assert openai_calls == ["called"], "fallback MUST fire on a transport GroqRateErr"
    assert out.model_id == OPENAI_GPT_4O_MINI


# ---------------------------------------------------------------------------
# H13 judge mode
# ---------------------------------------------------------------------------


def test_judge_mode_resolves_to_haiku() -> None:
    from regulaitor.models import config, router

    assert "judge" in router._VALID_MODES
    pm = router._MODE_MAP["judge"]
    assert pm.provider == router.PROVIDER_ANTHROPIC
    assert pm.model_id == config.ANTHROPIC_HAIKU_4_5


def test_five_existing_modes_unchanged() -> None:
    from regulaitor.models import config, router

    assert router._MODE_MAP["default"].model_id == config.ANTHROPIC_SONNET_4_6
    assert router._MODE_MAP["quality"].model_id == config.ANTHROPIC_SONNET_4_6
    assert router._MODE_MAP["evaluation"].model_id == config.OPENAI_GPT_4O
    assert router._MODE_MAP["cost"].model_id == config.GROQ_LLAMA_70B
    assert router._MODE_MAP["fallback"].model_id == config.OPENAI_GPT_4O_MINI
