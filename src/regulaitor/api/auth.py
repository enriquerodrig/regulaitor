"""H7 — Bearer token authentication for the FastAPI surface.

Single static token loaded from REGULAITOR_API_TOKEN env var at app startup.
Validation uses hmac.compare_digest (timing-attack safe).

verify_token uses Security(HTTPBearer) so that FastAPI/OpenAPI automatically
advertises the Bearer scheme in /openapi.json, enabling the Authorize button in /docs.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_API_TOKEN: str | None = None

_bearer = HTTPBearer(auto_error=False, scheme_name="REGULAITOR_API_TOKEN")


def load_api_token_or_raise() -> None:
    """Load and validate the API token from env. Called from FastAPI lifespan."""
    global _API_TOKEN
    raw = os.getenv("REGULAITOR_API_TOKEN", "").strip()
    if not raw:
        raise RuntimeError(
            "REGULAITOR_API_TOKEN missing or empty. Set it in .env before starting the API."
        )
    if len(raw) < 16:
        raise RuntimeError("REGULAITOR_API_TOKEN must be at least 16 characters (entropy guard).")
    _API_TOKEN = raw


def _token_hash(token: str) -> str:
    """SHA256[:8] — used for logging + rate-limit key. Never the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),  # noqa: B008
) -> None:
    """FastAPI Depends. Raises 401 on any auth failure; injects token_hash on success.

    Using Security(HTTPBearer) causes FastAPI to advertise the Bearer scheme in
    /openapi.json so the Swagger UI /docs shows the Authorize button.
    """
    if _API_TOKEN is None:
        # Defensive: lifespan loads token; this branch should be unreachable in production.
        raise HTTPException(status_code=500, detail="Internal server error")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    presented = credentials.credentials
    if not hmac.compare_digest(presented, _API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid API token")
    request.state.token_hash = _token_hash(presented)
