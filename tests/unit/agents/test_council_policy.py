from __future__ import annotations

from regulaitor.agents.council import AdvisoryMajorityPolicy
from regulaitor.citation.schemas import AuditVerdict, JudgeVote

P, B, R = AuditVerdict.PASS, AuditVerdict.BLOCK, AuditVerdict.REQUIRES_HUMAN_REVIEW


def _v(vote, ok=True):
    return JudgeVote(model_id="m", provider="p", vote=vote, reason="r", ok=ok, error_category=None)


def test_unanimous_three_ok():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(P), _v(P), _v(P)])
    assert verdict == P and label == "unanimous"


def test_majority_two_of_three():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(B), _v(B), _v(P)])
    assert verdict == B and label == "majority"


def test_split_one_one_one_is_rhr():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(P), _v(B), _v(R)])
    assert verdict == R and label == "split"


def test_degraded_two_ok_agree():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(B), _v(B), _v(P, ok=False)])
    assert verdict == B and label == "degraded"


def test_degraded_two_ok_disagree_is_rhr():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(B), _v(P), _v(P, ok=False)])
    assert verdict == R and label == "degraded"


def test_zero_ok_is_rhr_degraded():
    verdict, label = AdvisoryMajorityPolicy().aggregate(
        [_v(P, ok=False), _v(B, ok=False), _v(R, ok=False)]
    )
    assert verdict == R and label == "degraded"


def test_monotonic_aggregate_matches_advisory():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    a = AdvisoryMajorityPolicy().aggregate([_v(B), _v(B), _v(P)])
    m = MonotonicEscalatePolicy().aggregate([_v(B), _v(B), _v(P)])
    assert a == m


def test_monotonic_would_escalate_pass_on_unanimous_block():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    out = pol.would_escalate(AuditVerdict.PASS, [_v(B), _v(B), _v(B)])
    assert out == AuditVerdict.REQUIRES_HUMAN_REVIEW


def test_monotonic_never_relaxes_block():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    # 3x PASS but audited was BLOCK -> never relax: stays BLOCK.
    out = pol.would_escalate(AuditVerdict.BLOCK, [_v(P), _v(P), _v(P)])
    assert out == AuditVerdict.BLOCK


def test_monotonic_never_relaxes_rhr():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    # 3x PASS but audited was RHR -> never relax: stays RHR.
    out = pol.would_escalate(AuditVerdict.REQUIRES_HUMAN_REVIEW, [_v(P), _v(P), _v(P)])
    assert out == AuditVerdict.REQUIRES_HUMAN_REVIEW


def test_monotonic_no_escalate_when_not_unanimous():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    out = pol.would_escalate(AuditVerdict.PASS, [_v(B), _v(B), _v(P)])
    assert out == AuditVerdict.PASS


# ---------------------------------------------------------------------------
# v0.1.19 — bind_verdict helper + flag pin (ADR-0025)
# ---------------------------------------------------------------------------
#
# Tests for the bind_verdict(audited, review, council) top-level helper that
# wires MonotonicEscalatePolicy.would_escalate() into the Council layer.
# Conservative-only direction: PASS -> RHR on unanimous (3/3 ok) BLOCK only;
# never relaxes BLOCK or RHR. See spec §D1-§D3 + ADR-0025.


# --- v0.1.19 test fixtures (Auditor + Council vote builders) ---


def _make_audited(verdict: AuditVerdict, reason: str | None = None):
    """Build a minimal AuditedAnswer for bind_verdict testing.

    Has one Finding with one valid citation; verdict + reason are caller-controlled.
    """
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        AuditResult,
        Citation,
        Finding,
    )

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


def _make_review(votes: list[AuditVerdict]):
    """Build a minimal CouncilReview with the given vote sequence (all ok=True)."""
    from regulaitor.citation.schemas import CouncilReview, JudgeVote

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
        agreement="majority",
        diverges_from_auditor=True,  # caller-irrelevant for bind_verdict
        reason="test",
    )


# --- v0.1.19 bind_verdict tests ---


def test_bind_verdict_returns_none_when_flag_off(monkeypatch) -> None:
    """When _COUNCIL_BINDING is False, bind_verdict returns None even on
    unanimous BLOCK. Pins the flag-gating logic."""
    from regulaitor.agents import council as council_mod
    from regulaitor.agents.council import (
        CouncilAgent,
        MonotonicEscalatePolicy,
        bind_verdict,
    )

    monkeypatch.setattr(council_mod, "_COUNCIL_BINDING", False)
    agent = CouncilAgent(policy=MonotonicEscalatePolicy())
    audited = _make_audited(AuditVerdict.PASS)
    review = _make_review([B, B, B])
    assert bind_verdict(audited, review, agent) is None


def test_bind_verdict_returns_none_with_advisory_only_policy() -> None:
    """When CouncilAgent uses AdvisoryMajorityPolicy (no would_escalate),
    bind_verdict returns None even with unanimous BLOCK."""
    from regulaitor.agents.council import (
        AdvisoryMajorityPolicy,
        CouncilAgent,
        bind_verdict,
    )

    agent = CouncilAgent(policy=AdvisoryMajorityPolicy())
    audited = _make_audited(AuditVerdict.PASS)
    review = _make_review([B, B, B])
    assert bind_verdict(audited, review, agent) is None


def test_bind_verdict_escalates_pass_to_rhr_on_unanimous_block() -> None:
    """The dramatic v0.1.19 case: Auditor=PASS + Council 3/3 BLOCK ->
    binding returns a new AuditedAnswer with verdict=RHR and a reason
    starting with COUNCIL_BIND: prefix."""
    from regulaitor.agents.council import (
        CouncilAgent,
        MonotonicEscalatePolicy,
        bind_verdict,
    )

    agent = CouncilAgent(policy=MonotonicEscalatePolicy())
    audited = _make_audited(AuditVerdict.PASS)
    review = _make_review([B, B, B])
    new_audited = bind_verdict(audited, review, agent)
    assert new_audited is not None
    assert new_audited.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert new_audited.reason is not None
    assert new_audited.reason.startswith("COUNCIL_BIND:")


def test_bind_verdict_returns_none_when_no_escalation_needed() -> None:
    """2/3 BLOCK + 1 valid is NOT unanimous; would_escalate keeps PASS."""
    from regulaitor.agents.council import (
        CouncilAgent,
        MonotonicEscalatePolicy,
        bind_verdict,
    )

    agent = CouncilAgent(policy=MonotonicEscalatePolicy())
    audited = _make_audited(AuditVerdict.PASS)
    review = _make_review([B, B, P])  # P = AuditVerdict.PASS vote
    assert bind_verdict(audited, review, agent) is None


def test_bind_verdict_returns_none_for_already_rhr() -> None:
    """When audited verdict is already RHR, MonotonicEscalatePolicy never
    relaxes/escalates -> bind_verdict returns None. Pins the H13 false-RHR
    pattern stays UNCHANGED in v0.1.19 (deferred to v0.1.20+ evidence)."""
    from regulaitor.agents.council import (
        CouncilAgent,
        MonotonicEscalatePolicy,
        bind_verdict,
    )

    agent = CouncilAgent(policy=MonotonicEscalatePolicy())
    audited = _make_audited(AuditVerdict.REQUIRES_HUMAN_REVIEW)
    review = _make_review([B, B, B])  # even unanimous BLOCK doesn't change RHR
    assert bind_verdict(audited, review, agent) is None
    # And the leniency direction (3x PASS) also doesn't change RHR:
    review_pass = _make_review([P, P, P])
    assert bind_verdict(audited, review_pass, agent) is None


def test_bind_verdict_preserves_original_reason_in_prefix() -> None:
    """When binding fires, the new reason preserves the original auditor
    reason in 'Original auditor reason: <reason>.' format."""
    from regulaitor.agents.council import (
        CouncilAgent,
        MonotonicEscalatePolicy,
        bind_verdict,
    )

    agent = CouncilAgent(policy=MonotonicEscalatePolicy())
    audited = _make_audited(AuditVerdict.PASS, reason="Original reason X")
    review = _make_review([B, B, B])
    new_audited = bind_verdict(audited, review, agent)
    assert new_audited is not None
    assert "Original auditor reason: Original reason X." in new_audited.reason


def test_bind_verdict_preserves_audit_results() -> None:
    """Binding is verdict-only: new AuditedAnswer.audit_results == original.
    Per-citation validation results don't change."""
    from regulaitor.agents.council import (
        CouncilAgent,
        MonotonicEscalatePolicy,
        bind_verdict,
    )

    agent = CouncilAgent(policy=MonotonicEscalatePolicy())
    audited = _make_audited(AuditVerdict.PASS)
    review = _make_review([B, B, B])
    new_audited = bind_verdict(audited, review, agent)
    assert new_audited is not None
    assert new_audited.audit_results == audited.audit_results
    assert new_audited.answer == audited.answer  # answer body unchanged


def test_council_binding_flag_is_true() -> None:
    """v0.1.19 flag-pin: _COUNCIL_BINDING is True in production.
    Regression anchor preventing accidental flip back to False without ADR."""
    from regulaitor.agents.council import _COUNCIL_BINDING

    assert _COUNCIL_BINDING is True
