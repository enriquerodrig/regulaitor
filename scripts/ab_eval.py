"""H12 — A/B cost-vs-quality eval wrapper.

Runs the H8 harness once per non-Sonnet arm with REGULAITOR_ROUTER_MODE set so
the (read-only) Analyst's router resolves to that arm's model. The Sonnet arm
is NOT run here — its frozen H10/H11 baseline is reused in cost_analysis.md.

Path B report isolation: harness.main always writes evals/reports/latest.md
(no report_path kwarg exists). After each arm run we copy that file to
evals/reports/latest.<mode>.md, then restore the committed canonical baseline
via `git checkout HEAD -- evals/reports/latest.md`. This ensures the committed
Sonnet baseline is never left clobbered between arms or after a failed run.
Isolation is factored into the injectable `_isolate_report()` so $0 mocked
unit tests can stub it and never mutate the working tree (T8 review).

USER-GATED: real arms cost Anthropic/OpenAI/Groq credit; run only on explicit OK.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from evals.harness import _REPORT_PATH
from evals.harness import main as _harness_main

# (router mode, human label) — Sonnet excluded by design (frozen baseline).
AB_ARMS: list[tuple[str, str]] = [("evaluation", "gpt-4o"), ("cost", "llama-groq")]

# Deliberate private import: harness OWNS the path it writes. Single source of
# truth — re-declaring the literal here would silently diverge (empty per-arm
# reports in the paid Task-10 run) if harness ever relocates its report.
# Rebinding `ab_eval._REPORT_PATH` in tests still works (module-local name).


def _isolate_report(mode: str) -> None:
    """Path-B report isolation: snapshot this arm's report to a per-arm path,
    then restore the canonical committed baseline so a real Task-10 arm run
    never leaves evals/reports/latest.md clobbered.

    Extracted as a module-level function so unit tests can monkeypatch it to a
    no-op. The env set/restore contract is what those tests verify; real git/file
    mutation must not run in $0 mocked unit tests.

    The `git checkout` baseline-restore is intentionally fatal: `check=True`
    raises CalledProcessError, which aborts the whole A/B run (remaining arms
    skipped) rather than continuing with a clobbered/uncertain baseline.
    Recovery is the Task-10 pre-flight `cp evals/reports/latest.md /tmp/...`
    backup documented in the plan.
    """
    arm_report = _REPORT_PATH.with_name(f"latest.{mode}.md")
    if _REPORT_PATH.exists():
        arm_report.write_bytes(_REPORT_PATH.read_bytes())

    # Restore the committed canonical baseline (Sonnet numbers) so it is
    # never left clobbered by a non-Sonnet arm run.
    subprocess.run(
        ["git", "checkout", "HEAD", "--", str(_REPORT_PATH)],
        check=True,
    )


def run_arm(mode: str, *, gold_set: str, subset: int | None) -> None:
    """Run the full harness for one arm with the router env override set,
    restoring the prior env (exact prior value, or unset) afterwards.

    Path B: After _harness_main returns, delegates to _isolate_report(mode) to
    copy latest.md -> latest.<mode>.md and restore the committed canonical
    baseline from git so the Sonnet baseline is never left clobbered on disk.
    """
    prev = os.environ.get("REGULAITOR_ROUTER_MODE")
    os.environ["REGULAITOR_ROUTER_MODE"] = mode
    try:
        _harness_main(gold_set_path=Path(gold_set), subset=subset)
        _isolate_report(mode)
    finally:
        # Always restore the prior env value, even if an exception was raised.
        if prev is None:
            os.environ.pop("REGULAITOR_ROUTER_MODE", None)
        else:
            os.environ["REGULAITOR_ROUTER_MODE"] = prev


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="H12 A/B cost-vs-quality eval")
    p.add_argument("--gold-set", default="evals/gold_set.jsonl")
    p.add_argument(
        "--subset",
        type=int,
        default=None,
        help="First N chat cases (proportional docs). None = full 40.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    for mode, label in AB_ARMS:
        print(f"=== A/B arm: {label} (REGULAITOR_ROUTER_MODE={mode}) ===", flush=True)
        run_arm(mode, gold_set=args.gold_set, subset=args.subset)
