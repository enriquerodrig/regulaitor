"""H7 — POST /analyze handler with multipart upload + size cap."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from nanoid import generate

from regulaitor.api.auth import enforce_corpus_allowlist, verify_token
from regulaitor.api.errors import FileSizeExceeded, UnsupportedMediaType
from regulaitor.api.logging import log_api_document_turn
from regulaitor.api.schemas import AnalyzeResponse, to_analyze_response
from regulaitor.corpus.registry import ALL_NORMAS
from regulaitor.orchestration.document_graph import run_document
from regulaitor.security.rate_limit import analyze_limit, limiter

# authz-01: router-level default-deny (verify_token also declared per-route; FastAPI
# caches by callable identity so it runs once). A future route on this router is
# auth-gated even if its author forgets the per-route Depends.
router = APIRouter(tags=["document"], dependencies=[Depends(verify_token)])


def _max_bytes() -> int:
    """Read at call time so tests can monkeypatch.setenv before the request."""
    return int(os.getenv("REGULAITOR_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))


def _generate_case_id() -> str:
    return f"api-doc-{datetime.now(UTC):%Y%m%d}-{generate(size=8)}"


def _detect_mime(filename: str, head: bytes) -> str:
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    lower = filename.lower()
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return "text/markdown"
    raise UnsupportedMediaType(reason="unsupported file format")


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(analyze_limit)  # Fase 4: per-tenant limit (key = tenant:{id})
async def analyze(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    corpus: list[str] = Form(...),  # noqa: B008
    language: str = Form(...),  # noqa: B008
    _: None = Depends(verify_token),
) -> AnalyzeResponse:
    case_id = _generate_case_id()
    request.state.case_id = case_id

    body = await file.read()
    max_b = _max_bytes()
    if len(body) > max_b:
        raise FileSizeExceeded(size=len(body), max_size=max_b)
    if len(body) == 0:
        raise UnsupportedMediaType(reason="empty file")

    mime_type = _detect_mime(file.filename or "", body[:8])

    if language not in ("es", "en"):
        raise UnsupportedMediaType(reason=f"unsupported language: {language}")
    # Deep-review minor (§6 defense-in-depth): reject empty corpus list early.
    # Without this, run_document downstream hit IndexError on corpus[0] in
    # document_graph._aggregate (the v0.1.28 corpus-collapse-to-first-element
    # path). Return 415 here for a clean operator signal.
    if not corpus:
        raise UnsupportedMediaType(reason="corpus list cannot be empty")
    if not all(c in ALL_NORMAS for c in corpus):
        raise UnsupportedMediaType(reason="unsupported corpus member")
    # Fase 6B (ADR-0042): per-tenant corpus allowlist (403 if any member is off-list).
    enforce_corpus_allowlist(request, corpus)

    t0 = time.monotonic()
    # Deep-review I1: offload sync run_document() to thread so event loop stays
    # free for concurrent traffic. Doc-mode wallclock is multi-minute; without
    # this, all /analyze requests serialize and /ask is blocked too.
    report = await asyncio.to_thread(
        run_document,
        file_bytes=body,
        mime_type=mime_type,
        language=language,  # type: ignore[arg-type]
        corpus=corpus,
        case_id=case_id,
    )
    response_time_ms = int((time.monotonic() - t0) * 1000)
    response = to_analyze_response(report, response_time_ms=response_time_ms)
    log_api_document_turn(request, report, response)
    return response
