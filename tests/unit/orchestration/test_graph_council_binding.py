"""v0.1.19 — _council_node wiring tests for Council binding (ADR-0025).

Pins:
- The advisory path (no binding): existing behavior preserved.
- The binding-fires path (PASS + 3/3 BLOCK): _council_node returns new
  audited_answer with COUNCIL_BIND: reason prefix.
- The never-relax paths (BLOCK / RHR): verdict stays unchanged.
- Exception swallowing: same behavior as v0.1.18.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Context,
    CouncilReview,
    Finding,
    JudgeVote,
)
from regulaitor.orchestration.state import ChatState

B = AuditVerdict.BLOCK
P = AuditVerdict.PASS
R = AuditVerdict.REQUIRES_HUMAN_REVIEW


def _make_audited(verdict: AuditVerdict, reason: str | None = None) -> AuditedAnswer:
    citation = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="literal text",
    )
    audit_result = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    finding = Finding(text="claim", citations=[citation], severity="info")
    answer = Answer(query="q", language="es", text="resp", findings=[finding])
    return AuditedAnswer(
        answer=answer, verdict=verdict, audit_results=[audit_result], reason=reason
    )


def _make_review(votes: list[AuditVerdict]) -> CouncilReview:
    judges = [
        JudgeVote(
            model_id="fake",
            provider="fake",
            vote=v,
            reason="test",
            ok=True,
            error_category=None,
        )
        for v in votes
    ]
    return CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=judges,
        council_verdict=AuditVerdict.BLOCK if votes.count(B) >= 2 else AuditVerdict.PASS,
        agreement="unanimous" if len(set(votes)) == 1 else "majority",
        diverges_from_auditor=True,
        reason="test",
    )


def _make_state(audited: AuditedAnswer) -> ChatState:
    """Build a ChatState with all fields _council_node needs."""
    from datetime import datetime

    return ChatState(
        case_id="x",
        query="q",
        corpus="ai_act",
        language="es",
        answer=audited.answer,
        audited_answer=audited,
        context=Context(
            query="q",
            chunks=[],
            corpus="ai_act",
            language="es",
            retrieved_at=datetime.now(),
            embedding_model="test",
        ),
    )


def _patched_council_node(state: ChatState, votes: list[AuditVerdict]) -> dict:
    """Run _council_node with a mocked CouncilAgent that returns a synthetic
    review. Returns the node's output dict."""
    from regulaitor.orchestration import graph

    review = _make_review(votes)
    fake_agent = MagicMock()
    fake_agent.review.return_value = review
    # CouncilAgent uses MonotonicEscalatePolicy as the v0.1.19 default;
    # the mock just exposes _policy via the same attribute.
    from regulaitor.agents.council import MonotonicEscalatePolicy

    fake_agent._policy = MonotonicEscalatePolicy()

    # Monkey-patch _council() helper to return our fake agent.
    original_council = graph._council
    graph._council = lambda: fake_agent
    try:
        return graph._council_node(state)
    finally:
        graph._council = original_council


def test_council_node_records_review_when_no_binding() -> None:
    """Auditor=PASS + Council non-unanimous BLOCK → records review only;
    audited_answer not returned (so ChatState.audited_answer stays unchanged)."""
    state = _make_state(_make_audited(P))
    result = _patched_council_node(state, [B, B, P])  # 2/3 BLOCK, not unanimous
    assert "council_review" in result
    assert "audited_answer" not in result


def test_council_node_binds_verdict_on_unanimous_block() -> None:
    """Auditor=PASS + Council 3/3 BLOCK → binding fires; node returns both
    council_review AND escalated audited_answer with COUNCIL_BIND: prefix."""
    state = _make_state(_make_audited(P))
    result = _patched_council_node(state, [B, B, B])
    assert "council_review" in result
    assert "audited_answer" in result
    new_audited = result["audited_answer"]
    assert new_audited.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert new_audited.reason is not None
    assert new_audited.reason.startswith("COUNCIL_BIND:")


def test_council_node_never_relaxes_block() -> None:
    """Auditor=BLOCK + Council unanimous PASS → never relaxes; no binding."""
    state = _make_state(_make_audited(B))
    result = _patched_council_node(state, [P, P, P])
    assert "audited_answer" not in result


def test_council_node_never_relaxes_rhr() -> None:
    """Auditor=RHR + Council unanimous PASS → never relaxes; no binding.
    Pins the H13 false-RHR pattern UNCHANGED in v0.1.19 (per ADR-0025)."""
    state = _make_state(_make_audited(R))
    result = _patched_council_node(state, [P, P, P])
    assert "audited_answer" not in result


def test_council_node_swallows_exceptions_unchanged() -> None:
    """If Council.review raises, _council_node returns {} (existing behavior
    preserved; the chat turn must not break on Council failures)."""
    from regulaitor.orchestration import graph

    state = _make_state(_make_audited(P))
    fake_agent = MagicMock()
    fake_agent.review.side_effect = RuntimeError("simulated council failure")

    original_council = graph._council
    graph._council = lambda: fake_agent
    try:
        result = graph._council_node(state)
        assert result == {}
    finally:
        graph._council = original_council


def test_council_node_swallows_bind_verdict_exception() -> None:
    """Deep-review minor: if a future custom AggregationPolicy raises inside
    bind_verdict (e.g. buggy would_escalate implementation), _council_node
    must still return {} not propagate to the turn. The broad try/except in
    graph._council_node (lines 143-147) covers Council.review AND bind_verdict;
    the existing test covers only Council.review.
    """
    from unittest.mock import patch

    from regulaitor.orchestration import graph

    state = _make_state(_make_audited(P))
    # Council.review succeeds (returns a real-shaped review); bind_verdict raises.
    fake_agent = MagicMock()
    fake_review = MagicMock()
    fake_agent.review.return_value = fake_review

    original_council = graph._council
    graph._council = lambda: fake_agent
    try:
        with patch.object(
            graph, "bind_verdict", side_effect=RuntimeError("simulated bind_verdict bug")
        ):
            result = graph._council_node(state)
        assert result == {}
    finally:
        graph._council = original_council
