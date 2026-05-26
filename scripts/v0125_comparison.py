#!/usr/bin/env python
# ruff: noqa: E501  # diagnostic script; long lines acceptable
"""T2 Deliverable: Compare v0.1.25-prod vs v0.1.22-prod baseline ($0 cache analysis).

Reads:
  - evals/reports/v0.1.25/v0.1.25-prod.md (30 cases merged)
  - evals/reports/v0.1.22/probe.md + v0.1.22/v0.1.22-prod-main.md (cached baseline)

Outputs:
  - evals/reports/v0.1.25/comparison.md

Computes 7-metric A/B table, verdict counts, narrative.
Applies v0.1.24 O1 re-aggregation (acceptable_verdicts for 6 designated cases).

No API calls; $0 comparison.
"""

import re
from pathlib import Path
from statistics import mean

# v0.1.24 O1: 6 designated content-safety cases with acceptable_verdicts=[block, RHR, pass]
ACCEPTABLE_VERDICT_CASES = {
    "chat-014",
    "chat-015",
    "chat-029",
    "chat-030",
    "nis2-006",
    "dora-006",
}


def extract_report_cases(markdown_path: str) -> dict[str, dict]:
    """Parse per-case data from report markdown (shared pattern)."""
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    cases = {}

    # Split by ### case_id headers
    pattern = r"^### (?P<case_id>\S+)\n(?P<content>(?:.*?\n)*?)(?=^###|\Z)"
    for match in re.finditer(pattern, text, re.MULTILINE):
        case_id = match.group("case_id")
        content = match.group("content")

        # Parse verdict
        verdict_match = re.search(r"actual=`(\w+)`", content)
        actual_verdict = verdict_match.group(1) if verdict_match else None

        # RAG metrics
        rag_line_match = re.search(
            r"\*\*RAG metrics\*\*.*?faithfulness=([\d.]+) "
            r"answer_relevancy=([\d.]+) "
            r"context_precision=([\d.]+) "
            r"context_recall=([\d.]+)",
            content,
        )
        faithfulness = 0.0
        answer_relevancy = 0.0
        context_precision = 0.0
        context_recall = 0.0
        if rag_line_match:
            faithfulness = float(rag_line_match.group(1))
            answer_relevancy = float(rag_line_match.group(2))
            context_precision = float(rag_line_match.group(3))
            context_recall = float(rag_line_match.group(4))

        # Citations
        citations_match = re.search(r"precision=([\d.]+)\s+recall=([\d.]+)", content)
        citation_precision = 0.0
        citation_recall = 0.0
        if citations_match:
            citation_precision = float(citations_match.group(1))
            citation_recall = float(citations_match.group(2))

        # Verdict match (expected=`X` expected_symbol)
        expected_verdict_match = re.search(r"expected=`(\w+)`\s+(✅|❌)", content)
        verdict_match_symbol = expected_verdict_match.group(2) if expected_verdict_match else None

        # Severity match
        expected_severity_match = re.search(
            r"\*\*Severity\*\*.*?expected=`(\w+)`\s+(✅|❌)", content
        )
        severity_match_symbol = (
            expected_severity_match.group(2) if expected_severity_match else None
        )

        cases[case_id] = {
            "case_id": case_id,
            "actual_verdict": actual_verdict,
            "verdict_match": verdict_match_symbol == "✅",
            "severity_match": severity_match_symbol == "✅",
            "citation_precision": citation_precision,
            "citation_recall": citation_recall,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
        }

    return cases


def apply_acceptable_verdicts_recount(cases: dict[str, dict]) -> dict[str, dict]:
    """Apply v0.1.24 O1 re-aggregation: treat acceptable_verdicts as PASS for verdict_match."""
    for case_id in list(cases.keys()):
        if case_id in ACCEPTABLE_VERDICT_CASES:
            # These cases have acceptable_verdicts=[block, RHR, pass]
            # So any of these verdicts should count as PASS for verdict_match
            actual = cases[case_id]["actual_verdict"]
            if actual in ("block", "requires_human_review", "pass"):
                cases[case_id]["verdict_match"] = True
    return cases


def load_thresholds() -> dict[str, tuple[float, float]]:
    """Load v0.1.20-bar and aspirational thresholds."""
    return {
        "faithfulness_mean": (0.65, 0.85),
        "answer_relevancy_mean": (0.55, 0.85),
        "context_precision_mean": (0.55, 0.80),
        "citation_precision_mean": (0.25, 0.90),
        "citation_recall_mean": (0.60, 0.80),
        "verdict_match_rate": (0.35, 0.85),
        "severity_match_rate": (0.35, 0.80),
    }


def compute_metrics(cases: dict[str, dict]) -> dict[str, float]:
    """Compute 7 metrics from case data."""
    if not cases:
        return {}

    metrics = {
        "faithfulness_mean": mean(c["faithfulness"] for c in cases.values()),
        "answer_relevancy_mean": mean(c["answer_relevancy"] for c in cases.values()),
        "context_precision_mean": mean(c["context_precision"] for c in cases.values()),
        "citation_precision_mean": mean(c["citation_precision"] for c in cases.values()),
        "citation_recall_mean": mean(c["citation_recall"] for c in cases.values()),
        "verdict_match_rate": mean(1.0 if c["verdict_match"] else 0.0 for c in cases.values()),
        "severity_match_rate": mean(1.0 if c["severity_match"] else 0.0 for c in cases.values()),
    }
    return metrics


def main():
    """Compare v0.1.25-prod vs v0.1.22-prod."""
    # Load v0.1.25-prod
    v0125_path = Path("evals/reports/v0.1.25/v0.1.25-prod.md")
    if not v0125_path.exists():
        raise FileNotFoundError(f"v0.1.25-prod not found: {v0125_path}")

    v0125_cases = extract_report_cases(str(v0125_path))

    # Load v0.1.22-prod (combine probe + main)
    probe_path_v0122 = Path("evals/reports/v0.1.22/probe.md")
    main_path_v0122 = Path("evals/reports/v0.1.22/v0.1.22-prod-main.md")

    if not probe_path_v0122.exists():
        raise FileNotFoundError(f"v0.1.22 probe not found: {probe_path_v0122}")
    if not main_path_v0122.exists():
        raise FileNotFoundError(f"v0.1.22 main not found: {main_path_v0122}")

    v0122_cases = {}
    v0122_cases.update(extract_report_cases(str(probe_path_v0122)))
    v0122_cases.update(extract_report_cases(str(main_path_v0122)))

    # Apply v0.1.24 O1 re-aggregation to both sides
    v0125_cases = apply_acceptable_verdicts_recount(v0125_cases)
    v0122_cases = apply_acceptable_verdicts_recount(v0122_cases)

    # Compute metrics
    v0125_metrics = compute_metrics(v0125_cases)
    v0122_metrics = compute_metrics(v0122_cases)

    # Load thresholds
    thresholds = load_thresholds()

    # Verdict counts
    v0125_verdicts = {
        "pass": sum(1 for c in v0125_cases.values() if c["actual_verdict"] == "pass"),
        "requires_human_review": sum(
            1 for c in v0125_cases.values() if c["actual_verdict"] == "requires_human_review"
        ),
        "block": sum(1 for c in v0125_cases.values() if c["actual_verdict"] == "block"),
    }

    v0122_verdicts = {
        "pass": sum(1 for c in v0122_cases.values() if c["actual_verdict"] == "pass"),
        "requires_human_review": sum(
            1 for c in v0122_cases.values() if c["actual_verdict"] == "requires_human_review"
        ),
        "block": sum(1 for c in v0122_cases.values() if c["actual_verdict"] == "block"),
    }

    # Build report
    report_lines = [
        "# Comparison: v0.1.25-prod vs v0.1.22-prod baseline",
        "",
        "**Run:** v0.1.25 probe + main (chat-001..030)",
        "**Baseline:** v0.1.22-prod (H10 30-case cohort)",
        "**Comparison date:** 2026-05-26",
        "**Spec ref:** docs/superpowers/specs/v0.1.25-auditor-partial-routing-design.md",
        "**Note:** Metrics computed with v0.1.24 O1 re-aggregation (acceptable_verdicts={block, RHR, pass} "
        "for 6 designated content-safety cases: chat-014/015/029/030 + nis2-006/dora-006)",
        "",
        "## Metrics comparison (7-row bar table)",
        "",
        "| Metric | v0.1.25-prod | v0.1.22-prod | Delta | Bar | Pass | Improved |",
        "|---|---|---|---|---|---|---|",
    ]

    # Metric rows
    for metric_name in [
        "faithfulness_mean",
        "answer_relevancy_mean",
        "context_precision_mean",
        "citation_precision_mean",
        "citation_recall_mean",
        "verdict_match_rate",
        "severity_match_rate",
    ]:
        v0125_val = v0125_metrics.get(metric_name, 0.0)
        v0122_val = v0122_metrics.get(metric_name, 0.0)
        delta = v0125_val - v0122_val
        bar_val, aspirational_val = thresholds.get(metric_name, (0.0, 0.0))

        # Determine pass/improved symbols
        pass_symbol = "✅" if v0125_val >= bar_val else "❌"
        if delta > 0.005:
            improved_symbol = "✅"
        elif delta < -0.005:
            improved_symbol = "➖"
        else:
            improved_symbol = "➖"

        delta_str = f"{delta:+.2f}"
        report_lines.append(
            f"| {metric_name} | {v0125_val:.2f} | {v0122_val:.2f} | {delta_str} | "
            f"≥{bar_val:.2f} | {pass_symbol} | {improved_symbol} |"
        )

    report_lines.extend(
        [
            "",
            "## Per-metric narrative",
            "",
        ]
    )

    # Narrative
    for metric_name in [
        "faithfulness_mean",
        "answer_relevancy_mean",
        "context_precision_mean",
        "citation_precision_mean",
        "citation_recall_mean",
        "verdict_match_rate",
        "severity_match_rate",
    ]:
        v0125_val = v0125_metrics.get(metric_name, 0.0)
        v0122_val = v0122_metrics.get(metric_name, 0.0)
        delta = v0125_val - v0122_val
        bar_val, _ = thresholds.get(metric_name, (0.0, 0.0))

        pass_status = "PASS" if v0125_val >= bar_val else "FAIL"
        trend = "improvement" if delta > 0.005 else ("regression" if delta < -0.005 else "flat")

        report_lines.append(
            f"- **{metric_name}:** {v0125_val:.2f} vs baseline {v0122_val:.2f} "
            f"({delta:+.2f}) — bar {bar_val:.2f} {pass_status}; {trend}"
        )

    report_lines.extend(
        [
            "",
            "## Aggregate verdict counts",
            "",
            f"v0.1.25-prod: pass={v0125_verdicts['pass']} "
            f"RHR={v0125_verdicts['requires_human_review']} "
            f"block={v0125_verdicts['block']}",
            "",
            f"v0.1.22-prod: pass={v0122_verdicts['pass']} "
            f"RHR={v0122_verdicts['requires_human_review']} "
            f"block={v0122_verdicts['block']}",
            "",
            "## Summary",
            "",
            f"**{sum(1 for m in [v0125_metrics.get(k, 0.0) >= thresholds.get(k, (0.0, 0.0))[0] for k in ['faithfulness_mean', 'answer_relevancy_mean', 'context_precision_mean', 'citation_precision_mean', 'citation_recall_mean', 'verdict_match_rate', 'severity_match_rate']])} / 7 metrics PASS bar in v0.1.25-prod**",
            "",
            "## Note on per-citation audits",
            "",
            "v0.1.25-prod has per-citation audit trail available per v0.1.21.1 D2 "
            "(evals/schemas.py::ChatCaseResult.per_citation_audits); T6 mechanism analysis "
            "runs on prod only.",
        ]
    )

    # Write output
    output_path = Path("evals/reports/v0.1.25/comparison.md")
    output_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"OK: Comparison report written to {output_path}")


if __name__ == "__main__":
    main()
