"""H7 — FastAPI application entry point.

Lifespan loads the API token (fail-fast on missing/short). Exception handlers
are registered for all custom + backend + Anthropic + framework exceptions
plus a generic catch-all that redacts the original message.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from regulaitor.api import errors
from regulaitor.api.routes_analyze import router as analyze_router
from regulaitor.api.routes_ask import router as ask_router
from regulaitor.api.routes_health import router as health_router
from regulaitor.api.schemas import ErrorResponse
from regulaitor.corpus import loader as corpus_loader
from regulaitor.security import tenancy
from regulaitor.security.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fase 4: load the tenant registry (config-based; backward-compat single token).
    tenancy.load_tenants_or_raise()
    # Deep-review minor (architecture-coherence): pre-load manifests at startup
    # so the first /ask doesn't crash with KeyError("corpus not loaded; call
    # warmup() first") on the auto-corpus path. Mirrors the R11 fix that
    # Streamlit's app.py main() applied; the FastAPI surface needed equivalent.
    # corpus_loader.warmup() is idempotent (no-op after first call); safe to
    # invoke on every startup.
    corpus_loader.warmup()
    yield


app = FastAPI(
    title="RegulAItor API",
    version="0.0.8",
    description="Multi-agent regulatory compliance API. No citation, no answer.",
    lifespan=lifespan,
)
app.state.limiter = limiter


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = ErrorResponse(
        error_code="validation_error",
        message="Request body failed validation.",
        case_id=case_id,
    )
    return JSONResponse(status_code=422, content=body.model_dump())


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Map HTTPException 401/403 (e.g. from verify_token Depends) to ErrorResponse format.

    Narrowed to 401/403 only: RateLimitExceeded inherits from HTTPException and is
    handled by its own dedicated handler registered on the more-specific class.
    Other HTTPException status codes fall through to Starlette's default plain-text handler.
    """
    if exc.status_code not in (401, 403):
        raise exc
    case_id = getattr(request.state, "case_id", None)
    body = ErrorResponse(
        error_code=f"http_{exc.status_code}",
        message=str(exc.detail) if exc.detail else "Request failed.",
        case_id=case_id,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, errors.rate_limit_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.InjectionDetected, errors.injection_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.FileSizeExceeded, errors.file_size_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.UnsupportedMediaType, errors.unsupported_media_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.BackendError, errors.backend_error_handler)  # type: ignore[arg-type]
errors.register_anthropic_handlers(app)
app.add_exception_handler(Exception, errors.generic_handler)

app.include_router(health_router)
app.include_router(ask_router)
app.include_router(analyze_router)

# CORS — env-configurable allowlist. Empty value (default) = no CORS headers emitted
# (safe-by-default for non-browser API consumers). For browser deploy (Streamlit
# external, Next.js HX2 future), set REGULAITOR_CORS_ORIGINS to comma-separated list.
_cors_origins_raw = os.getenv("REGULAITOR_CORS_ORIGINS", "").strip()
if _cors_origins_raw:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=3600,
    )
