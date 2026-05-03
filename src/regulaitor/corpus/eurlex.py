"""HTTP client for EUR-Lex with allowlist and conditional requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from regulaitor.corpus.schemas import HttpCacheEntry, Language

ALLOWED_HOSTS = {"eur-lex.europa.eu"}


class EurLexAllowlistError(Exception):
    """Raised when a URL outside the allowlist is requested."""


@dataclass(frozen=True)
class FetchResultModified:
    content: bytes
    etag: str | None
    last_modified: str | None
    source_url: str
    fetched_at: datetime


@dataclass(frozen=True)
class FetchResultNotModified:
    pass


FetchResult = FetchResultModified | FetchResultNotModified

_LANG_TO_PATH: dict[Language, str] = {"es": "ES", "en": "EN"}


def _formex_url(celex: str, language: Language) -> str:
    return (
        f"https://eur-lex.europa.eu/legal-content/{_LANG_TO_PATH[language]}"
        f"/TXT/?uri=CELEX:{celex}"
    )


def _html_url(celex: str, language: Language) -> str:
    return (
        f"https://eur-lex.europa.eu/legal-content/{_LANG_TO_PATH[language]}"
        f"/TXT/HTML/?uri=CELEX:{celex}"
    )


class EurLexClient:
    """HTTP client targeting EUR-Lex with retry, conditional requests, allowlist."""

    def __init__(
        self,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "RegulAItor-corpus-ingest/0.1"},
        )

    def fetch_formex(
        self,
        celex: str,
        language: Language,
        cache: HttpCacheEntry | None = None,
    ) -> FetchResult:
        url = _formex_url(celex, language)
        return self._fetch(url, cache=cache, accept="application/xml")

    def fetch_html(
        self,
        celex: str,
        language: Language,
        cache: HttpCacheEntry | None = None,
    ) -> FetchResult:
        url = _html_url(celex, language)
        return self._fetch(url, cache=cache, accept="text/html")

    def _enforce_allowlist(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        if host not in ALLOWED_HOSTS:
            raise EurLexAllowlistError(f"host '{host}' not in allowlist")

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    def _fetch(
        self,
        url: str,
        *,
        cache: HttpCacheEntry | None,
        accept: str,
    ) -> FetchResult:
        self._enforce_allowlist(url)
        headers: dict[str, str] = {"Accept": accept}
        if cache is not None:
            if cache.etag:
                headers["If-None-Match"] = cache.etag
            if cache.last_modified:
                headers["If-Modified-Since"] = cache.last_modified

        response = self._client.get(url, headers=headers)
        if response.status_code == 304:
            return FetchResultNotModified()
        response.raise_for_status()
        return FetchResultModified(
            content=response.content,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
            source_url=str(response.url),
            fetched_at=datetime.now(UTC),
        )

    def close(self) -> None:
        self._client.close()
