"""Smoke tests for scripts.rag_build CLI argument parsing."""

from scripts.rag_build import _build_parser


def test_default_args() -> None:
    args = _build_parser().parse_args([])
    assert args.corpus == "all"
    assert args.lang == "all"
    assert args.force_rebuild is False
    assert args.verbose is False


def test_specific_corpus_and_lang() -> None:
    args = _build_parser().parse_args(["--corpus", "gdpr", "--lang", "en"])
    assert args.corpus == "gdpr"
    assert args.lang == "en"


def test_force_rebuild_flag() -> None:
    args = _build_parser().parse_args(["--force-rebuild"])
    assert args.force_rebuild is True
