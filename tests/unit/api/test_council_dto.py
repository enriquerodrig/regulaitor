from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulaitor.api.schemas import (
    AskRequest,
    _council_notice,
    _council_review_to_dto,
    to_ask_response,
)
from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote


def _cr(diverges):
    return CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="claude-haiku-4-5-20251001",
                provider="anthropic",
                vote=AuditVerdict.BLOCK,
                reason="no soporta",
                ok=True,
                error_category=None,
            )
        ],
        council_verdict=AuditVerdict.BLOCK,
        agreement="degraded",
        diverges_from_auditor=diverges,
        reason="x",
    )


def test_ask_request_accepts_council_flag():
    assert AskRequest(query="q", corpus="ai_act", language="es").council is None
    assert AskRequest(query="q", corpus="ai_act", language="es", council=True).council is True


def test_notice_present_only_when_diverges():
    assert _council_notice(_cr(True)) is not None
    assert _council_notice(_cr(False)) is None
    assert _council_notice(None) is None


def test_council_notice_suppressed_when_unavailable_no_judge_ok():
    """Sovereign deploy: when NO judge responded (all ok=False — e.g. no judge
    API keys, since Haiku/GPT-4o/Llama are all US-hosted and their keys are
    removed), the Council could not run. It did NOT 'diverge'; suppress the
    misleading notice so the deterministic Auditor verdict stands alone."""
    cr = CouncilReview(
        triggered=True,
        trigger_reason="high_severity",
        judges=[
            JudgeVote(
                model_id="claude-haiku-4-5-20251001",
                provider="anthropic",
                vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                reason="judge_failed",
                ok=False,
                error_category="RuntimeError",
            ),
            JudgeVote(
                model_id="gpt-4o",
                provider="openai",
                vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                reason="judge_failed",
                ok=False,
                error_category="RuntimeError",
            ),
        ],
        council_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        agreement="degraded",
        diverges_from_auditor=True,  # policy may still flag divergence when unavailable
        reason="council_unavailable: 0/2 judges responded",
    )
    assert _council_notice(cr) is None


def test_dto_redacts_to_allowlisted_fields():
    dto = _council_review_to_dto(_cr(True))
    assert dto.council_verdict == "block"
    assert dto.diverges_from_auditor is True
    j = dto.judges[0]
    assert j.model_id == "claude-haiku-4-5-20251001"
    assert j.vote == "block"
    # no raw answer/query text leaks through the DTO
    assert not hasattr(j, "answer")


def test_ask_request_council_rejects_string_coercion():
    # Pydantic lax mode would coerce "true" -> True; the API contract must be strict.
    with pytest.raises(ValidationError):
        AskRequest(query="q", corpus="ai_act", language="es", council="true")


def test_to_ask_response_wires_council_end_to_end():
    """Fix M2: to_ask_response populates both council and council_notice from ChatState."""
    from tests.unit.test_api_schemas import _make_chat_state

    # Path 1: council_review present and diverging → both fields populated.
    state = _make_chat_state(blocked=False)
    state.council_review = _cr(True)  # diverges_from_auditor=True, verdict=BLOCK
    resp = to_ask_response(state, response_time_ms=10)
    assert resp.council is not None
    assert resp.council.council_verdict == "block"
    assert resp.council_notice is not None

    # Path 2: council_review is None → both fields absent.
    state2 = _make_chat_state(blocked=False)
    assert state2.council_review is None
    resp2 = to_ask_response(state2, response_time_ms=10)
    assert resp2.council is None
    assert resp2.council_notice is None


def test_dto_round_trips_failed_judge():
    """Fix M3: a CouncilReview with a failed JudgeVote round-trips through the converter."""
    cr = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="m",
                provider="p",
                vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                reason="judge_failed",
                ok=False,
                error_category="RuntimeError",
            )
        ],
        council_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        agreement="degraded",
        diverges_from_auditor=False,
        reason="error",
    )
    dto = _council_review_to_dto(cr)
    j = dto.judges[0]
    assert j.ok is False
    assert j.error_category == "RuntimeError"
    assert j.vote == "requires_human_review"
    assert j.reason == "judge_failed"


# ---------------------------------------------------------------------------
# v0.1.19 — _council_notice branches on COUNCIL_BIND: reason prefix
# ---------------------------------------------------------------------------


def test_council_notice_indicates_binding_fired() -> None:
    """v0.1.19: when audited.reason starts with 'COUNCIL_BIND:', the notice
    text reflects the binding override (verdict promoted, not just advisory)."""
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        Citation,
        Finding,
    )

    # v0.1.21 (Capa B): Answer requires findings >=1. Inline a minimal
    # valid Finding so the test's intent (notice branching on COUNCIL_BIND
    # reason prefix) stays focused.
    _dummy_finding = Finding(
        text="dummy",
        citations=[Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")],
    )
    audited = AuditedAnswer(
        answer=Answer(query="q", language="es", text="resp", findings=[_dummy_finding]),
        verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        audit_results=[],
        reason=(
            "COUNCIL_BIND: 3/3 judges voted BLOCK; promoted pass -> "
            "requires_human_review. Original auditor reason: None."
        ),
    )
    notice = _council_notice(_cr(True), audited)
    assert notice is not None
    # The binding-fired notice should NOT contain the advisory message's
    # "no cambia" fragment; instead it should mention the promotion.
    assert "no cambia" not in notice
    assert "promov" in notice.lower() or "promot" in notice.lower() or "ascend" in notice.lower()


def test_council_notice_advisory_unchanged_when_no_binding() -> None:
    """v0.1.19 backward-compat: when audited.reason does NOT start with
    'COUNCIL_BIND:' (or audited is None), the advisory notice is unchanged."""
    # Case 1: audited has a non-binding reason → advisory notice.
    # v0.1.21 (Capa B): Answer requires findings >=1; reuse the dummy
    # from the prior test via inline construction.
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        Citation,
        Finding,
    )

    _dummy_finding = Finding(
        text="dummy",
        citations=[Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")],
    )
    audited = AuditedAnswer(
        answer=Answer(query="q", language="es", text="resp", findings=[_dummy_finding]),
        verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        audit_results=[],
        reason="REQUIRES_HUMAN_REVIEW: 1 of 1 citations invalid.",
    )
    notice = _council_notice(_cr(True), audited)
    assert notice is not None
    # Advisory notice path unchanged.
    assert "revisión colegiada" in notice or "Council" in notice

    # Case 2: audited=None (backward-compat with v0.1.18 callers).
    notice_no_audited = _council_notice(_cr(True), None)
    assert notice_no_audited is not None  # advisory divergence still emits notice
