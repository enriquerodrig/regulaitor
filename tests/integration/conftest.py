"""Shared fixtures for integration tests using httpx.MockTransport (no sockets)."""

from __future__ import annotations

from collections.abc import Callable, Generator

import httpx
import pytest
from fastapi.testclient import TestClient

_Handler = Callable[[httpx.Request], httpx.Response]

VALID_TEST_TOKEN = "test_token_at_least_16_chars_long"


@pytest.fixture
def mock_transport_factory() -> Callable[[_Handler], httpx.MockTransport]:
    def _make(handler: _Handler) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    return _make


@pytest.fixture(autouse=True)
def reset_limiter() -> None:
    """Reset the in-memory rate limit counters before each integration test.

    The ``limiter`` singleton is constructed once at module import time with
    an in-memory storage backend.  When the full test suite runs, requests
    from earlier tests accumulate and exhaust per-token/per-IP quotas for
    later tests.  Calling ``limiter.reset()`` clears all counters without
    re-creating the object, preserving any monkeypatched state.
    """
    from regulaitor.security.rate_limit import limiter

    limiter.reset()


@pytest.fixture
def api_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("REGULAITOR_API_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.setenv("REGULAITOR_RATE_LIMIT_DISABLED", "1")
    return VALID_TEST_TOKEN


@pytest.fixture
def auth_headers(api_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_token}"}


@pytest.fixture
def client(api_token: str) -> Generator[TestClient, None, None]:
    """TestClient that triggers app lifespan (loads token)."""
    from regulaitor.api.main import app

    with TestClient(app) as c:
        yield c
