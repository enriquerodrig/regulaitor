"""Unit tests for validate.validate against synthetic ParsedArticle lists."""

import pytest

from regulaitor.corpus.formex_parser import ParsedArticle
from regulaitor.corpus.validate import (
    EXPECTED_ARTICLE_COUNTS,
    ValidationFailure,
    validate,
)


def _art(num: str, text: str = "x") -> ParsedArticle:
    return ParsedArticle(articulo=num, title=None, text=text, paragraphs=[])


def test_expected_counts_constants() -> None:
    assert EXPECTED_ARTICLE_COUNTS["ai_act"] == 113
    assert EXPECTED_ARTICLE_COUNTS["gdpr"] == 99
    assert EXPECTED_ARTICLE_COUNTS["nis2"] == 46
    assert EXPECTED_ARTICLE_COUNTS["dora"] == 64


def test_validate_full_coverage_returns_ok_report() -> None:
    articles = [_art(str(i)) for i in range(1, 114)]
    report = validate("ai_act", articles, strict=False)
    assert report.coverage_ok is True
    assert report.expected == 113
    assert report.found == 113
    assert report.duplicates == []
    assert report.missing == []


def test_validate_partial_coverage_strict_raises() -> None:
    articles = [_art(str(i)) for i in range(1, 50)]  # only 49 of 113
    with pytest.raises(ValidationFailure):
        validate("ai_act", articles, strict=True)


def test_validate_detects_duplicates() -> None:
    articles = [_art("1"), _art("2"), _art("2"), _art("3")]
    report = validate("ai_act", articles, strict=False)
    assert "2" in report.duplicates


def test_validate_detects_empty_text() -> None:
    articles = [_art("1", text="")]
    report = validate("ai_act", articles, strict=False)
    assert "1" in report.empty


def test_validate_unknown_corpus_raises() -> None:
    with pytest.raises(KeyError):
        validate("unknown", [_art("1")], strict=False)  # type: ignore[arg-type]
