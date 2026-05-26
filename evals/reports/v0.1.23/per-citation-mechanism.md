# v0.1.23 T6: Per-Citation Mechanism Diagnostic

**Date:** 2026-05-26T06:57:32.934007Z  **Method:** Cache-mining v0.1.21.1 D2 trail  **Cohort:** H10 chat-001..030 (30 cases)

## Methodology

Analyzes per-citation audit records from v0.1.23-prod checkpoint JSONL files (probe + main 25 cases) against the 5-bucket spec (Design B §D6):

- **Bucket A:** RHR + empty citations
- **Bucket B:** BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)
- **Bucket C:** RHR + ≥1 citation + ≥2 invalid citations (v0.1.21 STRICT-count escalation, subject to v0.1.23 lenient-quorum override)
- **Bucket D:** RHR + ≥1 citation + exactly 1 invalid citation (edge case)
- **Bucket E:** Other (non-RHR or data-incomplete)

## 5-Bucket Count Table

| Bucket | Count | Percentage |
|--------|-------|-----------|
| A | 0 | 0.0% |
| B | 6 | 20.0% |
| C | 10 | 33.3% |
| D | 4 | 13.3% |
| E | 10 | 33.3% |

## Headline Finding

**Bucket C (quorum-escalated RHR per STRICT counting): 10/30 (33.3% of cohort)**

The v0.1.21 Tier 1 quorum mechanism (n_invalid >= 2 → RHR) fires on this many case(s). v0.1.23 Design B introduces lenient-quorum override (article + apartado exists, text-match can fail) — expected to reduce this count by loosening the escalation threshold.

## Per-Case Listing by Bucket

### Bucket B

- **chat-015**: verdict=block, n_emitted=1, n_invalid=1
- **chat-016**: verdict=block, n_emitted=4, n_invalid=4
- **chat-017**: verdict=block, n_emitted=3, n_invalid=3
- **chat-020**: verdict=block, n_emitted=4, n_invalid=4
- **chat-027**: verdict=block, n_emitted=3, n_invalid=3
- **chat-028**: verdict=block, n_emitted=3, n_invalid=3

### Bucket C

- **chat-003**: verdict=requires_human_review, n_emitted=4, n_invalid=3
- **chat-008**: verdict=requires_human_review, n_emitted=6, n_invalid=2
- **chat-018**: verdict=requires_human_review, n_emitted=6, n_invalid=3
- **chat-019**: verdict=requires_human_review, n_emitted=3, n_invalid=3
- **chat-021**: verdict=requires_human_review, n_emitted=4, n_invalid=3
- **chat-022**: verdict=requires_human_review, n_emitted=3, n_invalid=3
- **chat-023**: verdict=requires_human_review, n_emitted=3, n_invalid=2
- **chat-024**: verdict=requires_human_review, n_emitted=3, n_invalid=6
- **chat-025**: verdict=requires_human_review, n_emitted=4, n_invalid=3
- **chat-026**: verdict=requires_human_review, n_emitted=3, n_invalid=2

### Bucket D

- **chat-005**: verdict=requires_human_review, n_emitted=4, n_invalid=1
- **chat-007**: verdict=requires_human_review, n_emitted=5, n_invalid=1
- **chat-010**: verdict=requires_human_review, n_emitted=2, n_invalid=1
- **chat-013**: verdict=requires_human_review, n_emitted=2, n_invalid=1

### Bucket E

- **chat-001**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-002**: verdict=pass, n_emitted=4, n_invalid=0
- **chat-004**: verdict=pass, n_emitted=4, n_invalid=0
- **chat-006**: verdict=pass, n_emitted=5, n_invalid=0
- **chat-009**: verdict=pass, n_emitted=4, n_invalid=0
- **chat-011**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-012**: verdict=pass, n_emitted=3, n_invalid=0
- **chat-014**: verdict=pass, n_emitted=1, n_invalid=0
- **chat-029**: verdict=pass, n_emitted=1, n_invalid=0
- **chat-030**: verdict=pass, n_emitted=1, n_invalid=0

## Caveats (§22.22)

### Lenient vs Strict Counting
This diagnostic counts n_invalid using the STRICT per_citation_audits.validated field (all 3 checks: article exists, apartado exists, text match). v0.1.23 Design B Tier 1 quorum counts lenient_invalid (Check 1+2 only, skips text-match Check 3). Diagnostic cannot separate text-only failures from Check 1/2 failures, so the per-bucket counts here are NOT the same as production lenient-quorum counts. Real impact of v0.1.23 Design B measured at T4 paid validation.

### Bucket D Edge Case
Bucket D (RHR + exactly 1 invalid) represents the boundary where pre-v0.1.21 would NOT escalate (only ≥1 invalid → BLOCK) but v0.1.21 Tier 1 quorum also does NOT escalate (needs ≥2). These are neither old nor new mechanism failures; they may represent other Auditor paths (e.g., Strict-Answer < n_valid).

### Per-Citation Audits Trail Limitations
The per_citation_audits field (v0.1.21.1 D2) records the final STRICT-validated state but does NOT capture whether a citation would be lenient-valid (article + apartado exist despite text mismatch). Precise audit of lenient-quorum impact requires re-applying the lenient validator logic post-hoc to cached per-citation data.
