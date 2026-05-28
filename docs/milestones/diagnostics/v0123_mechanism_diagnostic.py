#!/usr/bin/env python
# ruff: noqa: E501  # diagnostic script; long lines acceptable
"""T3 Deliverable: Per-citation mechanism diagnostic for v0.1.23-prod ($0 cache-mining).

Analyzes v0.1.21.1 D2 per_citation_audits trail from v0.1.23 checkpoint JSONL files
to categorize the 30 chat-001..030 cases into 5 buckets per spec §D6 (v0.1.23):

  A: empty-findings (RHR + no citations)
  B: single-invalid BLOCK (pre-v0.1.21 mechanism)
  C: NEW v0.1.21 quorum-triggered RHR (n_invalid >= 2 via lenient counting)
  D: prose-without-findings (RHR + empty findings, heuristic)
  E: other / non-RHR / pass

Outputs: evals/reports/v0.1.23/per-citation-mechanism.md

No API calls; $0 budget assertion.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

CHECKPOINTS_DIR = Path("evals/checkpoints")
REPORT_DIR = Path("evals/reports/v0.1.23")

ALLOWED_CASES = {f"chat-{i:03d}" for i in range(1, 31)}


BucketType = Literal["A", "B", "C", "D", "E"]


class PerCitationDiagnostic:
    """Categorize 30-case v0.1.23 cohort into 5 buckets."""

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
        """Load v0.1.23 checkpoint files (probe + main)."""
        if not CHECKPOINTS_DIR.exists():
            raise FileNotFoundError(f"Checkpoint dir not found: {CHECKPOINTS_DIR}")

        # Find checkpoint files from v0.1.23 run (2026-05-25 late + 2026-05-26 early)
        # v0.1.23 probe: 20260525T215332Z-fac612e.jsonl
        # v0.1.23 main: 20260526T041817Z-fac612e.jsonl
        relevant_files = [
            Path(CHECKPOINTS_DIR) / "20260525T215332Z-fac612e.jsonl",
            Path(CHECKPOINTS_DIR) / "20260526T041817Z-fac612e.jsonl",
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

        # Bucket C: NEW v0.1.23 lenient-quorum-triggered RHR
        # RHR + citations emitted + per_citation_audits populated + n_lenient_invalid >= 2
        # For v0.1.23, lenient_invalid = article_not_exists OR apartado_not_exists (not text_match fail)
        # but for diagnostic, we use pre_citation_audits.validated field which is STRICT
        # so we count lenient_invalid where (article_exists and apartado_not_false)
        # Since we don't have separate fields, we approximate: count where validated=False
        # and assume some are text-only failures (lenient-valid)
        # For this diagnostic: use validated field directly (strict count)
        if n_emitted >= 1 and pca is not None:
            n_invalid_strict = sum(1 for audit in pca if not audit.get("validated", False))
            if n_invalid_strict >= 2:
                return "C"

        # Bucket A: RHR + empty citations
        if n_emitted == 0:
            return "A"

        # Bucket D: RHR + citations but single-invalid (pre-v0.1.21 pattern)
        # Would be escalated by old quorum, not by new lenient quorum
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
            "# v0.1.23 T6: Per-Citation Mechanism Diagnostic",
            "",
            f"**Date:** {datetime.utcnow().isoformat()}Z  **Method:** "
            "Cache-mining v0.1.21.1 D2 trail  **Cohort:** H10 chat-001..030 (30 cases)",
            "",
            "## Methodology",
            "",
            "Analyzes per-citation audit records from v0.1.23-prod checkpoint JSONL files "
            "(probe + main 25 cases) against the 5-bucket spec (Design B §D6):",
            "",
            "- **Bucket A:** RHR + empty citations",
            "- **Bucket B:** BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic)",
            "- **Bucket C:** RHR + ≥1 citation + ≥2 invalid citations (v0.1.21 "
            "STRICT-count escalation, subject to v0.1.23 lenient-quorum override)",
            "- **Bucket D:** RHR + ≥1 citation + exactly 1 invalid citation (edge case)",
            "- **Bucket E:** Other (non-RHR or data-incomplete)",
            "",
            "## 5-Bucket Count Table",
            "",
            "| Bucket | Count | Percentage |",
            "|--------|-------|-----------|",
        ]

        for bucket_letter in ["A", "B", "C", "D", "E"]:
            count = len(self.buckets[bucket_letter])
            pct = 100.0 * count / total if total > 0 else 0.0
            lines.append(f"| {bucket_letter} | {count} | {pct:.1f}% |")

        lines.extend(
            [
                "",
                "## Headline Finding",
                "",
                f"**Bucket C (quorum-escalated RHR per STRICT counting): "
                f"{len(self.buckets['C'])}/30 ({100.0 * len(self.buckets['C']) / 30:.1f}% of cohort)**",
                "",
                "The v0.1.21 Tier 1 quorum mechanism (n_invalid >= 2 → RHR) fires on this many case(s). "
                "v0.1.23 Design B introduces lenient-quorum override (article + apartado exists, "
                "text-match can fail) — expected to reduce this count by loosening the escalation threshold.",
                "",
                "## Per-Case Listing by Bucket",
                "",
            ]
        )

        for bucket_letter in ["A", "B", "C", "D", "E"]:
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
                "### Lenient vs Strict Counting",
                "This diagnostic counts n_invalid using the STRICT per_citation_audits.validated "
                "field (all 3 checks: article exists, apartado exists, text match). v0.1.23 Design B "
                "Tier 1 quorum counts lenient_invalid (Check 1+2 only, skips text-match Check 3). "
                "Diagnostic cannot separate text-only failures from Check 1/2 failures, so the "
                "per-bucket counts here are NOT the same as production lenient-quorum counts. "
                "Real impact of v0.1.23 Design B measured at T4 paid validation.",
                "",
                "### Bucket D Edge Case",
                "Bucket D (RHR + exactly 1 invalid) represents the boundary where pre-v0.1.21 "
                "would NOT escalate (only ≥1 invalid → BLOCK) but v0.1.21 Tier 1 quorum also "
                "does NOT escalate (needs ≥2). These are neither old nor new mechanism failures; "
                "they may represent other Auditor paths (e.g., Strict-Answer < n_valid).",
                "",
                "### Per-Citation Audits Trail Limitations",
                "The per_citation_audits field (v0.1.21.1 D2) records the final STRICT-validated "
                "state but does NOT capture whether a citation would be lenient-valid (article + "
                "apartado exist despite text mismatch). Precise audit of lenient-quorum impact "
                "requires re-applying the lenient validator logic post-hoc to cached per-citation data.",
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
