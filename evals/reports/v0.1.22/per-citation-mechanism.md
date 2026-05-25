# v0.1.22 T5: Per-Citation Mechanism Diagnostic

**Date:** 2026-05-25T19:05:41.130352Z  **Method:** Cache-mining v0.1.21.1 D2 trail  **Cohort:** H10 chat-001..030 (30 cases)

## Methodology

Analyzes per-citation audit records from v0.1.22-prod checkpoint JSONL files (probe-4 + main 25 cases) against the 5-bucket spec (ADR-0027 §D6):

- **Bucket A:** RHR + empty citations (Capa A+B+C defense-in-depth escape)
- **Bucket B:** BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)
- **Bucket C:** RHR + ≥1 citation + ≥2 invalid citations (v0.1.21 NEW quorum)
- **Bucket D:** RHR + empty citations (prose-without-findings residual)
- **Bucket E:** Other (non-RHR or data-incomplete)

## 5-Bucket Count Table

| Bucket | Count | Percentage |
|--------|-------|------------|
| A | 0 | 0.0% |
| B | 4 | 13.3% |
| C | 11 | 36.7% |
| D | 0 | 0.0% |
| E | 15 | 50.0% |

## Headline Finding

**NEW v0.1.21 Tier 1 quorum-triggered RHR cases (Bucket C): 11/30 (36.7% of cohort)**

The NEW escalation mechanism from v0.1.21 (Auditor RHR when n_invalid ≥ 2) fired on 11 case(s), representing the lower bound of the v0.1.21 T6 diagnostic UPPER bound interval [0, 36] ambiguous K≥2 cases.

## Per-Case Listing by Bucket

### Bucket B

- **chat-015**: verdict=block, n_emitted=1, n_invalid=1
- **chat-020**: verdict=block, n_emitted=4, n_invalid=4
- **chat-027**: verdict=block, n_emitted=3, n_invalid=3
- **chat-028**: verdict=block, n_emitted=3, n_invalid=3

### Bucket C

- **chat-003**: verdict=requires_human_review, n_emitted=4, n_invalid=3
- **chat-016**: verdict=requires_human_review, n_emitted=3, n_invalid=3
- **chat-017**: verdict=requires_human_review, n_emitted=2, n_invalid=4
- **chat-018**: verdict=requires_human_review, n_emitted=6, n_invalid=3
- **chat-019**: verdict=requires_human_review, n_emitted=3, n_invalid=4
- **chat-021**: verdict=requires_human_review, n_emitted=4, n_invalid=3
- **chat-022**: verdict=requires_human_review, n_emitted=3, n_invalid=4
- **chat-023**: verdict=requires_human_review, n_emitted=3, n_invalid=2
- **chat-024**: verdict=requires_human_review, n_emitted=4, n_invalid=4
- **chat-025**: verdict=requires_human_review, n_emitted=4, n_invalid=3
- **chat-026**: verdict=requires_human_review, n_emitted=3, n_invalid=2

### Bucket E

- **chat-001**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-002**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-004**: verdict=pass, n_emitted=4, n_invalid=0
- **chat-005**: verdict=requires_human_review, n_emitted=4, n_invalid=1
- **chat-006**: verdict=pass, n_emitted=5, n_invalid=0
- **chat-007**: verdict=requires_human_review, n_emitted=5, n_invalid=1
- **chat-008**: verdict=requires_human_review, n_emitted=5, n_invalid=1
- **chat-009**: verdict=pass, n_emitted=5, n_invalid=0
- **chat-010**: verdict=pass, n_emitted=2, n_invalid=0
- **chat-011**: verdict=pass, n_emitted=2, n_invalid=0
- **chat-012**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-013**: verdict=requires_human_review, n_emitted=2, n_invalid=1
- **chat-014**: verdict=pass, n_emitted=1, n_invalid=0
- **chat-029**: verdict=pass, n_emitted=1, n_invalid=0
- **chat-030**: verdict=requires_human_review, n_emitted=2, n_invalid=1

## Caveats (§22.22)

### Bucket A/D Overlap
Buckets A and D both represent 'RHR + empty citations' and are logically identical. The distinction was intended to separate "Capa A+B+C escape" (bucket A) from "prose-without-findings residual" (bucket D per v0.1.17), but the per_citation_audits trail alone cannot distinguish them reliably. This diagnostic assigns both to bucket A; a more granular heuristic (inspecting Analyst answer.text field for substantive prose) would be required to separate them.

### Per-Citation Audits Trail Limitations
The per_citation_audits field (v0.1.21.1 D2) records the final validated state per citation but does NOT track: (a) how many Capa C retry attempts occurred before emitting each citation, (b) whether a citation was emitted on a later attempt vs. the first, or (c) whether Capa A/B rejection occurred silently before any citation was emitted. Thus, bucket A counts represent 'final state = no citations', not 'no citations ever attempted'.

### Pre-v0.1.21 Baseline Impossible
Cannot mine v0.1.20 ARM B (production pre-D2) checkpoints for a comparable diagnostic because per_citation_audits was not persisted before v0.1.21.1 D2. The v0.1.21 T6 diagnostic's lower bound (0 unambiguous flips) came from cache-only analysis; this v0.1.22 fresh data is independent.

### Cache-Mining ≠ Ground Truth
This analysis is a post-hoc observation of persisted cache state, not an instrumented measurement of live production behavior. The bucket categorization is deterministic and reproducible, but carries the observational limitations of any cache-mining study (e.g., cache staleness, schema evolution).
