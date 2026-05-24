"""v0.1.20 — paid validation runner (mirrors scripts/h15_run.py).

Routes harness report output to evals/reports/v0.1.20/<tag>.md after each run,
then restores the committed canonical evals/reports/latest.md (Path-B isolation
pattern from h15_run.py + ab_eval.py). The harness writes its report
unconditionally to evals/reports/latest.md; we snapshot+restore so the
canonical baseline is never left clobbered by a paid v0.1.20 run.

USER-GATED: real runs cost Anthropic credit; invoke only on explicit OK after
the spec's SKIP/PROCEED gate (T3) authorizes. Invoke as:

  uv run --env-file .env python -m scripts.v0120_run --version v1.0 \\
      --cases-file evals/v0120_probe_a_ids.txt --tag armA-probe

Both arms run via SEPARATE invocations (full process restart between) per
spec §4 apples-to-apples controls.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from evals.harness import _REPORT_PATH
from evals.harness import main as _harness_main

_V0120_DIR = Path("evals/reports/v0.1.20")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader (h15_run.py precedent)."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(tag: str) -> None:
    """Path-B isolation: snapshot this run's report to evals/reports/v0.1.20/<tag>.md,
    then restore the committed canonical evals/reports/latest.md.

    Mirrors scripts/h15_run.py::_isolate_report exactly. If the harness process
    is hard-killed between writing latest.md and this call, recover the
    committed baseline with `git checkout HEAD -- evals/reports/latest.md`.
    """
    _V0120_DIR.mkdir(parents=True, exist_ok=True)
    dest = _V0120_DIR / f"{tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def run(*, version: str, cases_file: Path, tag: str) -> None:
    """Run the harness for ONE arm with env routing, snapshot, restore.

    version: "v1.0" (ARM A; baseline) or "v1.4" (ARM B; candidate).
    cases_file: allowlist (probe 5 ids OR main 59 ids).
    tag: report basename under evals/reports/v0.1.20/ (e.g. "armA-probe").
    """
    ids = _load_case_ids(cases_file)
    prev = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")
    os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = version
    try:
        try:
            # subset=None: the case_ids allowlist is the truth source. NO --subset
            # truncation (would silently drop cases beyond the count).
            _harness_main(subset=None, case_ids=ids)
        finally:
            # Snapshot + restore canonical latest.md even if the (paid) harness
            # crashed mid/post-run. h15_run.py precedent: this exception (if
            # any) replaces the original — acceptable per ab_eval.py pattern.
            _isolate_report(tag)
    finally:
        if prev is None:
            os.environ.pop("REGULAITOR_ANALYST_PROMPT_VERSION", None)
        else:
            os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = prev


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="v0.1.20 USER-GATED paid validation runner")
    p.add_argument(
        "--version",
        required=True,
        choices=["v1.0", "v1.4"],
        help="Analyst prompt version (v1.0 ARM A baseline / v1.4 ARM B candidate)",
    )
    p.add_argument(
        "--cases-file",
        type=Path,
        required=True,
        help="Newline-delimited case-id allowlist (e.g. evals/v0120_probe_a_ids.txt)",
    )
    p.add_argument(
        "--tag",
        required=True,
        help="Report basename under evals/reports/v0.1.20/ (e.g. armA-probe, armB-main)",
    )
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(version=a.version, cases_file=a.cases_file, tag=a.tag)
