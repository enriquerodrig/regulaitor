# v0.1.21 — Auditor RHR quorum diagnostic ($0 cache mining)

**Date:** 2026-05-24
**Source:** v0.1.20 ARM A checkpoints ['20260523T084207Z-d3e40ca', '20260523T162518Z-cfb1089']
**Purpose:** Estimate the impact of v0.1.21 Tier 1 Auditor quorum>=2 semantics on v0.1.20 ARM A RHR cases.

## §22.22 honest methodology caveat (final whole-branch review C3)

Pre-v0.1.21 code only escalated to RHR via the partial branch (some Findings pass, some blocked); v0.1.21 ADDS a NEW escalation path from all-pass-Findings to RHR when n_invalid_citations >= 2. The diagnostic cannot detect this NEW escalation from cache because (a) the cache does not persist per-citation `AuditResult` AND (b) cannot detect the absence of the new escalation (pre-v0.1.21 cases by construction never produced RHR via per-citation aggregation; every cached RHR is from the partial branch). The 0/36 LOWER/UPPER bound therefore measures something DIFFERENT than spec D5 intended. The mechanical MARGINAL conclusion is correct (no flip detectable from cache) but the reasoning the script encodes is structurally faulty: the `would_pass_unambiguous` bucket assumes pre-v0.1.21 K=1 RHR cases were possible, but pre-v0.1.21 K=1 invalid -> BLOCK never RHR. v0.1.22 paid validation if pursued would measure the real new-escalation impact directly via fresh ARM runs under v0.1.21 Auditor.

## Verdict

- **Unambiguous flips (K=1 RHR cases)**: 0
- **Ambiguous potential flips (K>=2 RHR cases)**: 0..36
- **RHR-no-citations cases (Tier 2 territory, skipped)**: 2
- **Decision per spec D5**: MARGINAL: defer paid validation indefinitely; Tier 1's value is mostly Tier 2-mediated (cleaner format -> fewer false RHRs from format issues).

## Per-case detail

| case_id | actual_verdict | emitted_count | bucket |
|---|---|---:|---|
| chat-003 | requires_human_review | 3 | would_pass_ambiguous |
| chat-007 | requires_human_review | 5 | would_pass_ambiguous |
| chat-008 | requires_human_review | 6 | would_pass_ambiguous |
| chat-013 | requires_human_review | 2 | would_pass_ambiguous |
| chat-016 | requires_human_review | 4 | would_pass_ambiguous |
| chat-017 | requires_human_review | 3 | would_pass_ambiguous |
| chat-018 | requires_human_review | 6 | would_pass_ambiguous |
| chat-019 | requires_human_review | 3 | would_pass_ambiguous |
| chat-021 | requires_human_review | 4 | would_pass_ambiguous |
| chat-022 | requires_human_review | 2 | would_pass_ambiguous |
| chat-023 | requires_human_review | 3 | would_pass_ambiguous |
| chat-024 | requires_human_review | 0 | rhr_no_citations_skip |
| chat-025 | requires_human_review | 5 | would_pass_ambiguous |
| chat-026 | requires_human_review | 3 | would_pass_ambiguous |
| chat-029 | requires_human_review | 2 | would_pass_ambiguous |
| chat-030 | requires_human_review | 2 | would_pass_ambiguous |
| dora-001 | requires_human_review | 5 | would_pass_ambiguous |
| dora-002 | requires_human_review | 4 | would_pass_ambiguous |
| dora-004 | requires_human_review | 0 | rhr_no_citations_skip |
| industry-c3 | requires_human_review | 2 | would_pass_ambiguous |
| industry-c4 | requires_human_review | 5 | would_pass_ambiguous |
| industry-c5 | requires_human_review | 4 | would_pass_ambiguous |
| industry-c8 | requires_human_review | 2 | would_pass_ambiguous |
| industry-g1 | requires_human_review | 4 | would_pass_ambiguous |
| industry-g2 | requires_human_review | 4 | would_pass_ambiguous |
| industry-g4 | requires_human_review | 7 | would_pass_ambiguous |
| industry-gv1 | requires_human_review | 4 | would_pass_ambiguous |
| industry-gv3 | requires_human_review | 5 | would_pass_ambiguous |
| industry-gv5 | requires_human_review | 3 | would_pass_ambiguous |
| industry-v1 | requires_human_review | 2 | would_pass_ambiguous |
| industry-v3 | requires_human_review | 2 | would_pass_ambiguous |
| industry-v4 | requires_human_review | 3 | would_pass_ambiguous |
| industry-v5 | requires_human_review | 3 | would_pass_ambiguous |
| nis2-001 | requires_human_review | 4 | would_pass_ambiguous |
| nis2-002 | requires_human_review | 3 | would_pass_ambiguous |
| nis2-005 | requires_human_review | 5 | would_pass_ambiguous |
| xcorpus-001 | requires_human_review | 3 | would_pass_ambiguous |
| xcorpus-002 | requires_human_review | 2 | would_pass_ambiguous |

## References

- Spec D5: `docs/superpowers/specs/2026-05-24-v0.1.21-auditor-quorum-hard-constraints-design.md`
- ADR-0027 (v0.1.21 closure docs)
- v0.1.20 T6.5 root-cause diagnostic: `evals/reports/v0.1.20/rhr-root-cause-diagnostic.md`
