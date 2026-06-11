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


def test_key_func_uses_tenant_when_present() -> None:
    """Fase 4: per-tenant key (isolated bucket) takes precedence over token_hash."""
    request = _request_with_state(
        SimpleNamespace(tenant=SimpleNamespace(tenant_id="acme"), token_hash="a1b2c3d4")
    )
    assert rate_limit._key_func(request) == "tenant:acme"


def test_ask_limit_resolves_per_tenant_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fase 4: slowapi passes key_func(request) to the limit callable; it resolves
    the tenant's configured limit, falling back to env when not a tenant key."""
    import json

    from regulaitor.security import tenancy

    for k in ("REGULAITOR_TENANTS_FILE", "REGULAITOR_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps(
            [
                {
                    "token": "tok_" + "a" * 20,
                    "tenant_id": "acme",
                    "name": "Acme",
                    "rate_limit_ask": "60/minute",
                    "rate_limit_analyze": "12/minute",
                }
            ]
        ),
    )
    tenancy.load_tenants_or_raise()
    try:
        assert rate_limit.ask_limit("tenant:acme") == "60/minute"
        assert rate_limit.analyze_limit("tenant:acme") == "12/minute"
        # unknown tenant id / non-tenant key -> env fallback
        monkeypatch.setenv("REGULAITOR_RATE_LIMIT_ASK", "7/minute")
        assert rate_limit.ask_limit("token:abc") == "7/minute"
        assert rate_limit.ask_limit("tenant:nope") == "7/minute"
    finally:
        tenancy._reset()


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


def test_safe_env_limit_falls_back_on_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review RL-1: a malformed env limit must NOT reach slowapi (it would fail-open);
    ask_limit falls back to the valid default instead."""
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_ASK", "garbage")
    # non-tenant key -> env path -> malformed -> safe default
    assert rate_limit.ask_limit("token:abc") == "30/minute"
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_ASK", "45/minute")
    assert rate_limit.ask_limit("token:abc") == "45/minute"


def test_limiter_instance_exists() -> None:
    assert rate_limit.limiter is not None
