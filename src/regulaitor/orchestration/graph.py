"""LangGraph wiring for H4 chat E2E flow.

Nodes: injection_check -> (conditional) retriever -> analyst -> auditor -> END.
The injection_check node short-circuits to END if the user query matches a
known injection pattern.

Decisions log 2026-05-05 entries: "Auditor lean en H4" (injection check) +
"LangGraph state shape: Pydantic v2 BaseModel".
"""

from __future__ import annotations

import functools
import json
import logging
import time
from typing import Any, cast

from langgraph.graph import END, StateGraph

from regulaitor.agents.analyst import AnalystAgent
from regulaitor.agents.auditor import AuditorAgent
from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.observability.langfuse_client import hash12, trace_turn
from regulaitor.orchestration.state import ChatState
from regulaitor.security import injection

logger = logging.getLogger("regulaitor.orchestration.graph")


# Lazy-init agent helpers. Avoids import-time I/O (AnalystAgent reads its
# prompt file in __init__); a missing prompt only fails at first use, not
# at module import. Each helper is cached so we still construct each agent
# at most once per process.
@functools.lru_cache(maxsize=1)
def _retriever() -> RetrieverAgent:
    return RetrieverAgent()


@functools.lru_cache(maxsize=1)
def _analyst() -> AnalystAgent:
    return AnalystAgent()


@functools.lru_cache(maxsize=1)
def _auditor() -> AuditorAgent:
    return AuditorAgent()


def _injection_check_node(state: ChatState) -> dict[str, Any]:
    blocked, reason = injection.is_injection(state.query)
    return {"injection_blocked": blocked, "injection_reason": reason}


def _route_after_injection(state: ChatState) -> str:
    return END if state.injection_blocked else "retriever"


def _retriever_node(state: ChatState) -> dict[str, Any]:
    ctx = _retriever().retrieve(state.query, state.corpus, state.language)
    return {"context": ctx}


def _analyst_node(state: ChatState) -> dict[str, Any]:
    if state.context is None:
        raise RuntimeError("analyst_node invoked without context (graph wiring bug)")
    answer = _analyst().analyze(state.query, state.context)
    return {"answer": answer}


def _auditor_node(state: ChatState) -> dict[str, Any]:
    if state.answer is None:
        raise RuntimeError("auditor_node invoked without answer (graph wiring bug)")
    audited = _auditor().audit(state.answer)
    return {"audited_answer": audited}


def build_graph() -> Any:
    """Compile the H4 chat graph. Returns a LangGraph compiled graph.

    Returns a fresh compiled graph each call; tests use this directly when
    they want isolation. Production callers should go through ``run`` which
    caches the compiled graph via ``_compiled_graph``.
    """
    g = StateGraph(ChatState)
    g.add_node("injection_check", _injection_check_node)
    g.add_node("retriever", _retriever_node)
    g.add_node("analyst", _analyst_node)
    g.add_node("auditor", _auditor_node)

    g.set_entry_point("injection_check")
    g.add_conditional_edges(
        "injection_check",
        _route_after_injection,
        {"retriever": "retriever", END: END},
    )
    g.add_edge("retriever", "analyst")
    g.add_edge("analyst", "auditor")
    g.add_edge("auditor", END)

    return g.compile()


@functools.lru_cache(maxsize=1)
def _compiled_graph() -> Any:
    """Cached compiled graph; built lazily on first invocation."""
    return build_graph()


def _trace_record(state: ChatState, latency_ms_total: int) -> dict[str, object]:
    """Metadata-only summary of a chat turn. NO raw query — only a
    sha256[:12] prefix (CLAUDE.md §10.5/§18.8). Shared by the JSON log
    line and the LangFuse trace."""
    query_hash = hash12(state.query)
    verdict: str
    n_findings = 0
    n_citations = 0
    n_validated = 0
    n_blocked = 0
    reason_code: str | None = None
    if state.injection_blocked:
        verdict = "blocked_injection"
        reason_code = state.injection_reason
    elif state.audited_answer is not None:
        audited = state.audited_answer
        verdict = audited.verdict.value
        n_findings = len(audited.answer.findings)
        n_citations = len(audited.audit_results)
        n_validated = sum(1 for r in audited.audit_results if r.validated)
        n_blocked = n_citations - n_validated
        reason_code = None if audited.reason is None else audited.reason.split(":", 1)[0]
    else:
        verdict = "no_answer"
    return {
        "case_id": state.case_id,
        "query_hash": query_hash,
        "corpus": state.corpus,
        "language": state.language,
        "verdict": verdict,
        "n_findings": n_findings,
        "n_citations": n_citations,
        "n_validated": n_validated,
        "n_blocked": n_blocked,
        "latency_ms_total": latency_ms_total,
        "reason_code": reason_code,
        "errors": list(state.errors),
    }


def _log_turn(state: ChatState, latency_ms_total: int) -> dict[str, object]:
    """Emit the structured JSON log line and return the record. Single
    source of truth for both the log line and the LangFuse trace."""
    record = _trace_record(state, latency_ms_total)
    logger.info("chat_turn: %s", json.dumps(record, ensure_ascii=False))
    return record


def run(*, query: str, corpus: str, language: str, case_id: str) -> ChatState:
    """Run the cached compiled graph; return the final ChatState."""
    with trace_turn(kind="chat", case_id=case_id, corpus=corpus, language=language) as tt:
        initial = ChatState(
            case_id=case_id,
            query=query,
            corpus=cast(Norma, corpus),
            language=cast(Language, language),
        )
        t0 = time.monotonic()
        final_dict = _compiled_graph().invoke(initial)
        latency_ms_total = int((time.monotonic() - t0) * 1000)
        state = ChatState.model_validate(final_dict)
        record = _log_turn(state, latency_ms_total)
        tt.set_root(
            verdict=record["verdict"],
            query_sha256_12=record["query_hash"],
            n_findings=record["n_findings"],
            n_citations=record["n_citations"],
            n_validated=record["n_validated"],
            n_blocked=record["n_blocked"],
            latency_ms_total=record["latency_ms_total"],
            # errors: pipeline error CATEGORY strings only (no user text);
            # see langfuse_client redaction allowlist.
            errors=record["errors"],
        )
        return state
