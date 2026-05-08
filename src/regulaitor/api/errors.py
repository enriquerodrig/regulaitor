"""H7 — Custom API exceptions + global exception handlers.

All handlers redact internal state (stack traces, raw exception messages,
internal flags) before returning. The response body is always an ErrorResponse
JSON object: {error_code, message, case_id}.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from regulaitor.api.schemas import ErrorResponse
from regulaitor.citation.schemas import DocumentBlockedError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom API exceptions
# ---------------------------------------------------------------------------


class InjectionDetected(Exception):  # noqa: N818 — spec uses non-Error suffix; see ADR 0009
    """Anti-injection gate rejected the input. Raised by routes_ask."""

    def __init__(self, case_id: str, reason_code: str) -> None:
        super().__init__(reason_code)
        self.case_id = case_id
        self.reason_code = reason_code


class BackendError(Exception):
    """Backend pipeline returned a state with errors or no audited_answer."""

    def __init__(self, case_id: str, errors: list[str]) -> None:
        super().__init__("backend_error")
        self.case_id = case_id
        self.errors = errors  # logged only, never returned


class FileSizeExceeded(Exception):  # noqa: N818 — spec uses non-Error suffix; see ADR 0009
    """Upload exceeds the configured max size."""

    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(f"size {size} exceeds max {max_size}")
        self.size = size
        self.max_size = max_size


class UnsupportedMediaType(Exception):  # noqa: N818 — spec uses non-Error suffix; see ADR 0009
    """Upload has an unsupported MIME type, missing magic bytes, or invalid form fields."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason_code = reason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build(error_code: str, message: str, case_id: str | None) -> ErrorResponse:
    return ErrorResponse(error_code=error_code, message=message, case_id=case_id)


def _json(
    response: ErrorResponse,
    status: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=status, content=response.model_dump(), headers=headers)


def _log_error(
    request: Request,
    *,
    status: int,
    error_code: str,
    case_id: str | None,
    **extra: Any,
) -> None:
    record = {
        "case_id": case_id,
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": status,
        "token_hash": getattr(request.state, "token_hash", None),
        "error_code": error_code,
        **extra,
    }
    logger.warning("api_error: %s", json.dumps(record, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def injection_handler(request: Request, exc: InjectionDetected) -> JSONResponse:
    body = _build("injection_blocked", "Input rejected by anti-injection gate.", exc.case_id)
    _log_error(request, status=400, error_code="injection_blocked", case_id=exc.case_id)
    return _json(body, 400)


async def document_blocked_handler(request: Request, exc: DocumentBlockedError) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build(
        "document_blocked",
        "Document rejected by sanitizer (critical content).",
        case_id,
    )
    _log_error(request, status=422, error_code="document_blocked", case_id=case_id)
    return _json(body, 422)


async def file_size_handler(request: Request, exc: FileSizeExceeded) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("payload_too_large", f"File size exceeds {exc.max_size} bytes.", case_id)
    _log_error(request, status=413, error_code="payload_too_large", case_id=case_id)
    return _json(body, 413)


async def unsupported_media_handler(request: Request, exc: UnsupportedMediaType) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("unsupported_media", "Unsupported file or input format.", case_id)
    _log_error(request, status=415, error_code="unsupported_media", case_id=case_id)
    return _json(body, 415)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("rate_limit_exceeded", "Too many requests. Retry later.", case_id)
    _log_error(request, status=429, error_code="rate_limit_exceeded", case_id=case_id)
    return _json(body, 429, headers={"Retry-After": "60"})


async def backend_error_handler(request: Request, exc: BackendError) -> JSONResponse:
    body = _build(
        "backend_error",
        f"Internal pipeline error. Reference: {exc.case_id}",
        exc.case_id,
    )
    # Truncate per-string (200 chars) and per-list (10 entries) to avoid logging
    # sensitive backend payloads in plain text (CLAUDE.md §18).
    truncated = [e[:200] for e in exc.errors[:10]]
    _log_error(
        request,
        status=500,
        error_code="backend_error",
        case_id=exc.case_id,
        backend_errors=truncated,
    )
    return _json(body, 500)


async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    msg = f"Internal server error. Reference: {case_id}" if case_id else "Internal server error."
    body = _build("internal_error", msg, case_id)
    _log_error(
        request,
        status=500,
        error_code="internal_error",
        case_id=case_id,
        exc_type=type(exc).__name__,
    )
    return _json(body, 500)


def register_anthropic_handlers(app: FastAPI) -> None:
    """Lazy import to avoid forcing anthropic dep at module import.

    Catches both ImportError (anthropic not installed) and AttributeError
    (partial install where the class names changed between versions).
    """
    try:
        from anthropic import AuthenticationError, BadRequestError
    except (ImportError, AttributeError):
        return

    async def auth_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        case_id = getattr(request.state, "case_id", None)
        body = _build(
            "upstream_auth_failed",
            "Upstream LLM auth failed (server config issue).",
            case_id,
        )
        _log_error(request, status=502, error_code="upstream_auth_failed", case_id=case_id)
        return _json(body, 502)

    async def bad_request_handler(request: Request, exc: BadRequestError) -> JSONResponse:
        case_id = getattr(request.state, "case_id", None)
        msg = str(exc).lower()
        if "credit balance" in msg:
            body = _build(
                "upstream_billing",
                "Upstream LLM billing issue. Try again later.",
                case_id,
            )
            _log_error(
                request,
                status=503,
                error_code="upstream_billing",
                case_id=case_id,
                exc_type=type(exc).__name__,
            )
            return _json(body, 503)
        body = _build(
            "upstream_bad_request",
            "Upstream LLM rejected the request.",
            case_id,
        )
        _log_error(
            request,
            status=502,
            error_code="upstream_bad_request",
            case_id=case_id,
            exc_type=type(exc).__name__,
        )
        return _json(body, 502)

    app.add_exception_handler(AuthenticationError, auth_handler)  # type: ignore[arg-type]
    app.add_exception_handler(BadRequestError, bad_request_handler)  # type: ignore[arg-type]
