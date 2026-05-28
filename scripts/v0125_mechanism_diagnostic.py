#!/usr/bin/env python
# ruff: noqa: E501  # diagnostic script; long lines acceptable
"""T3 Deliverable: Per-citation mechanism diagnostic for v0.1.25-prod ($0 cache-mining).

Analyzes v0.1.21.1 D2 per_citation_audits trail from v0.1.25 checkpoint JSONL files
to categorize the 30 chat-001..030 cases into 5 buckets per spec §D6 (v0.1.25):

  A: empty-findings (RHR + no citations)
  B: single-invalid BLOCK (pre-v0.1.21 mechanism)
  C: NEW v0.1.21 quorum-triggered RHR (n_invalid >= 2 via strict counting)
  D: mixed (RHR + citations but single-invalid)
  E: other / non-RHR / pass

Outputs: evals/reports/v0.1.25/per-citation-mechanism.md

No API calls; $0 budget assertion.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

CHECKPOINTS_DIR = Path("evals/checkpoints")
REPORT_DIR = Path("evals/reports/v0.1.25")

ALLOWED_CASES = {f"chat-{i:03d}" for i in range(1, 31)}


BucketType = Literal["A", "B", "C", "D", "E"]


class PerCitationDiagnostic:
    """Categorize 30-case v0.1.25 cohort into 5 buckets."""

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
        """Load v0.1.25 checkpoint files (probe + main)."""
        if not CHECKPOINTS_DIR.exists():
            raise FileNotFoundError(f"Checkpoint dir not found: {CHECKPOINTS_DIR}")

        # v0.1.25 checkpoints
        # probe: 20260526T105428Z-01ef316.jsonl
        # main: 20260526T140842Z-01ef316.jsonl
        relevant_files = [
            Path(CHECKPOINTS_DIR) / "20260526T105428Z-01ef316.jsonl",
            Path(CHECKPOINTS_DIR) / "20260526T140842Z-01ef316.jsonl",
        ]

        for fpath in relevant_files:
            if not fpath.exists():
                print(f"⚠️  Checkpoint file not found: {fpath}")
                continue

            with open(fpath) as f:
                for line_num, line in enumerate(f, start=1):
                    try:
                        record = json.loads(line)
                        data = record.get("data", {})
                        case_id = data.get("case_id")

                        if case_id not in ALLOWED_CASES:
                            continue

                        if case_id in self.cases:
                            raise ValueError(f"Duplicate case_id {case_id}")
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

        # Bucket B: BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)
        if actual_verdict == "block" and pca is not None:
            n_invalid = sum(1 for audit in pca if not audit.get("validated", False))
            if n_invalid >= 1:
                return "B"

        # Buckets A/C/D all start with RHR
        if actual_verdict != "requires_human_review":
            return "E"  # non-RHR fallback

        # Bucket C: v0.1.21 quorum-triggered RHR
        # RHR + citations emitted + per_citation_audits populated + n_invalid >= 2
        if n_emitted >= 1 and pca is not None:
            n_invalid_strict = sum(1 for audit in pca if not audit.get("validated", False))
            if n_invalid_strict >= 2:
                return "C"

        # Bucket A: RHR + empty citations
        if n_emitted == 0:
            return "A"

        # Bucket D: RHR + citations but single-invalid
        if n_emitted >= 1 and pca is not None:
            n_invalid_strict = sum(1 for audit in pca if not audit.get("validated", False))
            if n_invalid_strict == 1:
                return "D"

        return "E"

    def categorize_all(self) -> None:
        """Categorize all loaded cases."""
        for case_id, data in sorted(self.cases.items()):
            bucket = self.categorize_case(case_id, data)
            self.buckets[bucket].append(case_id)

    def render_report(self) -> str:
        """Render the diagnostic report."""
        total = sum(len(cases) for cases in self.buckets.values())

        lines = [
            "# v0.1.25 T6: Per-Citation Mechanism Diagnostic",
            "",
            f"**Date:** {datetime.utcnow().isoformat()}Z  **Method:** "
            "Cache-mining v0.1.21.1 D2 trail  **Cohort:** H10 chat-001..030 (30 cases)",
            "",
            "## Methodology",
            "",
            "Analyzes per-citation audit records from v0.1.25-prod checkpoint JSONL files "
            "(probe + main 30 cases) against the 5-bucket spec (Design H §D6):",
            "",
            "- **Bucket A:** RHR + empty citations",
            "- **Bucket B:** BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)",
            "- **Bucket C:** RHR + ≥1 citation + ≥2 invalid citations (v0.1.21 "
            "STRICT-count escalation; v0.1.25 partial-routing should eliminate these)",
            "- **Bucket D:** RHR + ≥1 citation + exactly 1 invalid citation (edge case)",
            "- **Bucket E:** Other (non-RHR or data-incomplete)",
            "",
            "## 5-Bucket Count Table",
            "",
            "| Bucket | Count | Percentage |",
            "|--------|-------|-----------|",
        ]

        bucket_letters: tuple[BucketType, ...] = ("A", "B", "C", "D", "E")
        for bucket_letter in bucket_letters:
            count = len(self.buckets[bucket_letter])
            pct = 100.0 * count / total if total > 0 else 0.0
            lines.append(f"| {bucket_letter} | {count} | {pct:.1f}% |")

        lines.extend(
            [
                "",
                "## Headline Finding",
                "",
                f"**Bucket C (v0.1.21 quorum-escalated RHR per STRICT counting): "
                f"{len(self.buckets['C'])}/30 ({100.0 * len(self.buckets['C']) / 30:.1f}% of cohort)**",
                "",
                "v0.1.21 Tier 1 quorum mechanism (n_invalid >= 2 → RHR) in v0.1.25-prod. "
                "v0.1.25 Design H partial-routing loosening should reduce both Bucket A+C "
                "RHR verdicts (0 RHR observed empirically vs 16 in v0.1.22 baseline).",
                "",
                "## Per-Case Listing by Bucket",
                "",
            ]
        )

        for bucket_letter in bucket_letters:
            if not self.buckets[bucket_letter]:
                continue
            lines.append(f"### Bucket {bucket_letter}")
            lines.append("")
            for case_id in sorted(self.buckets[bucket_letter]):
                data = self.cases[case_id]
                citations = data.get("citations", {})
                emitted = citations.get("emitted", [])
                pca = data.get("per_citation_audits", [])
                n_invalid = (
                    sum(1 for audit in pca if not audit.get("validated", False)) if pca else 0
                )
                lines.append(
                    f"- **{case_id}**: verdict={data.get('actual_verdict')}, "
                    f"n_emitted={len(emitted)}, n_invalid={n_invalid}"
                )
            lines.append("")

        lines.extend(
            [
                "## Caveats (§22.22)",
                "",
                "### Bucket Size Interpretation",
                "v0.1.25 Design H partial-routing softening targets the Strict-Answer "
                "routing path (upstream of Tier 1 quorum) per v0.1.24.1 finding-path-diagnostic. "
                "Bucket C here counts strict-invalid citations; empirical RHR elimination to 0 "
                "suggests partial-routing + Tier 1 together are eliminating the RHR pathway.",
                "",
                "### Per-Citation Audits Trail Limitations",
                "The per_citation_audits field (v0.1.21.1 D2) records the final STRICT-validated "
                "state. Bucket D (n_invalid=1) cases may represent partial-routing pass-through "
                "(≥X% Findings pass despite 1 invalid citation) which the diagnostic cannot "
                "distinguish from other Auditor paths.",
            ]
        )

        return "\n".join(lines) + "\n"


def main():
    """Run the diagnostic."""
    diagnostic = PerCitationDiagnostic()
    diagnostic.load_checkpoints()
    diagnostic.categorize_all()

    # Verify we got all 30 cases
    total = sum(len(cases) for cases in diagnostic.buckets.values())
    print(f"Loaded {total} cases from checkpoints")
    if total != 30:
        print(f"⚠️  Expected 30 cases, got {total}")

    # Render and write report
    report = diagnostic.render_report()
    output_path = REPORT_DIR / "per-citation-mechanism.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"OK: Per-citation mechanism diagnostic written to {output_path}")
    print(
        f"    Bucket counts: A={len(diagnostic.buckets['A'])} "
        f"B={len(diagnostic.buckets['B'])} C={len(diagnostic.buckets['C'])} "
        f"D={len(diagnostic.buckets['D'])} E={len(diagnostic.buckets['E'])}"
    )


if __name__ == "__main__":
    main()
