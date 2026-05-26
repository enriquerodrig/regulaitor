"""Unit tests for citation/validator.py — 3 strict checks against the corpus."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import validate


class _FakeLoader:
    """Minimal loader stub that satisfies LoaderProtocol for unit tests."""

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

    def get_article(self, norma: str, articulo: str, language: str) -> object:
        # The validator only uses get_article as an existence probe; the
        # returned object is intentionally opaque (no .text attribute) so the
        # validator must go through get_article_text for the no-apartado path.
        if (norma, articulo, language) not in self._articles:
            raise KeyError(f"{norma} has no articulo {articulo} in language {language}")
        return object()

    def get_paragraph(self, norma: str, articulo: str, apartado: str, language: str) -> str:
        key = (norma, articulo, apartado, language)
        if key not in self._paragraphs:
            raise KeyError(f"no apartado {apartado}")
        return self._paragraphs[key]

    def get_article_text(self, norma: str, articulo: str, language: str) -> str:
        key = (norma, articulo, language)
        if key not in self._articles:
            raise KeyError(f"{norma} has no articulo {articulo} in language {language}")
        return self._articles[key]

    def list_apartados(self, norma: str, articulo: str, language: str) -> list[str]:
        return [
            ap
            for (n, a, ap, lang) in self._paragraphs
            if n == norma and a == articulo and lang == language
        ]


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


def test_validate_text_from_other_apartado_rejected() -> None:
    """Text that matches a DIFFERENT apartado of the same article must be rejected.

    Regression: ensures the validator scopes the substring search to the
    claimed apartado, not the whole article. Citation claims apartado 1 but
    quotes the text of apartado 2; must fail.
    """
    fl = _FakeLoader({("ai_act", "6", "es"): "alpha text\n\nbeta text"})
    fl.add_paragraph("ai_act", "6", "1", "es", "alpha text")
    fl.add_paragraph("ai_act", "6", "2", "es", "beta text")

    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="beta text",
    )
    r = validate(c, loader=fl)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason


def test_validate_text_from_other_article_rejected() -> None:
    """Text that matches a DIFFERENT article must be rejected.

    Regression: ensures the no-apartado path scopes the substring search to
    the claimed article, not the whole corpus. Citation claims article 6 but
    quotes the text of article 7; must fail.
    """
    fl = _FakeLoader(
        {
            ("ai_act", "6", "es"): "alpha text",
            ("ai_act", "7", "es"): "beta text",
        }
    )

    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="beta text",
    )
    r = validate(c, loader=fl)
    assert r.validated is False
    assert r.article_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_article" in r.reason


# ---------------------------------------------------------------------------
# v0.1.24 (ADR-0031): failed_check field tests
# ---------------------------------------------------------------------------


def test_audit_result_failed_check_optional_field_default_none(
    loader_with_data: _FakeLoader,
) -> None:
    """AuditResult.failed_check defaults to None (backward-compat)."""
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.failed_check is None


def test_validator_populates_failed_check_1_when_article_not_exists(
    loader_with_data: _FakeLoader,
) -> None:
    """When Check 1 fails (article not found), failed_check=1."""
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is False
    assert r.failed_check == 1


def test_validator_populates_failed_check_2_when_apartado_not_exists(
    loader_with_data: _FakeLoader,
) -> None:
    """When Check 2 fails (apartado not found), failed_check=2."""
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
    assert r.failed_check == 2


def test_validator_populates_failed_check_3_when_text_not_match(
    loader_with_data: _FakeLoader,
) -> None:
    """When Check 3 fails (text not found), failed_check=3."""
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
    assert r.failed_check == 3


def test_validator_failed_check_none_when_all_checks_pass(
    loader_with_data: _FakeLoader,
) -> None:
    """When all checks pass, failed_check=None."""
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.failed_check is None
