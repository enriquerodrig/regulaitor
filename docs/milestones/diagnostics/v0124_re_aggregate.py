#!/usr/bin/env python
# ruff: noqa: E501
"""v0.1.24 T4.1: $0 verdict_match re-aggregation under acceptable_verdicts logic.

Reads cached v0.1.22-prod (probe + main, 30 cases combined) and v0.1.23-prod
(probe + main, 30 cases combined) report markdowns; for each per-case appendix
entry extracts (case_id, actual_verdict, expected_verdict, original verdict_match
symbol); loads the gold case from evals/gold_set.jsonl; recomputes verdict_match
using the new acceptable_verdicts logic (ADR-0031 D1):

    if gold_case.get('acceptable_verdicts'):
        new_match = actual_verdict in gold_case['acceptable_verdicts']
    else:
        new_match = (gold_case['expected_verdict'] == actual_verdict)

Outputs evals/reports/v0.1.24/verdict-match-re-aggregation.md with delta tables.

Pure Python, no API calls, $0 budget assertion.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean

# $0 budget assertion: no API calls
ASSERT_ZERO_BUDGET = True

# Paths
GOLD_SET_PATH = Path("evals/gold_set.jsonl")
REPORT_DIR = Path("evals/reports/v0.1.24")
OUTPUT_PATH = REPORT_DIR / "verdict-match-re-aggregation.md"

V0122_PROBE = Path("evals/reports/v0.1.22/probe.md")
V0122_MAIN = Path("evals/reports/v0.1.22/v0.1.22-prod-main.md")
V0123_PROBE = Path("evals/reports/v0.1.23/probe.md")
V0123_MAIN = Path("evals/reports/v0.1.23/v0.1.23-prod-main.md")


def extract_report_cases(markdown_path: Path) -> dict[str, dict]:
    """Parse per-case data from report markdown.

    Returns dict[case_id] -> {actual_verdict, expected_verdict, original_match}.
    """
    text = markdown_path.read_text(encoding="utf-8")
    cases: dict[str, dict] = {}

    # Split by ### case_id headers (case_id is "chat-NNN" or similar)
    pattern = r"^### (?P<case_id>\S+)\n(?P<content>(?:.*?\n)*?)(?=^###|\Z)"
    for match in re.finditer(pattern, text, re.MULTILINE):
        case_id = match.group("case_id")
        content = match.group("content")

        # Verdict line: "actual=`X` expected=`Y` (symbol)"
        m = re.search(
            r"actual=`(?P<actual>\w+)` expected=`(?P<expected>\w+)`\s+(?P<sym>✅|❌)", content
        )
        if not m:
            continue
        cases[case_id] = {
            "case_id": case_id,
            "actual_verdict": m.group("actual"),
            "expected_verdict": m.group("expected"),
            "original_match": m.group("sym") == "✅",
        }

    return cases


def load_gold_cases() -> dict[str, dict]:
    """Load gold cases keyed by id."""
    gold: dict[str, dict] = {}
    with GOLD_SET_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            gold[obj["id"]] = obj
    return gold


def recompute_match(actual_verdict: str, gold_case: dict) -> bool:
    """ADR-0031 D1 verdict_match logic."""
    acceptable = gold_case.get("acceptable_verdicts")
    if acceptable:
        return actual_verdict in acceptable
    return gold_case.get("expected_verdict") == actual_verdict


def aggregate_report(probe_path: Path, main_path: Path, gold: dict[str, dict]) -> dict:
    """Re-aggregate one report (probe + main combined)."""
    cases: dict[str, dict] = {}
    cases.update(extract_report_cases(probe_path))
    cases.update(extract_report_cases(main_path))

    rows = []
    flipped = []
    for case_id, c in sorted(cases.items()):
        gold_case = gold.get(case_id)
        if gold_case is None:
            # Unknown case (not in gold) — skip
            continue
        original_match = c["original_match"]
        new_match = recompute_match(c["actual_verdict"], gold_case)
        acceptable = gold_case.get("acceptable_verdicts")
        rows.append(
            {
                "case_id": case_id,
                "actual_verdict": c["actual_verdict"],
                "expected_verdict": gold_case.get("expected_verdict"),
                "acceptable_verdicts": acceptable,
                "original_match": original_match,
                "new_match": new_match,
                "flipped": (not original_match) and new_match,
            }
        )
        if (not original_match) and new_match:
            flipped.append(case_id)

    original_rate = mean(1.0 if r["original_match"] else 0.0 for r in rows) if rows else 0.0
    new_rate = mean(1.0 if r["new_match"] else 0.0 for r in rows) if rows else 0.0
    delta = new_rate - original_rate

    return {
        "rows": rows,
        "n_cases": len(rows),
        "original_rate": original_rate,
        "new_rate": new_rate,
        "delta": delta,
        "flipped": flipped,
    }


def render_per_case_table(rows: list[dict], only_flipped: bool = False) -> list[str]:
    """Render a per-case table (only flipped cases when only_flipped=True)."""
    lines: list[str] = []
    if only_flipped:
        rows = [r for r in rows if r["flipped"]]
    if not rows:
        lines.append("_No cases match this filter._")
        lines.append("")
        return lines

    lines.append("| case_id | actual | expected | acceptable_verdicts | original | new |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        acceptable_str = (
            ",".join(r["acceptable_verdicts"]) if r["acceptable_verdicts"] else "_(none)_"
        )
        original_sym = "✅" if r["original_match"] else "❌"
        new_sym = "✅" if r["new_match"] else "❌"
        lines.append(
            f"| {r['case_id']} | {r['actual_verdict']} | {r['expected_verdict']} | "
            f"{acceptable_str} | {original_sym} | {new_sym} |"
        )
    lines.append("")
    return lines


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    gold = load_gold_cases()

    v0122 = aggregate_report(V0122_PROBE, V0122_MAIN, gold)
    v0123 = aggregate_report(V0123_PROBE, V0123_MAIN, gold)

    lines: list[str] = [
        "# v0.1.24 — verdict_match re-aggregation under acceptable_verdicts logic",
        "",
        "**Date:** 2026-05-26",
        "**Script:** `scripts/v0124_re_aggregate.py`",
        "**Methodology:** $0 cache-only re-aggregation. Reads cached v0.1.22-prod and v0.1.23-prod report markdowns; per-case `actual_verdict` reused verbatim; verdict_match recomputed under ADR-0031 D1 acceptable_verdicts rule:",
        "",
        "```",
        "if gold_case.get('acceptable_verdicts'):",
        "    new_match = actual_verdict in gold_case['acceptable_verdicts']",
        "else:",
        "    new_match = (gold_case['expected_verdict'] == actual_verdict)",
        "```",
        "",
        "**Lineage:** ADR-0024 (eval-instrument hierarchical containment precedent) → ADR-0027/0029 (production state inherited) → ADR-0030 (REVERT lessons learned) → ADR-0031 (this milestone).",
        "",
        "## Delta summary",
        "",
        "| Report | N | Original verdict_match | New verdict_match | Delta | Flipped ❌→✅ |",
        "|---|---|---|---|---|---|",
        f"| v0.1.22-prod (probe+main) | {v0122['n_cases']} | {v0122['original_rate']:.2f} | {v0122['new_rate']:.2f} | {v0122['delta']:+.2f} | {len(v0122['flipped'])} |",
        f"| v0.1.23-prod (probe+main) | {v0123['n_cases']} | {v0123['original_rate']:.2f} | {v0123['new_rate']:.2f} | {v0123['delta']:+.2f} | {len(v0123['flipped'])} |",
        "",
        "## v0.1.22-prod per-case flips (acceptable_verdicts-aware)",
        "",
    ]
    lines += render_per_case_table(v0122["rows"], only_flipped=True)

    lines += [
        "## v0.1.23-prod per-case flips (acceptable_verdicts-aware)",
        "",
    ]
    lines += render_per_case_table(v0123["rows"], only_flipped=True)

    lines += [
        "## §22.22 caveats",
        "",
        "1. **Alignment, not improvement** (ADR-0031 §22.22 #1): the lift is a measurement-instrument fix; underlying production behavior is unchanged. Gold accepts what production was already doing safely (v0.1.22 T6 safety-floor confirmed 6/6 designated cases content-SAFE).",
        "2. **API-drift caveat** (ADR-0031 §22.22 #5): re-aggregation reuses cached `actual_verdict` from v0.1.22-prod (2026-05-24) and v0.1.23-prod (2026-05-26); reflects then-state, NOT a hypothetical now-state.",
        "3. **Per-case opt-in, not blanket loosening** (ADR-0031 §22.22 #6): only the 6 designated cases (chat-014, chat-015, chat-029, chat-030, nis2-006, dora-006) carry `acceptable_verdicts`. Of the cohort cases covered by these two reports, only the chat-014/015/029/030 subset is present (nis2-006/dora-006 are NOT in the H10 30-case cohort that v0.1.22/v0.1.23 measured).",
        "4. **Residual still exists** (ADR-0031 §22.22 #7): the post-lift verdict_match does NOT close the bar gap. v0.1.25+ targeted intervention is the candidate closer; v0.1.24 is necessary preparation, not sufficient resolution.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "uv run python scripts/v0124_re_aggregate.py",
        "```",
        "",
        "$0 cost. Outputs this file deterministically from the cached reports + gold set.",
        "",
    ]

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: re-aggregation report written to {OUTPUT_PATH}")
    print(
        f"v0.1.22-prod: {v0122['original_rate']:.2f} -> {v0122['new_rate']:.2f} ({v0122['delta']:+.2f}); flipped={v0122['flipped']}"
    )
    print(
        f"v0.1.23-prod: {v0123['original_rate']:.2f} -> {v0123['new_rate']:.2f} ({v0123['delta']:+.2f}); flipped={v0123['flipped']}"
    )


if __name__ == "__main__":
    main()
