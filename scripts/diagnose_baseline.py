# scripts/diagnose_baseline.py
"""H15 — $0 frozen diagnostic. Classifies each chat-NNN case in the committed
evals/reports/latest.md by the verdict-failure mechanism. No LLM, no network.

Three Analyst-attributable failure modes (all imply verdict mismatch):
over_citation : Analyst emitted citations AND recall>0 (correct article IS cited,
                buried in noise -> false RHR/BLOCK).
no_answer     : Analyst emitted nothing (no usable Answer -> audited_answer None
                -> auto-RHR).
wrong_article : Analyst active (emitted non-empty) but recall==0 (retrieved/cited
                entirely wrong articles — a distinct third failure mode).
other         : verdict matched (no failure to explain).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_CASE_RE = re.compile(r"^### (chat-\d+)\s*$", re.M)
_VERDICT_RE = re.compile(r"\*\*Verdict\*\*: actual=`([^`]+)` expected=`([^`]+)`")
_CIT_RE = re.compile(
    r"\*\*Citations\*\*: emitted=(\[[^\]]*\]) expected=(\[[^\]]*\]) "
    r"precision=([\d.]+) recall=([\d.]+)"
)


def parse_report(markdown: str) -> list[dict]:
    """Extract per-chat-case fields from the report's per-case appendix."""
    cases: list[dict] = []
    blocks = _CASE_RE.split(markdown)
    for i in range(1, len(blocks), 2):
        cid = blocks[i]
        body = blocks[i + 1]
        vm = _VERDICT_RE.search(body)
        cm = _CIT_RE.search(body)
        if vm is None or cm is None:
            continue
        emitted = ast.literal_eval(cm.group(1))
        cases.append(
            {
                "id": cid,
                "actual": vm.group(1),
                "expected": vm.group(2),
                "emitted": [str(x) for x in emitted],
                "recall": float(cm.group(4)),
            }
        )
    return cases


def classify_case(case: dict) -> str:
    """Classify a verdict-failure mechanism.

    other        : the verdict actually matched (no failure to explain).
    no_answer    : verdict mismatch, Analyst emitted nothing (no usable Answer
                   -> audited_answer None -> auto-RHR).
    over_citation: verdict mismatch, Analyst emitted citations AND recall>0
                   (the correct article IS cited, buried in noise -> false RHR/BLOCK).
    wrong_article: verdict mismatch, Analyst emitted citations but recall==0
                   (Analyst active but retrieved/cited entirely wrong articles —
                   a distinct third Analyst-attributable failure mode; e.g.
                   chat-017 emits 9 articles, none correct).
    """
    if case["actual"] == case["expected"]:
        return "other"
    if not case["emitted"]:
        return "no_answer"
    if case["recall"] > 0.0:
        return "over_citation"
    return "wrong_article"


def main(report_path: str = "evals/reports/latest.md") -> int:
    md = Path(report_path).read_text(encoding="utf-8")
    cases = parse_report(md)
    counts = {"over_citation": 0, "no_answer": 0, "wrong_article": 0, "other": 0}
    rows: list[str] = []
    for c in cases:
        label = classify_case(c)
        counts[label] += 1
        rows.append(f"{c['id']}\t{c['actual']}<-{c['expected']}\t{label}")
    n = len(cases)
    print(f"# H15 frozen diagnostic — {report_path} ({n} chat cases)")
    for r in rows:
        print(r)
    print("\n## Mechanism counts")
    for k, v in counts.items():
        pct = (v / n * 100) if n else 0.0
        print(f"{k}: {v}/{n} ({pct:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*(sys.argv[1:2] or [])))
