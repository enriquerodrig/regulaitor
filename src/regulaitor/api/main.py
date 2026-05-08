"""H7 — FastAPI application entry point.

Lifespan loads the API token (fail-fast on missing/short). Exception handlers
are registered for all custom + backend + Anthropic + framework exceptions
plus a generic catch-all that redacts the original message.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from regulaitor.api import auth, errors
from regulaitor.api.routes_analyze import router as analyze_router
from regulaitor.api.routes_ask import router as ask_router
from regulaitor.api.routes_health import router as health_router
from regulaitor.api.schemas import ErrorResponse
from regulaitor.citation.schemas import DocumentBlockedError
from regulaitor.security.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    auth.load_api_token_or_raise()
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


app.add_exception_handler(RequestValidationError, _validation_handler)
app.add_exception_handler(RateLimitExceeded, errors.rate_limit_handler)
app.add_exception_handler(errors.InjectionDetected, errors.injection_handler)
app.add_exception_handler(errors.FileSizeExceeded, errors.file_size_handler)
app.add_exception_handler(errors.UnsupportedMediaType, errors.unsupported_media_handler)
app.add_exception_handler(errors.BackendError, errors.backend_error_handler)
app.add_exception_handler(DocumentBlockedError, errors.document_blocked_handler)
errors.register_anthropic_handlers(app)
app.add_exception_handler(Exception, errors.generic_handler)

app.include_router(health_router)
app.include_router(ask_router)
app.include_router(analyze_router)
