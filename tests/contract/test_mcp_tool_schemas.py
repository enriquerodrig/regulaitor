"""Contract tests for MCP tool surfaces.

Verifies the 3 H3 tools have stable signatures that downstream clients can
rely on. Each test checks the function signature + docstring presence; if a
test fails, the H3 contract has changed and must be reviewed.
"""

from __future__ import annotations

import inspect

import pytest

from regulaitor.mcp_server import tools

pytestmark = pytest.mark.contract


def test_search_articles_signature() -> None:
    sig = inspect.signature(tools.search_articles)
    params = sig.parameters
    assert list(params.keys()) == ["query", "corpus", "language", "top_k"]
    assert params["top_k"].default is None
    assert tools.search_articles.__doc__ is not None


def test_fetch_article_signature() -> None:
    sig = inspect.signature(tools.fetch_article)
    params = sig.parameters
    assert list(params.keys()) == ["norma", "articulo", "language", "apartado"]
    assert params["apartado"].default is None
    assert tools.fetch_article.__doc__ is not None


def test_validate_citation_signature() -> None:
    sig = inspect.signature(tools.validate_citation)
    params = sig.parameters
    assert list(params.keys()) == ["citation"]
    assert tools.validate_citation.__doc__ is not None
