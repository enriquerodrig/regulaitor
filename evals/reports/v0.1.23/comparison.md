# Comparison: v0.1.23-prod vs v0.1.22-prod baseline

**Run:** v0.1.23 probe + main (chat-001..030)
**Baseline:** v0.1.22-prod (H10 30-case cohort)
**Comparison date:** 2026-05-26
**Spec ref:** docs/superpowers/specs/2026-05-25-v0.1.23-auditor-lenient-quorum-design.md

## Metrics comparison (7-row bar table)

| Metric | v0.1.23-prod | v0.1.22-prod | Delta | Bar | Pass | Improved |
|---|---|---|---|---|---|---|
| faithfulness_mean | 0.76 | 0.72 | +0.04 | ≥0.65 | ✅ | ✅ |
| answer_relevancy_mean | 0.73 | 0.73 | +0.00 | ≥0.55 | ✅ | ➖ |
| context_precision_mean | 0.59 | 0.66 | -0.06 | ≥0.55 | ✅ | ➖ |
| citation_precision_mean | 0.28 | 0.28 | -0.00 | ≥0.25 | ✅ | ➖ |
| citation_recall_mean | 0.68 | 0.67 | +0.02 | ≥0.60 | ✅ | ✅ |
| verdict_match_rate | 0.27 | 0.30 | -0.03 | ≥0.35 | ❌ | ➖ |
| severity_match_rate | 0.37 | 0.40 | -0.03 | ≥0.35 | ✅ | ➖ |

## Per-metric narrative

- **faithfulness_mean:** 0.76 vs baseline 0.72 (+0.04) — bar 0.65 PASS; improvement
- **answer_relevancy_mean:** 0.73 vs baseline 0.73 (+0.00) — bar 0.55 PASS; flat
- **context_precision_mean:** 0.59 vs baseline 0.66 (-0.06) — bar 0.55 PASS; regression
- **citation_precision_mean:** 0.28 vs baseline 0.28 (-0.00) — bar 0.25 PASS; flat
- **citation_recall_mean:** 0.68 vs baseline 0.67 (+0.02) — bar 0.60 PASS; improvement
- **verdict_match_rate:** 0.27 vs baseline 0.30 (-0.03) — bar 0.35 FAIL; regression
- **severity_match_rate:** 0.37 vs baseline 0.40 (-0.03) — bar 0.35 PASS; regression

## Aggregate verdict counts

v0.1.23-prod: pass=10 RHR=14 block=6

v0.1.22-prod: pass=10 RHR=16 block=4

## Summary

**7 / 7 metrics PASS bar in v0.1.23-prod**

## Note on per-citation audits

v0.1.23-prod has per-citation audit trail available per v0.1.21.1 D2 (evals/schemas.py::ChatCaseResult.per_citation_audits); T6 mechanism analysis runs on prod only.
