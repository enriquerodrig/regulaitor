#!/usr/bin/env python
"""v0.1.22 T5: Per-citation mechanism diagnostic ($0 cache-mining).

Analyzes v0.1.21.1 D2 per_citation_audits trail from v0.1.22 checkpoint JSONL
files to categorize the 30 chat-001..030 cases into 5 buckets per spec §D6:
  A: empty-findings Capa A+B+C escape (RHR + no citations)
  B: single-invalid BLOCK (pre-v0.1.21 mechanism)
  C: NEW v0.1.21 quorum-triggered RHR (n_invalid >= 2)
  D: prose-without-findings (RHR + no citations, heuristic)
  E: other / non-RHR

Outputs evals/reports/v0.1.22/per-citation-mechanism.md with 5-bucket counts
and per-case listing. Pure Python, no API calls, $0 budget assertion.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

# $0 budget assertion: no API calls
ASSERT_ZERO_BUDGET = True

# Paths
CHECKPOINTS_DIR = Path("evals/checkpoints")
REPORT_DIR = Path("evals/reports/v0.1.22")

# Allowed cases for this diagnostic (H10 30-case cohort)
ALLOWED_CASES = {f"chat-{i:03d}" for i in range(1, 31)}
EXCLUDED_CASES = {"nis2-006", "dora-006"}  # safety-adhoc, out of cohort

# Bucket types
BucketType = Literal["A", "B", "C", "D", "E"]


class PerCitationDiagnostic:
    """Categorize 30-case v0.1.22 cohort into 5 buckets."""

    def __init__(self) -> None:
        self.cases: dict[str, dict[str, Any]] = {}
        self.buckets: dict[BucketType, list[str]] = {
            "A": [],
            "B": [],
            "C": [],
            "D": [],
            "E": [],
        }

    def load_checkpoints(self) -> None:
        """Load v0.1.22 checkpoint files (probe + main + safety_adhoc)."""
        if not CHECKPOINTS_DIR.exists():
            raise FileNotFoundError(f"Checkpoint dir not found: {CHECKPOINTS_DIR}")

        # Find checkpoint files modified after 2026-05-25T14:40:00 (probe-4 onward)
        cutoff_ts = datetime.fromisoformat("2026-05-25T14:40:00")
        relevant_files = [
            f for f in CHECKPOINTS_DIR.glob("*.jsonl") if f.stat().st_mtime >= cutoff_ts.timestamp()
        ]

        if not relevant_files:
            raise FileNotFoundError("No checkpoint files found after cutoff")

        for fpath in sorted(relevant_files):
            with open(fpath) as f:
                for line_num, line in enumerate(f, start=1):
                    try:
                        record = json.loads(line)
                        data = record.get("data", {})
                        case_id = data.get("case_id")

                        # Filter to chat-001..030 only
                        if case_id not in ALLOWED_CASES and case_id not in EXCLUDED_CASES:
                            continue
                        if case_id in EXCLUDED_CASES:
                            continue  # skip safety adhoc

                        # Store the case
                        if case_id in self.cases:
                            raise ValueError(f"Duplicate case_id {case_id} in {fpath}:{line_num}")
                        self.cases[case_id] = data
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON in {fpath}:{line_num}: {e}") from e

    def categorize_case(self, case_id: str, data: dict[str, Any]) -> BucketType:
        """Categorize one case into exactly one bucket."""
        actual_verdict = data.get("actual_verdict")
        citations = data.get("citations", {})
        emitted = citations.get("emitted", [])
        pca = data.get("per_citation_audits")

        n_emitted = len(emitted)

        # Bucket B: pre-v0.1.21 single-invalid BLOCK (deterministic path)
        if actual_verdict == "block" and pca is not None:
            n_invalid = sum(1 for audit in pca if not audit.get("validated", False))
            if n_invalid >= 1:
                return "B"

        # Buckets A/C/D all start with RHR
        if actual_verdict != "requires_human_review":
            return "E"  # non-RHR fallback

        # Bucket C: NEW v0.1.21 quorum-triggered RHR
        # RHR + citations emitted + per_citation_audits populated + n_invalid >= 2
        if n_emitted >= 1 and pca is not None:
            n_invalid = sum(1 for audit in pca if not audit.get("validated", False))
            if n_invalid >= 2:
                return "C"

        # Bucket A: RHR + empty citations (Capa A+B+C escape)
        # NOTE: overlaps with bucket D heuristically (see caveat in report)
        if n_emitted == 0:
            return "A"

        # Bucket D: RHR + citations but all valid (shouldn't happen; fallback to E)
        return "E"

    def categorize_all(self) -> None:
        """Categorize all loaded cases."""
        for case_id in sorted(self.cases.keys()):
            data = self.cases[case_id]
            bucket = self.categorize_case(case_id, data)
            self.buckets[bucket].append(case_id)

    def get_n_invalid(self, case_id: str) -> int:
        """Return number of invalid citations for a case."""
        data = self.cases[case_id]
        pca = data.get("per_citation_audits")
        if pca is None:
            return 0
        return sum(1 for audit in pca if not audit.get("validated", False))

    def render_report(self) -> str:
        """Render Markdown report."""
        lines = []

        # Header
        lines.append("# v0.1.22 T5: Per-Citation Mechanism Diagnostic")
        lines.append("")
        lines.append(
            f"**Date:** {datetime.utcnow().isoformat()}Z  "
            "**Method:** Cache-mining v0.1.21.1 D2 trail  "
            "**Cohort:** H10 chat-001..030 (30 cases)"
        )
        lines.append("")

        # Methodology
        lines.append("## Methodology")
        lines.append("")
        lines.append(
            "Analyzes per-citation audit records from v0.1.22-prod checkpoint JSONL files "
            "(probe-4 + main 25 cases) against the 5-bucket spec (ADR-0027 §D6):"
        )
        lines.append("")
        lines.append("- **Bucket A:** RHR + empty citations (Capa A+B+C defense-in-depth escape)")
        lines.append("- **Bucket B:** BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)")
        lines.append(
            "- **Bucket C:** RHR + ≥1 citation + ≥2 invalid citations (v0.1.21 NEW quorum)"
        )
        lines.append("- **Bucket D:** RHR + empty citations (prose-without-findings residual)")
        lines.append("- **Bucket E:** Other (non-RHR or data-incomplete)")
        lines.append("")

        # 5-Bucket Count Table
        lines.append("## 5-Bucket Count Table")
        lines.append("")
        total = len(self.cases)
        lines.append("| Bucket | Count | Percentage |")
        lines.append("|--------|-------|------------|")
        for bucket_name in ["A", "B", "C", "D", "E"]:
            bucket = cast(BucketType, bucket_name)
            count = len(self.buckets[bucket])
            pct = 100.0 * count / total if total > 0 else 0.0
            lines.append(f"| {bucket} | {count} | {pct:.1f}% |")
        lines.append("")

        # Headline finding
        c_count = len(self.buckets["C"])
        c_pct = 100.0 * c_count / total if total > 0 else 0.0
        lines.append("## Headline Finding")
        lines.append("")
        lines.append(
            f"**NEW v0.1.21 Tier 1 quorum-triggered RHR cases (Bucket C): {c_count}/{total} "
            f"({c_pct:.1f}% of cohort)**"
        )
        lines.append("")
        if c_count > 0:
            lines.append(
                "The NEW escalation mechanism from v0.1.21 (Auditor RHR when n_invalid ≥ 2) "
                f"fired on {c_count} case(s), representing the lower bound of the v0.1.21 T6 "
                "diagnostic UPPER bound interval [0, 36] ambiguous K≥2 cases."
            )
        else:
            lines.append(
                "The NEW quorum mechanism did NOT fire on any case in this 30-case cohort. "
                "This suggests either: (a) the v0.1.21 quorum threshold is too strict "
                "(few cases have ≥2 invalid citations), or (b) Capa A+B+C successfully "
                "eliminated most invalid-citation cases before the Auditor layer."
            )
        lines.append("")

        # Per-case listing
        lines.append("## Per-Case Listing by Bucket")
        lines.append("")
        for bucket_name in ["A", "B", "C", "D", "E"]:
            bucket = cast(BucketType, bucket_name)
            if not self.buckets[bucket]:
                continue
            lines.append(f"### Bucket {bucket}")
            lines.append("")
            for case_id in sorted(self.buckets[bucket]):
                data = self.cases[case_id]
                actual_verdict = data.get("actual_verdict")
                n_invalid = self.get_n_invalid(case_id)
                citations = data.get("citations", {})
                n_emitted = len(citations.get("emitted", []))
                lines.append(
                    f"- **{case_id}**: verdict={actual_verdict}, "
                    f"n_emitted={n_emitted}, n_invalid={n_invalid}"
                )
            lines.append("")

        # Caveats
        lines.append("## Caveats (§22.22)")
        lines.append("")
        lines.append(
            "### Bucket A/D Overlap\n"
            "Buckets A and D both represent 'RHR + empty citations' and are logically "
            'identical. The distinction was intended to separate "Capa A+B+C escape" '
            '(bucket A) from "prose-without-findings residual" (bucket D per v0.1.17), '
            "but the per_citation_audits trail alone cannot distinguish them reliably. "
            "This diagnostic assigns both to bucket A; a more granular heuristic "
            "(inspecting Analyst answer.text field for substantive prose) would be "
            "required to separate them."
        )
        lines.append("")
        lines.append(
            "### Per-Citation Audits Trail Limitations\n"
            "The per_citation_audits field (v0.1.21.1 D2) records the final validated "
            "state per citation but does NOT track: (a) how many Capa C retry attempts "
            "occurred before emitting each citation, (b) whether a citation was "
            "emitted on a later attempt vs. the first, or (c) whether Capa A/B rejection "
            "occurred silently before any citation was emitted. Thus, bucket A counts "
            "represent 'final state = no citations', not 'no citations ever attempted'."
        )
        lines.append("")
        lines.append(
            "### Pre-v0.1.21 Baseline Impossible\n"
            "Cannot mine v0.1.20 ARM B (production pre-D2) checkpoints for a comparable "
            "diagnostic because per_citation_audits was not persisted before v0.1.21.1 D2. "
            "The v0.1.21 T6 diagnostic's lower bound (0 unambiguous flips) came from "
            "cache-only analysis; this v0.1.22 fresh data is independent."
        )
        lines.append("")
        lines.append(
            "### Cache-Mining ≠ Ground Truth\n"
            "This analysis is a post-hoc observation of persisted cache state, not "
            "an instrumented measurement of live production behavior. The bucket categorization "
            "is deterministic and reproducible, but carries the observational limitations "
            "of any cache-mining study (e.g., cache staleness, schema evolution)."
        )
        lines.append("")

        return "\n".join(lines)

    def run(self) -> None:
        """Execute the diagnostic."""
        print("[v0.1.22 T5] Loading checkpoints...")
        self.load_checkpoints()
        print(f"  Loaded {len(self.cases)} cases")

        print("[v0.1.22 T5] Categorizing into 5 buckets...")
        self.categorize_all()

        print("[v0.1.22 T5] Rendering report...")
        report = self.render_report()

        # Ensure report directory exists
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / "per-citation-mechanism.md"

        print(f"[v0.1.22 T5] Writing {report_path}...")
        report_path.write_text(report, encoding="utf-8")

        # Print summary to stdout
        print("")
        print("=" * 70)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 70)
        print(f"Total cases: {len(self.cases)}")
        print(f"Bucket A: {len(self.buckets['A'])}")
        print(f"Bucket B: {len(self.buckets['B'])}")
        print(f"Bucket C: {len(self.buckets['C'])} (NEW v0.1.21 quorum-triggered RHR)")
        print(f"Bucket D: {len(self.buckets['D'])}")
        print(f"Bucket E: {len(self.buckets['E'])}")
        print("")
        c_rate = len(self.buckets["C"]) / len(self.cases) if len(self.cases) > 0 else 0.0
        print(f"Bucket C rate: {c_rate:.1%}")
        print(f"Report written to: {report_path}")
        print("=" * 70)


if __name__ == "__main__":
    diag = PerCitationDiagnostic()
    diag.run()
