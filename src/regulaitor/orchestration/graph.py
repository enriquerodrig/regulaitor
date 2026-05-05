"""LangGraph wiring for H4 chat E2E flow.

Nodes: injection_check -> (conditional) retriever -> analyst -> auditor -> END.
The injection_check node short-circuits to END if the user query matches a
known injection pattern.

Decisions log 2026-05-05 entries: "Auditor lean en H4" (injection check) +
"LangGraph state shape: Pydantic v2 BaseModel".
"""

from __future__ import annotations

from typing import Any, cast

from langgraph.graph import END, StateGraph

from regulaitor.agents.analyst import AnalystAgent
from regulaitor.agents.auditor import AuditorAgent
from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.orchestration.state import ChatState
from regulaitor.security import injection

# Module-level singletons (cheap to construct; expensive resources lazy-loaded inside).
# AnalystAgent.__init__ reads its prompt file once; Retriever and Auditor are stateless.
_RETRIEVER = RetrieverAgent()
_ANALYST = AnalystAgent()
_AUDITOR = AuditorAgent()


def _injection_check_node(state: ChatState) -> dict[str, Any]:
    blocked, reason = injection.is_injection(state.query)
    return {"injection_blocked": blocked, "injection_reason": reason}


def _route_after_injection(state: ChatState) -> str:
    return END if state.injection_blocked else "retriever"


def _retriever_node(state: ChatState) -> dict[str, Any]:
    ctx = _RETRIEVER.retrieve(state.query, state.corpus, state.language)
    return {"context": ctx}


def _analyst_node(state: ChatState) -> dict[str, Any]:
    if state.context is None:
        raise RuntimeError("analyst_node invoked without context (graph wiring bug)")
    answer = _ANALYST.analyze(state.query, state.context)
    return {"answer": answer}


def _auditor_node(state: ChatState) -> dict[str, Any]:
    if state.answer is None:
        raise RuntimeError("auditor_node invoked without answer (graph wiring bug)")
    audited = _AUDITOR.audit(state.answer)
    return {"audited_answer": audited}


def build_graph() -> Any:
    """Compile the H4 chat graph. Returns a LangGraph compiled graph."""
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


def run(*, query: str, corpus: str, language: str, case_id: str) -> ChatState:
    """Run the compiled graph; return the final ChatState."""
    initial = ChatState(
        case_id=case_id,
        query=query,
        corpus=cast(Norma, corpus),
        language=cast(Language, language),
    )
    final_dict = build_graph().invoke(initial)
    return ChatState.model_validate(final_dict)
