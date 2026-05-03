"""Shared fixtures for integration tests using httpx.MockTransport (no sockets)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

_Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def mock_transport_factory() -> Callable[[_Handler], httpx.MockTransport]:
    def _make(handler: _Handler) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    return _make
