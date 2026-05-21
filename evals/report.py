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

# Threshold table — dual layer per ADR-0021 (v0.1.16).
# v0.1.20-bar = derived from H10 + H15 v1.2 measured baselines (spec §2 D2);
# aspirational = CLAUDE.md §17 long-term targets.
# Tuple shape: (metric_name, v0120_bar, aspirational, gated_in_report)
# - gated=True  → render ✅/❌ for both threshold columns.
# - gated=False → render `(info)` in both columns (e.g. context_recall_mean).
_THRESHOLDS: list[tuple[str, float, float, bool]] = [
    ("faithfulness_mean", 0.65, 0.85, True),
    ("answer_relevancy_mean", 0.55, 0.85, True),
    ("context_precision_mean", 0.55, 0.80, True),
    ("context_recall_mean", 0.0, 0.80, False),  # info-only carry; bar irrelevant
    ("citation_precision_mean", 0.25, 0.90, True),
    ("citation_recall_mean", 0.60, 0.80, True),
    ("verdict_match_rate", 0.35, 0.85, True),
    ("severity_match_rate", 0.35, 0.80, True),
]


def _render_aggregate_table(agg: AggregateMetrics) -> str:
    rows: list[str] = []
    rows.append("| Métrica | Valor | v0.1.20-bar | Aspiracional |")
    rows.append("|---|---|---|---|")
    for metric_name, v0120_bar, aspirational, gated in _THRESHOLDS:
        value = getattr(agg, metric_name)
        if not gated:
            bar_cell = "(info)"
            aspir_cell = "(info)"
        else:
            # v0.1.20-bar cell with pass/fail (soft mark per ADR-0021 D4).
            if value >= v0120_bar:
                bar_cell = f"≥{v0120_bar:.2f} ✅"
            else:
                bar_cell = f"≥{v0120_bar:.2f} ❌ ({value - v0120_bar:+.2f})"
            # Aspirational cell with pass/fail (info-only — never blocks).
            if value >= aspirational:
                aspir_cell = f"≥{aspirational:.2f} ✅"
            else:
                aspir_cell = f"≥{aspirational:.2f} ❌ ({value - aspirational:+.2f})"
        rows.append(f"| {metric_name} | {value:.2f} | {bar_cell} | {aspir_cell} |")

    # Latency + cost (single-threshold semantics — operational, not quality).
    # Place existing pass/fail in the v0.1.20-bar slot; aspirational slot = `(info)`.
    latency_pass = "✅" if agg.latency_p95_ms <= 12000 else f"❌ (+{agg.latency_p95_ms - 12000})"
    rows.append(f"| latency_p95_ms | {agg.latency_p95_ms} | ≤12000 {latency_pass} | (info) |")
    rows.append(f"| chat_latency_p95_ms | {agg.chat_latency_p95_ms} | (info) | (info) |")
    rows.append(f"| doc_latency_p95_ms | {agg.doc_latency_p95_ms} | (info) | (info) |")
    if agg.cost_per_chat_eur <= 0.05:
        cost_chat_pass = "✅"
    else:
        cost_chat_pass = f"❌ ({agg.cost_per_chat_eur - 0.05:+.3f})"
    rows.append(
        f"| cost_per_chat_eur | {agg.cost_per_chat_eur:.3f} | ≤0.05 {cost_chat_pass} | (info) |"
    )
    if agg.cost_per_doc_eur <= 0.50:
        cost_doc_pass = "✅"
    else:
        cost_doc_pass = f"❌ ({agg.cost_per_doc_eur - 0.50:+.3f})"
    rows.append(
        f"| cost_per_doc_eur | {agg.cost_per_doc_eur:.3f} | ≤0.50 {cost_doc_pass} | (info) |"
    )
    rows.append(f"| cost_total_eur | {agg.cost_total_eur:.2f} | (info) | (info) |")
    rows.append(f"| cache_hit_rate | {agg.cache_hit_rate:.2f} | (info) | (info) |")
    return "\n".join(rows)


def _render_caveats_block() -> str:
    """v0.1.16: render the v0.1.20-bar reading caveats subsection.

    Per spec §2 D2 caveats wording (verbatim). Inserted between the aggregate
    metrics table and the per-case appendix in `render_report`. The 4 bullets
    document the dual-layer interpretation, bar derivation lineage, judge family
    decision, and latency-contamination caveat carried from H8/§17.
    """
    parts: list[str] = []
    parts.append("## Caveats — v0.1.20-bar reading")
    parts.append("")
    parts.append(
        "1. **Aspirational column** = CLAUDE.md §17 long-term ideal targets; no run "
        "has ever hit them; they remain as direction-setting, not as v0.1.20 ship gate."
    )
    parts.append(
        "2. **v0.1.20-bar column** = anchored to H10 (full-30-case measured baseline) + "
        "H15 v1.2 (30-case partial intervention measurement); the 64-case set is harder "
        "so even matching the bar is meaningful evidence the maximalist-plan stack didn't "
        "regress on the easier subset."
    )
    parts.append(
        "3. **Judge family stays Haiku 4.5** per ADR-0010 D1 caveat (same vendor as "
        "production Sonnet, different model class). Cross-vendor migration deferred to "
        "HX (post-TFM); §19 satisfied literally; documented honestly."
    )
    parts.append(
        "4. **Latency p95** number remains contaminated by batch+rate-limit+tenacity "
        "backoff per H8 amendment §H8 + §17 note; v0.1.16 does NOT fix this. H17 LangFuse "
        "refactor is the proper instrument; until then `latency_p95_ms` is informational "
        "despite being formally gated in the report."
    )
    return "\n".join(parts)


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
    sections.append(_render_caveats_block())
    sections.append("")
    sections.append(f"## Per-case appendix — chat ({agg.n_chat_cases} cases)")
    sections.append("")
    for chat_r in chat_results:
        sections.append(_render_per_case_chat(chat_r))
        sections.append("")
    sections.append(f"## Per-case appendix — documents ({agg.n_doc_cases} cases)")
    sections.append("")
    for doc_r in doc_results:
        sections.append(_render_per_case_doc(doc_r))
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
