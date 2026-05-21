# v0.1.20-bar thresholds + judge family decision (v0.1.16)

**Status:** Architecture shipped 2026-05-21 (tag `v0.1.16-section17-thresholds`). v0.1.20 paid bundle measurement deferred to user budget recharge. Judge stays Haiku 4.5 per ADR-0010 D1 caveat (resolved as explicit "stay" in ADR-0021 D3).

**TFM dual-target:** the bar makes "v0.1.20 success" measurable. The aspirational §17 targets stay as long-term direction (informational); the v0.1.20-bar codifies "the next acceptable evidence point" derivable from H10 + H15 v1.2 measured baselines.

---

## WHAT

Two complementary changes to the evaluation pipeline:

1. **Dual-layer thresholds in `evals/report.py`**: the constant `_THRESHOLDS` now carries 4 fields per metric — `(metric, v0120_bar, aspirational, gated)`. The eval report renders a 4-column aggregate table `Métrica | Valor | v0.1.20-bar | Aspiracional` with pass/fail badges in each threshold column. The new function `_render_caveats_block` inserts a 4-bullet "Caveats — v0.1.20-bar reading" subsection between the aggregate table and the per-case appendix.

2. **Judge family decision**: ADR-0010 D1 had carried a same-vendor-judge caveat with "deferred to H12 router multi-LLM" since 2026-05-17. H12 closed without migrating. v0.1.16 D3 resolves the silent deferral: Haiku 4.5 stays as the v0.1.20 judge; cross-vendor migration (GPT-4o-mini or Llama-3.3-70b via Groq) moves to HX (post-TFM) with documented rationale.

The v0.1.20-bar values per metric:

| Metric | H10 baseline | H15 v1.2 (30 cases) | **v0.1.20-bar** | Aspirational §17 | Lineage |
|---|---|---|---|---|---|
| `faithfulness_mean` | 0.54 | 0.75 | **0.65** | ≥0.85 | Midway H10/H15. |
| `answer_relevancy_mean` | 0.53 | — | **0.55** | ≥0.85 | Slight improvement; H15 was citation-focused. |
| `context_precision_mean` | 0.48 | — | **0.55** | ≥0.80 | H10 + 0.07; v0.1.11 per-norma cap helps. |
| `citation_precision_mean` | 0.17 | 0.30 | **0.25** | ≥0.90 | H10 + 0.08; v1.2 minimal-citation into v1.3. |
| `citation_recall_mean` | 0.44 | 0.71 | **0.60** | ≥0.80 | H10 + 0.16, midway H10/H15. |
| `verdict_match_rate` | 0.28 | — | **0.35** | ≥0.85 | H10 + 0.07. Conservative. |
| `severity_match_rate` | 0.23 | 0.42 | **0.35** | ≥0.80 | Midway H10/H15. |

`context_recall_mean` stays info-only (carry-forward from current `_THRESHOLDS`). Latency + cost rows keep single-threshold semantics (operational concern).

## WHY

**The measurement-architecture gap pre-v0.1.16.** v0.1.10-v0.1.15 shipped 6 microhitos under the §22.22 honest framing "capability shipped + measurement deferred to v0.1.20 paid bundle". v0.1.20 will be the single bundled paid run measuring all of them at once — but without a numeric bar, the question "did v0.1.20 succeed?" has no defined answer. CLAUDE.md §17 aspirational targets (faithfulness ≥0.85, citation_precision ≥0.90, etc.) are clearly aspirational — the latest H10 frozen re-eval (`0cc9534`) shows faithfulness 0.54, citation_precision 0.17, citation_recall 0.44, ALL far below §17. H15 v1.2 30-case partial intervention lifted faithfulness to 0.75 and citation_recall to 0.71 (real improvement, still below §17), but never re-baselined on the full 64-case set (the 30 H8 baseline + 10 H14 cross-corpus + 10 v0.1.13 industry-c/v + 10 v0.1.15 industry-g/gv).

The dual layer resolves the tension: keep §17 as the long-term direction (visible in the report, informational) AND define an intermediate v0.1.20-bar derivable from measured precedent. Every bar value is anchored to an existing measured datapoint — no promised numbers. The 64-case set is harder than H10's 30 cases (new cases designed to push retrieval + reasoning), so matching the bar on the aggregate is non-trivial evidence the v0.1.10-v0.1.15 stack didn't regress on the easier subset.

**Why judge stays Haiku 4.5.** Brainstorming considered three alternatives:

1. **Keep Haiku 4.5** (chosen) — Haiku ≠ Sonnet in model class satisfies §19 "modelo juez distinto al de producción" literally; preserves H10 cache continuity (40 cached judge entries reusable at v0.1.20); known-quantity behavior across H8/H10/H15; single API key; user has $0 Anthropic budget right now.
2. **Migrate to GPT-4o-mini** — rejected for v0.1.16. Invalidates entire H10 judge cache; needs N=5 paid A/B (~$0.05) to confirm correlation before v0.1.20 commits the budget; introduces 2nd-vendor dependency for eval infra. Cross-vendor migration properly belongs to HX (post-TFM) when budget recharges and TFM defense pressure is off.
3. **Multi-judge consensus (Haiku + GPT-4o-mini + Llama-3.3-70b via Groq)** — rejected. 3× paid cost; Groq Llama I-2 contamination risk (H12 empirical); harness multi-judge orchestration code is non-trivial. Over-engineered for current scope.

The same-vendor weakness vs Sonnet prod is real and documented honestly in the report's Caveats subsection (3rd bullet). The cross-vendor option stays viable for HX.

**Why soft mark, not hard gate.** Brainstorming considered a `--gate` CLI flag (`make eval-gate` exiting non-zero on bar breach). Rejected: ADR-0010 D4 (no LLM in CI; $7/PR unsustainable on $10 budget) stays firm; v0.1.20 acceptance ritual is decisions_log narrative-driven, not automated; the report's ✅/❌ badges already provide the visible signal; CI integration would require running paid LLM calls in CI, which is the precise thing ADR-0010 D4 vetoed.

## HOW

**Architecturally** the change is pure rendering:

```
evals/report.py
├── _THRESHOLDS                          (3-tuple → 4-tuple)
├── _render_aggregate_table              (3 columns → 4 columns)
├── _render_caveats_block                (NEW: 4-bullet subsection)
├── _render_per_case_chat                (UNCHANGED)
├── _render_per_case_doc                 (UNCHANGED)
└── render_report                        (1-line insertion of _render_caveats_block)
```

`AggregateMetrics` schema (`evals/schemas.py`) unchanged — both threshold columns read values from the same Pydantic fields. `evals/harness.py`, `evals/judge.py`, `evals/cache.py`, `evals/metrics.py` UNCHANGED — the judge stays Haiku 4.5 (same SHA256 cache keys preserved).

**At the LLM level**, nothing changes. The judge (Haiku 4.5) still consumes the same prompts and produces the same scores. The new threshold columns are pure post-processing in the report renderer.

**At the test level**, 6 new $0 unit tests pin the architecture:
- `test_thresholds_table_covers_8_quality_metrics` — `_THRESHOLDS` has 8 entries with the expected metric names.
- `test_v0120_bar_values_pinned` — exact bar values (0.65 / 0.55 / 0.55 / 0.25 / 0.60 / 0.35 / 0.35).
- `test_aspirational_values_pinned` — exact CLAUDE.md §17 values (0.85 / 0.85 / 0.80 / 0.90 / 0.80 / 0.85 / 0.80).
- `test_v0120_bar_below_aspirational_for_gated_metrics` — sanity check against accidental row-swap.
- `test_render_aggregate_table_emits_4_column_headers_and_dual_marks` — table header + dual badges.
- `test_render_caveats_block_emits_all_4_anchors` — caveat block text contains all 4 anchor strings.

No LLM call in v0.1.16. Empirical measurement bundled into v0.1.20.

## IMPACT

**Capability shipped, measurement deferred.** v0.1.16 is the `n`-th milestone in a row to ship under the §22.22 honest framing: the contribution IS the bar architecture + the bar values derived from measured precedent + the judge-family decision documented. The empirical question ("does the v0.1.10-v0.1.15 stack clear the bar on the 64-case set?") is bundled into the v0.1.20 single paid validation run.

**v0.1.20 acceptance ritual unlocked.** Pre-v0.1.16, v0.1.20 had no defined "success" target. Post-v0.1.16: v0.1.20 will render the dual-layer report; decisions_log §v0.1.20 will narrate "X/8 metrics passed v0.1.20-bar; Y/8 below — documented as deeper system-level ceiling per H15/H15.1 §22.22 pattern" + per-metric production-default flips (Analyst v1.3 default? RetrievalConfig per-norma cap default?) decided in that narrative based on the actual results.

**§6 invariant intact.** `src/regulaitor/agents/auditor.py`, `src/regulaitor/citation/validator.py`, `src/regulaitor/citation/schemas.py`, `src/regulaitor/api/schemas.py`, ALL backend dirs UNCHANGED (verified by 3 git-diff checks at T5). Eval-internals (judge/cache/harness/metrics/schemas) UNCHANGED. The change is entirely in `evals/report.py` rendering + 1 new test file + 2 new docs (ADR + this memoria doc) + closure docs.

**Gate carry-forward.** v0.1.15 baseline 850 → v0.1.16 baseline 856 (850 + 6 new $0 unit tests). 0 failures, 1 skipped (carry). mypy strict 71 files exit 0 (mypy only checks `src/`; `evals/` change is mypy-invisible). Redteam-smoke 0.92 (prompt-blind + retriever-blind + Auditor-blind so unaffected by report-layer change; verified at closure).

**$0 milestone.** No paid LLM call in v0.1.16. Single bundled paid validation at v0.1.20 when budget recharges, following the cost-estimation discipline registered after H15.2 (probe min N=5, ranges with high=expected×1.5, no auth if budget<high-estimate, no paid run without harness checkpoint).

---

## §17 vs v0.1.20-bar relationship (callout)

> **CLAUDE.md §17** = 13 long-term aspirational metrics (faithfulness ≥0.85, citation_precision ≥0.90, citation_recall ≥0.80, answer_relevancy ≥0.85, context_precision ≥0.80, blocking_rate ≥0.95, latency p95 ≤12s, etc.). These are TARGETS not gates. No run has ever hit them.
>
> **v0.1.20-bar** = intermediate measured bar that v0.1.20 must clear. Each value is anchored to existing measured precedent (H10 30-case baseline + H15 v1.2 30-case partial intervention). The bar is BELOW aspirational by construction (sanity-checked by `test_v0120_bar_below_aspirational_for_gated_metrics`).
>
> **Relationship**: aspirational = direction (where the project wants to be long-term); bar = next-acceptable-evidence-point (where the project demonstrably IS, given H10+H15 measurements, and what v0.1.20 must at minimum confirm given the harder 64-case set).
>
> **v0.1.16 does NOT change §17**: aspirational values stay verbatim. v0.1.16 ADDS the bar layer; §17 stays as direction.

## Judge family lineage (callout)

> **ADR-0010 D1 (H8, 2026-05-10)**: chose Haiku 4.5 with explicit caveat "Same vendor (Haiku vs Sonnet, both Anthropic) weakens independence claim. Documented in report Caveats; deferred to H12 router multi-LLM."
>
> **H12 closure (2026-05-17)**: router shipped (Anthropic + OpenAI + Groq) but judge migration was NOT part of H12 scope. The ADR-0010 D1 deferral became a silent carry-forward.
>
> **v0.1.16 D3 (this milestone)**: explicit resolution. Judge stays Haiku 4.5 for the v0.1.20 paid bundle. Cross-vendor migration (GPT-4o-mini or Llama-3.3-70b via Groq) moves to HX (post-TFM) with documented rationale (no budget; cache continuity; correlation-confirmation A/B not feasible). The option stays viable; the decision is "stay for v0.1.20", not "stay forever".

---

## References

- Spec: `docs/superpowers/specs/2026-05-21-v0.1.16-section17-thresholds-judge-family-design.md`.
- ADR: `docs/adr/0021-v0120-bar-thresholds.md`.
- Predecessor ADRs: 0010 (H8 evaluation harness — D1 caveat resolved here), 0013 (H12 router multi-LLM — cross-vendor capability available), 0016 (H15 Auditor calibration — measurement precedent), 0018 (H15.2 wiring fix — measurement-architecture lineage), 0020 (v0.1.15 chat gap-analysis — §22.22 pattern).
- Bar derivation source: `evals/reports/latest.md` (H10 frozen re-eval @ `0cc9534`).
- H15 v1.2 partial measurement: `evals/reports/h15/candidate-v1.2.md`.
- §6 invariant lineage: `CLAUDE.md` §6 + ADR-0006 (H4 chat E2E).
- CLAUDE.md §17 (aspirational targets, preserved verbatim).
- §22.22 honest-framing precedent: H15 / H15.1 / v0.1.10 / v0.1.11 / v0.1.12 / v0.1.13 / v0.1.14 / v0.1.15.
- Future paid validation: v0.1.20 paid bundle (single bundled measurement of all maximalist-plan optimizations against this bar).
