"""H7 — POST /ask handler."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from nanoid import generate

from regulaitor.api.auth import enforce_corpus_allowlist, verify_token
from regulaitor.api.errors import BackendError, InjectionDetected
from regulaitor.api.logging import log_api_chat_turn
from regulaitor.api.schemas import AskRequest, AskResponse, PIISummaryDTO, to_ask_response
from regulaitor.orchestration.graph import run
from regulaitor.security import pii
from regulaitor.security.rate_limit import ask_limit, limiter

logger = logging.getLogger("regulaitor.api.routes_ask")

# authz-01: router-level default-deny (verify_token also declared per-route; FastAPI
# caches by callable identity so it runs once). A future route on this router is
# auth-gated even if its author forgets the per-route Depends.
router = APIRouter(tags=["chat"], dependencies=[Depends(verify_token)])


def _generate_case_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"api-ch-{stamp}-{generate(size=8)}"


@router.post("/ask", response_model=AskResponse)
@limiter.limit(ask_limit)  # Fase 4: per-tenant limit (key = tenant:{id})
async def ask(
    request: Request,
    payload: AskRequest,
    _: None = Depends(verify_token),
) -> AskResponse:
    case_id = _generate_case_id()
    request.state.case_id = case_id
    # Fase 6B (ADR-0042): per-tenant corpus allowlist + model_choice.
    enforce_corpus_allowlist(request, [payload.corpus])
    tenant = getattr(request.state, "tenant", None)

    # P2.3 (§18.5): scan the query for PII BEFORE the pipeline, so the operator alert
    # fires ahead of the external LLM call. Advisory (like /analyze): the answer is
    # still produced; the counts-only summary (§18.8) is surfaced to the caller who
    # decides. The raw values never leave security.pii — only counts are logged.
    _pii = pii.summarize_pii(payload.query)
    pii_summary = (
        PIISummaryDTO(total=_pii.total, counts=dict(_pii.counts)) if _pii is not None else None
    )
    if pii_summary is not None:
        logger.warning(
            "pii_detected_in_query: %s",
            json.dumps({"case_id": case_id, "pii_counts": pii_summary.counts}, ensure_ascii=False),
        )

    t0 = time.monotonic()
    # Deep-review I1: offload sync run() to thread so event loop stays free for
    # concurrent traffic. Without this, all /ask requests serialize end-to-end
    # because run() blocks on Sonnet calls (5-40s typical).
    state = await asyncio.to_thread(
        run,
        query=payload.query,
        corpus=payload.corpus,
        language=payload.language,
        case_id=case_id,
        council_override=payload.council,
        model_choice=tenant.model_choice if tenant is not None else None,
    )
    response_time_ms = int((time.monotonic() - t0) * 1000)
    if state.injection_blocked:
        raise InjectionDetected(case_id=case_id, reason_code="injection_blocked")
    if state.audited_answer is None or state.errors:
        raise BackendError(case_id=case_id, errors=list(state.errors))
    response = to_ask_response(state, response_time_ms=response_time_ms, pii_summary=pii_summary)
    log_api_chat_turn(request, state, response)
    return response
