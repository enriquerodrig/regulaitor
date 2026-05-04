"""Smoke test for the CLI argument parsing in scripts/ingest.py."""

from scripts.ingest import _build_parser


def test_default_args() -> None:
    args = _build_parser().parse_args([])
    assert args.corpus == "all"
    assert args.lang == "all"
    assert args.force_fetch is False
    assert args.force_reprocess is False
    assert args.no_html_fallback is False
    assert args.dry_run is False


def test_specific_corpus_lang() -> None:
    args = _build_parser().parse_args(["--corpus", "ai_act", "--lang", "es"])
    assert args.corpus == "ai_act"
    assert args.lang == "es"


def test_force_flags() -> None:
    args = _build_parser().parse_args(["--force-fetch", "--force-reprocess", "--dry-run"])
    assert args.force_fetch is True
    assert args.force_reprocess is True
    assert args.dry_run is True
