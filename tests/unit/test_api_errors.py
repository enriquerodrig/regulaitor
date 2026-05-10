"""Unit tests for api.errors — custom exceptions + handlers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from regulaitor.api import errors


def _request(case_id: str | None = None, token_hash: str | None = None) -> SimpleNamespace:
    state = SimpleNamespace()
    if case_id is not None:
        state.case_id = case_id
    if token_hash is not None:
        state.token_hash = token_hash
    return SimpleNamespace(method="POST", url=SimpleNamespace(path="/ask"), state=state)


def _body(response: JSONResponse) -> dict:
    return json.loads(response.body.decode("utf-8"))


@pytest.mark.asyncio
async def test_injection_handler_returns_400() -> None:
    exc = errors.InjectionDetected(case_id="api-ch-1", reason_code="injection_blocked")
    response = await errors.injection_handler(_request(), exc)
    assert response.status_code == 400
    body = _body(response)
    assert body["error_code"] == "injection_blocked"
    assert body["case_id"] == "api-ch-1"


@pytest.mark.asyncio
async def test_file_size_handler_returns_413() -> None:
    exc = errors.FileSizeExceeded(size=20_000_000, max_size=10_000_000)
    response = await errors.file_size_handler(_request(case_id="api-doc-1"), exc)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_unsupported_media_handler_returns_415() -> None:
    exc = errors.UnsupportedMediaType(reason="bad mime")
    response = await errors.unsupported_media_handler(_request(case_id="api-doc-1"), exc)
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_rate_limit_handler_returns_429_with_retry_after() -> None:
    exc = RateLimitExceeded(MagicMock(detail="30/minute"))
    response = await errors.rate_limit_handler(_request(case_id="api-ch-1"), exc)
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "60"


@pytest.mark.asyncio
async def test_backend_error_handler_does_not_leak_errors_list() -> None:
    """SSDLC: BackendError.errors is logged but NOT in the response body."""
    exc = errors.BackendError(
        case_id="api-ch-1", errors=["secret_internal_state", "stack_trace_leak"]
    )
    response = await errors.backend_error_handler(_request(case_id="api-ch-1"), exc)
    assert response.status_code == 500
    body_text = response.body.decode("utf-8")
    assert "secret_internal_state" not in body_text
    assert "stack_trace_leak" not in body_text


@pytest.mark.asyncio
async def test_generic_handler_does_not_leak_exception_message() -> None:
    """SSDLC: arbitrary exceptions must NOT leak str(exc) to the response body."""
    exc = RuntimeError("internal_secret_message_xyz")
    response = await errors.generic_handler(_request(case_id="api-ch-1"), exc)
    assert response.status_code == 500
    body_text = response.body.decode("utf-8")
    assert "internal_secret_message_xyz" not in body_text


def test_custom_exception_constructors() -> None:
    e1 = errors.InjectionDetected(case_id="x", reason_code="injection_blocked")
    assert e1.case_id == "x" and e1.reason_code == "injection_blocked"
    e2 = errors.BackendError(case_id="x", errors=["a"])
    assert e2.errors == ["a"]
    e3 = errors.FileSizeExceeded(size=1, max_size=2)
    assert e3.size == 1 and e3.max_size == 2
    e4 = errors.UnsupportedMediaType(reason="bad")
    assert e4.reason_code == "bad"


@pytest.mark.asyncio
async def test_backend_error_handler_empty_errors_list() -> None:
    """Boundary: empty errors list is valid input; handler returns 500 cleanly."""
    exc = errors.BackendError(case_id="api-ch-1", errors=[])
    response = await errors.backend_error_handler(_request(case_id="api-ch-1"), exc)
    assert response.status_code == 500
    body = _body(response)
    assert body["error_code"] == "backend_error"
    assert body["case_id"] == "api-ch-1"


def test_register_anthropic_handlers_skips_when_uninstalled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If anthropic SDK is not importable, the registration MUST silently skip."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "anthropic" or name.startswith("anthropic."):
            raise ImportError("simulated absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    app = MagicMock()
    errors.register_anthropic_handlers(app)
    # Should not have raised; should not have called add_exception_handler for anthropic types
    assert app.add_exception_handler.call_count == 0
