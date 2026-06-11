"""Fase 4 — config-based multi-tenancy (stateless; ADR-0039).

The system is stateless (no per-request data is stored), so tenant isolation is
auth + config + rate-limit + logging, NOT row-level DB scoping. A tenant registry
maps an API token to a `Tenant` (id, name, per-tenant rate limits). The registry
is loaded once at startup from config — no database.

Sources (first match wins):
  1. ``REGULAITOR_TENANTS_JSON``  — inline JSON array (easiest as a Space secret).
  2. ``REGULAITOR_TENANTS_FILE``  — path to a JSON array file.
  3. ``REGULAITOR_API_TOKEN``     — backward-compat: a single "default" tenant
                                    (existing single-token deploys keep working).

JSON entry shape:
  {"token": "<>=16 chars>", "tenant_id": "acme", "name": "Acme SL",
   "rate_limit_ask": "60/minute", "rate_limit_analyze": "10/minute"}

The token is the secret KEY and is NEVER stored on the `Tenant` model nor logged.
"""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path

from limits import parse_many  # slowapi dependency — the canonical rate-limit grammar
from pydantic import BaseModel, ConfigDict, Field, field_validator

_MIN_TOKEN_LEN = 16


def _validate_rate_limit(v: str) -> str:
    """Reject a rate-limit string slowapi cannot parse (review RL-1: fail CLOSED at
    load instead of fail-OPEN at request time, since the limiter silently drops an
    unparseable limit and serves the request unlimited)."""
    try:
        parsed = list(parse_many(v))
    except ValueError as exc:
        raise ValueError(f"invalid rate limit {v!r}: {exc}") from exc
    if not parsed or any(item.amount <= 0 for item in parsed):
        raise ValueError(f"rate limit {v!r} must specify a positive amount")
    return v


class Tenant(BaseModel):
    """One client organisation. No token, no secrets — config metadata only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    rate_limit_ask: str = "30/minute"
    rate_limit_analyze: str = "5/minute"

    @field_validator("rate_limit_ask", "rate_limit_analyze")
    @classmethod
    def _check_limit(cls, v: str) -> str:
        return _validate_rate_limit(v)


# (token, Tenant) pairs for constant-time resolution + a tenant_id -> Tenant index.
_TENANTS: list[tuple[str, Tenant]] = []
_BY_ID: dict[str, Tenant] = {}


def _reset() -> None:
    _TENANTS.clear()
    _BY_ID.clear()


def _parse_entries(raw: object, source: str) -> list[tuple[str, Tenant]]:
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"{source} must be a non-empty JSON array of tenant objects.")
    out: list[tuple[str, Tenant]] = []
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise RuntimeError(f"{source}[{i}] must be an object.")
        token = str(entry.get("token", "")).strip()
        if len(token) < _MIN_TOKEN_LEN:
            raise RuntimeError(
                f"{source}[{i}] token must be at least {_MIN_TOKEN_LEN} characters (entropy guard)."
            )
        if token in seen_tokens:
            raise RuntimeError(f"{source}[{i}] duplicate token.")
        fields = {k: v for k, v in entry.items() if k != "token"}
        tenant = Tenant(**fields)  # Pydantic validates id/name/limits, rejects extras
        if tenant.tenant_id in seen_ids:
            raise RuntimeError(f"{source}: duplicate tenant_id {tenant.tenant_id!r}.")
        seen_ids.add(tenant.tenant_id)
        seen_tokens.add(token)
        out.append((token, tenant))
    return out


def load_tenants_or_raise() -> None:
    """Load the tenant registry from config. Called from the FastAPI lifespan.

    Raises RuntimeError if nothing is configured (no tenants AND no single token).
    """
    _reset()
    inline = os.getenv("REGULAITOR_TENANTS_JSON", "").strip()
    file_path = os.getenv("REGULAITOR_TENANTS_FILE", "").strip()

    entries: list[tuple[str, Tenant]]
    if inline:
        # review TEN-LOAD-01: clean source-named error (fail-fast) instead of a raw
        # JSONDecodeError that does not name the offending env var.
        try:
            data = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"REGULAITOR_TENANTS_JSON is not valid JSON: {exc}") from exc
        entries = _parse_entries(data, "REGULAITOR_TENANTS_JSON")
    elif file_path:
        path = Path(file_path)
        if not path.is_file():
            raise RuntimeError(f"REGULAITOR_TENANTS_FILE not found: {file_path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"REGULAITOR_TENANTS_FILE {file_path} is not valid JSON: {exc}"
            ) from exc
        entries = _parse_entries(data, "REGULAITOR_TENANTS_FILE")
    else:
        # Backward-compat: single shared token -> one "default" tenant.
        token = os.getenv("REGULAITOR_API_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "No tenants configured. Set REGULAITOR_TENANTS_JSON / "
                "REGULAITOR_TENANTS_FILE, or REGULAITOR_API_TOKEN for single-tenant mode."
            )
        if len(token) < _MIN_TOKEN_LEN:
            raise RuntimeError(
                f"REGULAITOR_API_TOKEN must be at least {_MIN_TOKEN_LEN} characters "
                "(entropy guard)."
            )
        entries = [(token, Tenant(tenant_id="default", name="default"))]

    _TENANTS.extend(entries)
    _BY_ID.update({t.tenant_id: t for _, t in entries})


def resolve_tenant(token: str) -> Tenant | None:
    """Return the Tenant for a presented token, or None. Constant-time compare.

    Compares on UTF-8 bytes (review AUTH-1/TSC-1): hmac.compare_digest raises
    TypeError on non-ASCII *str* args, and the presented token is attacker-
    controlled (latin-1 decoded from the raw Authorization header) — a non-ASCII
    token must resolve to None -> 401, never crash to 500. Bytes never raise.
    """
    presented = token.encode("utf-8")
    match: Tenant | None = None
    for registered, tenant in _TENANTS:
        # compare ALL entries (no early return) so timing does not leak which token matched
        if hmac.compare_digest(presented, registered.encode("utf-8")):
            match = tenant
    return match


def tenant_by_id(tenant_id: str) -> Tenant | None:
    """Look up a tenant by id (used by the rate-limit value resolver)."""
    return _BY_ID.get(tenant_id)


def is_loaded() -> bool:
    return bool(_TENANTS)
