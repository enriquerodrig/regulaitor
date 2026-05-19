"""H15 — USER-GATED calibration/holdout runner.

Runs the H8 harness with REGULAITOR_ANALYST_PROMPT_VERSION set to the requested
prompt version, restricted to a case-id file, then snapshots the report to
evals/reports/h15/<tag>.md and restores the committed canonical
evals/reports/latest.md (mirrors scripts/ab_eval.py Path-B isolation, T8-hardened).

USER-GATED: real runs cost Anthropic credit; invoke only on explicit OK after a
--limit probe and a cost-tally warning. Invoke as:
  uv run --env-file .env python -m scripts.h15_run --version v1.0 \\
      --cases-file evals/h15_calibration_ids.txt --tag baseline-v1.0 --limit 3

Invoke from the repo root: `_H15_DIR` and the harness's `_REPORT_PATH` are repo-root-relative.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from evals.harness import _REPORT_PATH
from evals.harness import main as _harness_main

_H15_DIR = Path("evals/reports/h15")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader (Task-2 review precedent;
    the committed id files carry `#` header comment lines)."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(tag: str) -> None:
    """Path-B isolation: snapshot this run's report to evals/reports/h15/<tag>.md,
    then restore the committed canonical evals/reports/latest.md (so a paid H15
    run never leaves the canonical baseline clobbered). Mirrors
    scripts/ab_eval._isolate_report; injectable so $0 mocked tests stub it.

    If the harness process is hard-killed between writing latest.md and this call,
    recover the committed baseline with `git checkout HEAD -- evals/reports/latest.md`;
    the controller's documented Task-6 pre-flight `cp evals/reports/latest.md` backup
    is the external safety net.
    """
    _H15_DIR.mkdir(parents=True, exist_ok=True)
    dest = _H15_DIR / f"{tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def run(*, version: str, cases_file: Path, tag: str, limit: int | None) -> None:
    ids = _load_case_ids(cases_file)
    prev = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")
    os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = version
    try:
        try:
            _harness_main(subset=limit, case_ids=ids)
        finally:
            # Snapshot + restore canonical latest.md even if the (paid) harness
            # crashed mid/post-run — otherwise a crash leaves the committed
            # frozen baseline clobbered with no snapshot (frozen-baseline
            # integrity governs the entire H15 A/B). If _isolate_report itself
            # raises (e.g. git checkout fails) that replaces the original
            # exception — acceptable and consistent with ab_eval's fatal check=True.
            _isolate_report(tag)
    finally:
        if prev is None:
            os.environ.pop("REGULAITOR_ANALYST_PROMPT_VERSION", None)
        else:
            os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = prev


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="H15 USER-GATED calibration/holdout runner")
    p.add_argument("--version", required=True, help="Analyst prompt version, e.g. v1.0 / v1.1")
    p.add_argument(
        "--cases-file",
        type=Path,
        required=True,
        help=(
            "Newline-delimited case-id allowlist"
            " (e.g. evals/h15_calibration_ids.txt; '#'/blank lines skipped)."
        ),
    )
    p.add_argument("--tag", required=True, help="report basename under evals/reports/h15/")
    p.add_argument("--limit", type=int, default=None, help="probe: first N chat cases")
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(version=a.version, cases_file=a.cases_file, tag=a.tag, limit=a.limit)
