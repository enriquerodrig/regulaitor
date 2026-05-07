"""Allowlist of official EU regulatory domains for URI Action validation (H5).

Used by document/sanitizer.py: any URI Action embedded in a PDF whose host is
NOT in this set triggers a critical-block. CLAUDE.md §18.6 + §10/§11 (least
privilege, allowlist for HTTP fetch) — H5 minimal version, H7 expands.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

ALLOWED_DOMAINS_OFFICIAL_EU: Final[frozenset[str]] = frozenset(
    {
        "eur-lex.europa.eu",
        "boe.es",
        "digital-strategy.ec.europa.eu",
        "edpb.europa.eu",
    }
)


def is_uri_allowed(uri: str) -> bool:
    """Return True if the URI's host is in the official EU allowlist.

    Defensive against:
    - case differences (Host headers are case-insensitive per RFC 3986).
    - leading "www." prefix (tolerated, stripped before comparison).
    - subdomain attacks (e.g., eur-lex.europa.eu.attacker.com): we compare
      the full netloc against the exact set; substring matches do NOT pass.
    - non-http(s) schemes (file://, javascript:, etc.) — rejected by scheme.
    - malformed input — returns False, never raises.
    """
    if not uri:
        return False
    try:
        parsed = urlparse(uri)
    except ValueError:
        return False
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    host = parsed.netloc.lower()
    if not host:
        return False
    if host.startswith("www."):
        host = host[4:]
    return host in ALLOWED_DOMAINS_OFFICIAL_EU
