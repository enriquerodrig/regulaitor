"""Unit tests for HtmlParser against synthetic HTML fixtures."""

from pathlib import Path

import pytest

from regulaitor.corpus.html_parser import HtmlParseError, HtmlParser

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "html"


def test_parse_mini_returns_2_articles() -> None:
    parser = HtmlParser()
    articles = parser.parse((FIX / "ai_act_es_mini.html").read_bytes())
    assert len(articles) == 2
    assert [a.articulo for a in articles] == ["1", "2"]
    assert articles[0].title == "Objeto"
    assert "normas armonizadas" in articles[0].text


def test_parse_broken_template_raises() -> None:
    parser = HtmlParser()
    with pytest.raises(HtmlParseError, match="no recognisable article"):
        parser.parse((FIX / "ai_act_es_broken.html").read_bytes())


def test_parse_oj_format_extracts_title_and_clean_body() -> None:
    """Fase 3: the 2024+ EUR-Lex OJ format renames classes (sti-art -> oj-sti-art,
    normal -> oj-normal). The parser must recognise both so titles + clean body
    text are extracted (not the get_text fallback that merges the 'Artículo N'
    designation into the body)."""
    parser = HtmlParser()
    articles = parser.parse((FIX / "rts_es_mini_oj.html").read_bytes())
    assert [a.articulo for a in articles] == ["1", "2"]
    assert articles[0].title == "Objeto"
    assert articles[1].title == "Ámbito de aplicación"
    assert "normas técnicas" in articles[0].text
    # the article designation must NOT pollute the body text (clean extraction)
    assert "Artículo" not in articles[0].text
    # both oj-normal paragraphs are captured for article 2
    assert "entidades financieras" in articles[1].text
    assert "proveedores excluidos" in articles[1].text


def test_parse_oj_inline_spans_keep_word_spacing() -> None:
    """Fase 3 review F1: inline <span> tokens must NOT be glued together —
    get_text(strip=True) produced 'software,hardwareo'; the fix preserves the
    inter-span spaces so a verbatim citation validates against the corpus."""
    parser = HtmlParser()
    articles = {
        a.articulo: a for a in parser.parse((FIX / "rts_inline_spans_oj.html").read_bytes())
    }
    body = articles["7"].text
    assert "software, hardware o infraestructuras" in body
    assert "softwarehardware" not in body and "software,hardware" not in body


def test_parse_oj_strips_leaked_article_designation_in_title() -> None:
    """Fase 3 review F3: the OJ template sometimes leaks 'Article ' into the
    subtitle; a leading designation token (followed by a word) is stripped."""
    parser = HtmlParser()
    articles = {
        a.articulo: a for a in parser.parse((FIX / "rts_inline_spans_oj.html").read_bytes())
    }
    assert articles["4"].title == "Specific information to be provided"
