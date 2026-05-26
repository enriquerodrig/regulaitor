# v0.1.23 T4: Verdict Flip Review (10 H1 Cases)

**Scope:** v0.1.22.1 H1-dominant cases (10 chat cases identified as validator-too-strict in cache-mining diagnostic)

**Prediction per Design B spec:** Design B loosens Tier 1 quorum counting (lenient = Check 1+2 only, skips text-match Check 3) → ~6-7 of 10 H1 cases should flip RHR→PASS.

**Actual outcome:** TBD per this diagnostic.

## Summary

- **Flipped RHR→PASS (as predicted):** 0/10
- **Unchanged RHR:** 8/10
- **Unexpected flips:** 2/10

**Prediction confirmation rate:** 0/10 (0% of predicted 6-7 ≈ 0%)

## Per-Case Detail

| Case | v0.1.22 | v0.1.23 | Outcome |
|---|---|---|---|
| chat-016 | requires_human_review | block | RHR→BLOCK (lenient loosening but Strict-Answer blocked) |
| chat-017 | requires_human_review | block | RHR→BLOCK (lenient loosening but Strict-Answer blocked) |
| chat-018 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-019 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-021 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-022 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-023 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-024 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-025 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |
| chat-026 | requires_human_review | requires_human_review | RHR unchanged (lenient didn't help) |

## Root Cause Analysis

❌ **Design B did not flip H1 cases as predicted**. 2 unexpected outcomes detected. Likely causes:
   1. **API drift**: Sonnet output non-deterministic across 2-day gap; same queries produced different citations → different validator outcomes.
   2. **Lenient-quorum assumptions invalid**: Even with lenient counting, other Auditor paths (Strict-Answer routing, Finding-Lenient aggregation) block the answer before quorum escalation.
   3. **Measurement artifact**: v0.1.22 RHR might not actually be from quorum escalation (n_invalid >= 2) but from other paths → lenient doesn't help.
