# Comparison: v0.1.22-prod vs v0.1.20 ARM B baseline

**Run:** v0.1.22 probe + main (chat-001..030)
**Baseline:** v0.1.20 ARM B (H10 30-case cohort)
**Comparison date:** 2026-05-25
**Spec ref:** docs/superpowers/specs/2026-05-24-v0.1.22-paid-validation-design.md

## Metrics comparison (7-row bar table)

| Metric | v0.1.22-prod | ARM B v0.1.20 | Delta | Bar | Pass | Improved |
|---|---|---|---|---|---|---|
| faithfulness_mean | 0.71 | 0.76 | -0.05 | ≥0.65 | ✅ | ➖ |
| answer_relevancy_mean | 0.74 | 0.60 | +0.14 | ≥0.55 | ✅ | ✅ |
| context_precision_mean | 0.78 | 0.67 | +0.11 | ≥0.55 | ✅ | ✅ |
| citation_precision_mean | 0.21 | 0.29 | -0.08 | ≥0.25 | ❌ | ➖ |
| citation_recall_mean | 0.55 | 0.64 | -0.09 | ≥0.60 | ❌ | ➖ |
| verdict_match_rate | 0.30 | 0.30 | +0.00 | ≥0.35 | ❌ | ➖ |
| severity_match_rate | 0.40 | 0.33 | +0.07 | ≥0.35 | ✅ | ✅ |

## Per-metric narrative

- **faithfulness_mean:** 0.71 vs baseline 0.76 (-0.05) — bar 0.65 PASS; regression
- **answer_relevancy_mean:** 0.74 vs baseline 0.60 (+0.14) — bar 0.55 PASS; improvement
- **context_precision_mean:** 0.78 vs baseline 0.67 (+0.11) — bar 0.55 PASS; improvement
- **citation_precision_mean:** 0.21 vs baseline 0.29 (-0.08) — bar 0.25 FAIL; regression
- **citation_recall_mean:** 0.55 vs baseline 0.64 (-0.09) — bar 0.60 FAIL; regression
- **verdict_match_rate:** 0.30 vs baseline 0.30 (+0.00) — bar 0.35 FAIL; no change
- **severity_match_rate:** 0.40 vs baseline 0.33 (+0.07) — bar 0.35 PASS; improvement

## Aggregate verdict counts

v0.1.22-prod: pass=10 RHR=16 block=4

## Summary

**4/7 metrics PASS bar in v0.1.22-prod**
**3/7 metrics beat v0.1.20-ARM-B baseline**

## Note on per-citation audits

v0.1.22-prod has per-citation audit trail available per v0.1.21.1 D2 (evals/schemas.py::ChatCaseResult.per_citation_audits); v0.1.20-ARM-B has no trail (pre-D2) — T5 mechanism analysis (if pursued) runs on prod only.
