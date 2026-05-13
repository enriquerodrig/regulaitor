"""H9 — CLI wrapper for the red team runner."""

from __future__ import annotations

import argparse
from pathlib import Path

from redteam.runner import main


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run RegulAItor red team suite")
    p.add_argument(
        "--attacks",
        type=Path,
        default=Path("redteam/attacks.jsonl"),
        help="Path to the attacks jsonl",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Run only deterministic doc-mode attacks (no LLM, ~30s, $0).",
    )
    p.add_argument(
        "--baseline",
        type=float,
        default=None,
        help="Pre-improvement baseline block_rate to record in report.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(attacks_path=args.attacks, smoke=args.smoke, baseline=args.baseline)
