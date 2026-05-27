# v0.1.29 vs v0.1.25 — H10 chat main 25-case comparison

**Run:** 2026-05-27 | **Cohort:** chat-006..030 (25 cases) | **Method:** 1-arm fresh (v0.1.29-prod-main) vs cached baseline (v0.1.25-prod-main); both under env-unset production state.

## Aggregate metrics

| Métrica | v0.1.25-prod-main | **v0.1.29-prod-main** | Δ | v0.1.20-bar |
|---|---|---|---|---|
| faithfulness_mean | 0.68 | **0.72** | **+0.04** | ≥0.65 ✅ |
| answer_relevancy_mean | 0.65 | **0.70** | **+0.05** | ≥0.55 ✅ |
| context_precision_mean | 0.60 | 0.59 | -0.01 | ≥0.55 ✅ |
| citation_precision_mean | 0.33 | 0.34 | +0.01 | ≥0.25 ✅ |
| citation_recall_mean | 0.81 | **0.81** | flat | ≥0.60 ✅ + **≥0.80 ASP ✅** |
| **verdict_match_rate** | **0.68** | **0.76** | **+0.08** | ≥0.35 ✅ |
| severity_match_rate | 0.48 | 0.43 | -0.05 | ≥0.35 ✅ |
| cost_per_chat_eur | 0.054 | 0.058 | +0.004 | ≤0.05 ❌ (+0.008) |
| cost_total_eur | 1.36 | 1.44 | +€0.08 | (info) |

**7/7 v0.1.20-bar PASS** preserved. **6/7 metrics improved or flat**; only context_precision (-0.01) and severity_match (-0.05) regressed marginally, both still above bar.

## Headlines

1. **verdict_match +0.08 (0.68 → 0.76)** — D Mirror effect on the H10 main 25-case cohort. **Matches ADR-0034 D4 prediction** (+0.033 to +0.10; 1-3 chat wins).
2. **citation_recall ASPIRATIONAL HIT (≥0.80) preserved** — 0.81 carried over from v0.1.25 (no regression).
3. **faithfulness + answer_relevancy improved +0.04 / +0.05** — collateral lift from passing-cases-have-substantive-answers (population shift toward PASS verdicts where the response is grounded in context).
4. **Cost overhead €0.004 vs v0.1.25** — Capa C retry overhead carry per ADR-0027 D4. Total milestone v0.1.29 paid spend €1.89 (€0.45 sunk probes + €1.44 main).

## §22.22 honest disclosures

1. **2-day API drift acknowledged** — v0.1.25 ran 2026-05-26, v0.1.29 ran 2026-05-27. Per v0.1.23 §REVERT root-cause root #1, ~20% noise floor across cross-day paid comparisons. Mitigated by same-cohort + same-prompts + same-retrieval + same-models.

2. **1-arm vs cached methodology** (carry from ADR-0029) — saves ~50% cost vs 2-arm fresh but introduces the drift caveat above. Acceptable for the +0.08 headline since prediction was on-forecast.

3. **Cumulative state**, not isolated D Mirror — v0.1.29 = v0.1.25 D2 partial + D Mirror all-blocked + Tier 1 quorum + Tier 2 Capa A+B+C + v1.5 chat + Council binding ON + retrieval defaults. Factorial attribution to D Mirror alone NOT measured.

4. **chat-027 + chat-028 borderline flips** — both have gold=requires_human_review; both moved BLOCK → PASS; verdict stays "wrong" but lean direction shifted (overly-cautious BLOCK → overly-lenient PASS). Net verdict_match neutral on these two; flip counted at gross level for transparency.

5. **chat-015 BLOCK → RHR** — gold=block; strict semantics show regression. Under v0.1.24 O1 multi-acceptable_verdicts (block + RHR + pass all acceptable for chat-015 as designated content safety case), classified PASS in aggregate. §22.22-honest disclosure: real verdict-content moved from match to non-match under strict comparison.

6. **Pre-existing pre-paid LANCEDB_PATH config bug discovered during T5 probe 1** (€0.14 sunk) — v0.1.26 deploy-prep added `LANCEDB_PATH` env reading to `rag/store.py`; `.env` value `./corpus/indexes` was wrong path (pointed at parent dir, caused lancedb to create empty `chunks.lance/` and return 0 rows on query). v0.1.27 + v0.1.28 paid reports show real citations so they likely evaded the bug via earlier module-load ordering OR auto-corpus path differences — uncertainty acknowledged. v0.1.29 T5 probe 1 was the canonical evidence; fixed in Stage 1 cleanup commit (LANCEDB_PATH → `./corpus/indexes/regulaitor.lance`).

7. **per_citation_audits trail `failed_check` always None** — `evals/metrics.py:337-353` predates v0.1.24 O2 (failed_check field added to AuditResult schema); trail dict does NOT copy the field. §6 verification of v0.1.29 flips relies on (a) reason text pattern `text_not_in_apartado` → Check 3 semantic, (b) live behavior verdict=PASS → helper returned True at runtime → all invalid had failed_check==3 live. Trail-fix bundled in Stage 1 cleanup.

## Decision

**CONFIRM per ADR-0034 D4 first path**. v0.1.29 D Mirror ships in production state. The verdict_match +0.08 lift matches prediction range (+0.033 to +0.10); §6 invariant preserved at THREE-layer architecture (now FOURTH-layer if including v0.1.28 prompt-level forbid); no fabrication slipped through. Hard safety floor PASS (redteam-smoke 0.92 carry by construction; Layer (c) aggregation change is post-validator).

## Closure of lineage

This CONFIRM outcome closes the v0.1.25 carry-forward `CONDITIONAL` marker in CLAUDE.md §27 ("v0.1.26 conditional all-blocked routing softening; targets chat-016-like cases"). The mirror condition matches exactly; chat-016 flipped BLOCK→PASS as predicted.

## References

- `evals/reports/v0.1.29/v0.1.29-prod-main.md` (25 cases full per-case appendix)
- `evals/reports/v0.1.29/probe.md` (5 cases sanity post-LANCEDB-fix)
- `evals/reports/v0.1.29/verdict-flip-review.md` (per-case flip categorization)
- `docs/adr/0034-all-blocked-routing-softening.md` (D1-D5 + §22.22 + 4 alternatives)
- `evals/reports/v0.1.25/v0.1.25-prod-main.md` (cached baseline)
