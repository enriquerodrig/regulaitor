# ADR 0024 — Citation granularity confound (eval-instrument fix) (v0.1.18)

- **Status:** Accepted — 2026-05-22 — squash `<squash-sha>`, tag `v0.1.18-citation-granularity`
- **Deciders:** Project owner.
- **Companion ADRs:** 0010 (H8 evaluation harness — the canonical citation_precision/recall metric instrument this fixes; D7 cache-stores-judge-only is the substrate that enables $0 re-rendering), 0015 (H14 cross-corpus expansion — introduced the article-level expected_articles annotation style that exposed the H8 apartado-level baseline assumption), 0017 (H15.1 retriever optimization — the §22.22 design-defect disclosure on instrument invariance that flagged this exact confound; v0.1.18 RESOLVES it), 0021 (v0.1.16 dual-layer thresholds + v0.1.20-bar — the measurement venue that requires this instrument fix for a fair denominator), 0023 (v0.1.17.1 no-Answer fix — the immediately-preceding eval-side milestone; pattern reference for boundary-contract preservation).

## Context

The H15.1 §22.22 design-defect disclosure (ADR-0017, `docs/retriever_optimization.md`) flagged that v1.2's holdout citation=0.00 is dominated by the eval instrument's exact-match contract — NOT a measurement of v1.2's (or any future Analyst prompt's) actual citation quality.

**Empirical evidence (collected during v0.1.18 brainstorming, 2026-05-22):**

Gold set granularity distribution (64 chat cases):

| Bucket | Cases | Article-level expected | Apartado-level expected |
|--------|-------|------------------------|-------------------------|
| chat (H8) | 30 | 1 (chat-028, intentional — RGPD art 44 general principle) | 38 |
| nis2/dora/xcorpus (H14) | 14 | 20 | 0 |
| industry (v0.1.13/v0.1.15) | 20 | 70 | 0 |
| **TOTAL** | **64** | **91** | **38** |

Holdout report sample (`evals/reports/h15/holdout-v1.2-chat.md`, pre-v0.1.18):

```
- emitted=['2.2', '3.1', '3.2', '3.3']  expected=['2', '3']    precision=0.00  recall=0.00
- emitted=['20.1', '20.2', '21.1', '33.4']  expected=['21']    precision=0.00  recall=0.00
- emitted=['23.4']  expected=['23']                              precision=0.00  recall=0.00
```

Every 0.00/0.00 line is a granularity mismatch where the Analyst correctly cited apartados within the expected article. Under hierarchical containment match, the first row scores precision=1.00 + recall=1.00.

The fix lives in `evals/metrics.py::compute_citation_metrics` (where the simple set-intersection currently happens). The §6 invariant (`src/regulaitor/citation/validator.py`) is NOT touched — production-side citation VALIDATION (does the citation exist + match literally) stays byte-unchanged. v0.1.18 fixes only the post-hoc EVAL precision/recall metric that scores how well the Analyst's correct-by-validator citations align with the gold annotator's expected set.

## Decision

### D1 — Hierarchical containment match with directional asymmetry

Replace `compute_citation_metrics`'s set-intersection with a per-pair match rule `_citation_matches(emitted: str, expected: str) -> bool`:

| expected | emitted | match | rationale |
|----------|---------|-------|-----------|
| `"X"`    | `"X"`   | True  | exact article-level |
| `"X"`    | `"X.Y"` | True  | article-expected matches any apartado of X (the question doesn't care which sub-clause) |
| `"X.Y"`  | `"X.Y"` | True  | exact apartado-level |
| `"X.Y"`  | `"X.Z"` | False | different apartados = different obligations |
| `"X.Y"`  | `"X"`   | False | apartado-expected requires apartado-specific match; article-only emitted is too coarse |
| `"X"`    | `"W.Y"` | False | different article (W ≠ X) |
| `"X.Y"`  | `"W.Z"` | False | different article (W ≠ X) |

The asymmetry is deliberate: article-only expected is a coarser target that ANY apartado of that article satisfies (chat-028 RGPD art 44 general principle, every H14/industry case). Apartado-only expected is a finer target requiring the right sub-clause (chat-001 art 6.1 is the high-risk definition vs art 6.2 is the listing — different obligations).

Prefix-collision defended via trailing-dot startswith: `"106.1".startswith("6.")` is False (correctly), so `_citation_matches("106.1", "6")` returns False. Pinned by `test_citation_matches_different_article_apartado_levels`.

### D2 — Pure instrument fix (gold byte-unchanged)

No gold re-annotation. The 64 chat + 10 doc cases stay byte-unchanged. The instrument now handles BOTH legitimate granularities via D1.

chat-028 (the H8 article-level outlier) is intentional — RGPD art 44 is the general principle for international transfers, no specific apartado is the right citation. Confirmed by reading the case during brainstorming. Not annotator drift.

Boundary contract carried verbatim from v0.1.17.1: `evals/gold_set.jsonl` HARD git-diff invariant remains empty at pre-closure gate.

### D3 — Re-render historical reports from cache at $0 (with T3 implementation pivot)

Apply the new instrument to existing historical reports at $0. The plan originally specified `make eval-from-cache` for `evals/reports/latest.md` + `scripts/rerender_reports.py` for `h15/*.md`. **T3 controller-verification discovered that `make eval-from-cache` is NOT $0**: per `evals/harness.py:204-208`, the `--cache-only` flag caches ONLY the judge layer; the chat graph (Retriever → Analyst → Auditor) still calls real Anthropic API for the Analyst. With user's $0 Anthropic budget, that approach would incur hidden charges or fail with billing errors.

**Pivot:** ship `scripts/rerender_reports.py` (~200 lines) as the SOLE rerender mechanism (truly $0 — pure regex over markdown). Expanded scope to cover ALL 15 historical chat-mode reports (the plan's original 2-file `REPORTS_TO_RERENDER` undercounted; T0 glob discovered 15 files with the per-case Citation row format).

The script does focused string-surgery on per-case Citation rows + recomputes aggregate `citation_precision_mean` / `citation_recall_mean` from the new per-case values (excluding block cases per `evals/metrics.py::aggregate` convention). Idempotent.

**T3 verdict — 15 files re-rendered, 6 modified in the commit, 9 byte-identical post-script:**

*Headline flips (Done-when #9 anchor — H15.1 §22.22 design-defect RESOLVED):*

- `holdout-v1.2-chat.md`: precision_mean 0.00 → **0.65** (+0.65); recall_mean 0.00 → **0.64** (+0.64).
- `h15_1-holdout.md`: precision_mean 0.00 → **0.69** (+0.69); recall_mean 0.00 → **0.72** (+0.72).
- `holdout-v1.2-chat-probe.md`: precision_mean 0.00 → **0.71** (+0.71); recall_mean 0.00 → **1.00** (+1.00).

*H10 baseline + H8 cohort flips (smaller deltas; reflect both the new rule AND the block-case-exclusion aggregation convention):*

- `latest.md` (H10 baseline): precision_mean 0.18 → 0.21 (+0.03); recall_mean 0.48 → 0.56 (+0.07).
- `latest.cost.md`: precision_mean 0.49 → 0.56 (+0.08); recall_mean 0.60 → 0.69 (+0.09).
- `latest.evaluation.md`: precision_mean 0.46 → 0.53 (+0.07); recall_mean 0.55 → 0.63 (+0.08).

The 9 byte-identical files (4 H15-era cohort reports + 5 probes) had per-row values already invariant under both rules + aggregates already excluding block cases (the H15 study had its own aggregator that already did the exclusion). The script ran on them but produced byte-identical output — git correctly shows no diff.

Doc-mode reports (using `**Findings citations**` label) UNTOUCHED per §5 out-of-scope: doc-mode uses the same `compute_citation_metrics` transitively, so the fix applies to FUTURE v0.1.20 doc-mode runs. The 1 historical doc-mode probe (`docprobe-v1.2.md`) stays frozen as documented carry-forward.

### D4 — `_format_articulo` UNCHANGED, signature compatibility preserved

`_format_articulo(c: Citation) -> str` still produces `"X.Y"` when apartado present, `"X"` when absent. The new match rule operates on its output. `compute_citation_metrics` signature is unchanged (`emitted: list[str]`, `expected: list[str]`); only its INTERNAL logic changes.

`CitationMetrics` dataclass (the return type) is unchanged: `emitted`, `expected`, `precision`, `recall` fields, all the same types. Callers (harness, report renderer, aggregation) need NO modification.

Dedup-first behavior preserved (`sorted(set(emitted))` / `sorted(set(expected))` at function entry), so the 5 pre-existing `compute_citation_metrics` tests stay GREEN unchanged — including the `test_citation_metrics_dedup` edge case.

### D5 — This ADR documents the instrument change + retrospective re-rendering decision

This file. ADR count: 23 → **24**. The §6 invariant interpretive distinction documented here is important for TFM defense narrative: there are TWO citation layers in RegulAItor, and v0.1.18 touches only one:

- **Production-side citation VALIDATION** (`src/regulaitor/citation/validator.py`, the §6-invariant guardian): "Does the citation refer to an article/apartado that exists in the corpus? Does the citation text literally match the corpus text?" → byte-unchanged in v0.1.18.
- **Post-hoc EVAL precision/recall metric** (`evals/metrics.py::compute_citation_metrics`): "Of the citations the Analyst emitted, how many align with the gold annotator's expected set? Of the expected citations, how many did the Analyst cover?" → rewritten in v0.1.18 with hierarchical containment.

The production system's "no citation, no answer" guarantee operates entirely on the first layer. v0.1.18 fixes the post-hoc measurement layer that scores how good the Analyst is at picking the RIGHT citations from the validator-passing set.

## Consequences

**Positive:**

- **H15.1 §22.22 design-defect disclosure RESOLVED**: the instrument-artifact-not-quality narrative is no longer needed; v1.2's actual citation quality becomes visible retroactively. The new holdout `citation_recall` value (0.64) is the v1.2 prompt's real measurement.
- **v0.1.20 paid bundle measurement gets a fair denominator**: no more granularity-mismatch confound on the 35-of-64 article-level expected cases.
- **§6 invariant interpretive distinction documented**: production-side VALIDATION (citation/validator.py) is byte-unchanged; the EVAL precision/recall metric fix is cleanly separated. TFM defense narrative gains clarity on the two citation layers.
- **Backward consistency**: retrospective re-rendering of canonical historical reports means v0.1.20 comparison numbers are apples-to-apples vs H10/H15/H15.1.
- **$0 milestone**: pure-Python regex re-render + unit tests; no paid LLM.
- **Hierarchical containment is reusable**: `_citation_matches` is exportable for future eval extensions.
- **T3 pivot transparency**: the `make eval-from-cache` IS-NOT-$0 discovery is documented so future milestones don't repeat the assumption.

**Negative / accepted (per §22.22):**

- **The match rule's asymmetry adds cognitive load**: expected-side granularity controls the match leniency. Future eval contributors need to understand the asymmetry (documented in `_citation_matches` docstring + this ADR + spec).
- **No empirical validation of the v0.1.20 measurement narrative in v0.1.18**: v0.1.18 ships the prerequisite; v0.1.20 paid run validates that the v1.4 prompt + retrieval levers actually improve citation quality under the corrected instrument.
- **chat-028's article-level annotation is treated as intentional based on inspection**: if future annotators decide chat-028 should have been apartado-level, the v0.1.18 instrument silently still works (article-expected matches any apartado of art 44). The choice is reversible without instrument change.
- **Re-rendered historical reports change committed values**: pre-v0.1.18 commit history's report files are different from v0.1.18+ committed report files. Git history makes this auditable; the v0.1.18 closure docs make the change explicit.
- **Threshold-check annotations on aggregate lines are slightly stale** in re-rendered reports: e.g. `| citation_precision_mean | 0.65 | ≥0.90 | ❌ (-0.90) |` — the value `0.65` is correct, but the `(-0.90)` delta-from-threshold annotation was not updated by the script (regex captures only the metric value). Minor cosmetic carry-forward; v0.1.20 paid bundle regenerates fresh threshold comparisons.
- **The 9 byte-identical post-script files** (4 H15-era cohort + 5 probes) signal that the H15 study had its own aggregator that already excluded block cases — a subtle implementation detail of the historical pipeline, not a defect.
- **No partial-credit signal**: a case where the Analyst cites the right article but the wrong apartado (e.g. expected=["6.1"], emitted=["6.2"]) scores 0.0/0.0, same as completely-wrong-article. A future milestone could add partial-credit if v0.1.20 measurement surfaces this as a meaningful distinction (Option C from brainstorming, deferred).

## Alternatives considered

- **Normalize both to article granularity (drop apartado before comparing)** — rejected. Loses H8 apartado-discrimination signal. 29/30 H8 cases legitimately want apartado precision; chat-001 expected=['6.1','6.2'] vs emitted=['6.3','6.7'] should NOT match (different sub-clauses are different obligations).
- **Hierarchical with partial credit (0.5 for article-vs-apartado)** — rejected as YAGNI. Mixes Boolean with fractional in same metric (harder to reason about). Aggregation across cases needs care. v0.1.20 measurement goal is a fair denominator, not finer-grained signal. Reversibly addable in a future milestone if needed.
- **Light audit (chat-028 + 3-5 H14 spot-checks)** — rejected. chat-028 already verified intentional during brainstorming; H14 cases are recent and consistent (100% article-level annotation, no apartado-level outliers observed). No evidence of drift to motivate the audit.
- **Full granularity audit (all 64 cases)** — rejected. High-probability YAGNI (most-likely outcome: 0 changes after expensive audit).
- **Freeze historical reports + apply instrument only to v0.1.20+ runs** — rejected. Introduces a permanent §22.22 caveat (pre-v0.1.18 numbers use old instrument; direct comparison invalid). The TFM memoria would have to carry that caveat throughout. Retrospective consistency at $0 is cheap insurance against narrative friction.
- **Use `make eval-from-cache` for `latest.md` rerender** — rejected at T3 controller-verification. Not actually $0 (caches only judge layer; chat graph still calls Analyst API). T3 pivoted to use the rerender script exclusively for all 15 historical reports.

## References

- Spec: `docs/superpowers/specs/2026-05-22-v0.1.18-citation-granularity-design.md` (commit `48f2533`).
- Plan: `docs/superpowers/plans/2026-05-22-v0.1.18-citation-granularity.md` (commit `a27798e`).
- ADR-0010 (H8 evaluation harness — original metric instrument).
- ADR-0015 (H14 cross-corpus expansion — introduced article-level expected style).
- ADR-0017 (H15.1 retriever optimization — the §22.22 disclosure this resolves).
- ADR-0021 (v0.1.16 dual-layer thresholds — v0.1.20-bar measurement venue).
- ADR-0023 (v0.1.17.1 no-Answer fix — preceding eval-side milestone; pattern reference).
- Source data: `evals/reports/latest.md`, `evals/reports/h15/*.md`, `evals/gold_set.jsonl`.
- New metric helper: `evals/metrics.py::_citation_matches` (added v0.1.18, commit `eebcbcc`).
- Rewrite: `evals/metrics.py::compute_citation_metrics` (rewritten v0.1.18, commit `eebcbcc`; signature + return + dedup-first unchanged).
- Re-render script: `scripts/rerender_reports.py` (new v0.1.18, commit `8e24b22`).
- T3 pivot disclosure: `evals/harness.py:204-208` documents `--cache-only` caches judge layer only.
- Future paid validation: v0.1.20 paid bundle (when budget recharges).
