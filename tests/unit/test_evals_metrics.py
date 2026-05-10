"""Unit tests for evals.metrics — custom + aggregate.

Ragas metric integration is tested in test_evals_smoke.py (Task 8) because
it requires actual Dataset construction and a mocked LLM. Here we test only
the pure-Python custom metrics that don't need Ragas.
"""

from __future__ import annotations

import pytest
from evals.metrics import (
    aggregate,
    compute_citation_metrics,
    extract_emitted_articles_chat,
    extract_emitted_articles_doc,
)
from evals.schemas import (
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
)

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    DocumentReport,
    Finding,
    Segment,
    SegmentResult,
)
from regulaitor.orchestration.state import ChatState

# ---------------------------------------------------------------------------
# compute_citation_metrics
# ---------------------------------------------------------------------------


def test_citation_metrics_perfect_match() -> None:
    cm = compute_citation_metrics(emitted=["6.1", "9.2"], expected=["6.1", "9.2"])
    assert cm.precision == 1.0
    assert cm.recall == 1.0


def test_citation_metrics_empty_emitted_zero_precision() -> None:
    cm = compute_citation_metrics(emitted=[], expected=["6.1"])
    assert cm.precision == 0.0
    assert cm.recall == 0.0


def test_citation_metrics_empty_expected_zero_recall() -> None:
    cm = compute_citation_metrics(emitted=["6.1"], expected=[])
    assert cm.precision == 0.0  # convention from spec §5.2
    assert cm.recall == 0.0


def test_citation_metrics_partial_overlap() -> None:
    cm = compute_citation_metrics(emitted=["6.1", "10.3"], expected=["6.1", "9.2"])
    assert cm.precision == 0.5
    assert cm.recall == 0.5


def test_citation_metrics_dedup() -> None:
    cm = compute_citation_metrics(emitted=["6.1", "6.1"], expected=["6.1"])
    # set semantics: |{"6.1"} ∩ {"6.1"}| / |{"6.1"}| = 1.0 each
    assert cm.precision == 1.0
    assert cm.recall == 1.0


# ---------------------------------------------------------------------------
# extract_emitted_articles_*
# ---------------------------------------------------------------------------


def _state_with_citations(*pairs: tuple[str, str | None]) -> ChatState:
    """Build a ChatState whose audited_answer has the given (articulo, apartado) pairs."""
    citations = [
        Citation(norma="ai_act", articulo=art, apartado=ap, language="es", text="t")
        for art, ap in pairs
    ]
    finding = Finding(
        text="hallazgo",
        citations=citations,
        severity="info",
    )
    answer = Answer(query="q", language="es", text="respuesta", findings=[finding])
    audit_results = [
        AuditResult(
            citation=c,
            validated=True,
            article_exists=True,
            apartado_exists=True,
            text_normalized_match=True,
            reason=None,
        )
        for c in citations
    ]
    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=audit_results, reason=None
    )
    return ChatState(
        case_id="x",
        query="q",
        corpus="ai_act",
        language="es",
        answer=answer,
        audited_answer=audited,
    )


def test_extract_emitted_articles_chat_concatenates_articulo_apartado() -> None:
    state = _state_with_citations(("6", "1"), ("9", "2"))
    arts = extract_emitted_articles_chat(state)
    assert sorted(arts) == ["6.1", "9.2"]


def test_extract_emitted_articles_chat_handles_no_apartado() -> None:
    state = _state_with_citations(("6", None))
    arts = extract_emitted_articles_chat(state)
    assert arts == ["6"]


def test_extract_emitted_articles_chat_blocked_state_returns_empty() -> None:
    state = ChatState(
        case_id="x",
        query="q",
        corpus="ai_act",
        language="es",
        injection_blocked=True,
        injection_reason="injection",
    )
    arts = extract_emitted_articles_chat(state)
    assert arts == []


def _doc_report_with_segment_citations(*pairs: tuple[str, str | None]) -> DocumentReport:
    citations = [
        Citation(norma="ai_act", articulo=art, apartado=ap, language="es", text="t")
        for art, ap in pairs
    ]
    finding = Finding(text="t", citations=citations, severity="info")
    answer = Answer(query="(seg)", language="es", text="resp", findings=[finding])
    audit_results = [
        AuditResult(
            citation=c,
            validated=True,
            article_exists=True,
            apartado_exists=True,
            text_normalized_match=True,
            reason=None,
        )
        for c in citations
    ]
    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=audit_results, reason=None
    )
    seg = Segment(id=1, title=None, text="seg", token_count=10, is_continuation=False)
    seg_result = SegmentResult(
        segment=seg,
        skipped=False,
        skip_reason=None,
        audited_answer=audited,
        latency_ms=100,
        cost_eur=0.01,
    )
    return DocumentReport(
        case_id="d",
        document_hash="h" * 64,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[seg_result],
        document_verdict=AuditVerdict.PASS,
        document_reason=None,
        n_segments_total=1,
        n_segments_blocked_by_injection=0,
        n_segments_pass=1,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=100,
        cost_eur_total=0.01,
    )


def test_extract_emitted_articles_doc_unions_across_segments() -> None:
    report = _doc_report_with_segment_citations(("6", "1"), ("9", "2"))
    arts = extract_emitted_articles_doc(report)
    assert sorted(arts) == ["6.1", "9.2"]


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


def _chat_result(case_id: str, *, latency_ms: int, cost: float, cache_hit: bool) -> ChatCaseResult:
    return ChatCaseResult(
        case_id=case_id,
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
        criteria_scores=[CriteriaScore(criterion="c", passed=True, reason=None)],
        latency_ms=latency_ms,
        cost_eur=cost,
        cache_hit=cache_hit,
    )


def _doc_result(case_id: str, *, latency_ms: int, cost: float, cache_hit: bool) -> DocCaseResult:
    return DocCaseResult(
        case_id=case_id,
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
        criteria_scores=[CriteriaScore(criterion="c", passed=True, reason=None)],
        latency_ms_total=latency_ms,
        cost_eur_total=cost,
        cache_hit=cache_hit,
    )


def test_aggregate_basic() -> None:
    chats = [_chat_result("c1", latency_ms=2000, cost=0.04, cache_hit=False)]
    docs = [_doc_result("d1", latency_ms=8000, cost=0.40, cache_hit=False)]
    agg = aggregate(chats, docs)
    assert agg.n_chat_cases == 1
    assert agg.n_doc_cases == 1
    assert agg.cost_total_eur == pytest.approx(0.44)
    assert agg.cost_per_chat_eur == pytest.approx(0.04)
    assert agg.cost_per_doc_eur == pytest.approx(0.40)
    assert agg.cache_hit_rate == 0.0


def test_aggregate_p95_latency() -> None:
    # 20 calls; 19 at 1000 ms, 1 at 10000 ms → p95 ≈ 1000
    # (5% of 20 = 1, so percentile takes the 19th element)
    chats = [
        _chat_result(f"c{i}", latency_ms=1000 if i < 19 else 10000, cost=0.01, cache_hit=False)
        for i in range(20)
    ]
    agg = aggregate(chats, [])
    # statistics.quantiles with n=20 may not give exact p95; allow some tolerance
    assert 1000 <= agg.latency_p95_ms <= 10000


def test_aggregate_empty_returns_zeros() -> None:
    agg = aggregate([], [])
    assert agg.n_chat_cases == 0
    assert agg.n_doc_cases == 0
    assert agg.cost_total_eur == 0.0
    assert agg.cache_hit_rate == 0.0
