"""H7 — Bearer token authentication for the FastAPI surface.

Single static token loaded from REGULAITOR_API_TOKEN env var at app startup.
Validation uses hmac.compare_digest (timing-attack safe).
"""

from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import Header, HTTPException, Request

_API_TOKEN: str | None = None


def load_api_token_or_raise() -> None:
    """Load and validate the API token from env. Called from FastAPI lifespan."""
    global _API_TOKEN
    raw = os.getenv("REGULAITOR_API_TOKEN", "").strip()
    if not raw:
        raise RuntimeError(
            "REGULAITOR_API_TOKEN missing or empty. " "Set it in .env before starting the API."
        )
    if len(raw) < 16:
        raise RuntimeError("REGULAITOR_API_TOKEN must be at least 16 characters (entropy guard).")
    _API_TOKEN = raw


def _token_hash(token: str) -> str:
    """SHA256[:8] — used for logging + rate-limit key. Never the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


async def verify_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI Depends. Raises 401 on any auth failure; injects token_hash on success."""
    if _API_TOKEN is None:
        raise HTTPException(status_code=500, detail="API token not loaded")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    presented = authorization[len("Bearer ") :].strip()
    if not hmac.compare_digest(presented, _API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid API token")
    request.state.token_hash = _token_hash(presented)
