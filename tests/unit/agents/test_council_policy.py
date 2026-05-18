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


def test_council_binding_seam_is_off():
    from regulaitor.agents import council

    assert council._COUNCIL_BINDING is False
