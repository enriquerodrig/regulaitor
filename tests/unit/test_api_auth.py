"""Unit tests for api.auth — tenancy-based verify_token Depends (Fase 4).

Token-loading + registry validation live in tests/unit/security/test_tenancy.py;
here we test that verify_token resolves a tenant and injects request.state.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from regulaitor.api import auth
from regulaitor.security import tenancy

_TOKEN = "valid_token_at_least_16_chars__"


def _creds(scheme: str, token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    tenancy._reset()
    yield
    tenancy._reset()


def _load_single(monkeypatch: pytest.MonkeyPatch, token: str = _TOKEN) -> None:
    for k in ("REGULAITOR_TENANTS_JSON", "REGULAITOR_TENANTS_FILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REGULAITOR_API_TOKEN", token)
    tenancy.load_tenants_or_raise()


def test_token_hash_deterministic() -> None:
    h1 = auth._token_hash("abcdef")
    h2 = auth._token_hash("abcdef")
    assert h1 == h2 and len(h1) == 8


def test_token_hash_differs_per_token() -> None:
    assert auth._token_hash("token_one_xxxxxxx") != auth._token_hash("token_two_xxxxxxx")


def _build_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/ask",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_verify_token_missing_header(monkeypatch: pytest.MonkeyPatch) -> None:
    _load_single(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_build_request(), credentials=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_malformed_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    _load_single(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_build_request(), credentials=_creds("Basic", "abc123"))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    _load_single(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(
            _build_request(), credentials=_creds("Bearer", "wrong_token_xxxxxx")
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_trailing_whitespace_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """RFC 6750: Bearer token compared exactly; trailing whitespace is invalid."""
    _load_single(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_build_request(), credentials=_creds("Bearer", f"{_TOKEN}   "))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_valid_sets_tenant_and_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    _load_single(monkeypatch)
    request = _build_request()
    await auth.verify_token(request, credentials=_creds("Bearer", _TOKEN))
    assert request.state.token_hash == auth._token_hash(_TOKEN)
    assert request.state.tenant.tenant_id == "default"


@pytest.mark.asyncio
async def test_verify_token_resolves_correct_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    for k in ("REGULAITOR_TENANTS_FILE", "REGULAITOR_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    t1, t2 = "tok_" + "a" * 20, "tok_" + "b" * 20
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps(
            [
                {"token": t1, "tenant_id": "acme", "name": "Acme"},
                {"token": t2, "tenant_id": "globex", "name": "Globex"},
            ]
        ),
    )
    tenancy.load_tenants_or_raise()
    request = _build_request()
    await auth.verify_token(request, credentials=_creds("Bearer", t2))
    assert request.state.tenant.tenant_id == "globex"


@pytest.mark.asyncio
async def test_verify_token_unloaded_registry_raises_500() -> None:
    tenancy._reset()  # registry NOT loaded
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(
            _build_request(), credentials=_creds("Bearer", "anything_16_chars__")
        )
    assert exc.value.status_code == 500
