"""Unit tests for the router 'self_hosted' mode (probe R1).

The mode routes the Analyst to an open-source model on an OpenAI-compatible
endpoint (Mistral La Plateforme now; OVH/Scaleway/vLLM later). It reuses the
existing _call_openai_compatible path (incl. I1/I2 malformed-tool-call guards)
and is deliberately EXCLUDED from the controlled fallback so a sovereign run
never gets silently answered by the US-hosted GPT-4o-mini fallback.
"""

from __future__ import annotations

import httpx
import pytest

from regulaitor.models import router
from regulaitor.models.config import MISTRAL_SMALL, OPENAI_GPT_4O


def _client_returning(resp: object) -> object:
    """Minimal OpenAI-compatible client stub (mirrors test_router.py)."""

    class _Client:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**_kwargs: object) -> object:
                    return resp

    return _Client()


def _tool_call_resp(args: str = '{"findings": []}') -> object:
    class _Fn:
        name = "emit_answer"
        arguments = args

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

    return _Resp()


def _stub_result(model_id: str) -> router.CompletionResult:
    return router.CompletionResult(
        text="ok",
        tool_use_input=None,
        usage=router.Usage(input_tokens=1, output_tokens=1),
        model_id=model_id,
        latency_ms=1,
        cost_eur=0.0,
    )


# --- mode wiring -----------------------------------------------------------


def test_self_hosted_is_valid_mode() -> None:
    assert "self_hosted" in router._VALID_MODES


def test_self_hosted_maps_to_selfhost_provider_and_mistral() -> None:
    pm = router._MODE_MAP["self_hosted"]
    assert pm.provider == router.PROVIDER_SELFHOST
    assert pm.model_id == MISTRAL_SMALL


def test_six_existing_modes_unchanged() -> None:
    """Regression-zero: adding self_hosted leaves the prior 6 modes intact."""
    from regulaitor.models import config

    assert router._MODE_MAP["default"].model_id == config.ANTHROPIC_SONNET_4_6
    assert router._MODE_MAP["quality"].model_id == config.ANTHROPIC_SONNET_4_6
    assert router._MODE_MAP["evaluation"].model_id == config.OPENAI_GPT_4O
    assert router._MODE_MAP["cost"].model_id == config.GROQ_LLAMA_70B
    assert router._MODE_MAP["fallback"].model_id == config.OPENAI_GPT_4O_MINI
    assert router._MODE_MAP["judge"].model_id == config.ANTHROPIC_HAIKU_4_5


# --- _selfhost_client fail-fast --------------------------------------------


def test_selfhost_client_missing_base_url_fails_fast(monkeypatch) -> None:
    monkeypatch.delenv("REGULAITOR_SELFHOST_BASE_URL", raising=False)
    monkeypatch.setenv("REGULAITOR_SELFHOST_API_KEY", "k")
    with pytest.raises(RuntimeError, match="REGULAITOR_SELFHOST_BASE_URL"):
        router._selfhost_client()


def test_selfhost_client_missing_key_fails_fast(monkeypatch) -> None:
    monkeypatch.setenv("REGULAITOR_SELFHOST_BASE_URL", "https://api.mistral.ai/v1")
    monkeypatch.delenv("REGULAITOR_SELFHOST_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="REGULAITOR_SELFHOST_API_KEY"):
        router._selfhost_client()


def test_selfhost_client_constructs_with_base_url(monkeypatch) -> None:
    import openai

    monkeypatch.setenv("REGULAITOR_SELFHOST_BASE_URL", "https://api.mistral.ai/v1")
    monkeypatch.setenv("REGULAITOR_SELFHOST_API_KEY", "k")
    client = router._selfhost_client()
    assert isinstance(client, openai.OpenAI)
    assert "api.mistral.ai" in str(client.base_url)


# --- _call_selfhost via the shared OpenAI-compatible path ------------------


def test_call_selfhost_returns_completion_result(monkeypatch) -> None:
    monkeypatch.delenv("REGULAITOR_SELFHOST_MODEL", raising=False)
    monkeypatch.setattr(router, "_selfhost_client", lambda: _client_returning(_tool_call_resp()))
    out = router._call_selfhost(
        model_id=MISTRAL_SMALL,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=[{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
        max_tokens=100,
    )
    assert out.model_id == MISTRAL_SMALL
    assert out.tool_use_input == {"findings": []}
    # MISTRAL_SMALL is in PRICING -> notional cost > 0 (free tier real spend $0).
    assert out.cost_eur > 0.0


def test_call_selfhost_env_model_override_unknown_pricing_zero_cost(monkeypatch) -> None:
    """REGULAITOR_SELFHOST_MODEL overrides the served model id; an id absent from
    PRICING reports cost 0.0 (tolerant cost_eur) rather than crashing."""
    monkeypatch.setenv("REGULAITOR_SELFHOST_MODEL", "ovh/Meta-Llama-3_3-70B")
    monkeypatch.setattr(router, "_selfhost_client", lambda: _client_returning(_tool_call_resp()))
    out = router._call_selfhost(
        model_id=MISTRAL_SMALL,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=None,
        tool_choice=None,
        max_tokens=10,
    )
    assert out.model_id == "ovh/Meta-Llama-3_3-70B"
    assert out.cost_eur == 0.0


def test_call_selfhost_records_cost_into_accumulator(monkeypatch) -> None:
    """The shared _call_openai_compatible call site wires _record_cost_eur."""
    monkeypatch.delenv("REGULAITOR_SELFHOST_MODEL", raising=False)
    router.reset_cost_accumulator()
    monkeypatch.setattr(router, "_selfhost_client", lambda: _client_returning(_tool_call_resp()))
    router._call_selfhost(
        model_id=MISTRAL_SMALL,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=None,
        tool_choice=None,
        max_tokens=10,
    )
    assert router.get_accumulated_cost_eur() > 0.0


# --- dispatch + no-fallback semantics --------------------------------------


def test_complete_self_hosted_dispatches_to_selfhost(monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        router,
        "_call_selfhost",
        lambda **k: (seen.append("selfhost"), _stub_result(k["model_id"]))[1],
    )
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    out = router.complete(
        messages=[{"role": "user", "content": "x"}],
        system="s",
        model_choice="self_hosted",
    )
    assert seen == ["selfhost"]
    assert out.model_id == MISTRAL_SMALL


def test_self_hosted_does_not_fall_back_to_us_model(monkeypatch) -> None:
    """A sovereign run must surface its own transport failure, NOT be silently
    answered by the US-hosted GPT-4o-mini fallback (contaminates probe + breaks
    the sovereignty guarantee)."""
    transport_err = router.OpenAIConnErr(
        message="stub connection error",
        request=httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions"),
    )
    openai_calls: list[str] = []

    def _raise(**k):
        raise transport_err

    def _record_openai(**k):
        openai_calls.append("called")
        return _stub_result(k["model_id"])

    monkeypatch.setattr(router, "_call_selfhost", _raise)
    monkeypatch.setattr(router, "_call_openai", _record_openai)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)

    with pytest.raises(router.OpenAIConnErr):
        router.complete(
            messages=[{"role": "user", "content": "x"}],
            system="s",
            model_choice="self_hosted",
        )
    assert openai_calls == [], "self_hosted must NOT fall back to the US model"


def test_other_modes_still_fall_back(monkeypatch) -> None:
    """Regression: narrowing the no-fallback set to {fallback, self_hosted} does
    NOT disable fallback for the still-fallbackable modes (e.g. 'cost')."""
    from regulaitor.models.config import OPENAI_GPT_4O_MINI

    transport_err = router.GroqConnErr(
        message="stub",
        request=httpx.Request("POST", "https://api.groq.com/v1/chat/completions"),
    )
    calls: list[str] = []

    def _boom(**k):
        calls.append("primary")
        raise transport_err

    def _fallback(**k):
        calls.append("fallback")
        return _stub_result(k["model_id"])

    monkeypatch.setattr(router, "_call_groq", _boom)
    monkeypatch.setattr(router, "_call_openai", _fallback)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    out = router.complete(
        messages=[{"role": "user", "content": "x"}],
        system="s",
        model_choice="cost",
    )
    assert calls == ["primary", "fallback"]
    assert out.model_id == OPENAI_GPT_4O_MINI


def test_self_hosted_via_global_router_mode_env(monkeypatch) -> None:
    """REGULAITOR_ROUTER_MODE=self_hosted also resolves (global override path)."""
    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "self_hosted")
    assert router._resolve_mode("default") == "self_hosted"
    # And an unrelated invalid id for OPENAI_GPT_4O constant stays importable.
    assert OPENAI_GPT_4O == "gpt-4o"
