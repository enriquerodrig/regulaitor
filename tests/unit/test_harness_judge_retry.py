# tests/unit/test_harness_judge_retry.py
from __future__ import annotations

import httpx
import pytest
from anthropic._exceptions import OverloadedError
from evals import harness  # noqa: E402


class _FakeUsage:
    input_tokens = 11
    output_tokens = 7


class _FakeBlock:
    type = "text"
    text = "ok"


class _FakeResp:
    content = [_FakeBlock()]
    usage = _FakeUsage()


def _overloaded() -> OverloadedError:
    # Construct with a minimal real httpx.Response so the APIStatusError
    # constructor (which reads .status_code, .headers, .request) doesn't raise.
    # anthropic SDK 0.98.x does NOT re-export OverloadedError at the top-level
    # namespace; it lives in anthropic._exceptions and is imported from there.
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(status_code=529, request=req)
    return OverloadedError(message="Overloaded", response=resp, body=None)


def test_retries_transient_overloaded_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw: object) -> _FakeResp:
                calls["n"] += 1
                if calls["n"] < 3:
                    raise _overloaded()
                return _FakeResp()

    monkeypatch.setattr(harness, "_anthropic_client_factory", lambda: _Client(), raising=False)
    # Speed: tenacity.nap.sleep delegates to time.sleep; patch time.sleep so the
    # exponential backoff between retries is a no-op and the test runs instantly.
    monkeypatch.setattr("time.sleep", lambda _: None)
    text, ti, to = harness._real_anthropic_invoke(
        model="m", system="s", user="u", temperature=0.0, max_tokens=10
    )
    assert text == "ok" and ti == 11 and to == 7
    assert calls["n"] == 3  # retried twice, succeeded on the 3rd


def test_bounded_reraises_after_exhausting_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw: object) -> _FakeResp:
                calls["n"] += 1
                raise _overloaded()

    monkeypatch.setattr(harness, "_anthropic_client_factory", lambda: _Client(), raising=False)
    # Speed: tenacity.nap.sleep delegates to time.sleep; patch time.sleep so the
    # exponential backoff between retries is a no-op and the test runs instantly.
    monkeypatch.setattr("time.sleep", lambda _: None)
    with pytest.raises(OverloadedError):
        harness._real_anthropic_invoke(
            model="m", system="s", user="u", temperature=0.0, max_tokens=10
        )
    assert calls["n"] == 3  # bounded at stop_after_attempt(3)
