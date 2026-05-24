"""
Unit tests for scripts/v0120_compare.py comparison report generator.

Tests validate:
- Checkpoint loading
- Metric aggregation
- Cohort classification
- Bar evaluation
- Report structure
"""

import json

from scripts.v0120_compare import (
    V0120_BAR,
    CaseMetrics,
    aggregate_metrics,
    build_verdict_transition_matrix,
    classify_cohort,
    load_checkpoint,
)


def test_v0120_bar_pinned():
    """Verify ADR-0021 bar values are exact."""
    assert V0120_BAR["faithfulness"] == 0.65
    assert V0120_BAR["citation_recall"] == 0.60
    assert V0120_BAR["verdict_match"] == 0.35
    assert len(V0120_BAR) == 7  # 7 gated metrics


def test_classify_cohort_h10():
    """H10 chat cases classified correctly."""
    assert classify_cohort("chat-001") == "H10 chat"
    assert classify_cohort("chat-030") == "H10 chat"


def test_classify_cohort_h14():
    """H14 cross-corpus cases classified correctly."""
    assert classify_cohort("nis2-001") == "H14 cross-corpus"
    assert classify_cohort("dora-006") == "H14 cross-corpus"
    assert classify_cohort("xcorpus-001") == "H14 cross-corpus"


def test_classify_cohort_v0113():
    """v0.1.13 industry cases classified correctly."""
    assert classify_cohort("industry-c1") == "v0.1.13 industry"
    assert classify_cohort("industry-v5") == "v0.1.13 industry"


def test_classify_cohort_v0115():
    """v0.1.15 gap-analysis cases classified correctly."""
    assert classify_cohort("industry-g1") == "v0.1.15 gap-analysis"
    assert classify_cohort("industry-gv5") == "v0.1.15 gap-analysis"


def test_aggregate_metrics_empty():
    """Empty case list returns empty dict."""
    result = aggregate_metrics([])
    assert result == {}


def test_aggregate_metrics_single_case():
    """Single case aggregates correctly."""
    case = CaseMetrics(
        case_id="test-001",
        expected_verdict="pass",
        actual_verdict="pass",
        verdict_match=True,
        expected_severity="low",
        actual_severity="low",
        severity_match=True,
        faithfulness=0.8,
        answer_relevancy=0.7,
        context_precision=0.6,
        context_recall=0.5,
        citation_precision=0.4,
        citation_recall=0.9,
        latency_ms=100.0,
        cost_eur=0.01,
    )
    result = aggregate_metrics([case])
    assert result["faithfulness"] == 0.8
    assert result["verdict_match"] == 1.0
    assert result["severity_match"] == 1.0
    assert result["cost_eur_total"] == 0.01


def test_build_verdict_transition_matrix():
    """Verdict transition matrix counts correctly."""
    cases_a = [
        CaseMetrics(
            case_id="test-001",
            expected_verdict="pass",
            actual_verdict="pass",
            verdict_match=True,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.5,
            answer_relevancy=0.5,
            context_precision=0.5,
            context_recall=0.5,
            citation_precision=0.5,
            citation_recall=0.5,
            latency_ms=100.0,
            cost_eur=0.01,
        ),
    ]
    cases_b = [
        CaseMetrics(
            case_id="test-001",
            expected_verdict="pass",
            actual_verdict="requires_human_review",
            verdict_match=False,
            expected_severity=None,
            actual_severity=None,
            severity_match=None,
            faithfulness=0.5,
            answer_relevancy=0.5,
            context_precision=0.5,
            context_recall=0.5,
            citation_precision=0.5,
            citation_recall=0.5,
            latency_ms=100.0,
            cost_eur=0.01,
        ),
    ]

    matrix = build_verdict_transition_matrix(cases_a, cases_b)
    # A had "pass", B has "requires_human_review"
    assert matrix["pass"]["requires_human_review"] == 1


def test_load_checkpoint_minimal_jsonl(tmp_path):
    """Checkpoint loading parses JSONL correctly."""
    checkpoint_file = tmp_path / "test.jsonl"
    checkpoint_file.write_text(
        json.dumps(
            {
                "kind": "chat",
                "data": {
                    "case_id": "test-001",
                    "expected_verdict": "pass",
                    "actual_verdict": "pass",
                    "verdict_match": True,
                    "faithfulness": 0.5,
                    "answer_relevancy": 0.5,
                    "context_precision": 0.5,
                    "context_recall": 0.5,
                    "citations": {"precision": 0.5, "recall": 0.5},
                    "latency_ms": 100.0,
                    "cost_eur": 0.01,
                },
            }
        )
    )

    cases = load_checkpoint(checkpoint_file)
    assert len(cases) == 1
    assert cases[0].case_id == "test-001"
    assert cases[0].verdict_match is True
    assert cases[0].faithfulness == 0.5
