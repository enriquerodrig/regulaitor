"""H13 — Council divergence-study harness.

USER-GATED: forcing the Council over the gold set spends real
Anthropic/OpenAI/Groq credit. Run only on explicit OK (the H12 T10
pattern). $0 unit tests mock nothing — they exercise the pure
summarizer; the graph-running paths are pragma-no-cover (T14 only).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from regulaitor.citation.schemas import AuditVerdict

logger = logging.getLogger("scripts.council_eval")

_REPORT_PATH = Path(__file__).resolve().parents[1] / "evals/reports/latest.council.md"


def summarize_divergence(
    rows: list[dict],
    *,
    n_selected: int | None = None,
    n_skipped: int = 0,
) -> dict:
    """Pure: aggregate per-case auditor-vs-council rows."""
    n_total = len(rows)
    n_auto = sum(1 for r in rows if r["council"].trigger_reason != "api_override")
    n_div = sum(1 for r in rows if r["council"].diverges_from_auditor)
    n_flagged = sum(
        1
        for r in rows
        if r["auditor_verdict"] == AuditVerdict.PASS
        and r["council"].council_verdict != AuditVerdict.PASS
    )
    return {
        "n_total": n_total,
        "n_auto_triggered": n_auto,
        "n_diverged": n_div,
        "n_auditor_pass_council_flagged": n_flagged,
        "n_selected": n_selected if n_selected is not None else n_total,
        "n_skipped": n_skipped,
    }


def render_report(summary: dict, rows: list[dict]) -> str:
    lines = [
        "# H13 — Council Divergence Study",
        "",
        "> Advisory Council (verdict unchanged). Honest reframe of the §16.3",
        "> 'Done when': this study IS the deliverable (decisions §H13).",
        "> Note: this study forces council_override=True on every case, so",
        "> n_auto_triggered is 0 by construction (all rows are api_override).",
        "> Organic RHR/high-severity trigger frequency is observable in production",
        "> observability logs (T10), not in this forced study.",
        "",
        (
            f"- Gold chat cases selected: {summary['n_selected']} | "
            f"Summarized: {summary['n_total']} | "
            f"Skipped (injection-blocked or council-unavailable): {summary['n_skipped']}"
        ),
        f"- Auto-triggered subset (RHR or high-severity): {summary['n_auto_triggered']}",
        f"- Council diverged from mechanical Auditor: {summary['n_diverged']}",
        f"- Auditor=PASS but Council flagged: " f"{summary['n_auditor_pass_council_flagged']}",
        "",
        "| case | auditor | council | agreement | diverges |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        cr = r["council"]
        lines.append(
            f"| {i} | {r['auditor_verdict'].value} | "
            f"{cr.council_verdict.value} | {cr.agreement} | "
            f"{cr.diverges_from_auditor} |"
        )
    return "\n".join(lines) + "\n"


def _run_gold(limit: int | None) -> tuple[list[dict], int, int]:  # pragma: no cover - paid path
    from evals.harness import load_gold_set  # read-only reuse

    from regulaitor.corpus import loader as corpus_loader
    from regulaitor.orchestration import graph

    chat_cases, _doc_cases = load_gold_set()
    # Corpus loader must be populated before the retriever runs (mirrors evals/harness.py).
    corpus_loader.warmup()
    selected = chat_cases[:limit] if limit is not None else chat_cases
    n_selected = len(selected)
    rows: list[dict] = []
    for case in selected:
        try:
            state = graph.run(
                query=case.entrada,
                corpus=case.corpus_esperado,
                language="es",
                case_id=f"council-eval-{case.id}",
                council_override=True,
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 — per-case backend errors must not crash the full paid run (mirrors evals/harness.py run_chat_case); case is counted as skipped
            logger.warning("council-eval case %s failed (skipped): %s", case.id, type(exc).__name__)
            continue
        if state.audited_answer is None or state.council_review is None:
            continue
        rows.append(
            {
                "auditor_verdict": state.audited_answer.verdict,
                "council": state.council_review,
            }
        )
    n_skipped = n_selected - len(rows)
    return rows, n_selected, n_skipped


def main() -> None:  # pragma: no cover - paid path
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    rows, n_selected, n_skipped = _run_gold(args.limit)
    summary = summarize_divergence(rows, n_selected=n_selected, n_skipped=n_skipped)
    _REPORT_PATH.write_text(render_report(summary, rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover
    main()
