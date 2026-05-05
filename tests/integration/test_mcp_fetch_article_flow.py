"""Integration test: fetch_article against the real corpus loader."""

from __future__ import annotations

import pytest

from regulaitor.corpus import loader
from regulaitor.mcp_server import tools
from regulaitor.mcp_server.errors import NotFoundError


@pytest.fixture(scope="module", autouse=True)
def _warmup_loader() -> None:
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def test_fetch_existing_article_returns_text() -> None:
    fa = tools.fetch_article(norma="ai_act", articulo="1", language="es")
    assert fa.text  # non-empty
    assert fa.version  # CELEX present
    assert fa.source_url.startswith("http")
    assert fa.apartado is None


def test_fetch_existing_apartado_returns_paragraph_text() -> None:
    fa = tools.fetch_article(norma="ai_act", articulo="1", language="es", apartado="1")
    assert fa.text
    assert fa.apartado == "1"


def test_fetch_missing_article_raises_notfound() -> None:
    with pytest.raises(NotFoundError):
        tools.fetch_article(norma="ai_act", articulo="999", language="es")


def test_fetch_missing_apartado_raises_notfound() -> None:
    with pytest.raises(NotFoundError):
        tools.fetch_article(norma="ai_act", articulo="1", language="es", apartado="999")
