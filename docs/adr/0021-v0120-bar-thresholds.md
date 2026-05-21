# ADR 0021 — Dual-layer §17 thresholds + LLM-judge family stays Haiku 4.5 (v0.1.16)

- **Status:** Accepted — 2026-05-21 — squash `bc7b349`, tag `v0.1.16-section17-thresholds`
- **Deciders:** Project owner.
- **Companion ADRs:** 0010 (H8 evaluation harness — judge family lineage carried; D1 caveat resolved here), 0013 (H12 router multi-LLM — cross-vendor capability available but migration deferred), 0016 (H15 Auditor calibration — measurement precedent for the bar derivation), 0018 (H15.2 wiring fix — measurement-architecture milestone lineage), 0020 (v0.1.15 chat gap-analysis — capability-shipped + measurement-deferred §22.22 pattern carried).

## Context

The maximalist plan microhitos v0.1.10-v0.1.15 shipped under the §22.22 honest framing "capability shipped + measurement deferred to v0.1.20 paid bundle". v0.1.20 is the single bundled paid run that measures ALL maximalist-plan optimizations (per-article cap, per-norma cap, top_k_auto, industry gold extension, segmenter heading regex, gap-analysis chat mode) against the production baseline.

Without an intermediate numeric bar, v0.1.20 "success" is undefined. CLAUDE.md §17 lists 13 metrics with target numbers (faithfulness ≥0.85, citation_precision ≥0.90, citation_recall ≥0.80, etc.), but these are aspirational long-term targets — no run has ever hit them. The latest H10 frozen re-eval (`evals/reports/latest.md` @ `0cc9534`) shows faithfulness 0.54, citation_precision 0.17, citation_recall 0.44 — all far below §17 aspirational. H15 v1.2 30-case partial intervention lifted faithfulness to 0.75 and citation_recall to 0.71 — real improvement, still below §17, never re-baselined on the full 64-case set (the 30 H8 baseline + 10 H14 cross-corpus + 10 v0.1.13 industry-c/v + 10 v0.1.15 industry-g/gv).

Additionally, ADR-0010 D1 chose Haiku 4.5 as the judge with an explicit caveat: "Same vendor (Haiku vs Sonnet, both Anthropic) weakens independence claim. Documented in report Caveats; deferred to H12 [router multi-LLM]." H12 closed without flipping the judge; that deferral has been silent since 2026-05-17.

v0.1.16 resolves both: (a) defines the v0.1.20-bar (the soft mark v0.1.20 must clear), (b) explicitly decides the judge family question (stays Haiku 4.5; cross-vendor migration moved to HX post-TFM with documented rationale).

## Decision

### D1 — Thresholds shape = dual layer (aspirational + v0.1.20-bar), single source of truth

Replace `evals/report.py::_THRESHOLDS` 3-tuple `(metric, threshold, gated)` with a 4-tuple `(metric, v0120_bar, aspirational, gated)`. The v0.1.20-bar is the soft mark v0.1.20 must clear; aspirational §17 targets stay as long-term direction (info column, never blocks). One constant, both layers; report renders 4 columns: `Métrica | Valor | v0.1.20-bar | Aspiracional`.

### D2 — v0.1.20-bar values per metric (derived from measured precedent)

Every bar is anchored to existing measured datapoints. The 64-case set is intentionally harder than H10's 30 cases (+10 H14 cross-corpus + 10 v0.1.13 industry-c/v + 10 v0.1.15 industry-g/gv all designed to push retrieval/reasoning), so matching the bar on the aggregate is a non-trivial pass:

| Metric | H10 baseline | H15 v1.2 (30 cases) | **v0.1.20-bar** | Aspirational §17 | Lineage |
|---|---|---|---|---|---|
| `faithfulness_mean` | 0.54 | 0.75 | **0.65** | ≥0.85 | Midway H10/H15. |
| `answer_relevancy_mean` | 0.53 | — | **0.55** | ≥0.85 | Slight improvement; H15 was citation-focused. |
| `context_precision_mean` | 0.48 | — | **0.55** | ≥0.80 | H10 + 0.07; v0.1.11 per-norma cap (1/3→2/3 xcorpus-002 breakthrough). |
| `citation_precision_mean` | 0.17 | 0.30 | **0.25** | ≥0.90 | H10 + 0.08; v1.2 minimal-citation rule carried into v1.3. |
| `citation_recall_mean` | 0.44 | 0.71 | **0.60** | ≥0.80 | H10 + 0.16, midway H10/H15. Above §16.2 MVP floor ≥0.40. |
| `verdict_match_rate` | 0.28 | — | **0.35** | ≥0.85 | H10 + 0.07. Conservative; Auditor-mechanic-driven. |
| `severity_match_rate` | 0.23 | 0.42 | **0.35** | ≥0.80 | Midway H10/H15; v1.2 severity calibration into v1.3. |

`context_recall_mean` stays info-only (0.0 placeholder; gated=False). Latency + cost rows keep current single-threshold semantics (operational concern, not quality).

§16.2 MVP floors (citation_recall ≥0.40, redteam block_rate ≥0.90, coverage ≥80%) UNCHANGED — v0.1.20-bar 0.60 on citation_recall sits ABOVE the MVP floor.

### D3 — Judge family stays Haiku 4.5 (ADR-0010 D1 caveat resolved with explicit "stay")

No model migration. Rationale: (a) Haiku 4.5 ≠ Sonnet 4.6 in model class — §19 "modelo juez distinto al de producción" satisfied literally; (b) preserves H10 cache continuity (40 cached entries reusable at v0.1.20 if Analyst output unchanged); (c) known-quantity behavior (H8/H10/H15 all judged by Haiku — comparability across milestones); (d) single API key; (e) cross-vendor migration would invalidate the entire cache and require a full re-run on 64-case set just to confirm correlation — with $0 budget right now, premature.

Cross-vendor migration to GPT-4o-mini or Llama-3.3-70b via Groq remains an option for HX (post-TFM). The option is documented in Consequences and stays viable if a future signal demands it. Same-vendor weakness vs Sonnet prod is documented honestly in the report's Caveats subsection (3rd bullet — wait, 3rd bullet: judge family) per the existing transparency precedent.

### D4 — Enforcement = soft mark only

v0.1.20-bar metrics get ❌ badge in the report if below the bar; `make eval` exits 0 regardless (no build break). Soft mark matches the existing report-as-evidence pattern (ADR-0010 D4: no LLM in CI; $7/PR unsustainable). v0.1.20 acceptance ritual: decisions_log narrative interprets "X/8 metrics passed v0.1.20-bar; Y/8 below — documented as deeper system-level ceiling per H15/H15.1 §22.22 pattern" + per-metric production-default flips (Analyst v1.3, RetrievalConfig per-norma cap, etc.) decided in that narrative.

## Consequences

**Positive:**

- **Clear v0.1.20 acceptance ritual**: the bar exists, derivable from existing evidence (H10 + H15), interpretable by examiners.
- **Honest §22.22 framing**: aspirational targets remain visible (no overclaim, no dishonest hiding) AND a measurable intermediate bar is defined; the report shows both layers.
- **Cache continuity preserved**: judge stays Haiku 4.5 → H10's 40 cached entries reusable at v0.1.20 (partial savings; v1.3 evals will be cache-miss anyway because Analyst output differs).
- **ADR-0010 D1 caveat properly resolved**: the silent "deferred to H12" carry-forward is replaced with an explicit "stays Haiku in v0.1.16; cross-vendor migration moved to HX post-TFM" decision.
- **Single src file modified** (`evals/report.py`, ~50-80 lines): surgical change; backend H1-H5/H7 + Auditor + citation-validator + Pydantic schemas + DTOs + eval-internals (judge/cache/harness/metrics/schemas) BYTE-UNCHANGED.
- **6 new $0 unit tests** pin the architecture (bar values, aspirational values, dual-column render, caveats anchors, bar < aspirational sanity).

**Negative / accepted (documented honestly per §22.22):**

- **Same-vendor judge weakness persists**: Haiku 4.5 vs Sonnet 4.6 (both Anthropic) is weaker independence than cross-vendor. Documented in the report Caveats subsection (3rd bullet). The option to migrate to GPT-4o-mini or Llama-3.3-70b via Groq stays open for HX.
- **Latency p95 formally gated but operationally contaminated**: the `latency_p95_ms ≤ 12000` threshold remains in `_THRESHOLDS` rendering but the measured value (~572408 ms at H10) is batch+rate-limit+tenacity-backoff contaminated per H8 amendments. H17 LangFuse trace-based refactor is the proper instrument. v0.1.16 explicitly documents this in the Caveats subsection (4th bullet) — does NOT fix it.
- **No paid LLM run in v0.1.16**: the bar exists as a rendering target but no measurement happens until v0.1.20. v0.1.16's contribution IS the bar architecture + derivation rationale + judge-family decision — measurement is bundled into v0.1.20.
- **Soft mark only (no CI gate)**: a v0.1.20 run that misses the bar will NOT auto-revert via CI; the §22.22 narrative-driven acceptance ritual depends on the decisions_log entry interpretation at closure time. Acceptable trade-off vs CI integration cost (ADR-0010 D4 carries).

## Alternatives considered

- **Aspirational-only (no v0.1.20-bar)** — rejected. v0.1.20 success becomes purely narrative; no numeric anchor; reviewer cannot evaluate the bundled measurement against a defined target. Defeats the §22.22 honest framing's measurability claim.
- **Per-case-type stratified thresholds** (Q&A vs gap-analysis vs vague-real different bars) — rejected as premature optimization. v0.1.20 measurement will surface if stratification is needed; defer until evidence demands it. Adds per-stratum aggregation code to `evals/metrics.py` (non-trivial) without clear current need.
- **Hard `--gate` CLI flag** (`make eval-gate` target exiting non-zero on bar breach) — rejected. ADR-0010 D4 (no LLM in CI; $7/PR unsustainable on $10 budget) stays firm; over-engineered for current eval workflow; v0.1.20 acceptance ritual is decisions_log narrative-driven, not automated.
- **Judge migration to GPT-4o-mini (different vendor OpenAI)** — rejected for v0.1.16. Invalidates H10 cache; requires N=5 paid A/B (~$0.05) to confirm correlation with Haiku before committing v0.1.20 budget; introduces 2nd-vendor dependency for evaluation infrastructure; the user has $0 Anthropic budget right now. Cross-vendor decision properly belongs to HX (post-TFM) when budget recharges and TFM-defense pressure is off.
- **Multi-judge consensus (Haiku + GPT-4o-mini + Llama-3.3-70b)** — rejected for v0.1.16. 3× paid cost (~$7-8 vs ~$2.5 for single Haiku on 64-case set); Groq Llama I-2 contamination risk (H12 empirical); harness needs multi-judge orchestration code (eval-side change, non-trivial). Over-engineered for current scope; HX consideration if v0.1.20 reveals single-judge is a measurement bottleneck.

## References

- Spec: `docs/superpowers/specs/2026-05-21-v0.1.16-section17-thresholds-judge-family-design.md` (commit `83fceec`).
- Bar derivation source: `evals/reports/latest.md` (H10 frozen re-eval @ `0cc9534`, 30 chat + 10 doc).
- H15 v1.2 partial intervention measurement: `evals/reports/h15/candidate-v1.2.md` (30 chat A/B; never re-baselined on full 64-case set).
- ADR-0010 D1: "Judge = Anthropic Haiku 4.5" with same-vendor caveat documented; H12 deferral note. This ADR resolves the deferral.
- CLAUDE.md §17: aspirational targets (faithfulness ≥0.85, citation_precision ≥0.90, citation_recall ≥0.80, etc.) preserved verbatim; v0.1.16 ADDS the bar layer, does NOT alter §17.
- §6 invariant lineage: ADR-0006 (H4 chat E2E), CLAUDE.md §6. Auditor + citation-validator BYTE-UNCHANGED in v0.1.16.
- §22.22 honest-framing precedent: H15 / H15.1 / v0.1.10 / v0.1.11 / v0.1.12 / v0.1.13 / v0.1.14 / v0.1.15 all shipped under capability-shipped + measurement-deferred pattern.
- v0.1.20 paid bundle: single bundled measurement of all maximalist-plan optimizations against this bar.
- Memoria narrative: `docs/v0120_bar_thresholds.md` (WHAT/WHY/HOW/IMPACT + bar derivation table + judge-family lineage).
