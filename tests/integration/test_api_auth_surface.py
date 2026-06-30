"""Auth-surface hardening tests (audit authz-01 default-deny + authz-02 docs gate)."""

from __future__ import annotations

import importlib
import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from regulaitor.security import tenancy

_TOK = "tok_" + "s" * 20
_TENANTS_JSON = json.dumps([{"token": _TOK, "tenant_id": "acme", "name": "Acme"}])


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    for k in ("REGULAITOR_API_TOKEN", "REGULAITOR_TENANTS_FILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REGULAITOR_TENANTS_JSON", _TENANTS_JSON)
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    tenancy._reset()
    from regulaitor.api.main import app

    with TestClient(app) as c:
        yield c
    tenancy._reset()


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/ask", {"json": {"query": "x", "corpus": "ai_act", "language": "es"}}),
        (
            "post",
            "/analyze",
            {
                "files": {"file": ("d.md", b"# hi", "text/markdown")},
                "data": {"corpus": "ai_act", "language": "es"},
            },
        ),
        ("get", "/audit", {}),
    ],
)
def test_protected_route_requires_token(
    client: TestClient, method: str, path: str, kwargs: dict
) -> None:
    """authz-01: every non-public route default-denies without a Bearer token."""
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 401


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/health").status_code in (200, 503)


def test_unknown_route_returns_error_envelope(client: TestClient) -> None:
    """err-04: a routing 404 returns the uniform ErrorResponse envelope, not
    Starlette's plain {"detail": ...}."""
    r = client.get("/no-such-route")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "http_404"
    assert set(body) == {"error_code", "message", "case_id"}


def test_method_not_allowed_returns_error_envelope(client: TestClient) -> None:
    """err-04: a 405 (GET on the POST-only /ask) also returns the uniform envelope."""
    r = client.get("/ask")
    assert r.status_code == 405
    assert r.json()["error_code"] == "http_405"


def test_openapi_served_by_default(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200


def test_docs_endpoints_gated_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """authz-02: REGULAITOR_ENABLE_DOCS=0 removes the public schema endpoints.

    Checks the app config directly (no HTTP/lifespan) and reloads back to the
    default so the rest of the suite sees a docs-enabled app.
    """
    from regulaitor.api import main as main_mod

    monkeypatch.setenv("REGULAITOR_ENABLE_DOCS", "0")
    importlib.reload(main_mod)
    try:
        assert main_mod.app.openapi_url is None
        assert main_mod.app.docs_url is None
        assert main_mod.app.redoc_url is None
    finally:
        monkeypatch.delenv("REGULAITOR_ENABLE_DOCS", raising=False)
        importlib.reload(main_mod)
