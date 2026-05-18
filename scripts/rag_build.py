"""CLI wrapper for regulaitor.rag.build.run.

Usage:
    python -m scripts.rag_build --corpus all --lang all
    python -m scripts.rag_build --corpus ai_act --lang es --force-rebuild
"""

from __future__ import annotations

import argparse
import logging
import sys

from regulaitor.rag.build import run


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regulaitor.rag_build",
        description="Build RAG index: chunk + embed + upsert LanceDB + extend manifest.",
    )
    p.add_argument("--corpus", choices=["ai_act", "gdpr", "nis2", "dora", "all"], default="all")
    p.add_argument("--lang", choices=["es", "en", "all"], default="all")
    p.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Re-embed every chunk regardless of hash/model match",
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
        force_rebuild=args.force_rebuild,
    )
    print(summary.model_dump_json(indent=2))
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
