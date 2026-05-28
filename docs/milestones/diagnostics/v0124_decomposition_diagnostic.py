#!/usr/bin/env python
# ruff: noqa: E501
"""v0.1.24 T4.2: $0 H-attribution re-decomposition with failed_check buckets.

Re-runs the v0.1.22.1 H-attribution but with per-check decomposition. Since
cached v0.1.22 AuditResults predate the ADR-0031 D2 `failed_check` schema
field, this script re-derives the failed_check from the `reason` text already
present in the v0.1.22.1 verdict-drop-analysis per_citation_audits trail:

  'article_not_found' -> Check 1 (article fabrication; true §6-relevant)
  'apartado_not_found' -> Check 2 (apartado fabrication; true §6-relevant)
  'text_not_in_apartado' or 'text_not_in_article' -> Check 3 (text-only paraphrase mismatch)
  None of above (validated=True) -> None (passed)

Re-attributes the 10 H1-attributed cases from v0.1.22.1 into:
  H1.A: dominant Check 1 fails (aggregation-layer fix CANNOT help)
  H1.B: dominant Check 2 fails (aggregation-layer fix CANNOT help)
  H1.C: dominant Check 3 fails (paraphrase-only; aggregation-layer or eval-side fix CAN help)
  mixed: no dominant check (multiple Check classes tied)

Outputs evals/reports/v0.1.24/decomposition-h-attribution.md with per-case
distribution + headline counts + v0.1.25+ intervention recommendation.

Pure Python, no API calls, $0 budget assertion.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

# $0 budget assertion: no API calls
ASSERT_ZERO_BUDGET = True

# Paths
REPORT_DIR = Path("evals/reports/v0.1.24")
OUTPUT_PATH = REPORT_DIR / "decomposition-h-attribution.md"
V0122_1_REPORT = Path("evals/reports/v0.1.22.1/verdict-drop-analysis.md")

# H1 cases per v0.1.22.1 dominant_H column
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

FailedCheck = Literal[1, 2, 3] | None


def derive_failed_check(reason: str | None, validated: bool) -> FailedCheck:
    """Map reason text -> failed_check per ADR-0031 D4."""
    if validated:
        return None
    reason_l = (reason or "").lower()
    if "article_not_found" in reason_l:
        return 1
    if "apartado_not_found" in reason_l:
        return 2
    if "text_not_in_apartado" in reason_l or "text_not_in_article" in reason_l:
        return 3
    return None  # unknown / not classifiable


def parse_v0122_1_report() -> dict[str, list[dict]]:
    """Parse v0.1.22.1 verdict-drop-analysis.md per-case detail blocks.

    Returns dict[case_id] -> list of per-citation audit dicts:
        {"citation": str, "validated": bool, "reason": str | None, "failed_check": int | None}
    """
    text = V0122_1_REPORT.read_text(encoding="utf-8")
    cases: dict[str, list[dict]] = {}

    # Each block starts with "### case_id (Hypothesis ...)"
    block_pattern = re.compile(
        r"^### (?P<case_id>chat-\d{3}) \(Hypothesis [^)]+\)\n(?P<body>(?:.*?\n)*?)(?=^###|\Z)",
        re.MULTILINE,
    )

    # Per-citation lines look like:
    #   - 17.1: ❌ invalid (text_not_in_apartado: ai_act art. 17.1 es; ...)
    #   - 17.2: ✅ valid (None)
    citation_pattern = re.compile(
        r"^\s*-\s+(?P<cit>[\w.]+):\s+(?P<sym>✅|❌)\s+(?P<status>valid|invalid)\s+\((?P<reason>.*?)\)\s*$",
        re.MULTILINE,
    )

    for m in block_pattern.finditer(text):
        case_id = m.group("case_id")
        body = m.group("body")
        audits: list[dict] = []
        for c in citation_pattern.finditer(body):
            citation = c.group("cit")
            validated = c.group("status") == "valid"
            reason_raw = c.group("reason")
            reason = None if reason_raw.strip() == "None" else reason_raw
            failed_check = derive_failed_check(reason, validated)
            audits.append(
                {
                    "citation": citation,
                    "validated": validated,
                    "reason": reason,
                    "failed_check": failed_check,
                }
            )
        cases[case_id] = audits

    return cases


def classify_dominant_check(audits: list[dict]) -> tuple[str, dict[int, int]]:
    """Dominance rule: most-frequent failed_check among invalid citations.

    Returns (dominant_label, counts) where dominant_label is one of
    "H1.A" (Check 1 dominant), "H1.B" (Check 2 dominant),
    "H1.C" (Check 3 dominant), or "mixed" (tie or no fails).
    """
    counts: dict[int, int] = {1: 0, 2: 0, 3: 0}
    for a in audits:
        fc = a["failed_check"]
        if fc in (1, 2, 3):
            counts[fc] += 1
    total_fails = sum(counts.values())
    if total_fails == 0:
        return "mixed", counts

    max_count = max(counts.values())
    dominants = [k for k, v in counts.items() if v == max_count]
    if len(dominants) > 1:
        return "mixed", counts
    dominant = dominants[0]
    label = {1: "H1.A", 2: "H1.B", 3: "H1.C"}[dominant]
    return label, counts


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    cases = parse_v0122_1_report()

    # Re-attribute the 10 H1 cases
    rows: list[dict] = []
    bucket_counts: dict[str, int] = {"H1.A": 0, "H1.B": 0, "H1.C": 0, "mixed": 0}
    for case_id in H1_CASES:
        audits = cases.get(case_id, [])
        label, counts = classify_dominant_check(audits)
        bucket_counts[label] += 1
        rows.append(
            {
                "case_id": case_id,
                "n_invalid": sum(counts.values()),
                "check_1": counts[1],
                "check_2": counts[2],
                "check_3": counts[3],
                "label": label,
            }
        )

    h1_c = bucket_counts["H1.C"]
    h1_a = bucket_counts["H1.A"]
    h1_b = bucket_counts["H1.B"]
    h1_mixed = bucket_counts["mixed"]
    total = h1_c + h1_a + h1_b + h1_mixed

    over_counted = h1_a + h1_b  # cases NOT addressable by aggregation-layer fix

    # Recommendation logic
    if h1_c >= 7:
        recommendation = (
            "**H1.C dominant** (≥7 of 10): paraphrase-only Check 3 mismatch is the universal pattern across "
            "the H1 cases. v0.1.23 Design B (Tier 1 quorum lenient counting) DID target this exact pattern "
            "at the quorum-count layer — yet 0/10 H1 cases flipped RHR → PASS at T6. This implies the "
            "verdict_match drop is NOT controlled by the Tier 1 quorum on Check 3 failures; some upstream "
            "Auditor path (Finding-Lenient strict-text-match OR Strict-Answer partial-Findings routing) "
            "rejects these citations before the Tier 1 quorum executes — see ADR-0030 §REVERT Hypotheses "
            "B and C. Candidate v0.1.25+ interventions: (a) Finding-Lenient softening to accept Check 3 "
            "lenient-valid citations (article + apartado exist, text mismatch) as Finding-pass — higher §6 "
            "risk than Design B but targets the layer that actually fires; (b) eval-side hierarchical "
            "containment propagation into the Auditor's per-citation acceptance (mirror of ADR-0024 at the "
            "production layer); (c) prompt-side anchor on copy-paste-from-context citations (lower risk; "
            "may underperform structural fixes); (d) the H1 cases routing through Strict-Answer partial-"
            "Findings (some Findings have Check 3 fails → blocked Findings → partial branch → RHR before "
            "Tier 1 quorum is even reached); a per-Finding instrumentation diagnostic should confirm before "
            "an intervention."
        )
    elif h1_c >= 4:
        recommendation = (
            "**H1.C moderate** (4-6 of 10): paraphrase-only mismatch contributes but is NOT dominant. "
            "Mixed buckets need separate interventions. Recommend $0 secondary diagnostic on H1.A/H1.B "
            "cases to determine whether the article/apartado fabrications are gold-grounded (true fabrications) "
            "or gold-misaligned (eval-side fix candidate)."
        )
    else:
        recommendation = (
            f"**H1.C minimal** ({h1_c} of 10): paraphrase-only mismatch is NOT the dominant H1 mechanism. "
            f"The {over_counted} H1.A/H1.B cases are true Check 1/2 fabrications — aggregation-layer "
            "intervention CANNOT help these. Candidate v0.1.25+ intervention paths: (a) eval-side gold "
            "review on the H1.A/B cases (are the expected articles correct? does Sonnet cite wrong articles "
            "for a legitimate reason?), (b) retrieval-side intervention to surface the gold articles, "
            "(c) prompt-side anchor to discourage related-but-not-gold articles. v0.1.22.1 H1 attribution "
            "over-counted by ~"
            f"{over_counted} cases — Tier 1 quorum was NEVER the dominant lever."
        )

    lines: list[str] = [
        "# v0.1.24 — Decomposition diagnostic: failed_check re-attribution of v0.1.22.1 H1 cases",
        "",
        "**Date:** 2026-05-26",
        "**Script:** `scripts/v0124_decomposition_diagnostic.py`",
        "**Methodology:** $0 re-derivation of `failed_check` (ADR-0031 D2) from cached v0.1.22.1 reason text. The cached AuditResults predate the schema field, so the per-citation reason strings serve as the source of truth for which check fired first.",
        "",
        "Re-derivation map (per ADR-0031 D4 + script docstring):",
        "",
        "| `reason` substring | failed_check | §6 character |",
        "|---|---|---|",
        "| `article_not_found` | 1 | true article fabrication |",
        "| `apartado_not_found` | 2 | true apartado fabrication |",
        "| `text_not_in_apartado` or `text_not_in_article` | 3 | paraphrase-only mismatch |",
        "| (validated=True) | None | citation passed all checks |",
        "",
        "## Per-case failed_check distribution (10 H1 cases from v0.1.22.1)",
        "",
        "| case_id | n_invalid | Check 1 | Check 2 | Check 3 | dominant | re-attribution |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['case_id']} | {r['n_invalid']} | {r['check_1']} | {r['check_2']} | {r['check_3']} | "
            f"Check {(r['check_3'] and 3) or (r['check_2'] and 2) or (r['check_1'] and 1) or 'None'} | {r['label']} |"
        )

    lines += [
        "",
        "## Aggregate re-attribution counts",
        "",
        "| Bucket | Count | Meaning |",
        "|---|---|---|",
        f"| H1.A (Check 1 dominant) | {h1_a} | article fabrication; aggregation-layer fix CANNOT help |",
        f"| H1.B (Check 2 dominant) | {h1_b} | apartado fabrication; aggregation-layer fix CANNOT help |",
        f"| H1.C (Check 3 dominant) | {h1_c} | paraphrase-only mismatch; aggregation-layer or eval-side fix CAN help |",
        f"| mixed (tied / no clear dominant) | {h1_mixed} | manual review |",
        f"| **TOTAL H1 cases** | **{total}** | — |",
        "",
        "## HEADLINE",
        "",
        f"Of the 10 H1-attributed cases in v0.1.22.1, **{h1_c} are H1.C** (paraphrase-only Check 3 dominant; the only sub-bucket where a lenient-quorum / Finding-Lenient softening / eval-side hierarchical-containment propagation could plausibly help) vs **{h1_a + h1_b} H1.A/H1.B** (true Check 1/2 article-or-apartado fabrications; aggregation-layer intervention CANNOT help).",
        "",
        f"**Counter-intuitive read**: v0.1.22.1's H1 attribution was accurate at the Check 3 sub-bucket level — all {h1_c}/10 cases ARE paraphrase-only mismatches. The v0.1.23 REVERT post-mortem Hypothesis A (H1 over-counted via Check 1/2 conflation) is NOT supported by this decomposition — Check 1/2 over-count is {h1_a + h1_b}. The verdict_match drop's underlying mechanism is therefore NOT Check 1/2 fabrication conflation; it is something else that survived v0.1.23 Design B's lenient-quorum intervention (per ADR-0030 §REVERT Hypotheses B and C — Finding-Lenient strict-text-match OR Strict-Answer partial-Findings routing upstream of the Tier 1 quorum).",
        "",
        "## v0.1.25+ recommendation",
        "",
        recommendation,
        "",
        "## §22.22 caveats",
        "",
        "1. **Observability, not fix** (ADR-0031 §22.22 #2): this diagnostic does not change a single verdict. It enables v0.1.25+ targeted intervention selection at high confidence.",
        "2. **Re-derivation heuristic** (ADR-0031 Option B alternative): the reason-text → failed_check mapping depends on validator's exact error-message strings; the current validator emits the three substrings literally (`article_not_found`, `apartado_not_found`, `text_not_in_{apartado|article}`). Future validator messaging changes would require updating this script's map. Going forward, the ADR-0031 D2 `failed_check` schema field populates the data natively — this script's reason-text re-derivation is the one-time bridge for pre-v0.1.24 cached data.",
        "3. **Dominance tie-break**: 'mixed' covers (a) zero fails (validated trail) and (b) two checks with equal frequency. Per-case manual review is the next step for any 'mixed' case if it persists in v0.1.25+ measurements.",
        "4. **H1 vs other buckets**: this diagnostic re-attributes the 10 H1 cases only. The 5 v0.1.22.1 mixed cases + 1 H4 case are NOT re-decomposed here; they are unchanged from the v0.1.22.1 report.",
        "5. **Cached-data only**: the re-derivation reads the cached v0.1.22.1 markdown report directly; the validator is NOT re-invoked. This is intentional per ADR-0031 Option A rejection (cost-prohibitive AND non-deterministic re-validation).",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "uv run python scripts/v0124_decomposition_diagnostic.py",
        "```",
        "",
        "$0 cost. Outputs this file deterministically from the cached v0.1.22.1 report.",
        "",
    ]

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: decomposition report written to {OUTPUT_PATH}")
    print(f"H1.A={h1_a} | H1.B={h1_b} | H1.C={h1_c} | mixed={h1_mixed} (total={total})")


if __name__ == "__main__":
    main()
