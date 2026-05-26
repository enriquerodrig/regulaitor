# v0.1.24 — Decomposition diagnostic: failed_check re-attribution of v0.1.22.1 H1 cases

**Date:** 2026-05-26
**Script:** `scripts/v0124_decomposition_diagnostic.py`
**Methodology:** $0 re-derivation of `failed_check` (ADR-0031 D2) from cached v0.1.22.1 reason text. The cached AuditResults predate the schema field, so the per-citation reason strings serve as the source of truth for which check fired first.

Re-derivation map (per ADR-0031 D4 + script docstring):

| `reason` substring | failed_check | §6 character |
|---|---|---|
| `article_not_found` | 1 | true article fabrication |
| `apartado_not_found` | 2 | true apartado fabrication |
| `text_not_in_apartado` or `text_not_in_article` | 3 | paraphrase-only mismatch |
| (validated=True) | None | citation passed all checks |

## Per-case failed_check distribution (10 H1 cases from v0.1.22.1)

| case_id | n_invalid | Check 1 | Check 2 | Check 3 | dominant | re-attribution |
|---|---|---|---|---|---|---|
| chat-016 | 3 | 0 | 0 | 3 | Check 3 | H1.C |
| chat-017 | 4 | 0 | 0 | 4 | Check 3 | H1.C |
| chat-018 | 3 | 0 | 0 | 3 | Check 3 | H1.C |
| chat-019 | 4 | 0 | 0 | 4 | Check 3 | H1.C |
| chat-021 | 3 | 0 | 0 | 3 | Check 3 | H1.C |
| chat-022 | 4 | 0 | 0 | 4 | Check 3 | H1.C |
| chat-023 | 2 | 0 | 0 | 2 | Check 3 | H1.C |
| chat-024 | 4 | 0 | 0 | 4 | Check 3 | H1.C |
| chat-025 | 3 | 0 | 0 | 3 | Check 3 | H1.C |
| chat-026 | 2 | 0 | 0 | 2 | Check 3 | H1.C |

## Aggregate re-attribution counts

| Bucket | Count | Meaning |
|---|---|---|
| H1.A (Check 1 dominant) | 0 | article fabrication; aggregation-layer fix CANNOT help |
| H1.B (Check 2 dominant) | 0 | apartado fabrication; aggregation-layer fix CANNOT help |
| H1.C (Check 3 dominant) | 10 | paraphrase-only mismatch; aggregation-layer or eval-side fix CAN help |
| mixed (tied / no clear dominant) | 0 | manual review |
| **TOTAL H1 cases** | **10** | — |

## HEADLINE

Of the 10 H1-attributed cases in v0.1.22.1, **10 are H1.C** (paraphrase-only Check 3 dominant; the only sub-bucket where a lenient-quorum / Finding-Lenient softening / eval-side hierarchical-containment propagation could plausibly help) vs **0 H1.A/H1.B** (true Check 1/2 article-or-apartado fabrications; aggregation-layer intervention CANNOT help).

**Counter-intuitive read**: v0.1.22.1's H1 attribution was accurate at the Check 3 sub-bucket level — all 10/10 cases ARE paraphrase-only mismatches. The v0.1.23 REVERT post-mortem Hypothesis A (H1 over-counted via Check 1/2 conflation) is NOT supported by this decomposition — Check 1/2 over-count is 0. The verdict_match drop's underlying mechanism is therefore NOT Check 1/2 fabrication conflation; it is something else that survived v0.1.23 Design B's lenient-quorum intervention (per ADR-0030 §REVERT Hypotheses B and C — Finding-Lenient strict-text-match OR Strict-Answer partial-Findings routing upstream of the Tier 1 quorum).

## v0.1.25+ recommendation

**H1.C dominant** (≥7 of 10): paraphrase-only Check 3 mismatch is the universal pattern across the H1 cases. v0.1.23 Design B (Tier 1 quorum lenient counting) DID target this exact pattern at the quorum-count layer — yet 0/10 H1 cases flipped RHR → PASS at T6. This implies the verdict_match drop is NOT controlled by the Tier 1 quorum on Check 3 failures; some upstream Auditor path (Finding-Lenient strict-text-match OR Strict-Answer partial-Findings routing) rejects these citations before the Tier 1 quorum executes — see ADR-0030 §REVERT Hypotheses B and C. Candidate v0.1.25+ interventions: (a) Finding-Lenient softening to accept Check 3 lenient-valid citations (article + apartado exist, text mismatch) as Finding-pass — higher §6 risk than Design B but targets the layer that actually fires; (b) eval-side hierarchical containment propagation into the Auditor's per-citation acceptance (mirror of ADR-0024 at the production layer); (c) prompt-side anchor on copy-paste-from-context citations (lower risk; may underperform structural fixes); (d) the H1 cases routing through Strict-Answer partial-Findings (some Findings have Check 3 fails → blocked Findings → partial branch → RHR before Tier 1 quorum is even reached); a per-Finding instrumentation diagnostic should confirm before an intervention.

## §22.22 caveats

1. **Observability, not fix** (ADR-0031 §22.22 #2): this diagnostic does not change a single verdict. It enables v0.1.25+ targeted intervention selection at high confidence.
2. **Re-derivation heuristic** (ADR-0031 Option B alternative): the reason-text → failed_check mapping depends on validator's exact error-message strings; the current validator emits the three substrings literally (`article_not_found`, `apartado_not_found`, `text_not_in_{apartado|article}`). Future validator messaging changes would require updating this script's map. Going forward, the ADR-0031 D2 `failed_check` schema field populates the data natively — this script's reason-text re-derivation is the one-time bridge for pre-v0.1.24 cached data.
3. **Dominance tie-break**: 'mixed' covers (a) zero fails (validated trail) and (b) two checks with equal frequency. Per-case manual review is the next step for any 'mixed' case if it persists in v0.1.25+ measurements.
4. **H1 vs other buckets**: this diagnostic re-attributes the 10 H1 cases only. The 5 v0.1.22.1 mixed cases + 1 H4 case are NOT re-decomposed here; they are unchanged from the v0.1.22.1 report.
5. **Cached-data only**: the re-derivation reads the cached v0.1.22.1 markdown report directly; the validator is NOT re-invoked. This is intentional per ADR-0031 Option A rejection (cost-prohibitive AND non-deterministic re-validation).

## Reproducibility

```bash
uv run python scripts/v0124_decomposition_diagnostic.py
```

$0 cost. Outputs this file deterministically from the cached v0.1.22.1 report.
