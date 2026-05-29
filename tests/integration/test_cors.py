"""CORS preflight + simple-request behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _make_client(monkeypatch) -> TestClient:
    """Build a TestClient with CORS allowlist set to https://example.com."""
    # Ensure required envs exist for app startup
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-placeholder-16chars-min")
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "test-token-min-16-chars-long-enough")
    monkeypatch.setenv("REGULAITOR_CORS_ORIGINS", "https://example.com,https://app.example.com")

    # Import lazily so envs are read at module import
    import importlib

    import regulaitor.api.main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_cors_preflight_returns_allowed_origin(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.options(
        "/ask",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "https://example.com"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_disallowed_origin_omits_header(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.options(
        "/ask",
        headers={
            "Origin": "https://evil.example.org",
            "Access-Control-Request-Method": "POST",
        },
    )
    # When origin isn't in allowlist, FastAPI CORSMiddleware omits the
    # access-control-allow-origin header entirely (the browser then rejects)
    assert response.headers.get("access-control-allow-origin") != "https://evil.example.org"


def test_cors_simple_request_no_origin_header(monkeypatch):
    """Plain requests (non-browser, no Origin header) omit CORS headers."""
    client = _make_client(monkeypatch)
    response = client.options(
        "/ask",
        headers={
            "Access-Control-Request-Method": "POST",
        },
    )
    # Without an Origin header, CORS middleware doesn't emit CORS response headers
    assert "access-control-allow-origin" not in response.headers


def test_cors_env_var_literal_pinned():
    """Deep-review I5 regression anchor: api/main.py reads the env var name
    EXACTLY `REGULAITOR_CORS_ORIGINS` (NOT `_API_CORS_ORIGINS`). Docs drift
    twice (v0.1.26 + post-h16 deploy); this test pins the literal so a future
    rename forces an explicit refactor across docs + code together.
    """
    from pathlib import Path

    main_py = Path("src/regulaitor/api/main.py").read_text(encoding="utf-8")
    assert 'os.getenv("REGULAITOR_CORS_ORIGINS"' in main_py, (
        "api/main.py must read the CORS env via the canonical name "
        "REGULAITOR_CORS_ORIGINS (not REGULAITOR_API_CORS_ORIGINS). If you "
        "rename the env, update README.md + CLAUDE.md §27 + "
        "docs/technical_decisions_log.md + docs/H16_DEPLOY.md §2 + .env in "
        "the same commit to keep operators in sync."
    )
