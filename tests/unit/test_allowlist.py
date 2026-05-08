"""Tests for URI allowlist used by sanitizer."""

from __future__ import annotations

import pytest

from regulaitor.security.allowlist import (
    ALLOWED_DOMAINS_OFFICIAL_EU,
    is_uri_allowed,
)


def test_allowlist_contains_eur_lex():
    assert "eur-lex.europa.eu" in ALLOWED_DOMAINS_OFFICIAL_EU


def test_allowlist_size_is_bounded_for_h5():
    # H5 minimal — H7 will expand. Pin to detect accidental drift.
    # 5 entries: the original 4 + data.europa.eu (added 2026-05-07 after
    # real-PDF inspection found GDPR EUR-Lex PDFs link to it).
    assert len(ALLOWED_DOMAINS_OFFICIAL_EU) == 5


@pytest.mark.parametrize(
    "uri",
    [
        "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32016R0679",
        "http://eur-lex.europa.eu/x",
        "https://EUR-LEX.EUROPA.EU/y",  # case-insensitive
        "https://www.eur-lex.europa.eu/z",  # www prefix tolerated
        "https://boe.es/abc",
        "https://digital-strategy.ec.europa.eu/q",
        "https://edpb.europa.eu/r",
        "https://data.europa.eu/eli/reg/2016/679/oj",  # GDPR consolidated text
    ],
)
def test_allowlist_passes_official_eu(uri):
    assert is_uri_allowed(uri) is True


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.com/x",
        "http://attacker.example/eur-lex.europa.eu",  # path injection — domain wins
        "https://eur-lex.europa.eu.attacker.com/y",  # subdomain trick — must not pass
        "https://eur-lex-europa-eu.com/z",  # similar but distinct
    ],
)
def test_allowlist_rejects_non_official(uri):
    assert is_uri_allowed(uri) is False


def test_allowlist_handles_malformed_uri():
    # Defensive: malformed inputs should not crash.
    assert is_uri_allowed("not a url") is False
    assert is_uri_allowed("") is False
    assert is_uri_allowed("file:///etc/passwd") is False


def test_allowlist_rejects_http_scheme_without_host():
    # http(s) scheme but empty netloc must not pass (covers empty-host branch).
    assert is_uri_allowed("http://") is False
    assert is_uri_allowed("https:///path-only") is False


def test_allowlist_rejects_urlparse_value_error(monkeypatch):
    # Defensive ValueError path: simulate urlparse raising on input.
    from regulaitor.security import allowlist as allowlist_mod

    def boom(_uri: str) -> object:
        raise ValueError("simulated parse failure")

    monkeypatch.setattr(allowlist_mod, "urlparse", boom)
    assert allowlist_mod.is_uri_allowed("https://eur-lex.europa.eu/x") is False
