"""Integration tests for GET /health."""

from __future__ import annotations

import pytest


def test_health_returns_200_when_all_healthy(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    # Stub LanceDB count_rows to return >0
    from regulaitor.api import routes_health

    class _FakeTable:
        def count_rows(self) -> int:
            return 1011

    monkeypatch.setattr(routes_health, "connect", lambda: _FakeTable())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert any(c["name"] == "lancedb" and c["status"] == "ok" for c in body["checks"])
    assert any(c["name"] == "anthropic_key" and c["status"] == "present" for c in body["checks"])


def test_health_returns_503_when_lancedb_unreachable(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    from regulaitor.api import routes_health

    def _raise():
        raise FileNotFoundError("no lancedb")

    monkeypatch.setattr(routes_health, "connect", _raise)
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert any(c["name"] == "lancedb" and c["status"] == "unreachable" for c in body["checks"])


def test_health_returns_503_when_anthropic_key_missing(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from regulaitor.api import routes_health

    class _FakeTable:
        def count_rows(self) -> int:
            return 1011

    monkeypatch.setattr(routes_health, "connect", lambda: _FakeTable())
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"


def test_health_no_auth_required(client) -> None:
    """Health must respond without Authorization header (used by external pollers)."""
    # No headers passed; should still respond (with 200 or 503, not 401)
    response = client.get("/health")
    assert response.status_code in (200, 503)
