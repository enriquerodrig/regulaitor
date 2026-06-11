"""H7 — slowapi Limiter configured for per-token rate limiting.

The key function reads request.state.token_hash (set by api.auth.verify_token).
Pre-auth requests fall through to the IP-based fallback, but in practice they
short-circuit at the verify_token Depends with 401 before hitting the limiter.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from slowapi import Limiter
from slowapi.util import get_remote_address

from regulaitor.security import tenancy

logger = logging.getLogger(__name__)

_TENANT_PREFIX = "tenant:"


def _safe_env_limit(env_var: str, default: str) -> str:
    """Return a parseable limit (review RL-1): if the operator env value is malformed,
    fall back to the hardcoded default with a WARNING rather than handing slowapi an
    unparseable string (which it silently drops -> fail-open / no limit)."""
    raw = os.getenv(env_var, default)
    try:
        tenancy._validate_rate_limit(raw)
        return raw
    except ValueError:
        logger.warning("invalid %s=%r; falling back to %s", env_var, raw, default)
        return default


def _key_func(request: Any) -> str:
    """Per-tenant rate-limit key (isolated buckets). Fase 4: keyed by tenant_id so
    one tenant cannot exhaust another's quota. Falls back to token_hash then IP."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        return f"{_TENANT_PREFIX}{tenant.tenant_id}"
    token_hash = getattr(request.state, "token_hash", None)
    if token_hash:
        return f"token:{token_hash}"
    return f"ip:{get_remote_address(request)}"


def _tenant_from_key(key: str, attr: str, env_var: str, default: str) -> str:
    """Resolve a per-tenant limit value from the rate-limit key. slowapi calls the
    limit-value callable with key_func(request) when it declares a `key` param."""
    if key.startswith(_TENANT_PREFIX):
        t = tenancy.tenant_by_id(key[len(_TENANT_PREFIX) :])
        if t is not None:
            return str(getattr(t, attr))  # validated at load (Tenant field validator)
    return _safe_env_limit(env_var, default)


def ask_limit(key: str) -> str:
    """Per-tenant /ask rate limit; falls back to REGULAITOR_RATE_LIMIT_ASK / 30/minute."""
    return _tenant_from_key(key, "rate_limit_ask", "REGULAITOR_RATE_LIMIT_ASK", "30/minute")


def analyze_limit(key: str) -> str:
    """Per-tenant /analyze rate limit; falls back to REGULAITOR_RATE_LIMIT_ANALYZE / 5/minute."""
    return _tenant_from_key(key, "rate_limit_analyze", "REGULAITOR_RATE_LIMIT_ANALYZE", "5/minute")


def _is_disabled() -> bool:
    """Tests can set REGULAITOR_RATE_LIMIT_DISABLED=1 to short-circuit limits."""
    return os.getenv("REGULAITOR_RATE_LIMIT_DISABLED", "").strip() == "1"


limiter = Limiter(
    key_func=_key_func,
    default_limits=[],
    enabled=not _is_disabled(),
    storage_uri="memory://",
)
