"""H7 — GET /health: readiness check (LanceDB + env vars + API token state)."""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from regulaitor.api.schemas import HealthCheck, HealthResponse
from regulaitor.rag.store import connect

router = APIRouter(tags=["meta"])

_VERSION = "0.0.8"


def _check_lancedb() -> HealthCheck:
    try:
        table = connect()
        n_chunks = int(table.count_rows())
    except Exception as exc:  # noqa: BLE001 — readiness check intentionally broad
        return HealthCheck(name="lancedb", status="unreachable", detail=type(exc).__name__)
    if n_chunks < 1:
        return HealthCheck(name="lancedb", status="degraded", detail=f"{n_chunks} chunks")
    return HealthCheck(name="lancedb", status="ok", detail=f"{n_chunks} chunks")


def _check_anthropic_key() -> HealthCheck:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return HealthCheck(name="anthropic_key", status="missing", detail=None)
    return HealthCheck(name="anthropic_key", status="present", detail=None)


def _check_api_token() -> HealthCheck:
    from regulaitor.api.auth import _API_TOKEN

    if _API_TOKEN is None:
        return HealthCheck(name="api_token", status="missing", detail=None)
    return HealthCheck(name="api_token", status="present", detail=None)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse | JSONResponse:
    checks = [_check_lancedb(), _check_anthropic_key(), _check_api_token()]
    overall = "ok" if all(c.status in ("ok", "present") for c in checks) else "degraded"
    response = HealthResponse(status=overall, version=_VERSION, checks=checks)
    if overall != "ok":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response
