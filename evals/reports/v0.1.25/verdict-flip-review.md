# v0.1.25 T4: Verdict Flip Review (10 H1 Cases)

**Scope:** v0.1.22.1 H1-dominant cases (10 chat cases identified as validator-too-strict in cache-mining diagnostic)

**Prediction per Design H spec:** Design H softens Strict-Answer partial-routing (≥X% Findings pass despite 1+ invalid citations) → ~8-9 of 10 H1 cases should flip RHR→PASS.

**Actual outcome:** TBD per this diagnostic.

## Summary

- **Flipped RHR→PASS (as predicted):** 9/10
- **Unchanged RHR:** 0/10
- **Unexpected flips:** 1/10

**Prediction confirmation rate:** 9/10 (90% of predicted 8-9 ≈ 106%)

## Per-Case Detail

| Case | v0.1.22 | v0.1.25 | Outcome |
|---|---|---|---|
| chat-016 | requires_human_review | block | RHR→BLOCK (partial-routing but all-blocked) |
| chat-017 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-018 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-019 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-021 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-022 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-023 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-024 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-025 | requires_human_review | pass | RHR→PASS (as predicted) |
| chat-026 | requires_human_review | pass | RHR→PASS (as predicted) |

## Root Cause Analysis

✅ **Design H partial-routing loosening successful**: 9/10 H1 cases flipped RHR→PASS as predicted. The Strict-Answer partial-routing mechanism was the active bottleneck; softening it resolved most cases.
