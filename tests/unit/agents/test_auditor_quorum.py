"""v0.1.21 — Tier 1 Auditor RHR aggregation quorum tests (>=2 invalid -> turn RHR).

These tests pin the new escalation path added in v0.1.21. Pre-existing tests
in `test_auditor.py` (Lenient-Finding + Strict-Answer aggregation, the 3
fundamental PASS/BLOCK/RHR paths) stay GREEN unchanged under the new logic;
those tests use single-citation Findings, so Lenient swallows at most 1
invalid citation per all-pass branch — below the new escalation threshold.

**§22.22 honest framing (final whole-branch review C1+C2)**: the NEW v0.1.21
escalation path is "all Findings pass at Lenient-Finding level BUT total
invalid-citation count across the answer reaches ≥2". The canonical test
exercising this NEW path is
`test_aggregation_lenient_finding_passes_but_quorum_escalates` (added
post-final-review): 1 Finding with K=3 (1 valid + 2 invalid). Lenient saves
the Finding; pre-v0.1.21 the answer would have been PASS; v0.1.21
escalates to RHR via the new quorum branch.

The other tests in this file pin behaviors that the pre-v0.1.21 aggregator
ALREADY produced (partial-Findings RHR, single-Finding BLOCK, all-blocked
BLOCK). They are kept as regression anchors confirming v0.1.21 does NOT
disturb those pre-existing branches.

ADR-0027 / spec D1.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.agents.auditor import AuditorAgent
from regulaitor.citation.schemas import (
    Answer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)


def _citation(articulo: str = "6", apartado: str | None = "1", text: str = "t") -> Citation:
    return Citation(norma="ai_act", articulo=articulo, apartado=apartado, language="es", text=text)


def _audit_result(citation: Citation, *, validated: bool, reason: str | None) -> AuditResult:
    return AuditResult(
        citation=citation,
        validated=validated,
        article_exists=validated,
        apartado_exists=validated if citation.apartado else None,
        text_normalized_match=validated,
        reason=reason,
    )


def _answer(findings: list[Finding]) -> Answer:
    return Answer(query="q", language="es", text="response", findings=findings)


def test_aggregation_single_rhr_does_not_trigger_turn_rhr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """K=3 citations across 3 single-citation Findings, 1 invalid -> turn=RHR via PARTIAL branch.

    **Honest naming caveat (final whole-branch review C2)**: the test name
    historically said "single_rhr_does_not_trigger_turn_rhr" but the assertion
    expects RHR. The behavior pinned here is the pre-existing PARTIAL branch
    (some Findings pass, some blocked) which produces RHR — this is UNCHANGED
    behavior from before v0.1.21. The NEW v0.1.21 escalation path (all-pass-
    Findings + ≥2 invalid → RHR) is pinned by
    `test_aggregation_lenient_finding_passes_but_quorum_escalates` below.

    Here: 3 Findings each with K=1. Finding f3's only citation invalid → f3
    blocked → 2 pass + 1 blocked → partial → RHR (the pre-existing
    Strict-Answer partial branch, NOT the new quorum escalation).
    """
    from regulaitor.agents import auditor

    c1, c2, c3 = _citation("6", "1", "t1"), _citation("7", "1", "t2"), _citation("8", "1", "t3")
    f1 = Finding(text="f1", citations=[c1])
    f2 = Finding(text="f2", citations=[c2])
    f3 = Finding(text="f3", citations=[c3])
    answer = _answer([f1, f2, f3])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            side_effect=[
                _audit_result(c1, validated=True, reason=None),
                _audit_result(c2, validated=True, reason=None),
                _audit_result(c3, validated=False, reason="article_not_found"),
            ]
        ),
    )

    result = AuditorAgent().audit(answer)
    # PARTIAL branch (pre-existing pre-v0.1.21 behavior, UNCHANGED): 2/3
    # Findings pass + 1/3 blocked → RHR. The new v0.1.21 quorum escalation
    # path is NOT exercised here because not-all-Findings-pass; that path is
    # pinned by test_aggregation_lenient_finding_passes_but_quorum_escalates.
    assert result.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW


def test_aggregation_lenient_finding_passes_but_quorum_escalates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.21 NEW path: 1 Finding with K=3 (1 valid + 2 invalid). Under
    Lenient-Finding the Finding PASSES (>=1 valid citation). Under the
    pre-v0.1.21 Strict-Answer aggregator: all Findings pass -> turn=PASS.
    Under v0.1.21 quorum aggregator: all Findings pass BUT n_invalid=2 ->
    turn=RHR (NEW escalation).

    This is THE canonical test for the v0.1.21 D1 semantic change. Added
    post-final-review (C2) — the pre-existing 5 tests pinned behaviors that
    the old aggregator already produced; this test pins the actual new
    escalation path that v0.1.21 ships.
    """
    from regulaitor.agents import auditor

    c_good = _citation("6", "1", "good")
    c_bad1 = _citation("999", None, "bad1")
    c_bad2 = _citation("998", None, "bad2")
    finding = Finding(text="mixed evidence", citations=[c_good, c_bad1, c_bad2])
    answer = _answer([finding])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            side_effect=[
                _audit_result(c_good, validated=True, reason=None),
                _audit_result(c_bad1, validated=False, reason="article_not_found: 999"),
                _audit_result(c_bad2, validated=False, reason="article_not_found: 998"),
            ]
        ),
    )

    result = AuditorAgent().audit(answer)
    assert result.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW


def test_aggregation_two_rhrs_in_one_finding_block_that_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quorum>=2 within a single Finding -> that Finding is blocked (Lenient lets
    one citation save the Finding; 2 invalid in K=2 means 0 valid -> blocked).

    Pinning the boundary: K=2 with BOTH invalid -> Finding blocked -> turn BLOCK
    (since only 1 Finding total).
    """
    from regulaitor.agents import auditor

    c1, c2 = _citation("999", None, "t1"), _citation("998", None, "t2")
    finding = Finding(text="f1", citations=[c1, c2])
    answer = _answer([finding])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            side_effect=[
                _audit_result(c1, validated=False, reason="article_not_found: 999"),
                _audit_result(c2, validated=False, reason="article_not_found: 998"),
            ]
        ),
    )

    result = AuditorAgent().audit(answer)
    assert result.verdict == AuditVerdict.BLOCK


def test_aggregation_three_rhrs_across_findings_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 3 citations invalid (across 3 separate Findings) -> turn=BLOCK.

    Each Finding has K=1 and that 1 invalid, so each Finding is blocked.
    Strict-Answer aggregates all-blocked -> BLOCK.
    """
    from regulaitor.agents import auditor

    c1, c2, c3 = (
        _citation("999", None, "t1"),
        _citation("998", None, "t2"),
        _citation("997", None, "t3"),
    )
    f1 = Finding(text="f1", citations=[c1])
    f2 = Finding(text="f2", citations=[c2])
    f3 = Finding(text="f3", citations=[c3])
    answer = _answer([f1, f2, f3])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            side_effect=[
                _audit_result(c1, validated=False, reason="article_not_found: 999"),
                _audit_result(c2, validated=False, reason="article_not_found: 998"),
                _audit_result(c3, validated=False, reason="article_not_found: 997"),
            ]
        ),
    )

    result = AuditorAgent().audit(answer)
    assert result.verdict == AuditVerdict.BLOCK


def test_aggregation_single_citation_invalid_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """K=1 total with the citation invalid -> turn=BLOCK (not RHR).

    Spec D1 edge case: K=1 can never reach >=2, so per-citation RHR
    aggregation can NEVER trigger turn-RHR from a single-citation answer.
    The single invalid citation makes its Finding blocked; with only 1
    Finding total -> BLOCK.
    """
    from regulaitor.agents import auditor

    c1 = _citation("999", None, "t1")
    finding = Finding(text="f1", citations=[c1])
    answer = _answer([finding])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            return_value=_audit_result(c1, validated=False, reason="article_not_found: 999"),
        ),
    )

    result = AuditorAgent().audit(answer)
    assert result.verdict == AuditVerdict.BLOCK


def test_aggregation_two_findings_one_invalid_one_valid_still_rhr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """K=2 across 2 Findings, 1 invalid + 1 valid -> turn=RHR (the partial branch).

    Pre-existing Strict-Answer logic: not-all-pass + not-all-blocked = RHR.
    This pins that v0.1.21's per-citation quorum change does NOT regress the
    standard partial-success path.
    """
    from regulaitor.agents import auditor

    c_good = _citation("6", "1", "good")
    c_bad = _citation("999", None, "bad")
    f_good = Finding(text="good finding", citations=[c_good])
    f_bad = Finding(text="bad finding", citations=[c_bad])
    answer = _answer([f_good, f_bad])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            side_effect=[
                _audit_result(c_good, validated=True, reason=None),
                _audit_result(c_bad, validated=False, reason="article_not_found"),
            ]
        ),
    )

    result = AuditorAgent().audit(answer)
    assert result.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
