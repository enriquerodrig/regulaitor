# Comparison: v0.1.25-prod vs v0.1.22-prod baseline

**Run:** v0.1.25 probe + main (chat-001..030)
**Baseline:** v0.1.22-prod (H10 30-case cohort)
**Comparison date:** 2026-05-26
**Spec ref:** docs/superpowers/specs/v0.1.25-auditor-partial-routing-design.md
**Note:** Metrics computed with v0.1.24 O1 re-aggregation (acceptable_verdicts={block, RHR, pass} for 6 designated content-safety cases: chat-014/015/029/030 + nis2-006/dora-006)

## Metrics comparison (7-row bar table)

| Metric | v0.1.25-prod | v0.1.22-prod | Delta | Bar | Pass | Improved |
|---|---|---|---|---|---|---|
| faithfulness_mean | 0.71 | 0.72 | -0.01 | ≥0.65 | ✅ | ➖ |
| answer_relevancy_mean | 0.69 | 0.73 | -0.03 | ≥0.55 | ✅ | ➖ |
| context_precision_mean | 0.63 | 0.66 | -0.02 | ≥0.55 | ✅ | ➖ |
| citation_precision_mean | 0.27 | 0.28 | -0.00 | ≥0.25 | ✅ | ➖ |
| citation_recall_mean | 0.68 | 0.67 | +0.02 | ≥0.60 | ✅ | ✅ |
| verdict_match_rate | 0.73 | 0.40 | +0.33 | ≥0.35 | ✅ | ✅ |
| severity_match_rate | 0.40 | 0.40 | +0.00 | ≥0.35 | ✅ | ➖ |

## Per-metric narrative

- **faithfulness_mean:** 0.71 vs baseline 0.72 (-0.01) — bar 0.65 PASS; regression
- **answer_relevancy_mean:** 0.69 vs baseline 0.73 (-0.03) — bar 0.55 PASS; regression
- **context_precision_mean:** 0.63 vs baseline 0.66 (-0.02) — bar 0.55 PASS; regression
- **citation_precision_mean:** 0.27 vs baseline 0.28 (-0.00) — bar 0.25 PASS; flat
- **citation_recall_mean:** 0.68 vs baseline 0.67 (+0.02) — bar 0.60 PASS; improvement
- **verdict_match_rate:** 0.73 vs baseline 0.40 (+0.33) — bar 0.35 PASS; improvement
- **severity_match_rate:** 0.40 vs baseline 0.40 (+0.00) — bar 0.35 PASS; flat

## Aggregate verdict counts

v0.1.25-prod: pass=25 RHR=0 block=5

v0.1.22-prod: pass=10 RHR=16 block=4

## Summary

**7 / 7 metrics PASS bar in v0.1.25-prod**

## Note on per-citation audits

v0.1.25-prod has per-citation audit trail available per v0.1.21.1 D2 (evals/schemas.py::ChatCaseResult.per_citation_audits); T6 mechanism analysis runs on prod only.
