"""Unit tests for corpus.manifest: load, save_atomic, diff."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

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


def _make_lang_entry(text_hash: str, tokens: int = 100) -> LanguageEntry:
    return LanguageEntry(
        hash=text_hash,
        tokens=tokens,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/x",
    )


def _make_manifest(articles: list[ArticleEntry]) -> Manifest:
    return Manifest(
        corpus="ai_act",
        celex="32024R1689",
        version="2024-07-12",
        source_format="formex4",
        fetched_at=_now(),
        languages=["es", "en"],
        http_cache={"es": HttpCacheEntry(), "en": HttpCacheEntry()},
        stats=Stats(articles_total=len(articles), raw_size_bytes=0),
        articles=articles,
    )


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert manifest_mod.load(tmp_path / "missing.json") is None


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    article = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        languages={"es": _make_lang_entry("sha256:aa"), "en": _make_lang_entry("sha256:bb")},
    )
    m = _make_manifest([article])
    path = tmp_path / "ai_act.json"
    manifest_mod.save_atomic(path, m)
    assert path.exists()
    loaded = manifest_mod.load(path)
    assert loaded == m


def test_save_atomic_uses_tmp_then_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """save_atomic must never leave a partial file at the target path."""
    m = _make_manifest([])
    path = tmp_path / "ai_act.json"

    real_replace = manifest_mod.os.replace
    captured: dict[str, object] = {}

    def spy(src: str, dst: str) -> None:
        captured["src"] = src
        captured["dst"] = dst
        real_replace(src, dst)

    monkeypatch.setattr(manifest_mod.os, "replace", spy)
    manifest_mod.save_atomic(path, m)
    assert captured["dst"] == str(path)
    assert str(captured["src"]).endswith(".tmp")


def test_diff_no_old_manifest_marks_all_added() -> None:
    new = _make_manifest(
        [
            ArticleEntry(
                article_id="ai_act.1",
                articulo="1",
                languages={"es": _make_lang_entry("sha256:aa")},
            ),
            ArticleEntry(
                article_id="ai_act.2",
                articulo="2",
                languages={"es": _make_lang_entry("sha256:bb")},
            ),
        ]
    )
    diff = manifest_mod.diff(None, new)
    assert sorted(diff.added_articles) == ["ai_act.1", "ai_act.2"]
    assert diff.removed_articles == []
    assert diff.changed_articles == []
    assert diff.unchanged_articles == []


def test_diff_detects_changed_added_removed_unchanged() -> None:
    art1_old = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        languages={"es": _make_lang_entry("sha256:OLD1")},
    )
    art2_old = ArticleEntry(
        article_id="ai_act.2",
        articulo="2",
        languages={"es": _make_lang_entry("sha256:KEEP")},
    )
    art3_old = ArticleEntry(
        article_id="ai_act.3",
        articulo="3",
        languages={"es": _make_lang_entry("sha256:GONE")},
    )

    art1_new = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        languages={"es": _make_lang_entry("sha256:NEW1")},  # changed
    )
    art2_new = ArticleEntry(
        article_id="ai_act.2",
        articulo="2",
        languages={"es": _make_lang_entry("sha256:KEEP")},  # unchanged
    )
    art4_new = ArticleEntry(
        article_id="ai_act.4",
        articulo="4",
        languages={"es": _make_lang_entry("sha256:NEW4")},  # added
    )
    # art3 dropped → removed

    old = _make_manifest([art1_old, art2_old, art3_old])
    new = _make_manifest([art1_new, art2_new, art4_new])
    diff = manifest_mod.diff(old, new)
    assert diff.added_articles == ["ai_act.4"]
    assert diff.removed_articles == ["ai_act.3"]
    assert diff.changed_articles == ["ai_act.1"]
    assert diff.unchanged_articles == ["ai_act.2"]
