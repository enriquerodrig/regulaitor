"""Contract test: manifest written by save_atomic round-trips through load."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.schemas import (
    ArticleEntry,
    HttpCacheEntry,
    LanguageEntry,
    Manifest,
    Stats,
)


def _now() -> datetime:
    return datetime(2026, 4, 30, 18, 42, 13, tzinfo=UTC)


hex_hash = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64).map(
    lambda h: f"sha256:{h}"
)


@given(
    n_articles=st.integers(min_value=0, max_value=10),
    article_hashes=st.lists(hex_hash, max_size=10, unique=True),
)
@settings(
    max_examples=20,
    # deadline=None: this is a pure serialization round-trip; per-example WALL time is
    # irrelevant to correctness. Under pytest-randomly (P1.4) the test can now run
    # first, before any warmup, so a single example may coincide with a cold lazy
    # import (BGE-M3 tokenizer pulled in transitively) and blow Hypothesis's default
    # 200ms per-example deadline. Disabling the deadline (not just suppressing the
    # aggregate too_slow health check) makes the test order-/seed-independent.
    deadline=None,
    # database=None: disable Hypothesis's on-disk example database for this test. Under
    # pytest-randomly reordering on Windows, concurrent access to .hypothesis/examples
    # intermittently raised PermissionError (a known Windows file-locking flake); this
    # test does not need example replay. Removes the last order-/seed-dependence.
    database=None,
    # tmp_path is not reset between Hypothesis examples, but that is intentional:
    # each run overwrites the same file path, which correctly tests the atomic
    # write + load round-trip without needing a fresh directory per example.
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_manifest_roundtrip(tmp_path: Path, n_articles: int, article_hashes: list[str]) -> None:
    article_hashes = (article_hashes + [f"sha256:{'0' * 64}"] * n_articles)[:n_articles]
    articles = [
        ArticleEntry(
            article_id=f"ai_act.{i}",
            articulo=str(i),
            languages={
                "es": LanguageEntry(
                    hash=h,
                    tokens=10,
                    fetched_at=_now(),
                    source_url="https://eur-lex.europa.eu/x",
                ),
            },
        )
        for i, h in enumerate(article_hashes, start=1)
    ]
    m = Manifest(
        corpus="ai_act",
        celex="32024R1689",
        version="2024-07-12",
        source_format="formex4",
        fetched_at=_now(),
        languages=["es"],
        http_cache={"es": HttpCacheEntry()},
        stats=Stats(articles_total=len(articles), raw_size_bytes=0),
        articles=articles,
    )
    path = tmp_path / "ai_act.json"
    manifest_mod.save_atomic(path, m)
    loaded = manifest_mod.load(path)
    assert loaded == m


pytestmark = pytest.mark.contract
