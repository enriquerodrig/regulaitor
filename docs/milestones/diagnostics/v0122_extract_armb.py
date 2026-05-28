#!/usr/bin/env python
"""T4 Task 1: Extract ARM B baseline from v0.1.20 reports.

Reads:
  - evals/reports/v0.1.20/armB-probe.md (chat-001..005)
  - evals/reports/v0.1.20/armB-main.md (chat-006..030 + others)

Filters to chat-001..030, parses per-case metrics, aggregates, and writes:
  - evals/reports/v0.1.22/v0.1.20-armB-baseline.md

No API calls; $0 data extraction.
"""

import ast
import re
from pathlib import Path
from statistics import mean


def extract_report_cases(markdown_path: str) -> dict[str, dict]:
    """Parse per-case data from a report markdown file.

    Returns: {case_id: {verdict, severity, citations, metrics, ...}}
    """
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

        # Expected verdict from ✅/❌ symbol after expected=
        expected_verdict_match = re.search(r"expected=`(\w+)`\s+(✅|❌)", content)
        expected_verdict = expected_verdict_match.group(1) if expected_verdict_match else None
        verdict_match_symbol = expected_verdict_match.group(2) if expected_verdict_match else None

        # Expected severity similarly
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


def main():
    """Extract v0.1.20 ARM B baseline from two report files."""
    repo_root = Path(__file__).parent.parent
    reports_v0120 = repo_root / "evals" / "reports" / "v0.1.20"
    reports_v0122 = repo_root / "evals" / "reports" / "v0.1.22"

    # Ensure output directory exists
    reports_v0122.mkdir(parents=True, exist_ok=True)

    # Extract from both files
    probe_cases = extract_report_cases(str(reports_v0120 / "armB-probe.md"))
    main_cases = extract_report_cases(str(reports_v0120 / "armB-main.md"))

    # Combine and filter to chat-001..030
    all_cases = {**probe_cases, **main_cases}
    chat_cases = {
        k: v for k, v in all_cases.items() if k.startswith("chat-") and int(k.split("-")[1]) <= 30
    }

    # Verify all 30 cases present
    expected_ids = {f"chat-{i:03d}" for i in range(1, 31)}
    actual_ids = set(chat_cases.keys())
    missing = expected_ids - actual_ids
    if missing:
        raise ValueError(f"Missing cases: {sorted(missing)}")

    # Aggregate metrics (skip block cases for ragas metrics)
    block_verdict = {"block", "requires_human_review"}
    non_block_cases = {
        k: v for k, v in chat_cases.items() if v["actual_verdict"] not in block_verdict
    }

    def safe_mean(values):
        return mean(values) if values else 0.0

    faithfulness_mean = safe_mean(
        [v["faithfulness"] for v in non_block_cases.values() if v["faithfulness"] > 0]
    )
    answer_relevancy_mean = safe_mean([v["answer_relevancy"] for v in non_block_cases.values()])
    context_precision_mean = safe_mean([v["context_precision"] for v in non_block_cases.values()])
    citation_precision_mean = safe_mean([v["citation_precision"] for v in non_block_cases.values()])
    citation_recall_mean = safe_mean([v["citation_recall"] for v in non_block_cases.values()])

    # Verdict and severity match rates
    verdict_matches = sum(1 for v in chat_cases.values() if v["verdict_match"])
    verdict_match_rate = verdict_matches / len(chat_cases) if chat_cases else 0.0

    severity_matches = sum(1 for v in chat_cases.values() if v["severity_match"])
    severity_match_rate = severity_matches / len(chat_cases) if chat_cases else 0.0

    # Build report
    lines = []
    lines.append("# RegulAItor — ARM B Baseline Extraction (v0.1.20)")
    lines.append("")
    lines.append("**Source:** v0.1.20 armB-probe.md + armB-main.md")
    lines.append("**Scope:** H10 chat-001..030 (30 cases)")
    lines.append("**Extraction:** 2026-05-25 (v0.1.22 T4 Task 1)")
    lines.append("")

    lines.append("## Aggregate metrics (ARM B baseline)")
    lines.append("")
    lines.append("| Metric | Mean |")
    lines.append("|---|---|")
    lines.append(f"| faithfulness_mean | {faithfulness_mean:.2f} |")
    lines.append(f"| answer_relevancy_mean | {answer_relevancy_mean:.2f} |")
    lines.append(f"| context_precision_mean | {context_precision_mean:.2f} |")
    lines.append(f"| citation_precision_mean | {citation_precision_mean:.2f} |")
    lines.append(f"| citation_recall_mean | {citation_recall_mean:.2f} |")
    lines.append(f"| verdict_match_rate | {verdict_match_rate:.2f} |")
    lines.append(f"| severity_match_rate | {severity_match_rate:.2f} |")
    lines.append("")

    lines.append("## Per-case appendix")
    lines.append("")
    for case_id in sorted(chat_cases.keys()):
        case = chat_cases[case_id]
        lines.append(f"### {case_id}")
        lines.append("")
        lines.append(
            f"- **Verdict:** actual=`{case['actual_verdict']}` "
            f"expected=`{case['expected_verdict']}`"
        )
        lines.append(
            f"- **Severity:** actual=`{case['actual_severity']}` "
            f"expected=`{case['expected_severity']}`"
        )
        lines.append(
            f"- **Citations:** emitted={case['emitted_citations']} "
            f"expected={case['expected_citations']}"
        )
        lines.append(
            f"  - precision={case['citation_precision']:.2f} recall={case['citation_recall']:.2f}"
        )
        lines.append(
            f"- **RAG metrics:** faithfulness={case['faithfulness']:.2f} "
            f"answer_relevancy={case['answer_relevancy']:.2f} "
            f"context_precision={case['context_precision']:.2f} "
            f"context_recall={case['context_recall']:.2f}"
        )
        lines.append("")

    output_file = reports_v0122 / "v0.1.20-armB-baseline.md"
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Extracted ARM B baseline: {output_file}")
    print("[PASS] 30 cases verified")
    print(f"[INFO] {output_file.read_text(encoding='utf-8').count(chr(10))} lines")


if __name__ == "__main__":
    main()
