"""Unit tests for EurLexClient with mocked HTTP transport."""

from __future__ import annotations

import httpx
import pytest

from regulaitor.corpus.eurlex import (
    EurLexAllowlistError,
    EurLexClient,
    FetchResultModified,
    FetchResultNotModified,
)
from regulaitor.corpus.schemas import HttpCacheEntry


def test_fetch_formex_200_returns_modified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<CONS.ACT/>",
            headers={"ETag": 'W/"abc"', "Last-Modified": "Fri, 12 Jul 2024 00:00:00 GMT"},
        )

    client = EurLexClient(transport=httpx.MockTransport(handler))
    result = client.fetch_formex(celex="32024R1689", language="es")
    assert isinstance(result, FetchResultModified)
    assert result.content == b"<CONS.ACT/>"
    assert result.etag == 'W/"abc"'


def test_fetch_formex_304_returns_not_modified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304, content=b"")

    client = EurLexClient(transport=httpx.MockTransport(handler))
    cache = HttpCacheEntry(etag='W/"abc"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT")
    result = client.fetch_formex(celex="32024R1689", language="es", cache=cache)
    assert isinstance(result, FetchResultNotModified)


def test_fetch_formex_4xx_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    client = EurLexClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_formex(celex="bad", language="es")


def test_allowlist_blocks_non_eurlex_url() -> None:
    client = EurLexClient()
    with pytest.raises(EurLexAllowlistError):
        client._enforce_allowlist("https://evil.example/formex.xml")


def test_conditional_headers_set_when_cache_present() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["if_none_match"] = request.headers.get("If-None-Match", "")
        captured["if_modified_since"] = request.headers.get("If-Modified-Since", "")
        return httpx.Response(304)

    client = EurLexClient(transport=httpx.MockTransport(handler))
    cache = HttpCacheEntry(etag='W/"xyz"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT")
    client.fetch_formex(celex="32024R1689", language="es", cache=cache)
    assert captured["if_none_match"] == 'W/"xyz"'
    assert captured["if_modified_since"] == "Fri, 12 Jul 2024 00:00:00 GMT"
