"""Integration tests for ingest.run() end-to-end with mocked HTTP."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from regulaitor.corpus import ingest
from regulaitor.corpus import manifest as manifest_mod


@pytest.fixture
def es_xml() -> bytes:
    return Path("tests/fixtures/formex/ai_act_es_mini.xml").read_bytes()


@pytest.fixture
def en_xml() -> bytes:
    return Path("tests/fixtures/formex/ai_act_en_mini.xml").read_bytes()


def _make_handler(es_xml: bytes, en_xml: bytes, *, etag: str = 'W/"v1"'):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "ES/TXT" in path:
            content = es_xml
        elif "EN/TXT" in path:
            content = en_xml
        else:
            return httpx.Response(404)
        if request.headers.get("If-None-Match") == etag:
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=content,
            headers={"ETag": etag, "Last-Modified": "Fri, 12 Jul 2024 00:00:00 GMT"},
        )

    return handler


def test_first_run_creates_manifest_with_5_articles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    es_xml: bytes,
    en_xml: bytes,
) -> None:
    monkeypatch.setattr(ingest, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(ingest, "PROCESSED_DIR", tmp_path / "processed")

    # Inject mock client by monkeypatching the EurLexClient constructor
    handler = _make_handler(es_xml, en_xml)
    monkeypatch.setattr(
        ingest,
        "EurLexClient",
        lambda **kw: ingest._make_test_client(httpx.MockTransport(handler)),
    )
    # Override expected counts so 5-article fixture passes coverage
    monkeypatch.setattr(
        "regulaitor.corpus.validate.EXPECTED_ARTICLE_COUNTS",
        {"ai_act": 5, "gdpr": 99},
    )

    summary = ingest.run(corpus="ai_act", languages=["es", "en"])
    assert summary.errors == 0
    manifest_path = tmp_path / "manifests" / "ai_act.json"
    m = manifest_mod.load(manifest_path)
    assert m is not None
    assert m.stats.articles_total == 5
    assert {a.articulo for a in m.articles} == {"1", "2", "3", "4", "5"}
    assert all("es" in a.languages and "en" in a.languages for a in m.articles)


def test_rerun_with_no_changes_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    es_xml: bytes,
    en_xml: bytes,
) -> None:
    monkeypatch.setattr(ingest, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(ingest, "PROCESSED_DIR", tmp_path / "processed")
    handler = _make_handler(es_xml, en_xml)
    monkeypatch.setattr(
        ingest,
        "EurLexClient",
        lambda **kw: ingest._make_test_client(httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "regulaitor.corpus.validate.EXPECTED_ARTICLE_COUNTS",
        {"ai_act": 5, "gdpr": 99},
    )

    first = ingest.run(corpus="ai_act", languages=["es", "en"])
    second = ingest.run(corpus="ai_act", languages=["es", "en"])
    assert first.errors == 0
    assert second.errors == 0
    assert second.fetch_skipped == 2  # both ES and EN returned 304
    diffs = second.diffs.get("ai_act")
    assert diffs is not None
    assert diffs.changed_articles == []
    assert diffs.added_articles == []
    assert sorted(diffs.unchanged_articles) == [
        "ai_act.1",
        "ai_act.2",
        "ai_act.3",
        "ai_act.4",
        "ai_act.5",
    ]
