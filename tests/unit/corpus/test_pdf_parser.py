"""Unit tests for PdfParser._parse_text against synthetic strings.

The PDF I/O path (pdfplumber) is exercised via the integration smoke test;
unit tests use plain strings to validate the regex/structure logic in isolation.
"""

from __future__ import annotations

import pytest

from regulaitor.corpus.pdf_parser import PdfParseError, PdfParser


def _parse(text: str) -> list:
    return PdfParser()._parse_text(text)


def test_parses_two_articles_es() -> None:
    text = (
        "Some preamble text that should be ignored.\n"
        "\n"
        "Artículo 1\n"
        "Objeto\n"
        "1. Este Reglamento establece normas armonizadas.\n"
        "2. Se aplica a proveedores en la Unión.\n"
        "\n"
        "Artículo 2\n"
        "Ámbito de aplicación\n"
        "El presente Reglamento se aplica a sistemas de IA.\n"
    )
    arts = _parse(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert arts[0].title == "Objeto"
    assert "normas armonizadas" in arts[0].text
    assert len(arts[0].paragraphs) == 2
    assert arts[0].paragraphs[0].apartado == "1"
    assert arts[0].paragraphs[1].apartado == "2"
    assert arts[1].title == "Ámbito de aplicación"
    assert arts[1].paragraphs[0].apartado == "1"  # falls back to single paragraph


def test_parses_two_articles_en() -> None:
    text = (
        "Article 1\n"
        "Subject matter\n"
        "1. This Regulation lays down rules.\n"
        "\n"
        "Article 2\n"
        "Scope\n"
        "1. It applies to providers.\n"
        "2. It applies to deployers.\n"
    )
    arts = _parse(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert arts[0].title == "Subject matter"
    assert arts[1].title == "Scope"
    assert len(arts[1].paragraphs) == 2


def test_keep_first_dedupes_back_references() -> None:
    """A second 'Article N' header (annex back-ref) must not displace the body article."""
    text = (
        "Article 1\nFirst article\n1. Body of one.\n"
        "Article 2\nSecond article\n1. Body of two.\n"
        "\n"
        "ANNEX I\n"
        "Article 1\n"  # back-reference header inside annex; must be ignored
        "Cross reference table.\n"
    )
    arts = _parse(text)
    # We get 2 articles (1, 2). The annex 'Article 1' is deduplicated to the FIRST occurrence,
    # so the body article 1 wins. Annex content past article 2 is captured in article 2's body.
    assert [a.articulo for a in arts] == ["1", "2"]
    assert "Body of one" in arts[0].text
    assert "Body of two" in arts[1].text


def test_toc_lines_with_dots_are_excluded() -> None:
    """ToC entries like 'Article 1 — Subject matter ... 12' do not match strict header."""
    text = (
        "TABLE OF CONTENTS\n"
        "Article 1 — Subject matter ........ 12\n"
        "Article 2 — Scope .................... 13\n"
        "\n"
        "Article 1\n"
        "Subject matter\n"
        "Body of article one.\n"
        "Article 2\n"
        "Scope\n"
        "Body of article two.\n"
    )
    arts = _parse(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert "Body of article one" in arts[0].text


def test_no_articles_raises() -> None:
    with pytest.raises(PdfParseError, match="no recognisable article markers"):
        _parse("Some text that has no Article header at all, just prose and paragraphs.\n")


def test_article_without_numbered_paragraphs_yields_single_apartado() -> None:
    text = (
        "Article 1\n"
        "Definitions\n"
        "For the purposes of this Regulation, the following definitions apply:\n"
    )
    arts = _parse(text)
    assert len(arts) == 1
    assert arts[0].paragraphs[0].apartado == "1"
    assert "definitions apply" in arts[0].paragraphs[0].text


def test_parse_byte_path_via_extract_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse(bytes) calls _extract_text then _parse_text — verify glue."""

    captured = {}

    def fake_extract(_b: bytes) -> str:
        captured["called"] = True
        return "Article 1\nFoo\nBar.\n"

    monkeypatch.setattr(PdfParser, "_extract_text", staticmethod(fake_extract))
    arts = PdfParser().parse(b"%PDF-fake")
    assert captured["called"]
    assert len(arts) == 1
    assert arts[0].articulo == "1"


def test_parses_nis2_directive_structure_es() -> None:
    text = (
        "Artículo 1\n"
        "Objeto\n"
        "1. La presente Directiva establece medidas destinadas a garantizar "
        "un elevado nivel común de ciberseguridad en la Unión.\n"
        "Artículo 2\n"
        "Ámbito de aplicación\n"
        "1. La presente Directiva se aplicará a las entidades esenciales e "
        "importantes a que se refiere el anexo.\n"
    )
    arts = _parse(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert arts[0].title == "Objeto"
    assert "elevado nivel común de ciberseguridad" in arts[0].paragraphs[0].text


def test_parses_dora_regulation_structure_en() -> None:
    text = (
        "Article 1\n"
        "Subject matter\n"
        "1. This Regulation lays down uniform requirements concerning the "
        "security of network and information systems.\n"
        "Article 2\n"
        "Scope\n"
        "1. This Regulation applies to financial entities as defined herein.\n"
    )
    arts = _parse(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert arts[0].title == "Subject matter"
    assert "uniform requirements" in arts[0].paragraphs[0].text
