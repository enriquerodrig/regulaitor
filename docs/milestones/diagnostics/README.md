# Archived diagnostic scripts (v0.1.20-v0.1.24)

One-shot diagnostic + paid-run scripts from the v0.1.20 → v0.1.24 milestone
window. Archived 2026-05-28 (Stage 3 pre-H16 polish) to declutter `scripts/`
while preserving the TFM evidence trail.

Per `CLAUDE.md` §22.4: files are **archived** (moved here) not deleted. Each
script was the canonical evidence for its milestone's paid run or diagnostic;
references in `docs/technical_decisions_log.md` §v0.1.20 → §v0.1.24 + the
corresponding ADRs (0026-0031) point at these files (paths updated post-move).

## Scripts retained in `scripts/`

The following are NOT archived because they remain operationally useful:

- `v0125_run.py` + `v0127_run.py` + `v0129_run.py` + `v0130_run.py` — paid-run
  runners (each is a near-identical copy with milestone-specific tag/dir;
  pattern reused for any future paid validation).
- `v0124_*` and earlier diagnostics that produced ONLY closure-deferred
  reports were archived since the reports themselves are the evidence; the
  scripts are reproducible via the squash commit + cache state at the time.

## Contents (16 scripts; 5604 LOC)

| Script | Milestone | Purpose |
|---|---|---|
| `v0120_run.py` | v0.1.20 | Paid A/B v1.0 vs v1.4 runner |
| `v0120_compare.py` | v0.1.20 | Transition matrix comparison (bug fixed at v0.1.21.1 D1) |
| `v0121_quorum_diagnostic.py` | v0.1.21 | $0 cache-mining Tier 1 quorum bounds |
| `v0122_run.py` | v0.1.22 | Paid cumulative-impact run |
| `v0122_extract_armb.py` | v0.1.22 | $0 ARM B cohort extraction from v0.1.20 |
| `v0122_comparison.py` | v0.1.22 | A/B comparison report |
| `v0122_mechanism_diagnostic.py` | v0.1.22 | 5-bucket per-citation mechanism |
| `v0122_1_verdict_diagnostic.py` | v0.1.22.1 | H1-H4 4-hypothesis classifier (789 LOC) |
| `v0123_run.py` | v0.1.23 | Paid Auditor lenient quorum Design B run |
| `v0123_comparison.py` | v0.1.23 | A/B comparison (lift refuted) |
| `v0123_mechanism_diagnostic.py` | v0.1.23 | 5-bucket diff |
| `v0123_merge_reports.py` | v0.1.23 | Probe + main merge helper |
| `v0123_verdict_flip_review.py` | v0.1.23 | 0/10 flip confirmation (REVERT trigger) |
| `v0124_re_aggregate.py` | v0.1.24 | O1 cached re-aggregation (+0.10 lift) |
| `v0124_decomposition_diagnostic.py` | v0.1.24 | O2 H1.A/B/C decomposition |
| `v0124_1_finding_path_diagnostic.py` | v0.1.24.1 | Path B Strict-Answer attribution |

All ADRs and reports referencing these scripts continue to work via the
new paths under `docs/milestones/diagnostics/`.
