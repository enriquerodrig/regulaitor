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
