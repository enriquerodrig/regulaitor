"""Integration test: validate_citation against the real corpus loader."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.corpus import loader
from regulaitor.mcp_server import tools


@pytest.fixture(scope="module", autouse=True)
def _warmup_loader() -> None:
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def test_validate_invalid_article_returns_not_found_reason() -> None:
    c = Citation(
        norma="ai_act",
        articulo="999",
        language="es",
        text="any text",
    )
    r = tools.validate_citation(c)
    assert r.validated is False
    assert r.article_exists is False
    assert r.reason is not None
    assert "article_not_found" in r.reason


def test_validate_invalid_apartado_returns_apartado_not_found_reason() -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="999",
        language="es",
        text="any text",
    )
    r = tools.validate_citation(c)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is False
    assert r.reason is not None
    assert "apartado_not_found" in r.reason


def test_validate_text_not_in_apartado_returns_text_match_reason() -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto que con seguridad no aparece nunca en el corpus oficial",
    )
    r = tools.validate_citation(c)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason
