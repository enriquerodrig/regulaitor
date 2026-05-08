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
