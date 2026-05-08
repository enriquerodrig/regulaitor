"""Unit tests for api.auth — token loading + verify_token Depends."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from regulaitor.api import auth


@pytest.fixture(autouse=True)
def reset_token() -> None:
    """Each test starts with no loaded token."""
    auth._API_TOKEN = None
    yield
    auth._API_TOKEN = None


def test_load_api_token_or_raise_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="REGULAITOR_API_TOKEN missing"):
        auth.load_api_token_or_raise()


def test_load_api_token_or_raise_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "   ")
    with pytest.raises(RuntimeError, match="REGULAITOR_API_TOKEN missing"):
        auth.load_api_token_or_raise()


def test_load_api_token_or_raise_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "short")
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        auth.load_api_token_or_raise()


def test_load_api_token_or_raise_loads_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "this_is_a_valid_token_at_least_16_chars")
    auth.load_api_token_or_raise()
    assert auth._API_TOKEN == "this_is_a_valid_token_at_least_16_chars"


def test_token_hash_deterministic() -> None:
    h1 = auth._token_hash("abcdef")
    h2 = auth._token_hash("abcdef")
    assert h1 == h2
    assert len(h1) == 8


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
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "valid_token_at_least_16_chars__")
    auth.load_api_token_or_raise()
    request = _build_request(headers={})
    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_token(request, authorization=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "valid_token_at_least_16_chars__")
    auth.load_api_token_or_raise()
    request = _build_request()
    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_token(request, authorization="Basic abc123")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "valid_token_at_least_16_chars__")
    auth.load_api_token_or_raise()
    request = _build_request()
    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_token(request, authorization="Bearer wrong_token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_valid_sets_state_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "valid_token_at_least_16_chars__"
    monkeypatch.setenv("REGULAITOR_API_TOKEN", token)
    auth.load_api_token_or_raise()
    request = _build_request()
    await auth.verify_token(request, authorization=f"Bearer {token}")
    assert request.state.token_hash == auth._token_hash(token)


@pytest.mark.asyncio
async def test_verify_token_unloaded_token_raises_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_API_TOKEN", raising=False)
    # Do NOT call load_api_token_or_raise → _API_TOKEN stays None
    request = _build_request()
    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_token(request, authorization="Bearer anything")
    assert exc_info.value.status_code == 500
