"""H7 — HTTP-level structured logging for API requests.

Emits one log record per successful request (errors are logged separately by
api.errors handlers). Records carry both backend fields (verdict, n_findings,
cost_eur for documents) and HTTP fields (status, token_hash, redacted IP).
"""

from __future__ import annotations

import ipaddress
import json
import logging
from typing import Any

from regulaitor.api.schemas import AnalyzeResponse, AskResponse
from regulaitor.citation.schemas import DocumentReport
from regulaitor.orchestration.state import ChatState

logger = logging.getLogger(__name__)


def _redact_ip(client_ip: str | None) -> str | None:
    """IPv4 -> /24 prefix, IPv6 -> /48 prefix. Returns None on parse failure."""
    if not client_ip:
        return None
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv4Address):
        net = ipaddress.ip_network(f"{ip}/24", strict=False)
        return str(net.network_address)
    net = ipaddress.ip_network(f"{ip}/48", strict=False)
    return str(net.network_address)


def log_api_chat_turn(request: Any, state: ChatState, response: AskResponse) -> None:
    """Emit one structured INFO record for a completed /ask request."""
    record = {
        "case_id": state.case_id,
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": 200,
        "token_hash": getattr(request.state, "token_hash", None),
        "client_ip_redacted": _redact_ip(request.client.host if request.client else None),
        "verdict": response.verdict,
        "n_findings": len(response.answer.findings),
        "n_citations": len(response.audit_results),
        "n_validated": sum(1 for r in response.audit_results if r.validated),
        "response_time_ms": response.response_time_ms,
        "corpus": str(state.corpus),
        "language": str(state.language),
    }
    logger.info("api_chat_turn: %s", json.dumps(record, ensure_ascii=False))


def log_api_document_turn(request: Any, report: DocumentReport, response: AnalyzeResponse) -> None:
    """Emit one structured INFO record for a completed /analyze request."""
    record = {
        "case_id": report.case_id,
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": 200,
        "token_hash": getattr(request.state, "token_hash", None),
        "client_ip_redacted": _redact_ip(request.client.host if request.client else None),
        "document_verdict": response.document_verdict,
        "n_segments_total": response.n_segments_total,
        "n_segments_pass": response.n_segments_pass,
        "n_segments_block": response.n_segments_block,
        "n_segments_review": response.n_segments_review,
        "n_segments_blocked_by_injection": response.n_segments_blocked_by_injection,
        "latency_ms_total": response.latency_ms_total,
        "cost_eur_total": response.cost_eur_total,
        "response_time_ms": response.response_time_ms,
        "corpus": report.corpus,
        "language": str(report.language),
    }
    logger.info("api_document_turn: %s", json.dumps(record, ensure_ascii=False))
