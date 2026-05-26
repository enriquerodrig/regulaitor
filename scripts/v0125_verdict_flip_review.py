#!/usr/bin/env python
# ruff: noqa: E501,SIM108,B007  # diagnostic script; long lines + simple loops acceptable
"""T4 Deliverable: Verdict flip review for v0.1.25 vs v0.1.22 (10 H1 cases).

Analyzes the 10 v0.1.22.1 H1-dominant cases (chat-016, 017, 018, 019, 021, 022,
023, 024, 025, 026) across v0.1.22-prod and v0.1.25-prod to identify whether
Design H's partial-routing loosening caused the predicted RHR→PASS flips.

Per spec D4: predicts ~8-9 of 10 H1 cases would flip RHR→PASS due to partial-routing.
This script checks actual outcomes vs predictions.

Outputs: evals/reports/v0.1.25/verdict-flip-review.md

No API calls; $0 comparison.
"""

import re
from pathlib import Path


def extract_case_verdict(markdown_path: str, case_id: str) -> str | None:
    """Extract actual_verdict for a specific case from report markdown."""
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    # Find case block
    pattern = rf"^### {re.escape(case_id)}\n(?P<content>(?:.*?\n)*?)(?=^###|\Z)"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None

    content = match.group("content")
    verdict_match = re.search(r"\*\*Verdict\*\*.*?actual=`(\w+)`", content)
    return verdict_match.group(1) if verdict_match else None


def extract_h1_cases() -> list[str]:
    """Return the 10 H1-dominant cases from v0.1.22.1."""
    return [
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


def main():
    """Analyze verdict flips for H1 cases."""
    h1_cases = extract_h1_cases()

    # Load v0.1.22-prod verdicts
    v0122_probe = Path("evals/reports/v0.1.22/probe.md")
    v0122_main = Path("evals/reports/v0.1.22/v0.1.22-prod-main.md")

    v0122_verdicts = {}
    for case_id in h1_cases:
        if case_id.startswith("chat-00"):
            path = v0122_probe
        else:
            path = v0122_main
        if path.exists():
            verdict = extract_case_verdict(str(path), case_id)
            if verdict:
                v0122_verdicts[case_id] = verdict

    # Load v0.1.25-prod verdicts
    v0125_path = Path("evals/reports/v0.1.25/v0.1.25-prod.md")
    v0125_verdicts = {}
    for case_id in h1_cases:
        if v0125_path.exists():
            verdict = extract_case_verdict(str(v0125_path), case_id)
            if verdict:
                v0125_verdicts[case_id] = verdict

    # Analyze flips
    flips = []
    no_flips = []
    unexpected = []

    for case_id in h1_cases:
        v0122 = v0122_verdicts.get(case_id)
        v0125 = v0125_verdicts.get(case_id)

        if not v0122 or not v0125:
            continue

        # Predict: if v0.1.22 was RHR, Design H partial-routing should flip to PASS
        if v0122 == "requires_human_review":
            if v0125 == "pass":
                flips.append((case_id, v0122, v0125, "RHR→PASS (as predicted)"))
            elif v0125 == "block":
                unexpected.append(
                    (
                        case_id,
                        v0122,
                        v0125,
                        "RHR→BLOCK (partial-routing but all-blocked)",
                    )
                )
            elif v0125 == "requires_human_review":
                no_flips.append(
                    (case_id, v0122, v0125, "RHR unchanged (partial-routing didn't help)")
                )
        elif v0122 == "pass":
            if v0125 == "requires_human_review":
                unexpected.append((case_id, v0122, v0125, "PASS→RHR (regression; API drift)"))
            elif v0125 != v0122:
                unexpected.append((case_id, v0122, v0125, f"{v0122}→{v0125} (unexpected)"))
        elif v0122 == "block":
            if v0125 == "requires_human_review":
                unexpected.append(
                    (case_id, v0122, v0125, "BLOCK→RHR (partial-routing loosened to RHR)")
                )
            elif v0125 != v0122:
                unexpected.append((case_id, v0122, v0125, f"{v0122}→{v0125} (unexpected)"))

    # Build report
    lines = [
        "# v0.1.25 T4: Verdict Flip Review (10 H1 Cases)",
        "",
        "**Scope:** v0.1.22.1 H1-dominant cases (10 chat cases identified as "
        "validator-too-strict in cache-mining diagnostic)",
        "",
        "**Prediction per Design H spec:** Design H softens Strict-Answer partial-routing "
        "(≥X% Findings pass despite 1+ invalid citations) → ~8-9 of 10 H1 cases "
        "should flip RHR→PASS.",
        "",
        "**Actual outcome:** TBD per this diagnostic.",
        "",
        "## Summary",
        "",
        f"- **Flipped RHR→PASS (as predicted):** {len(flips)}/10",
        f"- **Unchanged RHR:** {len(no_flips)}/10",
        f"- **Unexpected flips:** {len(unexpected)}/10",
        "",
        f"**Prediction confirmation rate:** {len(flips)}/10 "
        f"({100.0 * len(flips) / 10:.0f}% of predicted 8-9 ≈ {100.0 * len(flips) / (8.5):.0f}%)",
        "",
    ]

    # Per-case detail
    lines.extend(
        [
            "## Per-Case Detail",
            "",
            "| Case | v0.1.22 | v0.1.25 | Outcome |",
            "|---|---|---|---|",
        ]
    )

    for case_id in sorted(h1_cases):
        v0122 = v0122_verdicts.get(case_id, "?")
        v0125 = v0125_verdicts.get(case_id, "?")

        # Find outcome bucket
        outcome = "unknown"
        for case, old, new, desc in flips + no_flips + unexpected:
            if case == case_id:
                outcome = desc
                break

        lines.append(f"| {case_id} | {v0122} | {v0125} | {outcome} |")

    lines.extend(
        [
            "",
            "## Root Cause Analysis",
            "",
        ]
    )

    if len(flips) >= 8:
        lines.append(
            "✅ **Design H partial-routing loosening successful**: "
            f"{len(flips)}/10 H1 cases flipped RHR→PASS as predicted. "
            "The Strict-Answer partial-routing mechanism was the active bottleneck; "
            "softening it resolved most cases."
        )
    elif len(flips) > 0:
        lines.append(
            f"⚠️  **Partial success**: {len(flips)}/10 H1 cases flipped RHR→PASS "
            "(below predicted 8-9). Analysis:"
        )
        if len(unexpected) > 0:
            lines.append(
                f"   - {len(unexpected)} unexpected outcomes (RHR→BLOCK, PASS→RHR, etc.) "
                "suggest API drift between v0.1.22 (2026-05-24) and v0.1.25 (2026-05-26) "
                "in Sonnet citation emission."
            )
        if len(no_flips) > 0:
            lines.append(
                f"   - {len(no_flips)} cases remained RHR despite partial-routing softening, "
                "suggesting other Auditor paths (Finding-Lenient, Tier 1 quorum with n≥2) "
                "still block the answer."
            )
    else:
        lines.append(
            f"❌ **Design H did not flip H1 cases as predicted**. "
            f"{len(unexpected)} unexpected outcomes detected. Likely causes:"
        )
        lines.append(
            "   1. **API drift**: Sonnet output non-deterministic across 1-day gap; "
            "same queries produced different citations → different validator outcomes."
        )
        lines.append(
            "   2. **Partial-routing assumptions invalid**: Even with softened partial-routing, "
            "other Auditor paths (Finding-Lenient aggregation, Tier 1 quorum >= 2) "
            "block the answer before partial-routing executes."
        )
        lines.append(
            "   3. **Measurement artifact**: v0.1.22 RHR might not actually be from Strict-Answer "
            "partial path (where partial-routing applies) but from other Auditor paths → "
            "partial-routing doesn't help."
        )

    lines.append("")

    # Write output
    output_path = Path("evals/reports/v0.1.25/verdict-flip-review.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK: Verdict flip review written to {output_path}")
    print(f"    Flipped RHR->PASS: {len(flips)}/10 (predicted 8-9)")
    print(f"    Unchanged RHR: {len(no_flips)}/10")
    print(f"    Unexpected: {len(unexpected)}/10")


if __name__ == "__main__":
    main()
