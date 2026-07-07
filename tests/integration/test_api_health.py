"""Integration tests for GET /health + lifespan startup."""

from __future__ import annotations

import pytest


def test_lifespan_calls_corpus_warmup_at_startup(
    api_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deep-review minor (architecture-coherence): the FastAPI lifespan must
    call corpus_loader.warmup() so the first /ask doesn't crash with
    KeyError("corpus ai_act not loaded; call warmup() first") on the auto-
    corpus path. Mirrors the R11 Streamlit fix in app.py main().
    """
    from fastapi.testclient import TestClient

    from regulaitor.api.main import app
    from regulaitor.corpus import loader as corpus_loader

    call_count = [0]
    original_warmup = corpus_loader.warmup

    def tracked_warmup() -> None:
        call_count[0] += 1
        original_warmup()

    monkeypatch.setattr(corpus_loader, "warmup", tracked_warmup)
    monkeypatch.setattr("regulaitor.api.main.corpus_loader.warmup", tracked_warmup)

    with TestClient(app):
        pass  # entering the context runs the lifespan startup

    assert call_count[0] >= 1, (
        "FastAPI lifespan must call corpus_loader.warmup() at startup to "
        "prevent KeyError on the first /ask request (deep-review minor)."
    )


class _FakeTable:
    def count_rows(self) -> int:
        return 1011


def _stub_lancedb_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.api import routes_health

    monkeypatch.setattr(routes_health, "connect", lambda **_: _FakeTable())


# --- public /health: readiness STATUS only, no config detail (deep-review I3) ---


def test_health_returns_200_when_all_healthy(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    _stub_lancedb_ok(monkeypatch)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]  # non-empty; sourced from pyproject


def test_health_public_hides_config_detail(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """The public /health must NOT leak the per-subsystem checks (corpus size, which
    keys are configured) to an unauthenticated caller — that is reconnaissance."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    _stub_lancedb_ok(monkeypatch)
    body = client.get("/health").json()
    assert set(body.keys()) == {"status", "version"}  # NO "checks"
    assert "anthropic_key" not in client.get("/health").text
    assert "chunks" not in client.get("/health").text


def test_health_returns_503_when_lancedb_unreachable(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    from regulaitor.api import routes_health

    def _raise(**_: object) -> None:
        raise FileNotFoundError("no lancedb")

    monkeypatch.setattr(routes_health, "connect", _raise)
    response = client.get("/health")
    assert response.status_code == 503  # orchestrator healthcheck still catches it
    assert response.json()["status"] == "degraded"


def test_health_returns_503_when_anthropic_key_missing(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _stub_lancedb_ok(monkeypatch)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_health_no_auth_required(client) -> None:
    """Public health must respond without Authorization header (external pollers)."""
    response = client.get("/health")
    assert response.status_code in (200, 503)  # not 401


# --- authed /health/detailed: full per-subsystem checks behind verify_token ---


def test_health_detailed_requires_auth(client) -> None:
    """The detailed checks (config surface) must NOT be reachable unauthenticated."""
    assert client.get("/health/detailed").status_code == 401


def test_health_detailed_returns_checks_when_authed(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    _stub_lancedb_ok(monkeypatch)
    body = client.get("/health/detailed", headers=auth_headers).json()
    assert body["status"] == "ok"
    assert any(c["name"] == "lancedb" and c["status"] == "ok" for c in body["checks"])
    assert any(c["name"] == "anthropic_key" and c["status"] == "present" for c in body["checks"])


def test_health_detailed_audit_db_subcheck_is_nonfatal(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """obs-08: a broken opt-in audit DB is REPORTED but does NOT 503 the service."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    _stub_lancedb_ok(monkeypatch)
    blocker = tmp_path / "f"  # parent-is-a-file → audit DB cannot open
    blocker.write_text("x")
    monkeypatch.setenv("REGULAITOR_AUDIT_DB", str(blocker / "sub" / "a.db"))

    response = client.get("/health/detailed", headers=auth_headers)
    assert response.status_code == 200  # criticals ok → up despite the broken audit DB
    checks = response.json()["checks"]
    assert any(c["name"] == "audit_db" and c["status"] == "degraded" for c in checks)


def test_health_detailed_audit_db_absent_when_unconfigured(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key")
    monkeypatch.delenv("REGULAITOR_AUDIT_DB", raising=False)
    _stub_lancedb_ok(monkeypatch)
    checks = client.get("/health/detailed", headers=auth_headers).json()["checks"]
    assert not any(c["name"] == "audit_db" for c in checks)


def test_metrics_404_when_disabled(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # P3.1: fail-secure — /metrics is not exposed unless REGULAITOR_ENABLE_METRICS=1.
    monkeypatch.delenv("REGULAITOR_ENABLE_METRICS", raising=False)
    assert client.get("/metrics").status_code == 404


def test_metrics_prometheus_when_enabled(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_ENABLE_METRICS", "1")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "regulaitor_turns_total" in r.text  # HELP/TYPE always render


def test_metrics_no_auth_required(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # Like /health, a scraper must reach it without a token (network-restricted in deploy).
    monkeypatch.setenv("REGULAITOR_ENABLE_METRICS", "1")
    assert client.get("/metrics").status_code == 200  # no Authorization header
