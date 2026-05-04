"""Unit tests for corpus._targets.expand_targets."""

from regulaitor.corpus._targets import (
    ALL_LANGUAGES,
    ALL_NORMAS,
    expand_targets,
)


def test_expand_all_returns_all_norms_and_langs() -> None:
    corpora, langs = expand_targets("all", "all")
    assert corpora == list(ALL_NORMAS)
    assert langs == list(ALL_LANGUAGES)


def test_expand_specific_corpus_keeps_only_that_one() -> None:
    corpora, langs = expand_targets("ai_act", "all")
    assert corpora == ["ai_act"]
    assert langs == list(ALL_LANGUAGES)


def test_expand_specific_lang_keeps_only_that_one() -> None:
    corpora, langs = expand_targets("all", ["en"])
    assert corpora == list(ALL_NORMAS)
    assert langs == ["en"]


def test_expand_both_specific() -> None:
    corpora, langs = expand_targets("gdpr", ["es"])
    assert corpora == ["gdpr"]
    assert langs == ["es"]


def test_all_norms_includes_advanced_corpora() -> None:
    """The constant should include nis2 and dora even though they're H14, so
    expand_targets('all', 'all') is forward-compatible."""
    assert "nis2" in ALL_NORMAS
    assert "dora" in ALL_NORMAS
