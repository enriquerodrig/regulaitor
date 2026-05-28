"""Test build_verdict_transition_matrix correctness (spec D1)."""

from scripts.v0120_compare import CaseMetrics, build_verdict_transition_matrix


def test_transition_matrix_diagonal_and_off_diagonal_populated():
    """Synthetic checkpoint with known transitions → matrix counts all entries."""
    cases_a = [
        CaseMetrics(
            case_id="chat-001",
            expected_verdict="pass",
            actual_verdict="pass",
            verdict_match=True,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.8,
            answer_relevancy=0.9,
            context_precision=0.7,
            context_recall=0.6,
            citation_precision=0.5,
            citation_recall=0.6,
            latency_ms=1000,
            cost_eur=0.1,
        ),
        CaseMetrics(
            case_id="chat-002",
            expected_verdict="pass",
            actual_verdict="requires_human_review",
            verdict_match=False,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.5,
            answer_relevancy=0.4,
            context_precision=0.3,
            context_recall=0.2,
            citation_precision=0.1,
            citation_recall=0.2,
            latency_ms=1200,
            cost_eur=0.15,
        ),
        CaseMetrics(
            case_id="chat-003",
            expected_verdict="pass",
            actual_verdict="block",
            verdict_match=False,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.3,
            answer_relevancy=0.2,
            context_precision=0.1,
            context_recall=0.1,
            citation_precision=0.0,
            citation_recall=0.0,
            latency_ms=800,
            cost_eur=0.05,
        ),
    ]

    cases_b = [
        CaseMetrics(
            case_id="chat-001",
            expected_verdict="pass",
            actual_verdict="pass",
            verdict_match=True,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.85,
            answer_relevancy=0.92,
            context_precision=0.75,
            context_recall=0.65,
            citation_precision=0.55,
            citation_recall=0.65,
            latency_ms=1050,
            cost_eur=0.12,
        ),
        CaseMetrics(
            case_id="chat-002",
            expected_verdict="pass",
            actual_verdict="pass",
            verdict_match=True,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.6,
            answer_relevancy=0.5,
            context_precision=0.4,
            context_recall=0.3,
            citation_precision=0.2,
            citation_recall=0.3,
            latency_ms=1100,
            cost_eur=0.14,
        ),
        CaseMetrics(
            case_id="chat-003",
            expected_verdict="pass",
            actual_verdict="block",
            verdict_match=False,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.35,
            answer_relevancy=0.25,
            context_precision=0.15,
            context_recall=0.15,
            citation_precision=0.05,
            citation_recall=0.05,
            latency_ms=850,
            cost_eur=0.06,
        ),
    ]

    matrix = build_verdict_transition_matrix(cases_a, cases_b)

    # Diagonal: pass→pass=1, RHR→pass=1, block→block=1
    assert matrix["pass"]["pass"] == 1, f"pass→pass should be 1, got {matrix['pass']['pass']}"
    assert (
        matrix["requires_human_review"]["pass"] == 1
    ), f"RHR→pass should be 1, got {matrix['requires_human_review']['pass']}"
    assert matrix["block"]["block"] == 1, f"block→block should be 1, got {matrix['block']['block']}"

    # Off-diagonal transitions
    assert (
        matrix["pass"]["requires_human_review"] == 0
    ), f"pass→RHR should be 0, got {matrix['pass']['requires_human_review']}"
    assert matrix["pass"]["block"] == 0, f"pass→block should be 0, got {matrix['pass']['block']}"


def test_transition_matrix_missing_case_b_skipped():
    """If case_id exists in A but not B, skip (don't populate matrix entry)."""
    cases_a = [
        CaseMetrics(
            case_id="chat-999",
            expected_verdict="pass",
            actual_verdict="pass",
            verdict_match=True,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.8,
            answer_relevancy=0.9,
            context_precision=0.7,
            context_recall=0.6,
            citation_precision=0.5,
            citation_recall=0.6,
            latency_ms=1000,
            cost_eur=0.1,
        ),
    ]
    cases_b = []  # Empty — chat-999 not in B

    matrix = build_verdict_transition_matrix(cases_a, cases_b)

    # No transition recorded
    assert sum(sum(row.values()) for row in matrix.values()) == 0
