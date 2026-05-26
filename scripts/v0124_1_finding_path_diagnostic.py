#!/usr/bin/env python3
"""
v0.1.24.1 — Per-Finding Auditor path attribution diagnostic.

Cross-version comparison of v0.1.22-prod vs v0.1.23-prod actual_verdict
for the 10 H1 cases identified in v0.1.22.1.

Methodology:
- Load per-case actual_verdict from v0.1.22 and v0.1.23 reports
- Cross-reference the 10 H1 cases (see H1_CASES below)
- Categorize each case per cross-version Path (A/B/C-ish per spec §2.3)
- Output finding-path-attribution.md with case_id → Path mapping

Cost: $0 (pure cache mining; no API calls)
"""

import re
from dataclasses import dataclass
from pathlib import Path

# Define the 10 H1 cases from v0.1.22.1 diagnostic
H1_CASES = [
    "chat-016",
    "chat-017",
    "chat-018",
    "chat-019",
    "chat-021",
    "chat-022",
    "chat-023",
    "chat-024",
    "chat-025",
    "chat-026",
]

REPORTS_DIR = Path(__file__).parent.parent / "evals" / "reports"


@dataclass
class CaseVerdict:
    case_id: str
    v022_verdict: str  # from v0.1.22-prod
    v023_verdict: str  # from v0.1.23-prod
    path: str  # categorized path (A / B / C-ish / ambiguous)


def parse_case_verdicts(report_path: Path) -> dict[str, str]:
    """Extract case_id → actual_verdict from per-case appendix of markdown report.

    Parses lines like:
    ### chat-016
    - **Verdict**: actual=`requires_human_review` expected=`pass` ❌

    Returns dict mapping case_id → actual_verdict string
    (e.g. 'pass', 'block', 'requires_human_review')
    """
    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    verdicts = {}
    content = report_path.read_text(encoding="utf-8")

    # Match ### chat-XXX followed by Verdict line
    pattern = r"^### (chat-\d+)\s*\n.*?- \*\*Verdict\*\*: actual=`(\w+)`"
    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)

    for match in matches:
        case_id = match.group(1)
        actual_verdict = match.group(2)
        verdicts[case_id] = actual_verdict

    return verdicts


def categorize_path(v22_verdict: str, v23_verdict: str) -> str:
    """Categorize the cross-version transition per spec §2.3 inference table.

    Table from spec:
    | v0.1.22 verdict | v0.1.23 verdict | Inference |
    |---|---|---|
    | RHR | PASS | Path A (Tier 1 firing; lenient quorum unlocked) |
    | RHR | RHR | Path B (partial routing; Tier 1 didn't fire) |
    | RHR | BLOCK | Path C-ish (all-blocked post-v0.1.23) OR API drift |

    Only path-categorizes cases where v22_verdict == 'requires_human_review'.
    """
    if v22_verdict == "requires_human_review":
        if v23_verdict == "pass":  # noqa: SIM116
            return "A (Tier 1 firing)"
        elif v23_verdict == "requires_human_review":
            return "B (Strict-Answer partial routing)"
        elif v23_verdict == "block":
            return "C-ish (all-blocked OR API drift)"
        else:
            return "ambiguous"
    elif v22_verdict == v23_verdict:
        return "unchanged (not in scope)"
    else:
        return "ambiguous (v22 non-RHR baseline)"


def main() -> None:
    # Load verdicts from v0.1.22 (main + probe) and v0.1.23 (main + probe)
    v22_main = REPORTS_DIR / "v0.1.22" / "v0.1.22-prod-main.md"
    v22_probe = REPORTS_DIR / "v0.1.22" / "probe.md"
    v23_main = REPORTS_DIR / "v0.1.23" / "v0.1.23-prod-main.md"
    v23_probe = REPORTS_DIR / "v0.1.23" / "probe.md"

    v22_verdicts = {}
    v22_verdicts.update(parse_case_verdicts(v22_main))
    v22_verdicts.update(parse_case_verdicts(v22_probe))

    v23_verdicts = {}
    v23_verdicts.update(parse_case_verdicts(v23_main))
    v23_verdicts.update(parse_case_verdicts(v23_probe))

    # Process the 10 H1 cases
    results = []
    for case_id in H1_CASES:
        v22 = v22_verdicts.get(case_id, "unknown")
        v23 = v23_verdicts.get(case_id, "unknown")
        path = categorize_path(v22, v23)
        results.append(CaseVerdict(case_id=case_id, v022_verdict=v22, v023_verdict=v23, path=path))

    # Aggregate counts
    path_counts: dict[str, int] = {
        "A (Tier 1 firing)": 0,
        "B (Strict-Answer partial routing)": 0,
        "C-ish (all-blocked OR API drift)": 0,
        "ambiguous": 0,
    }
    for result in results:
        if result.path in path_counts:
            path_counts[result.path] += 1
        else:
            # edge case: unchanged/etc
            pass

    # Determine dominant path
    dominant_path: tuple[str | None, int] = max(
        [(k, v) for k, v in path_counts.items() if v > 0],
        key=lambda x: x[1],
        default=(None, 0),
    )

    # Determine v0.1.25 design recommendation (per spec D3 table)
    design_rec: str = ""
    if dominant_path[0] == "A (Tier 1 firing)" and dominant_path[1] >= 5:  # ≥ 50%
        design_rec = "Design G (Tier 1 lenient + Finding-Lenient lenient)"
    elif dominant_path[0] == "B (Strict-Answer partial routing)" and dominant_path[1] >= 5:
        design_rec = "Design H (Strict-Answer partial routing softening)"
    elif dominant_path[0] == "C-ish (all-blocked OR API drift)" and dominant_path[1] >= 5:
        design_rec = "Design D (Finding-Lenient lenient only)"
    else:
        design_rec = "Inconclusive — recommend per-Finding instrumentation (v0.1.24.2)"

    # Write the report
    output_dir = REPORTS_DIR / "v0.1.24.1"
    output_dir.mkdir(exist_ok=True)

    report_path = output_dir / "finding-path-attribution.md"
    report_content = generate_report(results, path_counts, dominant_path, design_rec)
    report_path.write_text(report_content, encoding="utf-8")

    print(f"Report written to {report_path}")
    print("\nAggregate counts:")
    for path, count in path_counts.items():
        print(f"  {path}: {count}/10")
    print(f"\nDominant path: {dominant_path[0]} ({dominant_path[1]}/10)")
    print(f"v0.1.25 recommendation: {design_rec}")


def generate_report(
    results: list[CaseVerdict],
    path_counts: dict[str, int],
    dominant_path: tuple[str | None, int],
    design_rec: str,
) -> str:
    """Generate the markdown report."""
    lines = [
        "# v0.1.24.1 — Per-Finding Auditor Path Attribution",
        "",
        "**Date**: 2026-05-26",
        (
            "**Methodology**: Cross-version comparison v0.1.22-prod vs "
            "v0.1.23-prod actual_verdict for 10 H1 cases"
        ),
        (
            "**Lineage**: v0.1.22.1 H1 diagnostic → v0.1.23 REVERT "
            "(0/10 flipped) → v0.1.24 O2 (H1.C=10/10) → THIS spec"
        ),
        "",
        "## Cross-version comparison table",
        "",
        "| case_id | v0.1.22-prod verdict | v0.1.23-prod verdict | Path |",
        "|---|---|---|---|",
    ]

    for result in results:
        lines.append(
            f"| {result.case_id} | {result.v022_verdict} | "
            f"{result.v023_verdict} | {result.path} |"
        )

    lines.extend(["", "## Aggregate counts", ""])

    for path, count in path_counts.items():
        pct = (count / 10) * 100
        lines.append(f"- {path} = {count}/10 ({pct:.0f}%)")

    ambiguous = 10 - sum(path_counts.values())
    lines.append(f"- ambiguous / unknown = {ambiguous}/10")

    lines.extend(
        [
            "",
            "## HEADLINE",
            "",
            f"**Dominant path identified**: {dominant_path[0]} ({dominant_path[1]}/10)",
            "",
            f"**v0.1.25 design recommendation**: {design_rec}",
            "",
            "## §22.22 caveats",
            "",
            (
                "1. Cross-version inference confounded by Sonnet "
                "non-determinism (~20% noise floor per v0.1.23 "
                "§REVERT root cause #1)"
            ),
            (
                "2. Path C-ish ambiguity: cases that went RHR → BLOCK "
                "could be all-blocked routing change OR API drift; "
                "cannot definitively separate"
            ),
            (
                "3. Per-Finding citation grouping is LOST in cached "
                "AuditResults (post-Auditor aggregation); cross-version "
                "is the workaround"
            ),
            (
                "4. Recommendation accuracy depends on accurate "
                "v0.1.22.1 H1 attribution + accurate v0.1.24 O2 "
                "H1.C confirmation; both validated to date"
            ),
            (
                "5. v0.1.25+ Design selection still requires user "
                "judgment; this diagnostic narrows but doesn't fully "
                "determine"
            ),
            "",
        ]
    )

    return "\n".join(lines)


if __name__ == "__main__":
    main()
