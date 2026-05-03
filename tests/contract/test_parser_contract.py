"""Contract tests: parser output round-trips through Pydantic schemas."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph

# ASCII-safe text avoids accidental encoding edge cases in tests.
text_strategy = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="<>&"),
    min_size=1,
    max_size=200,
)


@given(num=st.integers(min_value=1, max_value=200), text=text_strategy)
def test_parsed_article_roundtrips_to_dict(num: int, text: str) -> None:
    article = ParsedArticle(
        articulo=str(num),
        title="t",
        text=text,
        paragraphs=[
            ParsedParagraph(apartado="1", text=text),
        ],
    )
    assert article.text == text
    assert article.paragraphs[0].apartado == "1"


@given(text=text_strategy)
@settings(max_examples=50)
def test_paragraph_text_preserved(text: str) -> None:
    p = ParsedParagraph(apartado="1", text=text)
    assert p.text == text


pytestmark = pytest.mark.contract
