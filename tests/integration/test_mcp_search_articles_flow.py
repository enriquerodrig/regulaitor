"""Slow integration test: search_articles end-to-end via stdio subprocess.

Loads BGE-M3 + bge-reranker-v2-m3 + the live LanceDB; takes ~15s wall-clock.
Marked slow; excluded from CI fast suite.
"""

from __future__ import annotations

import pytest

from regulaitor.corpus import loader
from regulaitor.mcp_server import tools
from regulaitor.rag import reranker

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module", autouse=True)
def _warmup() -> None:
    loader.reset()
    loader.warmup()
    reranker.warmup()
    yield
    loader.reset()


def test_search_articles_returns_filtered_ranked_chunks() -> None:
    results = tools.search_articles(
        query="sistemas de inteligencia artificial de alto riesgo",
        corpus="ai_act",
        language="es",
        top_k=5,
    )
    assert len(results) == 5
    assert all(r.norma == "ai_act" for r in results)
    assert all(r.language == "es" for r in results)

    # Scores are monotonically non-increasing
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_articles_returns_at_most_top_k() -> None:
    results = tools.search_articles(
        query="proteccion de datos personales",
        corpus="gdpr",
        language="es",
        top_k=3,
    )
    assert len(results) <= 3
    assert all(r.norma == "gdpr" for r in results)
