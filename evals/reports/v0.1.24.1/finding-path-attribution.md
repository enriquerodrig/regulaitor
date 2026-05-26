# v0.1.24.1 — Per-Finding Auditor Path Attribution

**Date**: 2026-05-26
**Methodology**: Cross-version comparison v0.1.22-prod vs v0.1.23-prod actual_verdict for 10 H1 cases
**Lineage**: v0.1.22.1 H1 diagnostic → v0.1.23 REVERT (0/10 flipped) → v0.1.24 O2 (H1.C=10/10) → THIS spec

## Cross-version comparison table

| case_id | v0.1.22-prod verdict | v0.1.23-prod verdict | Path |
|---|---|---|---|
| chat-016 | requires_human_review | block | C-ish (all-blocked OR API drift) |
| chat-017 | requires_human_review | block | C-ish (all-blocked OR API drift) |
| chat-018 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-019 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-021 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-022 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-023 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-024 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-025 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |
| chat-026 | requires_human_review | requires_human_review | B (Strict-Answer partial routing) |

## Aggregate counts

- A (Tier 1 firing) = 0/10 (0%)
- B (Strict-Answer partial routing) = 8/10 (80%)
- C-ish (all-blocked OR API drift) = 2/10 (20%)
- ambiguous = 0/10 (0%)
- ambiguous / unknown = 0/10

## HEADLINE

**Dominant path identified**: B (Strict-Answer partial routing) (8/10)

**v0.1.25 design recommendation**: Design H (Strict-Answer partial routing softening)

## §22.22 caveats

1. Cross-version inference confounded by Sonnet non-determinism (~20% noise floor per v0.1.23 §REVERT root cause #1)
2. Path C-ish ambiguity: cases that went RHR → BLOCK could be all-blocked routing change OR API drift; cannot definitively separate
3. Per-Finding citation grouping is LOST in cached AuditResults (post-Auditor aggregation); cross-version is the workaround
4. Recommendation accuracy depends on accurate v0.1.22.1 H1 attribution + accurate v0.1.24 O2 H1.C confirmation; both validated to date
5. v0.1.25+ Design selection still requires user judgment; this diagnostic narrows but doesn't fully determine
