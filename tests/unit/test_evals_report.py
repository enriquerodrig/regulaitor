"""Unit tests for evals.report — markdown rendering."""

from __future__ import annotations

from evals.report import (
    _render_aggregate_table,
    _render_per_case_chat,
    _render_per_case_doc,
    render_report,
)
from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
    EvalRunMeta,
)


def _meta() -> EvalRunMeta:
    return EvalRunMeta(
        run_date="2026-05-10T18:00:00+00:00",
        commit_sha="abcd123",
        production_model="claude-sonnet-4-6",
        judge_model="claude-haiku-4-5-20251001",
        temperature=0.0,
        subset=None,
        cache_only=False,
    )


def _agg() -> AggregateMetrics:
    return AggregateMetrics(
        n_chat_cases=30,
        n_doc_cases=10,
        faithfulness_mean=0.87,
        answer_relevancy_mean=0.91,
        context_precision_mean=0.78,
        context_recall_mean=0.82,
        citation_precision_mean=0.93,
        citation_recall_mean=0.79,
        verdict_match_rate=0.90,
        severity_match_rate=0.83,
        chat_latency_p95_ms=4500,
        doc_latency_p95_ms=28000,
        latency_p95_ms=24000,
        cost_per_chat_eur=0.041,
        cost_per_doc_eur=0.487,
        cost_total_eur=6.83,
        cache_hit_rate=0.05,
    )


def _chat_result() -> ChatCaseResult:
    return ChatCaseResult(
        case_id="chat-001",
        expected_verdict="pass",
        actual_verdict="pass",
        verdict_match=True,
        expected_severity="medium",
        actual_severity="medium",
        severity_match=True,
        citations=CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0),
        faithfulness=0.9,
        answer_relevancy=0.9,
        context_precision=0.8,
        context_recall=0.8,
        criteria_scores=[CriteriaScore(criterion="Cita art. 6.1", passed=True, reason="ok")],
        latency_ms=2100,
        cost_eur=0.04,
        cache_hit=False,
    )


def _doc_result() -> DocCaseResult:
    return DocCaseResult(
        case_id="doc-001",
        expected_document_verdict="pass",
        actual_document_verdict="pass",
        verdict_match=True,
        expected_n_segments=5,
        actual_n_segments=5,
        n_segments_within_tolerance=True,
        findings_citations=CitationMetrics(
            emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0
        ),
        faithfulness=0.85,
        criteria_scores=[
            CriteriaScore(criterion="Detecta sistema alto riesgo", passed=True, reason=None)
        ],
        latency_ms_total=8000,
        cost_eur_total=0.40,
        cache_hit=False,
    )


def test_render_aggregate_table_includes_all_metrics() -> None:
    md = _render_aggregate_table(_agg())
    assert "faithfulness" in md
    assert "0.87" in md
    assert "≥0.85" in md
    assert "✅" in md  # at least one passing metric


def test_render_aggregate_table_marks_failures() -> None:
    agg = _agg().model_copy(update={"faithfulness_mean": 0.50})
    md = _render_aggregate_table(agg)
    assert "❌" in md
    assert "0.50" in md or "0.5" in md


def test_render_per_case_chat_includes_id_and_verdict() -> None:
    md = _render_per_case_chat(_chat_result())
    assert "chat-001" in md
    assert "pass" in md
    assert "Cita art. 6.1" in md


def test_render_per_case_doc_includes_id_and_segments() -> None:
    md = _render_per_case_doc(_doc_result())
    assert "doc-001" in md
    assert "5" in md  # n_segments


def test_render_report_full_document() -> None:
    md = render_report(_meta(), _agg(), [_chat_result()], [_doc_result()])
    # Header
    assert "RegulAItor — Evaluation Report" in md
    assert "abcd123" in md
    assert "claude-sonnet-4-6" in md
    assert "claude-haiku-4-5-20251001" in md
    # Aggregate
    assert "faithfulness" in md
    # Per-case
    assert "chat-001" in md
    assert "doc-001" in md
    # Reproducibility + caveats
    assert "make eval-from-cache" in md
    assert "Caveats" in md or "caveats" in md.lower()
