"""H7 — slowapi Limiter configured for per-token rate limiting.

The key function reads request.state.token_hash (set by api.auth.verify_token).
Pre-auth requests fall through to the IP-based fallback, but in practice they
short-circuit at the verify_token Depends with 401 before hitting the limiter.
"""

from __future__ import annotations

import os
from typing import Any

from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request: Any) -> str:
    """Per-token rate limit key. Falls back to client IP if no token_hash set."""
    token_hash = getattr(request.state, "token_hash", None)
    if token_hash:
        return f"token:{token_hash}"
    return f"ip:{get_remote_address(request)}"


def _is_disabled() -> bool:
    """Tests can set REGULAITOR_RATE_LIMIT_DISABLED=1 to short-circuit limits."""
    return os.getenv("REGULAITOR_RATE_LIMIT_DISABLED", "").strip() == "1"


limiter = Limiter(
    key_func=_key_func,
    default_limits=[],
    enabled=not _is_disabled(),
    storage_uri="memory://",
)
