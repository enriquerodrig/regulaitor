"""Integration tests for GET /audit (Fase 6B; ADR-0041 §9 — tenant-scoped trail)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from regulaitor.observability import audit_store
from regulaitor.security import tenancy

_ACME = "tok_" + "a" * 20
_GLOBEX = "tok_" + "g" * 20


@pytest.fixture
def audit_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Generator[TestClient, None, None]:
    for k in ("REGULAITOR_API_TOKEN", "REGULAITOR_TENANTS_FILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps(
            [
                {"token": _ACME, "tenant_id": "acme", "name": "Acme"},
                {"token": _GLOBEX, "tenant_id": "globex", "name": "Globex"},
            ]
        ),
    )
    monkeypatch.setenv("REGULAITOR_AUDIT_DB", str(tmp_path / "audit.db"))
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    # Pre-populate: 2 acme turns + 1 globex turn.
    audit_store.record(case_id="a1", tenant_id="acme", mode="chat", query="q1", verdict="pass")
    audit_store.record(case_id="a2", tenant_id="acme", mode="chat", query="q2", verdict="block")
    audit_store.record(
        case_id="g1", tenant_id="globex", mode="chat", query="secret-globex", verdict="block"
    )
    tenancy._reset()
    from regulaitor.api.main import app

    with TestClient(app) as c:
        yield c
    tenancy._reset()


def test_audit_returns_own_rows(audit_client: TestClient) -> None:
    r = audit_client.get("/audit", headers={"Authorization": f"Bearer {_ACME}"})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["total"] == 2
    assert {e["case_id"] for e in body["entries"]} == {"a1", "a2"}


def test_audit_cannot_see_other_tenant(audit_client: TestClient) -> None:
    """The load-bearing isolation test: acme must NEVER see globex's rows."""
    r = audit_client.get("/audit", headers={"Authorization": f"Bearer {_ACME}"})
    body = r.json()
    case_ids = {e["case_id"] for e in body["entries"]}
    assert "g1" not in case_ids
    globex_hash = hashlib.sha256(b"secret-globex").hexdigest()
    assert all(e["query_sha256"] != globex_hash for e in body["entries"])


def test_globex_sees_only_its_own(audit_client: TestClient) -> None:
    r = audit_client.get("/audit", headers={"Authorization": f"Bearer {_GLOBEX}"})
    body = r.json()
    assert body["total"] == 1
    assert [e["case_id"] for e in body["entries"]] == ["g1"]


def test_audit_never_returns_raw_query(audit_client: TestClient) -> None:
    """§18.8: only the SHA-256 is exposed; the raw query bytes never appear."""
    r = audit_client.get("/audit", headers={"Authorization": f"Bearer {_ACME}"})
    assert "q1" not in r.text and "q2" not in r.text  # raw queries never serialized
    assert all(e["query_sha256"] for e in r.json()["entries"])


def test_audit_requires_auth(audit_client: TestClient) -> None:
    assert audit_client.get("/audit").status_code == 401


def test_audit_limit_out_of_range_rejected(audit_client: TestClient) -> None:
    h = {"Authorization": f"Bearer {_ACME}"}
    assert audit_client.get("/audit?limit=0", headers=h).status_code == 422
    assert audit_client.get("/audit?limit=999", headers=h).status_code == 422


def test_audit_fails_closed_when_no_tenant(audit_client: TestClient) -> None:
    """If auth were ever weakened to not set request.state.tenant, the endpoint must
    return an EMPTY view — never fall back to the unscoped global read of all rows."""
    from regulaitor.api.auth import verify_token
    from regulaitor.api.main import app

    app.dependency_overrides[verify_token] = lambda: None  # bypass without setting tenant
    try:
        r = audit_client.get("/audit", headers={"Authorization": f"Bearer {_ACME}"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    # Without fail-closed, recent(None) is a global SELECT * → would leak all 3 rows.
    assert body["entries"] == []
    assert body["total"] == 0


def test_audit_disabled_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("REGULAITOR_API_TOKEN", "REGULAITOR_TENANTS_FILE", "REGULAITOR_AUDIT_DB"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps([{"token": _ACME, "tenant_id": "acme", "name": "Acme"}]),
    )
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    tenancy._reset()
    from regulaitor.api.main import app

    with TestClient(app) as c:
        r = c.get("/audit", headers={"Authorization": f"Bearer {_ACME}"})
    tenancy._reset()
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["total"] == 0
    assert body["entries"] == []
