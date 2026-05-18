"""CLI wrapper for regulaitor.corpus.ingest.run.

Usage:
    python -m scripts.ingest --corpus ai_act --lang es,en
    python -m scripts.ingest --force-fetch --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from regulaitor.corpus.ingest import run


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regulaitor.ingest",
        description="Ingest a regulatory corpus from EUR-Lex.",
    )
    p.add_argument("--corpus", choices=["ai_act", "gdpr", "nis2", "dora", "all"], default="all")
    p.add_argument("--lang", choices=["es", "en", "all"], default="all")
    p.add_argument("--force-fetch", action="store_true", help="Ignore HTTP 304 cache")
    p.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Reprocess all articles, ignore hash cache",
    )
    p.add_argument(
        "--no-html-fallback",
        action="store_true",
        help="Disable HTML fallback when Formex fails",
    )
    p.add_argument("--dry-run", action="store_true", help="Do not write the manifest")
    p.add_argument(
        "--use-local-only",
        action="store_true",
        help="Skip HTTP, read corpus/raw/{corpus}_{lang}.{xml,html} from disk only",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    summary = run(
        corpus=args.corpus,
        languages="all" if args.lang == "all" else [args.lang],
        force_fetch=args.force_fetch,
        force_reprocess=args.force_reprocess,
        allow_html_fallback=not args.no_html_fallback,
        dry_run=args.dry_run,
        use_local_only=args.use_local_only,
    )
    print(summary.format_human())
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
