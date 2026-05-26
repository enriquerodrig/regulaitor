#!/usr/bin/env python
# ruff: noqa: E501,SIM108,B007  # diagnostic script; long lines + simple loops acceptable
"""T4 Deliverable: Verdict flip review for v0.1.23 vs v0.1.22 (10 H1 cases).

Analyzes the 10 v0.1.22.1 H1-dominant cases (chat-016, 017, 018, 019, 021, 022,
023, 024, 025, 026) across v0.1.22-prod and v0.1.23-prod to identify whether
Design B's lenient-quorum loosening caused the predicted RHR→PASS flips.

Per spec D4: predicts ~6-7 of 10 cases would flip RHR→PASS due to lenient counting.
This script checks actual outcomes vs predictions.

Outputs: evals/reports/v0.1.23/verdict-flip-review.md

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

    # Load v0.1.23-prod verdicts
    v0123_path = Path("evals/reports/v0.1.23/v0.1.23-prod.md")
    v0123_verdicts = {}
    for case_id in h1_cases:
        if v0123_path.exists():
            verdict = extract_case_verdict(str(v0123_path), case_id)
            if verdict:
                v0123_verdicts[case_id] = verdict

    # Analyze flips
    flips = []
    no_flips = []
    unexpected = []

    for case_id in h1_cases:
        v0122 = v0122_verdicts.get(case_id)
        v0123 = v0123_verdicts.get(case_id)

        if not v0122 or not v0123:
            continue

        # Predict: if v0.1.22 was RHR, Design B might flip to PASS (if lenient-valid)
        # Design B loosens quorum, so we expect RHR→PASS or RHR→BLOCK (if other paths)
        if v0122 == "requires_human_review":
            if v0123 == "pass":
                flips.append((case_id, v0122, v0123, "RHR→PASS (as predicted)"))
            elif v0123 == "block":
                unexpected.append(
                    (
                        case_id,
                        v0122,
                        v0123,
                        "RHR→BLOCK (lenient loosening but Strict-Answer blocked)",
                    )
                )
            elif v0123 == "requires_human_review":
                no_flips.append((case_id, v0122, v0123, "RHR unchanged (lenient didn't help)"))
        elif v0122 == "pass":
            if v0123 == "requires_human_review":
                unexpected.append((case_id, v0122, v0123, "PASS→RHR (regression; API drift)"))
            elif v0123 != v0122:
                unexpected.append((case_id, v0122, v0123, f"{v0122}→{v0123} (unexpected)"))
        elif v0122 == "block":
            if v0123 == "requires_human_review":
                unexpected.append(
                    (case_id, v0122, v0123, "BLOCK→RHR (loosening narrowed to Strict-Answer)")
                )
            elif v0123 != v0122:
                unexpected.append((case_id, v0122, v0123, f"{v0122}→{v0123} (unexpected)"))

    # Build report
    lines = [
        "# v0.1.23 T4: Verdict Flip Review (10 H1 Cases)",
        "",
        "**Scope:** v0.1.22.1 H1-dominant cases (10 chat cases identified as "
        "validator-too-strict in cache-mining diagnostic)",
        "",
        "**Prediction per Design B spec:** Design B loosens Tier 1 quorum counting "
        "(lenient = Check 1+2 only, skips text-match Check 3) → ~6-7 of 10 H1 cases "
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
        f"({100.0 * len(flips) / 10:.0f}% of predicted 6-7 ≈ {100.0 * len(flips) / (6.5):.0f}%)",
        "",
    ]

    # Per-case detail
    lines.extend(
        [
            "## Per-Case Detail",
            "",
            "| Case | v0.1.22 | v0.1.23 | Outcome |",
            "|---|---|---|---|",
        ]
    )

    for case_id in sorted(h1_cases):
        v0122 = v0122_verdicts.get(case_id, "?")
        v0123 = v0123_verdicts.get(case_id, "?")

        # Find outcome bucket
        outcome = "unknown"
        for case, old, new, desc in flips + no_flips + unexpected:
            if case == case_id:
                outcome = desc
                break

        lines.append(f"| {case_id} | {v0122} | {v0123} | {outcome} |")

    lines.extend(
        [
            "",
            "## Root Cause Analysis",
            "",
        ]
    )

    if len(flips) >= 6:
        lines.append(
            "✅ **Design B lenient-quorum loosening successful**: "
            f"{len(flips)}/10 H1 cases flipped RHR→PASS as predicted. "
            "The ~validator-too-strict mechanism was the bottleneck; "
            "lenient counting resolved most cases."
        )
    elif len(flips) > 0:
        lines.append(
            f"⚠️  **Partial success**: {len(flips)}/10 H1 cases flipped RHR→PASS "
            "(below predicted 6-7). Analysis:"
        )
        if len(unexpected) > 0:
            lines.append(
                f"   - {len(unexpected)} unexpected outcomes (RHR→BLOCK, PASS→RHR, etc.) "
                "suggest API drift between v0.1.22 (2026-05-24) and v0.1.23 (2026-05-26) "
                "in Sonnet citation emission."
            )
        if len(no_flips) > 0:
            lines.append(
                f"   - {len(no_flips)} cases remained RHR despite lenient loosening, "
                "suggesting other Auditor paths (Strict-Answer, Finding-Lenient) "
                "still block the answer."
            )
    else:
        lines.append(
            f"❌ **Design B did not flip H1 cases as predicted**. "
            f"{len(unexpected)} unexpected outcomes detected. Likely causes:"
        )
        lines.append(
            "   1. **API drift**: Sonnet output non-deterministic across 2-day gap; "
            "same queries produced different citations → different validator outcomes."
        )
        lines.append(
            "   2. **Lenient-quorum assumptions invalid**: Even with lenient counting, "
            "other Auditor paths (Strict-Answer routing, Finding-Lenient aggregation) "
            "block the answer before quorum escalation."
        )
        lines.append(
            "   3. **Measurement artifact**: v0.1.22 RHR might not actually be from quorum "
            "escalation (n_invalid >= 2) but from other paths → lenient doesn't help."
        )

    lines.append("")

    # Write output
    output_path = Path("evals/reports/v0.1.23/verdict-flip-review.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK: Verdict flip review written to {output_path}")
    print(f"    Flipped RHR->PASS: {len(flips)}/10 (predicted 6-7)")
    print(f"    Unchanged RHR: {len(no_flips)}/10")
    print(f"    Unexpected: {len(unexpected)}/10")


if __name__ == "__main__":
    main()
