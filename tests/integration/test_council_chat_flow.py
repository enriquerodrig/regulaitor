from __future__ import annotations

from datetime import UTC
from unittest.mock import patch

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote
from regulaitor.orchestration import graph as g


def _council_review(verdict=AuditVerdict.BLOCK, diverges=True):
    return CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="m",
                provider="p",
                vote=verdict,
                reason="r",
                ok=True,
                error_category=None,
            )
        ],
        council_verdict=verdict,
        agreement="degraded",
        diverges_from_auditor=diverges,
        reason="test",
    )


def _state_with_audited():
    from datetime import datetime

    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        Citation,
        Context,
        Finding,
    )
    from regulaitor.orchestration.state import ChatState

    ans = Answer(
        query="q",
        language="es",
        text="t",
        findings=[
            Finding(
                text="f",
                citations=[
                    Citation(
                        norma="ai_act",
                        articulo="6",
                        apartado="1",
                        language="es",
                        text="x",
                    )
                ],
                severity="high",
            )
        ],
    )
    ctx = Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        embedding_model="test",
    )
    state = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    state.audited_answer = AuditedAnswer(
        answer=ans, verdict=AuditVerdict.PASS, audit_results=[], reason=None
    )
    state.context = ctx
    return state


def test_council_node_attaches_review_without_changing_verdict():
    """v0.1.19: council node records review; bind_verdict returns None when
    policy.would_escalate returns same verdict as current, so the node
    returns only {"council_review": ...} without "audited_answer"."""
    state = _state_with_audited()
    with patch.object(g, "_council") as mk:
        # Mock the council agent and its policy's would_escalate method.
        # would_escalate returns the current verdict (no escalation), so
        # bind_verdict returns None and the node only returns council_review.
        mk.return_value.review.return_value = _council_review()
        mk.return_value._policy.would_escalate.return_value = AuditVerdict.PASS
        out = g._council_node(state)
    assert isinstance(out["council_review"], CouncilReview)
    # bind_verdict returns None (no escalation), so no "audited_answer" in out.
    assert "audited_answer" not in out


def test_council_node_returns_empty_when_context_missing():
    """Guard: audited_answer set but context is None → {} (advisory, no crash)."""
    state = _state_with_audited()
    state.context = None  # simulate a graph rewiring where context never set
    # _council() should never be called; no mock needed
    out = g._council_node(state)
    assert out == {}


def test_council_node_swallows_exceptions():
    # Covers BOTH _council() construction failure and .review() failure
    # (both inside the single try in _council_node).
    state = _state_with_audited()
    with patch.object(g, "_council") as mk:
        mk.return_value.review.side_effect = RuntimeError("boom")
        out = g._council_node(state)
    assert out == {}  # advisory: failure yields no state change


def test_run_threads_council_override(monkeypatch):
    seen = {}

    class _FakeCompiled:
        def invoke(self, initial):
            seen["override"] = initial.council_override
            initial.audited_answer = None
            return initial.model_dump()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _FakeCompiled())
    g.run(query="q", corpus="ai_act", language="es", case_id="c", council_override=True)
    assert seen["override"] is True
