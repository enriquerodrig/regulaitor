"""H7 — GET /health: readiness check (LanceDB + env vars + API token state)."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from regulaitor.api.schemas import HealthCheck, HealthResponse
from regulaitor.rag.store import connect

router = APIRouter(tags=["meta"])

_VERSION = "0.0.8"


def _check_lancedb() -> HealthCheck:
    try:
        # obs-02: READ-ONLY probe — never materialise an empty index from a health
        # check (that would mask the real "index missing" condition as a 0-chunk one).
        table = connect(create=False)
        n_chunks = int(table.count_rows())
    except FileNotFoundError:
        return HealthCheck(name="lancedb", status="unreachable", detail="index missing")
    except Exception as exc:  # noqa: BLE001 — readiness check intentionally broad
        return HealthCheck(name="lancedb", status="unreachable", detail=type(exc).__name__)
    if n_chunks < 1:
        return HealthCheck(name="lancedb", status="degraded", detail=f"{n_chunks} chunks")
    return HealthCheck(name="lancedb", status="ok", detail=f"{n_chunks} chunks")


def _check_audit_db() -> HealthCheck | None:
    """obs-08: non-fatal sub-check, only when the opt-in audit trail is configured.
    Reported in `checks` but does NOT gate the overall status / 503 — auditing is a
    non-critical opt-in subsystem and must never take the service down."""
    from regulaitor.observability import audit_store

    if not audit_store.is_enabled():
        return None
    if audit_store.is_healthy():
        return HealthCheck(name="audit_db", status="ok", detail="reachable")
    return HealthCheck(name="audit_db", status="degraded", detail="unreachable")


def _check_anthropic_key() -> HealthCheck:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return HealthCheck(name="anthropic_key", status="missing", detail=None)
    return HealthCheck(name="anthropic_key", status="present", detail=None)


def _check_api_token() -> HealthCheck:
    # Fase 4: the tenant registry stands in for the old single-token check.
    from regulaitor.security import tenancy

    if not tenancy.is_loaded():
        return HealthCheck(name="api_token", status="missing", detail=None)
    return HealthCheck(name="api_token", status="present", detail=None)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse | JSONResponse:
    # Critical checks gate the overall status (→ 503 for orchestrators).
    critical = [_check_lancedb(), _check_anthropic_key(), _check_api_token()]
    overall: Literal["ok", "degraded"] = (
        "ok" if all(c.status in ("ok", "present") for c in critical) else "degraded"
    )
    # obs-08: append the audit-DB sub-check as INFORMATIONAL — it is reported but does
    # not flip `overall` (a broken opt-in audit trail must not 503 the service).
    checks = list(critical)
    audit_check = _check_audit_db()
    if audit_check is not None:
        checks.append(audit_check)
    response = HealthResponse(status=overall, version=_VERSION, checks=checks)
    if overall != "ok":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response
