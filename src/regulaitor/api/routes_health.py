"""H7 — GET /health (public liveness) + GET /health/detailed (authed readiness).

Split per deep-review I3 / roadmap Q1.1: the public /health returns only the
readiness STATUS (200 / 503) so an unauthenticated caller learns ready/not-ready
but not which subsystem, the corpus size, or which keys are configured. The full
per-subsystem detail moves behind auth at /health/detailed.
"""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from regulaitor.api.auth import verify_token
from regulaitor.api.schemas import HealthCheck, HealthResponse, LivenessResponse
from regulaitor.observability import metrics
from regulaitor.rag.store import connect

router = APIRouter(tags=["meta"])

try:
    _VERSION = version("regulaitor")  # single source of truth = pyproject version
except PackageNotFoundError:  # pragma: no cover — package is always installed in prod
    _VERSION = "0.0.0"


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


def _gather_checks() -> tuple[Literal["ok", "degraded"], list[HealthCheck]]:
    """Run the critical readiness checks + the informational audit sub-check.

    `overall` is gated ONLY by the critical checks (→ 503 for orchestrators). The
    audit-DB sub-check (obs-08) is reported but never flips `overall` — a broken
    opt-in audit trail must not 503 the service.
    """
    critical = [_check_lancedb(), _check_anthropic_key(), _check_api_token()]
    overall: Literal["ok", "degraded"] = (
        "ok" if all(c.status in ("ok", "present") for c in critical) else "degraded"
    )
    checks = list(critical)
    audit_check = _check_audit_db()
    if audit_check is not None:
        checks.append(audit_check)
    return overall, checks


@router.get("/health", response_model=LivenessResponse)
async def health() -> LivenessResponse | JSONResponse:
    """Public liveness + readiness gate — status only, no config detail (deep-review
    I3). 200 when ready, 503 otherwise; the orchestrator healthcheck (`curl --fail`)
    still works, but a reconnaissance caller learns neither which subsystem failed
    nor the corpus size / configured keys. Full detail: GET /health/detailed."""
    overall, _checks = _gather_checks()
    response = LivenessResponse(status=overall, version=_VERSION)
    if overall != "ok":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response


@router.get("/health/detailed", response_model=HealthResponse)
async def health_detailed(_: None = Depends(verify_token)) -> HealthResponse | JSONResponse:
    """Authenticated readiness detail — the per-subsystem checks (LanceDB row count,
    key/token presence, audit-DB reachability). Behind verify_token so the config
    surface is not exposed unauthenticated. Operators use it for the sovereignty
    proof (anthropic_key: missing under the sovereign profile)."""
    overall, checks = _gather_checks()
    response = HealthResponse(status=overall, version=_VERSION, checks=checks)
    if overall != "ok":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> PlainTextResponse:
    """P3.1 metrics floor — Prometheus text exposition of the §6 verdict distribution
    (turns by mode+verdict → a scraper computes the live block-rate) + PII-query count.
    Fail-secure: 404 unless REGULAITOR_ENABLE_METRICS=1 (usage volume is not advertised
    publicly; the operator scrapes it on an internal network). No auth — like /health,
    it must be reachable by an unauthenticated scraper; restrict it at the network layer.
    """
    if not metrics.is_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return PlainTextResponse(
        metrics.render_prometheus(), media_type="text/plain; version=0.0.4; charset=utf-8"
    )
