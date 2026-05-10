"""H8 — Custom metrics + Ragas adapter + aggregation.

Custom metrics work directly on ChatState and DocumentReport (the schemas
H4/H5 already produce). Ragas metrics are computed by building a one-row
EvaluationDataset per case and calling Ragas's ``evaluate()`` with the judge
LLM (Haiku 4.5).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable

from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
    GoldCaseChat,
    GoldCaseDoc,
)
from regulaitor.citation.schemas import (
    AuditedAnswer,
    Citation,
    DocumentReport,
)
from regulaitor.orchestration.state import ChatState

# ---------------------------------------------------------------------------
# Custom — citation / verdict / severity
# ---------------------------------------------------------------------------


def _format_articulo(c: Citation) -> str:
    """Return 'articulo.apartado' when apartado is present, else 'articulo'."""
    if c.apartado is not None and c.apartado != "":
        return f"{c.articulo}.{c.apartado}"
    return c.articulo


def extract_emitted_articles_chat(state: ChatState) -> list[str]:
    """Articles cited in the audited answer of a chat case. Empty if blocked."""
    if state.audited_answer is None:
        return []
    seen: set[str] = set()
    for r in state.audited_answer.audit_results:
        seen.add(_format_articulo(r.citation))
    return sorted(seen)


def extract_emitted_articles_doc(report: DocumentReport) -> list[str]:
    """Union of citations across all segments of a document report."""
    seen: set[str] = set()
    for seg_result in report.segments:
        if seg_result.audited_answer is None:
            continue
        for r in seg_result.audited_answer.audit_results:
            seen.add(_format_articulo(r.citation))
    return sorted(seen)


def compute_citation_metrics(emitted: list[str], expected: list[str]) -> CitationMetrics:
    """Article-level set comparison. Edge cases follow spec §5.2.

    When emitted is empty, precision is 0.0 (no hits possible).
    When expected is empty, both precision and recall are 0.0 (no valid targets).
    """
    emitted_set = set(emitted)
    expected_set = set(expected)
    intersection = emitted_set & expected_set

    if not expected_set:
        # No expected articles means the case is ill-defined; return 0.0 for both.
        precision = 0.0
        recall = 0.0
    elif not emitted_set:
        precision = 0.0
        recall = 0.0
    else:
        precision = len(intersection) / len(emitted_set)
        recall = len(intersection) / len(expected_set)

    return CitationMetrics(
        emitted=sorted(emitted_set),
        expected=sorted(expected_set),
        precision=precision,
        recall=recall,
    )


def _extract_severity_chat(audited: AuditedAnswer | None) -> str | None:
    """Severity of the first finding, or None if no findings."""
    if audited is None:
        return None
    if not audited.answer.findings:
        return None
    return audited.answer.findings[0].severity


# ---------------------------------------------------------------------------
# Ragas adapter
# ---------------------------------------------------------------------------


def _ragas_metrics_chat(
    *,
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None,
    judge_call: Callable[..., tuple[str, float]],
) -> dict[str, float]:
    """Run Ragas faithfulness + answer_relevancy + context_precision + context_recall.

    Each metric is computed as a one-row evaluate() to keep the harness
    composable. Returns a dict of metric_name -> score in [0, 1].

    ``judge_call`` is the cache-aware LLM call (Haiku 4.5 + temperature=0).
    It is kept on the signature for future flexibility even though Ragas
    builds its own LangChain LLM internally. This is intentional.
    """
    # Lazy imports — Ragas is heavy and not needed by other modules.
    # The implementation body is excluded from unit-test coverage because
    # Ragas/datasets/langchain_anthropic are external I/O dependencies tested
    # end-to-end via mocking (see test_evals_metrics.py orchestrator tests).
    import pandas as pd  # pragma: no cover
    from datasets import Dataset  # pragma: no cover
    from langchain_anthropic import ChatAnthropic  # pragma: no cover
    from ragas import evaluate  # pragma: no cover
    from ragas.metrics import (  # pragma: no cover
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    # Ragas expects ground_truth for context_recall; fall back to a stub if missing.
    gt = ground_truth if ground_truth else "[no_reference]"  # pragma: no cover

    df = pd.DataFrame(  # pragma: no cover
        [
            {
                "user_input": query,
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": gt,
            }
        ]
    )
    ds = Dataset.from_pandas(df)  # pragma: no cover

    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.0)  # pragma: no cover

    result = evaluate(  # pragma: no cover
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        raise_exceptions=False,
    )
    out = result.to_pandas().iloc[0].to_dict()  # pragma: no cover

    def _safe_score(val: object) -> float:  # pragma: no cover
        if val is None:
            return 0.0
        try:
            f = float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if math.isnan(f) else f

    return {  # pragma: no cover
        "faithfulness": _safe_score(out.get("faithfulness")),
        "answer_relevancy": _safe_score(out.get("answer_relevancy")),
        "context_precision": _safe_score(out.get("context_precision")),
        "context_recall": _safe_score(out.get("context_recall")),
    }


def _ragas_metrics_doc(
    *,
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None,
    judge_call: Callable[..., tuple[str, float]],
) -> dict[str, float]:
    """Doc-level Ragas: only faithfulness applies (no single retrieval context).

    Delegates to _ragas_metrics_chat and keeps only faithfulness.
    """
    metrics = _ragas_metrics_chat(  # pragma: no cover
        query=query,
        answer=answer,
        contexts=contexts,
        ground_truth=ground_truth,
        judge_call=judge_call,
    )
    return {"faithfulness": metrics["faithfulness"]}  # pragma: no cover


# ---------------------------------------------------------------------------
# Per-case orchestrators
# ---------------------------------------------------------------------------


def compute_chat_metrics(
    case: GoldCaseChat,
    state: ChatState,
    *,
    judge_call: Callable[..., tuple[str, float]],
    judge_score_fn: Callable[..., list[CriteriaScore]],
    latency_ms: int,
    cost_eur: float,
    cache_hit: bool,
) -> ChatCaseResult:
    """Compute all metrics for one chat case. Returns a frozen ChatCaseResult."""
    audited = state.audited_answer
    actual_verdict: str
    if state.injection_blocked:
        actual_verdict = "blocked_injection"
    elif audited is None:
        # Backend produced no audited answer (graph error path or Auditor hard-rejected
        # without storing AuditedAnswer). Mapping to "requires_human_review" is more
        # honest than "block": the system did not classify, it errored.
        actual_verdict = "requires_human_review"
    else:
        actual_verdict = audited.verdict.value

    # Citations
    emitted_articles = extract_emitted_articles_chat(state)
    citations = compute_citation_metrics(
        emitted=emitted_articles, expected=case.articulos_esperados
    )

    # Severity
    actual_severity = _extract_severity_chat(audited)
    severity_match: bool | None
    if case.severidad_esperada is None:
        severity_match = None
    else:
        severity_match = case.severidad_esperada == actual_severity

    # Ragas metrics
    contexts = [c.text for c in state.context.chunks] if state.context else []
    answer_text = audited.answer.text if audited else ""
    ragas = _ragas_metrics_chat(
        query=case.entrada,
        answer=answer_text,
        contexts=contexts,
        ground_truth=case.salida_esperada,
        judge_call=judge_call,
    )

    # Custom criteria via judge
    criteria_scores = judge_score_fn(
        criteria=case.criterios_evaluacion,
        query=case.entrada,
        actual_answer=answer_text,
        expected_answer=case.salida_esperada,
        cited_articles=emitted_articles,
        expected_articles=case.articulos_esperados,
    )

    return ChatCaseResult(
        case_id=case.id,
        expected_verdict=case.expected_verdict,
        actual_verdict=actual_verdict,  # type: ignore[arg-type]
        verdict_match=(actual_verdict == case.expected_verdict),
        expected_severity=case.severidad_esperada,
        actual_severity=actual_severity,  # type: ignore[arg-type]
        severity_match=severity_match,
        citations=citations,
        faithfulness=ragas["faithfulness"],
        answer_relevancy=ragas["answer_relevancy"],
        context_precision=ragas["context_precision"],
        context_recall=ragas["context_recall"],
        criteria_scores=criteria_scores,
        latency_ms=latency_ms,
        cost_eur=cost_eur,
        cache_hit=cache_hit,
    )


def compute_doc_metrics(
    case: GoldCaseDoc,
    report: DocumentReport,
    *,
    judge_call: Callable[..., tuple[str, float]],
    judge_score_fn: Callable[..., list[CriteriaScore]],
    latency_ms_total: int,
    cost_eur_total: float,
    cache_hit: bool,
) -> DocCaseResult:
    """Compute metrics for one document case."""
    actual_verdict = report.document_verdict.value

    emitted_articles = extract_emitted_articles_doc(report)
    findings_citations = compute_citation_metrics(
        emitted=emitted_articles, expected=case.expected_findings_articulos
    )

    n_segments_within_tolerance = (
        abs(report.n_segments_total - case.expected_n_segments) <= case.n_segments_tolerance
    )

    # Ragas faithfulness: aggregate the answer text across segments
    answer_text = " ".join(
        seg.audited_answer.answer.text for seg in report.segments if seg.audited_answer is not None
    )
    # Use each segment's own text as the context for faithfulness.
    # H5 SegmentResult does not carry retrieved corpus chunks at report level
    # (deferred to H10/H17 polish), so segment text is the closest faithful proxy.
    contexts = [seg.segment.text for seg in report.segments if seg.audited_answer is not None]
    ragas = _ragas_metrics_doc(
        query=f"Analiza este documento contra {','.join(case.corpus_esperado)}",
        answer=answer_text or "[no_answer]",
        contexts=contexts,
        ground_truth=None,
        judge_call=judge_call,
    )

    criteria_scores = judge_score_fn(
        criteria=case.criterios_evaluacion,
        query=f"Analisis documento {case.id}",
        actual_answer=answer_text,
        expected_answer=None,
        cited_articles=emitted_articles,
        expected_articles=case.expected_findings_articulos,
    )

    return DocCaseResult(
        case_id=case.id,
        expected_document_verdict=case.expected_document_verdict,
        actual_document_verdict=actual_verdict,  # type: ignore[arg-type]
        verdict_match=(actual_verdict == case.expected_document_verdict),
        expected_n_segments=case.expected_n_segments,
        actual_n_segments=report.n_segments_total,
        n_segments_within_tolerance=n_segments_within_tolerance,
        findings_citations=findings_citations,
        faithfulness=ragas["faithfulness"],
        criteria_scores=criteria_scores,
        latency_ms_total=latency_ms_total,
        cost_eur_total=cost_eur_total,
        cache_hit=cache_hit,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _safe_mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _safe_p95(values: list[int]) -> int:
    if not values:
        return 0
    if len(values) < 2:
        return values[0]
    qs = statistics.quantiles(values, n=20)
    return int(qs[18])  # 95th percentile (index 18 of 19 cut-points in n=20)


def aggregate(
    chat_results: list[ChatCaseResult],
    doc_results: list[DocCaseResult],
) -> AggregateMetrics:
    """Aggregate per-case results into headline metrics for the report."""
    chat_n = len(chat_results)
    doc_n = len(doc_results)

    faithfulness_values = [r.faithfulness for r in chat_results] + [
        r.faithfulness for r in doc_results
    ]
    answer_relevancy_values = [r.answer_relevancy for r in chat_results]
    context_precision_values = [r.context_precision for r in chat_results]
    context_recall_values = [r.context_recall for r in chat_results]

    citation_precision_values = [r.citations.precision for r in chat_results] + [
        r.findings_citations.precision for r in doc_results
    ]
    citation_recall_values = [r.citations.recall for r in chat_results] + [
        r.findings_citations.recall for r in doc_results
    ]

    verdict_match_values = [1.0 if r.verdict_match else 0.0 for r in chat_results] + [
        1.0 if r.verdict_match else 0.0 for r in doc_results
    ]

    # severity_match_rate denominator excludes chat cases where severidad_esperada=None
    # (the gold case did not specify a severity expectation). Reported rate is over the
    # subset of cases that DID expect a severity, not over all chat cases.
    severity_match_values = [
        1.0 if r.severity_match else 0.0 for r in chat_results if r.severity_match is not None
    ]

    chat_latency_values = [r.latency_ms for r in chat_results]
    doc_latency_values = [r.latency_ms_total for r in doc_results]
    latency_values = chat_latency_values + doc_latency_values

    chat_costs = [r.cost_eur for r in chat_results]
    doc_costs = [r.cost_eur_total for r in doc_results]

    cache_hits = [r.cache_hit for r in chat_results] + [r.cache_hit for r in doc_results]
    cache_hit_rate = sum(1 for h in cache_hits if h) / len(cache_hits) if cache_hits else 0.0

    return AggregateMetrics(
        n_chat_cases=chat_n,
        n_doc_cases=doc_n,
        faithfulness_mean=_safe_mean(faithfulness_values),
        answer_relevancy_mean=_safe_mean(answer_relevancy_values),
        context_precision_mean=_safe_mean(context_precision_values),
        context_recall_mean=_safe_mean(context_recall_values),
        citation_precision_mean=_safe_mean(citation_precision_values),
        citation_recall_mean=_safe_mean(citation_recall_values),
        verdict_match_rate=_safe_mean(verdict_match_values),
        severity_match_rate=_safe_mean(severity_match_values),
        chat_latency_p95_ms=_safe_p95(chat_latency_values),
        doc_latency_p95_ms=_safe_p95(doc_latency_values),
        latency_p95_ms=_safe_p95(latency_values),
        cost_per_chat_eur=_safe_mean(chat_costs),
        cost_per_doc_eur=_safe_mean(doc_costs),
        cost_total_eur=sum(chat_costs) + sum(doc_costs),
        cache_hit_rate=cache_hit_rate,
    )
