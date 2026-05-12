"""H8 — Markdown report generator.

Pure function `render_report(meta, agg, chat_results, doc_results) -> str`.
No I/O; the harness writes the result to evals/reports/latest.md.
"""

from __future__ import annotations

from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    DocCaseResult,
    EvalRunMeta,
)

# Threshold table per CLAUDE.md §17. (metric_name, threshold, gated)
_THRESHOLDS = [
    ("faithfulness_mean", 0.85, True),
    ("answer_relevancy_mean", 0.85, True),
    ("context_precision_mean", 0.80, True),
    ("context_recall_mean", 0.80, False),  # info-only, not gated
    ("citation_precision_mean", 0.90, True),
    ("citation_recall_mean", 0.80, True),
    ("verdict_match_rate", 0.85, True),
    ("severity_match_rate", 0.80, True),
]


def _render_aggregate_table(agg: AggregateMetrics) -> str:
    rows: list[str] = []
    rows.append("| Métrica | Valor | Threshold | Pass |")
    rows.append("|---|---|---|---|")
    for metric_name, threshold, gated in _THRESHOLDS:
        value = getattr(agg, metric_name)
        if not gated:
            mark = "➖"
            threshold_str = "(info)"
        elif value >= threshold:
            mark = "✅"
            threshold_str = f"≥{threshold:.2f}"
        else:
            mark = f"❌ ({value - threshold:+.2f})"
            threshold_str = f"≥{threshold:.2f}"
        rows.append(f"| {metric_name} | {value:.2f} | {threshold_str} | {mark} |")

    # Latency + cost (different threshold semantics)
    latency_pass = "✅" if agg.latency_p95_ms <= 12000 else f"❌ (+{agg.latency_p95_ms - 12000})"
    rows.append(f"| latency_p95_ms | {agg.latency_p95_ms} | ≤12000 | {latency_pass} |")
    # Per-mode latencies are info-only for now (combined is the gated metric per spec §5.4)
    rows.append(f"| chat_latency_p95_ms | {agg.chat_latency_p95_ms} | (info) | ➖ |")
    rows.append(f"| doc_latency_p95_ms | {agg.doc_latency_p95_ms} | (info) | ➖ |")
    if agg.cost_per_chat_eur <= 0.05:
        cost_chat_pass = "✅"
    else:
        cost_chat_pass = f"❌ ({agg.cost_per_chat_eur - 0.05:+.3f})"
    rows.append(f"| cost_per_chat_eur | {agg.cost_per_chat_eur:.3f} | ≤0.05 | {cost_chat_pass} |")
    if agg.cost_per_doc_eur <= 0.50:
        cost_doc_pass = "✅"
    else:
        cost_doc_pass = f"❌ ({agg.cost_per_doc_eur - 0.50:+.3f})"
    rows.append(f"| cost_per_doc_eur | {agg.cost_per_doc_eur:.3f} | ≤0.50 | {cost_doc_pass} |")
    rows.append(f"| cost_total_eur | {agg.cost_total_eur:.2f} | (info) | ➖ |")
    rows.append(f"| cache_hit_rate | {agg.cache_hit_rate:.2f} | (info) | ➖ |")
    return "\n".join(rows)


def _render_per_case_chat(r: ChatCaseResult) -> str:
    parts: list[str] = []
    parts.append(f"### {r.case_id}")
    parts.append("")
    verdict_mark = "✅" if r.verdict_match else "❌"
    sev_mark = "✅" if r.severity_match else "❌" if r.severity_match is False else "➖"
    parts.append(
        f"- **Verdict**: actual=`{r.actual_verdict}` expected=`{r.expected_verdict}` {verdict_mark}"
    )
    parts.append(
        f"- **Severity**: actual=`{r.actual_severity}` expected=`{r.expected_severity}` {sev_mark}"
    )
    parts.append(
        f"- **Citations**: emitted={r.citations.emitted} expected={r.citations.expected} "
        f"precision={r.citations.precision:.2f} recall={r.citations.recall:.2f}"
    )
    parts.append(
        f"- **RAG metrics**: faithfulness={r.faithfulness:.2f} "
        f"answer_relevancy={r.answer_relevancy:.2f} "
        f"context_precision={r.context_precision:.2f} "
        f"context_recall={r.context_recall:.2f}"
    )
    parts.append(
        f"- **Latency**: {r.latency_ms} ms"
        f" | **Cost**: {r.cost_eur:.4f} €"
        f" | **Cache hit**: {r.cache_hit}"
    )
    parts.append("- **Criteria**:")
    for cs in r.criteria_scores:
        cs_mark = "✅" if cs.passed else "❌"
        reason = f" — {cs.reason}" if cs.reason else ""
        parts.append(f"  - {cs_mark} {cs.criterion}{reason}")
    return "\n".join(parts)


def _render_per_case_doc(r: DocCaseResult) -> str:
    parts: list[str] = []
    parts.append(f"### {r.case_id}")
    parts.append("")
    verdict_mark = "✅" if r.verdict_match else "❌"
    seg_mark = "✅" if r.n_segments_within_tolerance else "❌"
    parts.append(
        f"- **Verdict**: actual=`{r.actual_document_verdict}`"
        f" expected=`{r.expected_document_verdict}` {verdict_mark}"
    )
    parts.append(
        f"- **Segments**: actual={r.actual_n_segments} expected={r.expected_n_segments} {seg_mark}"
    )
    parts.append(
        f"- **Findings citations**: emitted={r.findings_citations.emitted} "
        f"expected={r.findings_citations.expected} "
        f"precision={r.findings_citations.precision:.2f} recall={r.findings_citations.recall:.2f}"
    )
    parts.append(f"- **Faithfulness**: {r.faithfulness:.2f}")
    parts.append(
        f"- **Latency total**: {r.latency_ms_total} ms"
        f" | **Cost**: {r.cost_eur_total:.4f} €"
        f" | **Cache hit**: {r.cache_hit}"
    )
    parts.append("- **Criteria**:")
    for cs in r.criteria_scores:
        cs_mark = "✅" if cs.passed else "❌"
        reason = f" — {cs.reason}" if cs.reason else ""
        parts.append(f"  - {cs_mark} {cs.criterion}{reason}")
    return "\n".join(parts)


def render_report(
    meta: EvalRunMeta,
    agg: AggregateMetrics,
    chat_results: list[ChatCaseResult],
    doc_results: list[DocCaseResult],
) -> str:
    """Pure function: produce the full evals/reports/latest.md content."""
    sections: list[str] = []
    sections.append("# RegulAItor — Evaluation Report")
    sections.append("")
    sections.append(
        f"**Run:** {meta.run_date} | **Commit:** `{meta.commit_sha}` | "
        f"**Models:** {meta.production_model} (prod), {meta.judge_model} (judge)"
    )
    total_cases = agg.n_chat_cases + agg.n_doc_cases
    cache_hits = int(round(agg.cache_hit_rate * total_cases))
    cache_misses = total_cases - cache_hits
    subset_str = "full" if meta.subset is None else f"first {meta.subset}"
    sections.append(
        f"**Settings:** temperature={meta.temperature}, subset={subset_str},"
        f" cache hits/misses: {cache_hits}/{cache_misses}"
        f" | **Total cost:** {agg.cost_total_eur:.2f} €"
    )
    sections.append("")
    sections.append("## Aggregate metrics")
    sections.append("")
    sections.append(_render_aggregate_table(agg))
    sections.append("")
    sections.append(f"## Per-case appendix — chat ({agg.n_chat_cases} cases)")
    sections.append("")
    for r in chat_results:
        sections.append(_render_per_case_chat(r))
        sections.append("")
    sections.append(f"## Per-case appendix — documents ({agg.n_doc_cases} cases)")
    sections.append("")
    for r in doc_results:
        sections.append(_render_per_case_doc(r))
        sections.append("")
    sections.append("## Reproducibilidad")
    sections.append("")
    sections.append("```bash")
    sections.append(
        "make eval-from-cache  # regenera este report sin coste si la cache está poblada"
    )
    sections.append("make eval             # corre full set; consume crédito Anthropic")
    sections.append("```")
    sections.append("")
    sections.append("## Caveats")
    sections.append("")
    sections.append(
        "Resultados sobre N=" + str(total_cases) + " casos sintetizados con "
        "autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan "
        "distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que "
        "producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a "
        "H12 (router multi-LLM real)."
    )
    return "\n".join(sections) + "\n"
