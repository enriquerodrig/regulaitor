"""Unit tests for FormexParser against synthetic XML fixtures."""

from pathlib import Path

import pytest

from regulaitor.corpus.formex_parser import (
    FormexParser,
    FormexValidationError,
    ParsedArticle,  # noqa: F401 – verifies public API export
    ParsedParagraph,  # noqa: F401 – verifies public API export
)

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "formex"


def test_parse_mini_es_returns_5_articles() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_es_mini.xml").read_bytes())
    assert len(articles) == 5
    assert [a.articulo for a in articles] == ["1", "2", "3", "4", "5"]


def test_parse_mini_es_extracts_titles_and_text() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_es_mini.xml").read_bytes())
    art1 = articles[0]
    assert art1.title == "Objeto"
    assert "normas armonizadas" in art1.text
    assert "proveedores" in art1.text
    assert len(art1.paragraphs) == 2
    assert art1.paragraphs[0].apartado == "1"
    assert art1.paragraphs[1].apartado == "2"


def test_parse_mini_en_returns_5_articles() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_en_mini.xml").read_bytes())
    assert len(articles) == 5
    assert articles[0].title == "Subject matter"


def test_parse_no_articles_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError, match="zero ARTICLE"):
        parser.parse((FIX / "malformed_no_articles.xml").read_bytes())


def test_parse_missing_article_number_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError, match="NO.ARTICLE"):
        parser.parse((FIX / "malformed_missing_num.xml").read_bytes())


def test_parse_invalid_xml_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError):
        parser.parse(b"<not><valid")


def test_parsed_article_text_collapses_whitespace() -> None:
    parser = FormexParser()
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<CONS.ACT><ARTICLE><NO.ARTICLE>1</NO.ARTICLE>"
        b"<TI.ART>T</TI.ART><PARAG><NO.P>1</NO.P>"
        b"<TXT>line1   line2\n\nline3</TXT></PARAG></ARTICLE></CONS.ACT>"
    )
    article = parser.parse(xml)[0]
    assert article.text == "line1 line2 line3"
    assert article.paragraphs[0].text == "line1 line2 line3"


def test_long_article_returns_single_parsed_article() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_with_long_article.xml").read_bytes())
    assert len(articles) == 1
    assert articles[0].articulo == "6"
    assert len(articles[0].text) > 5000  # stress text


def test_parse_paragraph_without_no_p_falls_back_cleanly() -> None:
    parser = FormexParser()
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<CONS.ACT><ARTICLE>"
        b"<NO.ARTICLE>1</NO.ARTICLE>"
        b"<TI.ART>Title that should NOT appear in body</TI.ART>"
        b"<PARAG><TXT>Body without NO.P numbering.</TXT></PARAG>"
        b"</ARTICLE></CONS.ACT>"
    )
    article = parser.parse(xml)[0]
    assert article.articulo == "1"
    assert article.title == "Title that should NOT appear in body"
    assert article.text == "Body without NO.P numbering."
    # Critical: title and article number must NOT leak into article.text
    assert "Title" not in article.text
    assert article.text != "1 Title that should NOT appear in body Body without NO.P numbering."


def test_parse_title_with_inline_markup() -> None:
    parser = FormexParser()
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<CONS.ACT><ARTICLE>"
        b"<NO.ARTICLE>1</NO.ARTICLE>"
        b'<TI.ART><HT TYPE="BOLD">Subject matter</HT></TI.ART>'
        b"<PARAG><NO.P>1</NO.P><TXT>Body.</TXT></PARAG>"
        b"</ARTICLE></CONS.ACT>"
    )
    article = parser.parse(xml)[0]
    assert article.title == "Subject matter"


def test_parse_unexpected_root_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError, match="unexpected root"):
        parser.parse(
            b'<?xml version="1.0"?>'
            b"<WRONG_ROOT>"
            b"<ARTICLE><NO.ARTICLE>1</NO.ARTICLE>"
            b"<PARAG><NO.P>1</NO.P><TXT>x</TXT></PARAG>"
            b"</ARTICLE>"
            b"</WRONG_ROOT>"
        )
