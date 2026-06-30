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
from starlette.exceptions import HTTPException as StarletteHTTPException

from regulaitor.api import errors
from regulaitor.api.routes_analyze import router as analyze_router
from regulaitor.api.routes_ask import router as ask_router
from regulaitor.api.routes_audit import router as audit_router
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


# authz-02: /docs, /redoc and /openapi.json are an UNAUTHENTICATED map of the API
# surface. Gated behind REGULAITOR_ENABLE_DOCS (default ON to preserve dev DX + the
# BFF `npm run gen:types` workflow that reads /openapi.json). Set =0 before an
# external pilot to stop advertising the schema publicly.
_docs_enabled = os.getenv("REGULAITOR_ENABLE_DOCS", "1").strip() != "0"

app = FastAPI(
    title="RegulAItor API",
    version="0.0.8",
    description="Multi-agent regulatory compliance API. No citation, no answer.",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
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
    """Map ANY HTTPException to the uniform ErrorResponse JSON shape (audit err-04).

    Previously only 401/403 were mapped; every other app-raised code was re-raised
    into the generic catch-all and reported as 500. Now all codes keep their status.
    Registered on BOTH fastapi.HTTPException AND starlette.exceptions.HTTPException so
    that framework-raised routing errors (404 unmatched route, 405 method) also return
    the {error_code, message, case_id} envelope instead of Starlette's plain
    {"detail": ...} — one consistent error shape for API consumers.

    RateLimitExceeded subclasses the Starlette HTTPException but has its own dedicated
    handler registered on the (more specific) RateLimitExceeded class; Starlette's
    MRO-first-match dispatch picks that, so 429 is never routed here. 5xx detail is
    redacted to avoid leaking internals.
    """
    case_id = getattr(request.state, "case_id", None)
    message = str(exc.detail) if exc.detail and exc.status_code < 500 else "Request failed."
    body = ErrorResponse(
        error_code=f"http_{exc.status_code}",
        message=message,
        case_id=case_id,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, errors.rate_limit_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.InjectionDetected, errors.injection_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.FileSizeExceeded, errors.file_size_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.UnsupportedMediaType, errors.unsupported_media_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.CorpusNotAllowed, errors.corpus_not_allowed_handler)  # type: ignore[arg-type]
app.add_exception_handler(errors.BackendError, errors.backend_error_handler)  # type: ignore[arg-type]
errors.register_anthropic_handlers(app)
app.add_exception_handler(Exception, errors.generic_handler)

app.include_router(health_router)
app.include_router(ask_router)
app.include_router(analyze_router)
app.include_router(audit_router)

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
