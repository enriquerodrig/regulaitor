# v0.1.25 T6: Per-Citation Mechanism Diagnostic

**Date:** 2026-05-26T19:17:05.391735Z  **Method:** Cache-mining v0.1.21.1 D2 trail  **Cohort:** H10 chat-001..030 (30 cases)

## Methodology

Analyzes per-citation audit records from v0.1.25-prod checkpoint JSONL files (probe + main 30 cases) against the 5-bucket spec (Design H §D6):

- **Bucket A:** RHR + empty citations
- **Bucket B:** BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)
- **Bucket C:** RHR + ≥1 citation + ≥2 invalid citations (v0.1.21 STRICT-count escalation; v0.1.25 partial-routing should eliminate these)
- **Bucket D:** RHR + ≥1 citation + exactly 1 invalid citation (edge case)
- **Bucket E:** Other (non-RHR or data-incomplete)

## 5-Bucket Count Table

| Bucket | Count | Percentage |
|--------|-------|-----------|
| A | 0 | 0.0% |
| B | 5 | 16.7% |
| C | 0 | 0.0% |
| D | 0 | 0.0% |
| E | 25 | 83.3% |

## Headline Finding

**Bucket C (v0.1.21 quorum-escalated RHR per STRICT counting): 0/30 (0.0% of cohort)**

v0.1.21 Tier 1 quorum mechanism (n_invalid >= 2 → RHR) in v0.1.25-prod. v0.1.25 Design H partial-routing loosening should reduce both Bucket A+C RHR verdicts (0 RHR observed empirically vs 16 in v0.1.22 baseline).

## Per-Case Listing by Bucket

### Bucket B

- **chat-015**: verdict=block, n_emitted=1, n_invalid=1
- **chat-016**: verdict=block, n_emitted=3, n_invalid=3
- **chat-020**: verdict=block, n_emitted=4, n_invalid=4
- **chat-027**: verdict=block, n_emitted=4, n_invalid=4
- **chat-028**: verdict=block, n_emitted=3, n_invalid=3

### Bucket E

- **chat-001**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-002**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-003**: verdict=pass, n_emitted=4, n_invalid=3
- **chat-004**: verdict=pass, n_emitted=4, n_invalid=0
- **chat-005**: verdict=pass, n_emitted=4, n_invalid=1
- **chat-006**: verdict=pass, n_emitted=5, n_invalid=0
- **chat-007**: verdict=pass, n_emitted=5, n_invalid=1
- **chat-008**: verdict=pass, n_emitted=5, n_invalid=1
- **chat-009**: verdict=pass, n_emitted=5, n_invalid=0
- **chat-010**: verdict=pass, n_emitted=2, n_invalid=0
- **chat-011**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-012**: verdict=pass, n_emitted=4, n_invalid=0
- **chat-013**: verdict=pass, n_emitted=2, n_invalid=1
- **chat-014**: verdict=pass, n_emitted=1, n_invalid=0
- **chat-017**: verdict=pass, n_emitted=3, n_invalid=5
- **chat-018**: verdict=pass, n_emitted=6, n_invalid=3
- **chat-019**: verdict=pass, n_emitted=3, n_invalid=3
- **chat-021**: verdict=pass, n_emitted=3, n_invalid=2
- **chat-022**: verdict=pass, n_emitted=3, n_invalid=3
- **chat-023**: verdict=pass, n_emitted=3, n_invalid=2
- **chat-024**: verdict=pass, n_emitted=3, n_invalid=5
- **chat-025**: verdict=pass, n_emitted=5, n_invalid=4
- **chat-026**: verdict=pass, n_emitted=4, n_invalid=3
- **chat-029**: verdict=pass, n_emitted=1, n_invalid=0
- **chat-030**: verdict=pass, n_emitted=1, n_invalid=0

## Caveats (§22.22)

### Bucket Size Interpretation
v0.1.25 Design H partial-routing softening targets the Strict-Answer routing path (upstream of Tier 1 quorum) per v0.1.24.1 finding-path-diagnostic. Bucket C here counts strict-invalid citations; empirical RHR elimination to 0 suggests partial-routing + Tier 1 together are eliminating the RHR pathway.

### Per-Citation Audits Trail Limitations
The per_citation_audits field (v0.1.21.1 D2) records the final STRICT-validated state. Bucket D (n_invalid=1) cases may represent partial-routing pass-through (≥X% Findings pass despite 1 invalid citation) which the diagnostic cannot distinguish from other Auditor paths.
