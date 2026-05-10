"""H7 — POST /ask handler."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from nanoid import generate

from regulaitor.api.auth import verify_token
from regulaitor.api.errors import BackendError, InjectionDetected
from regulaitor.api.logging import log_api_chat_turn
from regulaitor.api.schemas import AskRequest, AskResponse, to_ask_response
from regulaitor.orchestration.graph import run
from regulaitor.security.rate_limit import limiter

router = APIRouter(tags=["chat"])


def _generate_case_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"api-ch-{stamp}-{generate(size=8)}"


def _rate_limit_value() -> str:
    return os.getenv("REGULAITOR_RATE_LIMIT_ASK", "30/minute")


@router.post("/ask", response_model=AskResponse)
@limiter.limit(_rate_limit_value)
async def ask(
    request: Request,
    payload: AskRequest,
    _: None = Depends(verify_token),
) -> AskResponse:
    case_id = _generate_case_id()
    request.state.case_id = case_id
    t0 = time.monotonic()
    state = run(
        query=payload.query,
        corpus=payload.corpus,
        language=payload.language,
        case_id=case_id,
    )
    response_time_ms = int((time.monotonic() - t0) * 1000)
    if state.injection_blocked:
        raise InjectionDetected(case_id=case_id, reason_code="injection_blocked")
    if state.audited_answer is None or state.errors:
        raise BackendError(case_id=case_id, errors=list(state.errors))
    response = to_ask_response(state, response_time_ms=response_time_ms)
    log_api_chat_turn(request, state, response)
    return response
