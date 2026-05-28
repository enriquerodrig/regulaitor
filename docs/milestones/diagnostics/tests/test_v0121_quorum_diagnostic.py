"""v0.1.21 — Tests for the quorum diagnostic script (loader + classifier + threshold)."""

from __future__ import annotations

from evals.schemas import (
    ChatCaseResult,
    CitationMetrics,
)
from scripts.v0121_quorum_diagnostic import (
    classify_case,
    classify_recommendation,
)


def _chat_case(case_id: str, verdict: str, emitted: list[str]) -> ChatCaseResult:
    return ChatCaseResult(
        case_id=case_id,
        expected_verdict="pass",
        actual_verdict=verdict,  # type: ignore[arg-type]
        verdict_match=False,
        expected_severity=None,
        actual_severity=None,
        severity_match=None,
        citations=CitationMetrics(expected=[], emitted=emitted, precision=0.0, recall=0.0),
        faithfulness=0.5,
        answer_relevancy=0.5,
        context_precision=0.5,
        context_recall=0.5,
        criteria_scores=[],
        latency_ms=1000,
        cost_eur=0.01,
        cache_hit=False,
    )


def test_classify_single_citation_rhr_is_unambiguous_flip() -> None:
    """Pins the classifier behavior on a SYNTHETIC K=1 RHR input.

    **Honest caveat (final whole-branch review C3)**: this input cannot
    exist in real audit data — pre-v0.1.21 code never produced K=1 RHR
    (a single-Finding answer with its only citation invalid → BLOCK, not
    RHR). This test pins the classifier's branch behavior on the synthetic
    input only (so the classifier code path stays callable + the bucket
    label is stable), NOT a real-data scenario. The empirical 0
    "would_pass_unambiguous" count over v0.1.20 ARM A cache reflects this
    structural absence, not v0.1.21's actual impact. See
    `scripts/v0121_quorum_diagnostic.py` module docstring §22.22 caveat.
    """
    case = _chat_case("chat-001", "requires_human_review", ["6.1"])
    c = classify_case(case)
    assert c.bucket == "would_pass_unambiguous"
    assert c.emitted_count == 1


def test_classify_multi_citation_rhr_is_ambiguous_flip() -> None:
    case = _chat_case("chat-002", "requires_human_review", ["6.1", "7.2", "8.3"])
    c = classify_case(case)
    assert c.bucket == "would_pass_ambiguous"
    assert c.emitted_count == 3


def test_classify_recommendation_threshold_classifier() -> None:
    # Spec D5 thresholds: >10 strong, 5-10 moderate, <=5 marginal.
    assert "MARGINAL" in classify_recommendation(0)
    assert "MARGINAL" in classify_recommendation(4)
    assert "MARGINAL" in classify_recommendation(5) or "MODERATE" in classify_recommendation(5)
    assert "MODERATE" in classify_recommendation(7)
    assert "MODERATE" in classify_recommendation(10)
    assert "STRONG" in classify_recommendation(11)
    assert "STRONG" in classify_recommendation(18)
