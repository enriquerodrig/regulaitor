"""Bearer token authentication for the FastAPI surface (H7; Fase 4 multi-tenant).

The presented Bearer token is resolved to a `Tenant` via security.tenancy (the
registry is loaded once at startup from config). On success the tenant + a token
hash are injected into request.state for downstream rate limiting + logging.
Backward-compat: a single REGULAITOR_API_TOKEN resolves to a "default" tenant.

verify_token uses Security(HTTPBearer) so FastAPI/OpenAPI advertises the Bearer
scheme in /openapi.json (the Authorize button in /docs).
"""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from regulaitor.security import tenancy

_bearer = HTTPBearer(auto_error=False, scheme_name="REGULAITOR_API_TOKEN")


def _token_hash(token: str) -> str:
    """SHA256[:8] — used for logging + rate-limit fallback. Never the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),  # noqa: B008
) -> None:
    """FastAPI Depends. Raises 401 on auth failure; injects tenant + token_hash."""
    if not tenancy.is_loaded():
        # Defensive: lifespan loads the registry; unreachable in production.
        raise HTTPException(status_code=500, detail="Internal server error")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    presented = credentials.credentials
    tenant = tenancy.resolve_tenant(presented)
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid API token")
    request.state.tenant = tenant
    request.state.token_hash = _token_hash(presented)
