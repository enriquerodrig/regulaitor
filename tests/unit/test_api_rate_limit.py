"""Unit tests for security.rate_limit — Limiter + key func."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from regulaitor.security import rate_limit


def _request_with_state(state: SimpleNamespace) -> SimpleNamespace:
    """Build a minimal request-like object with state and client attributes."""
    return SimpleNamespace(
        state=state,
        client=SimpleNamespace(host="10.0.0.1"),
        scope={"type": "http", "client": ("10.0.0.1", 12345), "headers": []},
        headers={},
    )


def test_key_func_uses_token_hash_when_present() -> None:
    request = _request_with_state(SimpleNamespace(token_hash="a1b2c3d4"))
    assert rate_limit._key_func(request) == "token:a1b2c3d4"


def test_key_func_falls_back_to_ip_without_token() -> None:
    request = _request_with_state(SimpleNamespace())
    key = rate_limit._key_func(request)
    assert key.startswith("ip:")


def test_is_disabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_RATE_LIMIT_DISABLED", raising=False)
    assert rate_limit._is_disabled() is False


def test_is_disabled_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    assert rate_limit._is_disabled() is True


def test_is_disabled_other_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "0")
    assert rate_limit._is_disabled() is False
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "yes")
    assert rate_limit._is_disabled() is False


def test_limiter_instance_exists() -> None:
    assert rate_limit.limiter is not None
