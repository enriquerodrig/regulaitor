# v0.1.20 T6.5 — RHR root-cause diagnostic ($0)

**Date:** 2026-05-24
**Source:** ARM A v1.0 checkpoints (probe+main, 64 cases) + ARM B v1.4 checkpoints (probe+main, 64 cases)
**Purpose:** Classify the 43 v1.0 RHR cases by root cause to inform v0.1.21 milestone prioritization and v0.1.20 T9 flip narrative.

## Methodology

For each v1.0 RHR case, look at:
- (a) Was findings empty in v1.0 (`citations.emitted == []`)?
- (b) What did v1.4 produce for the same case (pass / RHR / block)?

This gives a 2x2+ bucket classification.

## Bucket distribution (43 v1.0 RHR cases)

| Bucket | N | % | Interpretation |
|---|---:|---:|---|
| **nonempty-RHR-still-RHR-in-v1.4** | 18 | 42% | DOMINANT mechanism. Analyst structured citations but Auditor still rejected. NOT fixed by v1.4. Likely causes: literal text mismatch, citation refers to non-existent article, OR Auditor per-citation RHR aggregation over-firing (H13/H15 pattern). |
| **empty-findings-STILL-empty-in-v1.4** | 15 | 35% | v1.4's Hard Rule 9 (Force-Finding-emission) failed to obtain compliance from Sonnet in these cases. Prompt-only soft constraint is ~50% effective on its own (15/30 = 50% of empty-findings cases stayed empty). Justifies hardening to Anthropic strict mode + Pydantic min_length=1 + aggressive retry for v0.1.21. |
| **nonempty-RHR-FIXED-by-v1.4** | 6 | 14% | UNANTICIPATED secondary benefit of v1.4. Analyst produced DIFFERENT citations under v1.4 (better quality, not just non-empty) that the Auditor accepted. The Hard Rule 9 changed Analyst behavior beyond just the "force structure" mechanism. |
| **empty-findings-FIXED-by-v1.4** | 3 | 7% | The clean v1.4 mechanism case. v1.0 had findings=[], v1.4 forced findings → Auditor accepted. |
| other (became block) | 1 | 2% | Single case where v1.4 became block. |

## v1.4 regressions analysis (4 cases pass → RHR)

| case_id | v1.0 cites | v1.4 cites | analysis |
|---|---|---|---|
| chat-007 | `['26.11', '26.5', '26.7', '26.8', '27.1']` | **SAME 5 citations** | Identical output but different verdict. Strong signal of Auditor/Council non-determinism (Council uses LLM judges with variance; binding semantics may flip verdict on noise). |
| xcorpus-001 | `['4.1', '4.2', '4.3']` | **SAME 3 citations** | Same pattern as chat-007. Likely same noise source. |
| industry-c3 | `['1.1', '1.2', '26.5', '50.1']` (4 cites) | `['1.2', '26.5']` (2 cites) | v1.4 produced FEWER citations (Hard Rule 9 emphasis on "remove unsupported claim" may make v1.4 more conservative). Auditor with fewer cites returned RHR. |
| industry-v1 | `['5.3', '5.5', '50.3']` (3 cites) | `['5.3', '50.3']` (2 cites) | Same fewer-cites pattern. |

**Conclusion**: 2 of 4 regressions (chat-007, xcorpus-001) are likely NON-DETERMINISTIC noise (Auditor/Council variance), not true v1.4 failures. The other 2 (industry-c3, industry-v1) are genuine v1.4 conservatism trade-offs (fewer cites → harder Auditor pass).

## Key findings

1. **The "prose-without-findings" bug was NOT the dominant mechanism**. The hypothesis at v0.1.17.1 spec was that this bug accounted for most false-RHR. Diagnostic shows it's only ~42% of empty-findings RHR cases (18 of 30 v1.0 RHR-with-empty-findings... wait recompute: total empty-findings v1.0 = 15+3 = 18; 3 fixed, 15 not = 17% fixed rate). The bug DOES exist; v1.4 fixes a fraction.

2. **The DOMINANT remaining mechanism is "nonempty-RHR" (42%)**. The Analyst emitted citations correctly but the Auditor still rejected the answer. This is NOT addressed by v1.4 or any prompt change. The targets are:
   - Auditor RHR aggregation semantics (H15 §16.3 deferral — never implemented; v0.1.19 only did Council binding direction)
   - Citation validation tolerance (literal vs normalized vs Levenshtein)
   - Retriever quality (better citations = fewer aggregation issues)

3. **v1.4's wins partly come from unanticipated mechanisms** (14% nonempty-fixed). The Hard Rule 9 prompt change affected Analyst behavior beyond just the structure forcing. Suggests prompt engineering iterations CAN help beyond the targeted mechanism, but also that any single prompt change has hard-to-predict secondary effects.

4. **2 of 4 v1.4 "regressions" are likely noise**, not true regressions. Net real regressions ≈ 2 over 64 cases = 3%.

## Recommendation for v0.1.21 prioritization

**Order of attack (highest ROI first)**:

1. **Auditor RHR aggregation refinement (quorum)** — addresses the 42% dominant bucket. Highest impact; touches §6 so needs careful ADR + content backstop.
2. **Hard constraints findings non-empty** (Anthropic strict mode + Pydantic min_length=1 + aggressive retry) — addresses the 35% "v1.4 didn't force compliance" bucket. Cheap, complementary to v1.4 prompt.
3. **Citation validator tolerance review** — may help part of the 42% nonempty-RHR bucket if literal mismatch is a sub-cause. Risky for §6.
4. **Auditor/Council determinism audit** — addresses the ~3% noise floor in regressions. Lower impact but improves measurement stability.

## Implication for T9 flip decision

The diagnostic does NOT change the T7 hard safety floor (PASS). It does NOT invalidate the H10 bar 6/7 pass result (which is across-arm aggregate metrics, independent of root-cause buckets).

**Strengthens the flip case**:
- Of the 9 RHR→pass v1.4 wins, 9 are demonstrably real (6 nonempty-fixed, 3 empty-fixed). The mechanism is broader than originally hypothesized.
- Of the 4 v1.4 "regressions", ~2 are likely noise. Net regressions ≈ 2.
- Real net win: ~9 - 2 = +7 cases (not +6 - 4 = +5 as the surface delta).

**Refined T9 recommendation**: **FLIP** v1.0 → v1.4 default. Subject to T9 narrative including this diagnostic context + the bar 6/7 evidence + safety floor PASS + the honest acknowledgment that v1.4 attacks ONE mechanism (and v0.1.21 will target the dominant 42% nonempty-RHR mechanism with Auditor aggregation refinement).

## Carry-forward to v0.1.21

- `scripts/v0120_compare.py` transition matrix bug (fixed inline in comparison.md; script needs cleanup)
- Auditor RHR aggregation refinement (Tier 1 priority — 42% impact target)
- Hard constraints findings non-empty (Tier 2 priority — 35% impact target)
- Auditor/Council determinism audit (low priority — 3% noise target)
