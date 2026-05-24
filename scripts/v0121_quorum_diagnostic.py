"""v0.1.21 — Auditor RHR quorum diagnostic ($0 cache mining over v0.1.20 ARM A).

Loads v0.1.20 ARM A checkpoints (probe + main = 64 cases) from the JSONL files
in `evals/checkpoints/` and attempts to estimate the impact of the v0.1.21
Auditor quorum semantic on those v0.1.20 ARM A RHR cases.

§22.22 honest methodology caveat (final whole-branch review issue C3)
=====================================================================
**The classifier this script encodes is structurally faulty as a measurement
of v0.1.21 D1's actual impact.** The script's "would_pass_unambiguous"
bucket assumes that pre-v0.1.21 code could produce K=1 RHR cases — that is,
that a single per-citation invalid in a single-Finding answer would have
escalated the turn to RHR before v0.1.21. **This is incorrect**: pre-v0.1.21
code in `src/regulaitor/agents/auditor.py` only escalated to RHR via the
PARTIAL branch (some Findings pass + some blocked). A single invalid
citation in a single-Finding answer pre-v0.1.21 produced BLOCK (Lenient
cannot save the Finding when its only citation is invalid → Finding
blocked → all-blocked-Findings → turn BLOCK), NEVER RHR. So the empirical
"0 unambiguous flips" result is correct for the wrong reason: there were
0 K=1 RHR cases because pre-v0.1.21 code by construction never produced
them, NOT because v0.1.21's quorum aggregator doesn't change anything.

What v0.1.21 D1 actually adds is a NEW escalation path from the all-pass-
Findings branch when n_invalid_citations ≥ 2 (Lenient-Finding swallowed
≥2 invalid citations within passing Findings). The diagnostic CANNOT
detect this NEW escalation from cache because:
- (a) the cache does not persist per-citation `AuditResult` (only the
  aggregate `actual_verdict` + the article-level `citations.emitted` list);
- (b) cannot detect the absence of the new escalation either (pre-v0.1.21
  cases by construction never produced RHR via per-citation aggregation —
  every cached RHR is from the partial branch, NOT from any-RHR aggregation
  that v0.1.21 strengthens).

The 0/36 LOWER/UPPER bound therefore measures something DIFFERENT than
spec D5 intended. The mechanical MARGINAL conclusion (0 ≤ 5 threshold)
holds — there is no detectable flip from cache — but the reasoning the
script encodes is structurally faulty. v0.1.22 paid validation, if pursued,
would measure the real new-escalation impact directly via fresh ARM runs
under the v0.1.21 Auditor (where per-citation AuditResults are observed
live, not replayed from cache).

What this diagnostic still computes (with the above caveat):
- For each v0.1.20 ARM A case with verdict=RHR AND emitted_count>=1:
  - If emitted_count==1 -> classified as "would_pass_unambiguous" UNDER
    THE SCRIPT'S (FAULTY) MODEL. Real-world count: 0 (pre-v0.1.21 never
    produced K=1 RHR; expected count is structurally 0).
  - If emitted_count>=2 -> classified as "would_pass_ambiguous". The real
    v0.1.21 escalation could flip these RHR→PASS, RHR→RHR (unchanged via
    the partial branch), or trigger fresh PASS→RHR escalations via the
    NEW path that the script cannot detect from cache.
- Final classification per spec D5 decision criterion: based on the
  "would_pass_unambiguous" count alone (mechanically correct empty result
  via the faulty model).
  > 10 -> strong v0.1.22 recommend
  5-10 -> moderate
  ≤ 5 -> marginal

The cache-mining methodology cannot replay per-citation validation under
the new aggregator, AND cannot retroactively reconstruct what the new
escalation path would have produced from cached aggregate verdicts.

Spec lineage: D5 + §7 risk row "Diagnostic re-run gives misleading signal
(cache mining != real run); flip count is a LOWER bound." Final-review C3
documents the deeper structural reason: the classifier is correct for the
wrong reason because pre-v0.1.21 K=1 RHR cases are nil by construction.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evals.checkpoint import load_completed
from evals.schemas import ChatCaseResult, DocCaseResult

DEFAULT_CHECKPOINT_ROOT = Path("evals/checkpoints")
REPORT_PATH = Path("evals/reports/v0.1.21/quorum-diagnostic.md")

# v0.1.20 ARM A run IDs as committed to evals/checkpoints/ (see T0 step inventory).
# Empirical run IDs from `ls evals/checkpoints/` at v0.1.20 close — the
# diagnostic loads ALL of them and unions the case_ids; case_ids are unique
# across probe + main.
DEFAULT_ARM_A_RUN_IDS: tuple[str, ...] = (
    "20260523T084207Z-d3e40ca",  # ARM A probe
    "20260523T162518Z-cfb1089",  # ARM A main
)


@dataclass(frozen=True)
class CaseFlipClassification:
    case_id: str
    actual_verdict: str
    emitted_count: int
    bucket: Literal[
        "would_pass_unambiguous",  # single-citation RHR; quorum guarantees PASS
        "would_pass_ambiguous",  # multi-citation RHR; flip 0..emitted_count
        "not_rhr_skip",  # verdict != RHR
        "rhr_no_citations_skip",  # verdict==RHR + 0 emitted (Tier 2 territory)
    ]


def classify_case(case: ChatCaseResult | DocCaseResult) -> CaseFlipClassification:
    if isinstance(case, DocCaseResult):
        # Doc-mode cases use a different verdict field; skip in this diagnostic
        # (Tier 1 quorum semantics are chat-only in v0.1.21 scope per spec §6).
        return CaseFlipClassification(
            case_id=case.case_id,
            actual_verdict=case.actual_document_verdict,
            emitted_count=len(case.findings_citations.emitted),
            bucket="not_rhr_skip",
        )
    if case.actual_verdict != "requires_human_review":
        return CaseFlipClassification(
            case_id=case.case_id,
            actual_verdict=case.actual_verdict,
            emitted_count=len(case.citations.emitted),
            bucket="not_rhr_skip",
        )
    emitted_count = len(case.citations.emitted)
    if emitted_count == 0:
        return CaseFlipClassification(
            case_id=case.case_id,
            actual_verdict=case.actual_verdict,
            emitted_count=0,
            bucket="rhr_no_citations_skip",
        )
    if emitted_count == 1:
        return CaseFlipClassification(
            case_id=case.case_id,
            actual_verdict=case.actual_verdict,
            emitted_count=1,
            bucket="would_pass_unambiguous",
        )
    return CaseFlipClassification(
        case_id=case.case_id,
        actual_verdict=case.actual_verdict,
        emitted_count=emitted_count,
        bucket="would_pass_ambiguous",
    )


def classify_recommendation(unambiguous_flip_count: int) -> str:
    if unambiguous_flip_count > 10:
        return "STRONG: recommend v0.1.22 paid 30-case A/B."
    if unambiguous_flip_count >= 5:
        return "MODERATE: v0.1.22 paid A/B optional (cost/benefit judgment call)."
    return (
        "MARGINAL: defer paid validation indefinitely; Tier 1's value is mostly "
        "Tier 2-mediated (cleaner format -> fewer false RHRs from format issues)."
    )


def build_report_markdown(
    classifications: list[CaseFlipClassification],
    *,
    run_ids: tuple[str, ...],
) -> str:
    unambiguous_flips = [c for c in classifications if c.bucket == "would_pass_unambiguous"]
    ambiguous_flips = [c for c in classifications if c.bucket == "would_pass_ambiguous"]
    rhr_no_cites = [c for c in classifications if c.bucket == "rhr_no_citations_skip"]
    recommendation = classify_recommendation(len(unambiguous_flips))

    lines: list[str] = []
    lines.append("# v0.1.21 — Auditor RHR quorum diagnostic ($0 cache mining)")
    lines.append("")
    lines.append("**Date:** 2026-05-24")
    lines.append(f"**Source:** v0.1.20 ARM A checkpoints {list(run_ids)}")
    lines.append(
        "**Purpose:** Estimate the impact of v0.1.21 Tier 1 Auditor quorum>=2 "
        "semantics on v0.1.20 ARM A RHR cases."
    )
    lines.append("")
    lines.append("## §22.22 honest methodology caveat (final whole-branch review C3)")
    lines.append("")
    lines.append(
        "Pre-v0.1.21 code only escalated to RHR via the partial branch "
        "(some Findings pass, some blocked); v0.1.21 ADDS a NEW escalation "
        "path from all-pass-Findings to RHR when n_invalid_citations >= 2. "
        "The diagnostic cannot detect this NEW escalation from cache because "
        "(a) the cache does not persist per-citation `AuditResult` AND (b) "
        "cannot detect the absence of the new escalation (pre-v0.1.21 cases "
        "by construction never produced RHR via per-citation aggregation; "
        "every cached RHR is from the partial branch). The 0/36 LOWER/UPPER "
        "bound therefore measures something DIFFERENT than spec D5 intended. "
        "The mechanical MARGINAL conclusion is correct (no flip detectable "
        "from cache) but the reasoning the script encodes is structurally "
        "faulty: the `would_pass_unambiguous` bucket assumes pre-v0.1.21 K=1 "
        "RHR cases were possible, but pre-v0.1.21 K=1 invalid -> BLOCK never "
        "RHR. v0.1.22 paid validation if pursued would measure the real "
        "new-escalation impact directly via fresh ARM runs under v0.1.21 "
        "Auditor."
    )
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- **Unambiguous flips (K=1 RHR cases)**: {len(unambiguous_flips)}")
    lines.append(f"- **Ambiguous potential flips (K>=2 RHR cases)**: 0..{len(ambiguous_flips)}")
    lines.append(f"- **RHR-no-citations cases (Tier 2 territory, skipped)**: {len(rhr_no_cites)}")
    lines.append(f"- **Decision per spec D5**: {recommendation}")
    lines.append("")
    lines.append("## Per-case detail")
    lines.append("")
    lines.append("| case_id | actual_verdict | emitted_count | bucket |")
    lines.append("|---|---|---:|---|")
    for c in sorted(classifications, key=lambda x: x.case_id):
        if c.bucket == "not_rhr_skip":
            continue
        lines.append(f"| {c.case_id} | {c.actual_verdict} | {c.emitted_count} | {c.bucket} |")
    lines.append("")
    lines.append("## References")
    lines.append("")
    spec_ref = (
        "- Spec D5: `docs/superpowers/specs/"
        "2026-05-24-v0.1.21-auditor-quorum-hard-constraints-design.md`"
    )
    lines.append(spec_ref)
    lines.append("- ADR-0027 (v0.1.21 closure docs)")
    diag_ref = (
        "- v0.1.20 T6.5 root-cause diagnostic: "
        "`evals/reports/v0.1.20/rhr-root-cause-diagnostic.md`"
    )
    lines.append(diag_ref)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint-root",
        type=Path,
        default=DEFAULT_CHECKPOINT_ROOT,
        help="Directory containing v0.1.20 ARM A JSONL checkpoint files.",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=None,
        help="One or more run IDs to load (default: ARM A probe + main).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPORT_PATH,
        help="Output markdown report path.",
    )
    args = parser.parse_args()
    run_ids = tuple(args.run_id) if args.run_id else DEFAULT_ARM_A_RUN_IDS

    all_cases: list[ChatCaseResult | DocCaseResult] = []
    for run_id in run_ids:
        all_cases.extend(load_completed(run_id, root=args.checkpoint_root))

    classifications = [classify_case(c) for c in all_cases]
    report_md = build_report_markdown(classifications, run_ids=run_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report_md, encoding="utf-8")
    print(f"Diagnostic report written to: {args.out}")
    unambiguous = sum(1 for c in classifications if c.bucket == "would_pass_unambiguous")
    ambiguous = sum(1 for c in classifications if c.bucket == "would_pass_ambiguous")
    print(f"Unambiguous flips: {unambiguous}")
    print(f"Ambiguous potential flips: 0..{ambiguous}")
    print(f"Recommendation: {classify_recommendation(unambiguous)}")


if __name__ == "__main__":
    main()
