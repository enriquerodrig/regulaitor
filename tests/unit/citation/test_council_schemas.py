from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote


def _vote(vote=AuditVerdict.PASS, ok=True):
    return JudgeVote(
        model_id="claude-haiku-4-5-20251001",
        provider="anthropic",
        vote=vote,
        reason="cita soporta la afirmación",
        ok=ok,
        error_category=None,
    )


def test_judgevote_is_frozen():
    v = _vote()
    with pytest.raises(ValidationError):
        v.vote = AuditVerdict.BLOCK


def test_councilreview_roundtrip():
    cr = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[_vote(), _vote(AuditVerdict.BLOCK)],
        council_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        agreement="split",
        diverges_from_auditor=True,
        reason="2 judges split",
    )
    assert cr.judges[0].provider == "anthropic"
    assert cr.trigger_reason == "auditor_rhr"
    assert cr.council_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert cr.agreement == "split"
    assert cr.diverges_from_auditor is True
    assert len(cr.judges) == 2


def test_councilreview_rejects_bad_trigger_reason():
    with pytest.raises(ValidationError):
        CouncilReview(
            triggered=False,
            trigger_reason="bogus",
            judges=[],
            council_verdict=AuditVerdict.PASS,
            agreement="degraded",
            diverges_from_auditor=False,
            reason="x",
        )


def test_judgevote_error_path():
    v = JudgeVote(
        model_id="llama-70b",
        provider="groq",
        vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        reason="judge_failed",
        ok=False,
        error_category="RuntimeError",
    )
    assert v.ok is False
    assert v.error_category == "RuntimeError"


def test_councilreview_rejects_bad_agreement():
    with pytest.raises(ValidationError):
        CouncilReview(
            triggered=True,
            trigger_reason="auditor_rhr",
            judges=[_vote()],
            council_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
            agreement="bogus",
            diverges_from_auditor=False,
            reason="invalid agreement",
        )


def test_councilreview_rejects_inconsistent_triggered():
    with pytest.raises(ValidationError):
        CouncilReview(
            triggered=False,
            trigger_reason="auditor_rhr",
            judges=[],
            council_verdict=AuditVerdict.PASS,
            agreement="degraded",
            diverges_from_auditor=False,
            reason="x",
        )
