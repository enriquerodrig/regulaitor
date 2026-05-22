# scripts/rerender_reports.py
"""v0.1.18 — One-shot $0 re-render for historical chat-mode eval reports.

The v0.1.18 plan originally relied on `make eval-from-cache` to re-render
`evals/reports/latest.md`. T3 controller-verification found that the
--cache-only flag (per evals/harness.py:204-208) caches ONLY the judge
layer — the chat graph (Retriever → Analyst → Auditor) still calls real
Anthropic API for the Analyst. With $0 user budget, that approach is
NOT $0 as the plan assumed. Pivoted T3 to use ONLY this script (truly
$0 — pure regex over markdown files).

This script does focused string-surgery on chat-mode reports:
1. Parse per-case rows of the form:
   `- **Citations**: emitted=[...] expected=[...] precision=X.XX recall=Y.YY`
2. Recompute precision/recall via the new v0.1.18
   evals.metrics.compute_citation_metrics (hierarchical containment).
3. Patch the values in place.
4. Recompute aggregate citation_precision_mean / citation_recall_mean
   from the new per-case values (excluding block cases per the existing
   aggregation rule in evals/metrics.py::aggregate — block cases have
   empty expected lists and are not counted in the mean).
5. Patch aggregate header values in place.

$0 throughout — no LLM call. Pure string surgery + Python recomputation
over already-rendered report markdown. Idempotent (re-running on
already-rendered files produces identical output).

Doc-mode reports (using `**Findings citations**` label) are OUT OF SCOPE
per spec §5: doc-mode uses the same compute_citation_metrics transitively,
so the fix applies to FUTURE doc-mode runs at v0.1.20. The 1 historical
doc-mode probe (docprobe-v1.2.md) stays frozen.

CLI: `python -m scripts.rerender_reports` (no args; processes the 15
known chat-mode report files).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from statistics import mean

from evals.metrics import compute_citation_metrics

# Chat-mode reports with the `- **Citations**: emitted=[...]` per-case row format.
# 15 files: latest.md (H10 baseline) + 14 H15-era reports.
# docprobe-v1.2.md uses `**Findings citations**` (doc-mode label) — out of scope.
REPORTS_TO_RERENDER: list[Path] = [
    Path("evals/reports/latest.md"),
    Path("evals/reports/latest.cost.md"),
    Path("evals/reports/latest.evaluation.md"),
    Path("evals/reports/h15/baseline-v1.0.md"),
    Path("evals/reports/h15/baseline-v1.0-probe.md"),
    Path("evals/reports/h15/candidate-v1.1-probe.md"),
    Path("evals/reports/h15/candidate-v1.2.md"),
    Path("evals/reports/h15/candidate-v1.2-probe.md"),
    Path("evals/reports/h15/h15_1-cand1.md"),
    Path("evals/reports/h15/h15_1-cand1-probe.md"),
    Path("evals/reports/h15/h15_1-cand2.md"),
    Path("evals/reports/h15/h15_1-holdout.md"),
    Path("evals/reports/h15/h15_2-cand1-probe.md"),
    Path("evals/reports/h15/holdout-v1.2-chat.md"),
    Path("evals/reports/h15/holdout-v1.2-chat-probe.md"),
]

# Matches lines like:
#   - **Citations**: emitted=['2.2', '3.1'] expected=['2', '3'] precision=0.00 recall=0.00
_CITATION_LINE_RE = re.compile(
    r"^(- \*\*Citations\*\*: emitted=)(\[[^\]]*\])( expected=)(\[[^\]]*\])"
    r"( precision=)(\d+\.\d+)( recall=)(\d+\.\d+)(.*)$",
    re.M,
)

# Matches aggregate header rows. Two known formats:
#   | citation_precision_mean | 0.18 | ... |
#   - **citation_precision_mean:** 0.18
# We match on either pattern.
_AGG_PRECISION_RE = re.compile(
    r"^(\| citation_precision(?:_mean)?\s*\|\s*)(\d+\.\d+)(\s*.*)$", re.M
)
_AGG_RECALL_RE = re.compile(r"^(\| citation_recall(?:_mean)?\s*\|\s*)(\d+\.\d+)(\s*.*)$", re.M)
_AGG_PRECISION_BULLET_RE = re.compile(
    r"^(- \*\*citation_precision_mean:\*\*\s*)(\d+\.\d+)(.*)$", re.M
)
_AGG_RECALL_BULLET_RE = re.compile(r"^(- \*\*citation_recall_mean:\*\*\s*)(\d+\.\d+)(.*)$", re.M)


def rerender_report(path: Path) -> dict[str, float | int]:
    """Patch all Citation rows + aggregate headers in `path` in place.

    Returns a summary dict with old/new aggregate values + row count.
    Excludes block cases (expected=[]) from the aggregate mean per the
    existing aggregation rule in evals/metrics.py::aggregate.
    """
    text = path.read_text(encoding="utf-8")

    old_precisions: list[float] = []
    old_recalls: list[float] = []
    new_precisions: list[float] = []
    new_recalls: list[float] = []
    new_precisions_non_block: list[float] = []
    new_recalls_non_block: list[float] = []

    def replace_line(m: re.Match[str]) -> str:
        emitted = ast.literal_eval(m.group(2))
        expected = ast.literal_eval(m.group(4))
        old_p = float(m.group(6))
        old_r = float(m.group(8))
        old_precisions.append(old_p)
        old_recalls.append(old_r)

        cm = compute_citation_metrics(
            emitted=[str(x) for x in emitted],
            expected=[str(x) for x in expected],
        )
        new_precisions.append(cm.precision)
        new_recalls.append(cm.recall)

        # Block cases (empty expected) are excluded from aggregate mean.
        if expected:
            new_precisions_non_block.append(cm.precision)
            new_recalls_non_block.append(cm.recall)

        return (
            f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
            f"{m.group(5)}{cm.precision:.2f}{m.group(7)}{cm.recall:.2f}{m.group(9)}"
        )

    new_text = _CITATION_LINE_RE.sub(replace_line, text)

    n_rows = len(new_precisions)
    if n_rows == 0:
        return {
            "rows": 0,
            "old_precision_mean": 0.0,
            "old_recall_mean": 0.0,
            "new_precision_mean": 0.0,
            "new_recall_mean": 0.0,
        }

    # Aggregate mean over non-block cases only (matches evals/metrics.py::aggregate).
    new_precision_mean = mean(new_precisions_non_block) if new_precisions_non_block else 0.0
    new_recall_mean = mean(new_recalls_non_block) if new_recalls_non_block else 0.0

    # Patch the aggregate header values via 4 possible formats.
    def replace_precision(m: re.Match[str]) -> str:
        return f"{m.group(1)}{new_precision_mean:.2f}{m.group(3)}"

    def replace_recall(m: re.Match[str]) -> str:
        return f"{m.group(1)}{new_recall_mean:.2f}{m.group(3)}"

    new_text = _AGG_PRECISION_RE.sub(replace_precision, new_text)
    new_text = _AGG_RECALL_RE.sub(replace_recall, new_text)
    new_text = _AGG_PRECISION_BULLET_RE.sub(replace_precision, new_text)
    new_text = _AGG_RECALL_BULLET_RE.sub(replace_recall, new_text)

    path.write_text(new_text, encoding="utf-8")

    return {
        "rows": n_rows,
        "old_precision_mean": float(mean(old_precisions)),
        "old_recall_mean": float(mean(old_recalls)),
        "new_precision_mean": float(new_precision_mean),
        "new_recall_mean": float(new_recall_mean),
    }


def main() -> int:
    # NOTE on printed deltas: old_precision_mean is a per-row mean INCLUDING
    # block cases (empty expected) while new_precision_mean EXCLUDES them
    # (matching evals/metrics.py::aggregate). On a re-run of an already-correct
    # file the on-disk values are byte-identical (the script is idempotent),
    # but the printed delta may be non-zero due to the differing denominators.
    # See ADR-0024 Consequences for the apples-to-oranges caveat.
    print("v0.1.18 rerender — applying hierarchical containment to historical reports")
    print()
    for path in REPORTS_TO_RERENDER:
        if not path.exists():
            print(f"  SKIP (not found): {path}")
            continue
        summary = rerender_report(path)
        if summary["rows"] == 0:
            print(f"  SKIP (no Citation rows): {path}")
            continue
        delta_p = summary["new_precision_mean"] - summary["old_precision_mean"]
        delta_r = summary["new_recall_mean"] - summary["old_recall_mean"]
        print(f"  {path}")
        print(f"    rows patched: {summary['rows']}")
        print(
            f"    precision_mean: {summary['old_precision_mean']:.2f} -> "
            f"{summary['new_precision_mean']:.2f} (delta={delta_p:+.2f})"
        )
        print(
            f"    recall_mean:    {summary['old_recall_mean']:.2f} -> "
            f"{summary['new_recall_mean']:.2f} (delta={delta_r:+.2f})"
        )
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
