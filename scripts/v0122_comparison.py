#!/usr/bin/env python
"""T4 Task 2: Compare v0.1.22-prod vs v0.1.20 ARM B baseline.

Reads:
  - evals/reports/v0.1.22/probe.md (chat-001..005)
  - evals/reports/v0.1.22/v0.1.22-prod-main.md (chat-006..030)
  - evals/reports/v0.1.22/v0.1.20-armB-baseline.md (from Task 1)

Extracts metrics, loads thresholds from evals/report.py, computes deltas,
and writes comparison.md with 7-row metric table + narrative + aggregate counts.

No API calls; $0 comparison.
"""

import ast
import re
from pathlib import Path
from statistics import mean


def extract_report_cases(markdown_path: str) -> dict[str, dict]:
    """Parse per-case data from a report markdown file (shared with v0122_extract_armb.py)."""
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    cases = {}

    # Split by ### case_id headers
    pattern = r"^### (?P<case_id>\S+)\n(?P<content>(?:.*?\n)*?)(?=^###|\Z)"
    for match in re.finditer(pattern, text, re.MULTILINE):
        case_id = match.group("case_id")
        content = match.group("content")

        # Parse fields
        verdict_match = re.search(r"actual=`(\w+)`", content)
        actual_verdict = verdict_match.group(1) if verdict_match else None

        severity_match = re.search(r"\*\*Severity\*\*.*?actual=`(\w+)`", content)
        actual_severity = severity_match.group(1) if severity_match else None

        # Expected verdict
        expected_verdict_match = re.search(r"expected=`(\w+)`\s+(✅|❌)", content)
        expected_verdict = expected_verdict_match.group(1) if expected_verdict_match else None
        verdict_match_symbol = expected_verdict_match.group(2) if expected_verdict_match else None

        # Expected severity
        expected_severity_match = re.search(
            r"\*\*Severity\*\*.*?expected=`(\w+)`\s+(✅|❌|➖)", content
        )
        expected_severity = expected_severity_match.group(1) if expected_severity_match else None
        severity_match_symbol = (
            expected_severity_match.group(2) if expected_severity_match else None
        )

        # Citations
        citations_match = re.search(r"emitted=(\[.*?\])", content)
        emitted_citations = []
        if citations_match:
            try:
                emitted_citations = ast.literal_eval(citations_match.group(1))
            except (ValueError, SyntaxError):
                emitted_citations = []

        expected_citations_match = re.search(r"expected=(\[.*?\])", content)
        expected_citations = []
        if expected_citations_match:
            try:
                expected_citations = ast.literal_eval(expected_citations_match.group(1))
            except (ValueError, SyntaxError):
                expected_citations = []

        # Citation metrics
        citation_precision_match = re.search(r"precision=([\d.]+)", content)
        citation_precision = (
            float(citation_precision_match.group(1)) if citation_precision_match else 0.0
        )

        citation_recall_match = re.search(r"recall=([\d.]+)", content)
        citation_recall = float(citation_recall_match.group(1)) if citation_recall_match else 0.0

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

        cases[case_id] = {
            "case_id": case_id,
            "actual_verdict": actual_verdict,
            "expected_verdict": expected_verdict,
            "verdict_match": verdict_match_symbol == "✅",
            "actual_severity": actual_severity,
            "expected_severity": expected_severity,
            "severity_match": severity_match_symbol == "✅",
            "emitted_citations": emitted_citations,
            "expected_citations": expected_citations,
            "citation_precision": citation_precision,
            "citation_recall": citation_recall,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
        }

    return cases


def extract_baseline_metrics(markdown_path: str) -> dict[str, float]:
    """Parse aggregate metrics from v0.1.20-armB-baseline.md."""
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    metrics = {}
    pattern = r"^\|\s*(\w+_(?:mean|rate))\s*\|\s*([\d.]+)\s*\|"
    for match in re.finditer(pattern, text, re.MULTILINE):
        metric_name = match.group(1)
        value = float(match.group(2))
        metrics[metric_name] = value

    return metrics


def load_thresholds() -> dict[str, tuple[float, float]]:
    """Load v0.1.20-bar and aspirational thresholds from evals/report.py."""
    # Hardcoded thresholds matching evals/report.py::_THRESHOLDS
    return {
        "faithfulness_mean": (0.65, 0.85),
        "answer_relevancy_mean": (0.55, 0.85),
        "context_precision_mean": (0.55, 0.80),
        "citation_precision_mean": (0.25, 0.90),
        "citation_recall_mean": (0.60, 0.80),
        "verdict_match_rate": (0.35, 0.85),
        "severity_match_rate": (0.35, 0.80),
    }


def main():
    """Compare v0.1.22-prod vs v0.1.20 ARM B baseline."""
    repo_root = Path(__file__).parent.parent
    reports_v0122 = repo_root / "evals" / "reports" / "v0.1.22"

    # Extract v0.1.22 prod cases
    probe_cases = extract_report_cases(str(reports_v0122 / "probe.md"))
    main_cases = extract_report_cases(str(reports_v0122 / "v0.1.22-prod-main.md"))

    all_cases = {**probe_cases, **main_cases}
    chat_cases = {
        k: v for k, v in all_cases.items() if k.startswith("chat-") and int(k.split("-")[1]) <= 30
    }

    # Extract baseline metrics
    baseline_metrics = extract_baseline_metrics(str(reports_v0122 / "v0.1.20-armB-baseline.md"))

    # Compute v0.1.22 aggregates (matching v0122_extract_armb.py logic)
    block_verdict = {"block", "requires_human_review"}
    non_block_cases = {
        k: v for k, v in chat_cases.items() if v["actual_verdict"] not in block_verdict
    }

    def safe_mean(values):
        return mean(values) if values else 0.0

    v0122_metrics = {
        "faithfulness_mean": safe_mean(
            [v["faithfulness"] for v in non_block_cases.values() if v["faithfulness"] > 0]
        ),
        "answer_relevancy_mean": safe_mean(
            [v["answer_relevancy"] for v in non_block_cases.values()]
        ),
        "context_precision_mean": safe_mean(
            [v["context_precision"] for v in non_block_cases.values()]
        ),
        "citation_precision_mean": safe_mean(
            [v["citation_precision"] for v in non_block_cases.values()]
        ),
        "citation_recall_mean": safe_mean([v["citation_recall"] for v in non_block_cases.values()]),
        "verdict_match_rate": sum(1 for v in chat_cases.values() if v["verdict_match"])
        / len(chat_cases),
        "severity_match_rate": sum(1 for v in chat_cases.values() if v["severity_match"])
        / len(chat_cases),
    }

    thresholds = load_thresholds()

    # Build comparison report
    lines = []
    lines.append("# Comparison: v0.1.22-prod vs v0.1.20 ARM B baseline")
    lines.append("")
    lines.append("**Run:** v0.1.22 probe + main (chat-001..030)")
    lines.append("**Baseline:** v0.1.20 ARM B (H10 30-case cohort)")
    lines.append("**Comparison date:** 2026-05-25")
    lines.append(
        "**Spec ref:** docs/superpowers/specs/2026-05-24-v0.1.22-paid-validation-design.md"
    )
    lines.append("")

    lines.append("## Metrics comparison (7-row bar table)")
    lines.append("")
    lines.append("| Metric | v0.1.22-prod | ARM B v0.1.20 | Delta | Bar | Pass | Improved |")
    lines.append("|---|---|---|---|---|---|---|")

    bar_pass_count = 0
    improved_count = 0

    for metric in [
        "faithfulness_mean",
        "answer_relevancy_mean",
        "context_precision_mean",
        "citation_precision_mean",
        "citation_recall_mean",
        "verdict_match_rate",
        "severity_match_rate",
    ]:
        prod_mean = v0122_metrics[metric]
        baseline_mean = baseline_metrics.get(metric, 0.0)
        delta = prod_mean - baseline_mean
        bar, _ = thresholds[metric]
        bar_pass = prod_mean >= bar
        improved = delta > 0

        if bar_pass:
            bar_pass_count += 1
            pass_mark = "✅"
        else:
            pass_mark = "❌"

        improved_mark = "✅" if improved else "➖"

        lines.append(
            f"| {metric} | {prod_mean:.2f} | {baseline_mean:.2f} | "
            f"{delta:+.2f} | ≥{bar:.2f} | {pass_mark} | {improved_mark} |"
        )

        if improved:
            improved_count += 1

    lines.append("")

    # Per-metric narrative
    lines.append("## Per-metric narrative")
    lines.append("")

    for metric in [
        "faithfulness_mean",
        "answer_relevancy_mean",
        "context_precision_mean",
        "citation_precision_mean",
        "citation_recall_mean",
        "verdict_match_rate",
        "severity_match_rate",
    ]:
        prod_mean = v0122_metrics[metric]
        baseline_mean = baseline_metrics.get(metric, 0.0)
        delta = prod_mean - baseline_mean
        bar, _ = thresholds[metric]
        bar_pass = "PASS" if prod_mean >= bar else "FAIL"

        lines.append(
            f"- **{metric}:** {prod_mean:.2f} vs baseline {baseline_mean:.2f} ({delta:+.2f}) "
            f"— bar {bar:.2f} {bar_pass}; "
            f"{'improvement' if delta > 0 else 'regression' if delta < 0 else 'no change'}"
        )

    lines.append("")

    # Aggregate verdict/severity counts
    pass_count = sum(1 for v in chat_cases.values() if v["actual_verdict"] == "pass")
    rhr_count = sum(
        1 for v in chat_cases.values() if v["actual_verdict"] == "requires_human_review"
    )
    block_count = sum(1 for v in chat_cases.values() if v["actual_verdict"] == "block")

    lines.append("## Aggregate verdict counts")
    lines.append("")
    lines.append(f"v0.1.22-prod: pass={pass_count} RHR={rhr_count} block={block_count}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"**{bar_pass_count}/7 metrics PASS bar in v0.1.22-prod**")
    lines.append(f"**{improved_count}/7 metrics beat v0.1.20-ARM-B baseline**")
    lines.append("")

    lines.append("## Note on per-citation audits")
    lines.append("")
    lines.append(
        "v0.1.22-prod has per-citation audit trail available per v0.1.21.1 D2 "
        "(evals/schemas.py::ChatCaseResult.per_citation_audits); v0.1.20-ARM-B has no trail "
        "(pre-D2) — T5 mechanism analysis (if pursued) runs on prod only."
    )

    output_file = reports_v0122 / "comparison.md"
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Comparison report: {output_file}")
    print(f"   {bar_pass_count}/7 metrics PASS v0.1.20-bar")
    print(f"   {improved_count}/7 metrics improved vs baseline")
    print(f"   {output_file.read_text(encoding='utf-8').count(chr(10))} lines")


if __name__ == "__main__":
    main()
