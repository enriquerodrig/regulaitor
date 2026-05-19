"""H8 — CLI wrapper for the evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.harness import main


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run RegulAItor evaluation harness")
    p.add_argument(
        "--gold-set",
        type=Path,
        default=Path("evals/gold_set.jsonl"),
        help="Path to the gold set jsonl",
    )
    p.add_argument(
        "--subset",
        type=int,
        default=None,
        help="Run only first N chat cases (proportional doc cases). None = full",
    )
    p.add_argument(
        "--cache-only",
        action="store_true",
        help="Fail on any cache miss (no live API calls). Default: live mode.",
    )
    p.add_argument(
        "--cases-file",
        type=Path,
        default=None,
        help=(
            "Newline-delimited case-id allowlist"
            " (e.g. evals/h15_calibration_ids.txt; '#' and blank lines ignored)."
            " None = all. NOTE: --subset, if also given, further truncates"
            " AFTER this filter."
        ),
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ids: set[str] | None = None
    if args.cases_file is not None:
        ids = {
            ln.strip()
            for ln in args.cases_file.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        }
    main(
        gold_set_path=args.gold_set,
        subset=args.subset,
        cache_only=args.cache_only,
        case_ids=ids,
    )
