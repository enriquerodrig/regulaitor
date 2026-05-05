"""Unit tests for citation/validator.py — 3 strict checks against the corpus."""

from __future__ import annotations

from typing import Any

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import validate


class _FakeLoader:
    """Minimal loader stub that exposes get_paragraph and get_article-like behaviour."""

    def __init__(self, articles: dict[tuple[str, str, str], str]) -> None:
        # key: (norma, articulo, language) -> full article text
        self._articles = articles
        # key: (norma, articulo, apartado, language) -> paragraph text
        self._paragraphs: dict[tuple[str, str, str, str], str] = {}

    def add_paragraph(
        self,
        norma: str,
        articulo: str,
        apartado: str,
        language: str,
        text: str,
    ) -> None:
        self._paragraphs[(norma, articulo, apartado, language)] = text

    def get_article(self, norma: str, articulo: str, language: str) -> Any:
        if (norma, articulo, language) not in self._articles:
            raise KeyError(f"{norma} has no articulo {articulo} in language {language}")
        # Return a minimal stand-in object; the validator only needs to know it exists
        # for the article-level "no apartado given, match against full text" path.
        # The validator pulls full text via a helper we expose:
        return _FakeArticle(self._articles[(norma, articulo, language)])

    def get_paragraph(self, norma: str, articulo: str, apartado: str, language: str) -> str:
        key = (norma, articulo, apartado, language)
        if key not in self._paragraphs:
            raise KeyError(f"no apartado {apartado}")
        return self._paragraphs[key]

    def list_apartados(self, norma: str, articulo: str, language: str) -> list[str]:
        return [
            ap
            for (n, a, ap, lang) in self._paragraphs
            if n == norma and a == articulo and lang == language
        ]


class _FakeArticle:
    def __init__(self, text: str) -> None:
        self.text = text


@pytest.fixture
def loader_with_data() -> _FakeLoader:
    full_text = "El Artículo 6 establece reglas — incluido el apartado 1."
    apartado_1 = "El apartado 1 fija el ámbito"
    fl = _FakeLoader({("ai_act", "6", "es"): full_text})
    fl.add_paragraph("ai_act", "6", "1", "es", apartado_1)
    return fl


def test_validate_happy_path_with_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is True
    assert r.reason is None


def test_validate_happy_path_without_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="el artículo 6 establece reglas",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.apartado_exists is None  # no apartado given => check skipped
    assert r.text_normalized_match is True


def test_validate_article_not_found(loader_with_data: _FakeLoader) -> None:
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is False
    assert r.reason is not None
    assert "article_not_found" in r.reason


def test_validate_apartado_not_found(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="99",
        language="es",
        text="text",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is False
    assert r.reason is not None
    assert "apartado_not_found" in r.reason


def test_validate_text_not_in_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason


def test_validate_text_not_in_article(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_article" in r.reason


def test_validate_normalizes_accents_and_case(loader_with_data: _FakeLoader) -> None:
    # Citation has caps + missing accents; corpus has lowercase + accents
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="EL APARTADO 1 FIJA EL AMBITO",  # no acento on "ambito"
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True


def test_validate_normalizes_dashes(loader_with_data: _FakeLoader) -> None:
    # Corpus has em-dash —; citation uses ascii -
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="el artículo 6 establece reglas - incluido el apartado 1",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
