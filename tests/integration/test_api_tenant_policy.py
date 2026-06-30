"""Integration tests for Fase 6B (ADR-0042): per-tenant corpus allowlist +
model_choice threading at the /ask and /analyze routes."""

from __future__ import annotations

import json
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from regulaitor.api.auth import enforce_corpus_allowlist
from regulaitor.api.errors import CorpusNotAllowed
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)
from regulaitor.orchestration.state import ChatState
from regulaitor.security import tenancy
from regulaitor.security.tenancy import Tenant

_TOK = "tok_" + "z" * 20
_TENANT = {
    "token": _TOK,
    "tenant_id": "acme",
    "name": "Acme",
    "allowed_corpora": ["ai_act"],
    "model_choice": "self_hosted",
}
_HEADERS = {"Authorization": f"Bearer {_TOK}"}


def _ok_state() -> ChatState:
    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="texto")
    finding = Finding(text="hallazgo", citations=[cit], severity="info")
    answer = Answer(query="q", language="es", text="respuesta", findings=[finding])
    audit = AuditResult(
        citation=cit,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=[audit], reason=None
    )
    return ChatState(
        case_id="api-ch-fake-1",
        query="q",
        corpus="ai_act",
        language="es",
        answer=answer,
        audited_answer=audited,
    )


@pytest.fixture
def policy_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    for k in ("REGULAITOR_API_TOKEN", "REGULAITOR_TENANTS_FILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REGULAITOR_TENANTS_JSON", json.dumps([_TENANT]))
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    tenancy._reset()
    from regulaitor.api.main import app

    with TestClient(app) as c:
        yield c
    tenancy._reset()


def test_ask_corpus_not_in_allowlist_returns_403(
    policy_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "regulaitor.api.routes_ask.run",
        lambda **kw: (captured.update(kw), _ok_state())[1],
    )
    r = policy_client.post(
        "/ask", headers=_HEADERS, json={"query": "q", "corpus": "gdpr", "language": "es"}
    )
    assert r.status_code == 403
    assert r.json()["error_code"] == "corpus_not_allowed"
    assert captured == {}  # the pipeline is never invoked for a disallowed corpus


def test_ask_allowed_corpus_passes_tenant_model_choice(
    policy_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "regulaitor.api.routes_ask.run",
        lambda **kw: (captured.update(kw), _ok_state())[1],
    )
    r = policy_client.post(
        "/ask", headers=_HEADERS, json={"query": "q", "corpus": "ai_act", "language": "es"}
    )
    assert r.status_code == 200
    assert captured["model_choice"] == "self_hosted"  # tenant's mode threaded to run()


def test_analyze_corpus_not_in_allowlist_returns_403(policy_client: TestClient) -> None:
    files = {"file": ("doc.md", b"# Doc\nContenido de prueba.", "text/markdown")}
    r = policy_client.post(
        "/analyze", headers=_HEADERS, files=files, data={"corpus": "gdpr", "language": "es"}
    )
    assert r.status_code == 403
    assert r.json()["error_code"] == "corpus_not_allowed"


# --- enforce_corpus_allowlist helper (the shared invariant) -----------------


def _req(tenant: object) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(tenant=tenant))


def test_helper_no_tenant_fails_closed() -> None:
    # authz-03: reaching the helper with no tenant means auth did not run — deny.
    with pytest.raises(CorpusNotAllowed):
        enforce_corpus_allowlist(SimpleNamespace(state=SimpleNamespace()), ["gdpr"])


def test_helper_no_allowlist_is_noop() -> None:
    enforce_corpus_allowlist(_req(Tenant(tenant_id="a", name="A")), ["gdpr"])


def test_helper_allowed_corpus_is_noop() -> None:
    t = Tenant(tenant_id="a", name="A", allowed_corpora=["gdpr", "ai_act"])
    enforce_corpus_allowlist(_req(t), ["gdpr"])  # subset of the allowlist -> no raise


def test_helper_disallowed_member_raises() -> None:
    t = Tenant(tenant_id="a", name="A", allowed_corpora=["gdpr"])
    with pytest.raises(CorpusNotAllowed):
        enforce_corpus_allowlist(_req(t), ["gdpr", "ai_act"])
