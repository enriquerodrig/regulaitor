"""Unit tests for rag.build with stubbed embedder and reranker."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.rag import build, embeddings, reranker

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "rag"


@pytest.fixture(autouse=True)
def stub_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub embeddings and reranker so unit tests don't load real models."""
    monkeypatch.setattr(
        embeddings, "embed", lambda texts, batch_size=16: [[0.1] * 1024 for _ in texts]
    )
    monkeypatch.setattr(embeddings, "token_count", lambda text: len(text.split()))
    monkeypatch.setattr(embeddings, "model_identifier", lambda: "BAAI/bge-m3@test")
    monkeypatch.setattr(reranker, "warmup", lambda: None)


@pytest.fixture
def setup_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy fixtures to tmp_path-based corpus tree and patch all paths."""
    manifests_dir = tmp_path / "corpus" / "manifests"
    processed_dir = tmp_path / "corpus" / "processed"
    manifests_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)

    shutil.copy(FIX / "mini_manifest.json", manifests_dir / "ai_act.json")
    shutil.copy(FIX / "mini_processed_es.json", processed_dir / "ai_act_es.json")
    shutil.copy(FIX / "mini_processed_en.json", processed_dir / "ai_act_en.json")

    # Patch the constants build.py uses
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_first_build_chunks_all_articles_and_extends_manifest(setup_fs: Path) -> None:
    summary = build.run(corpus="ai_act", languages=["es", "en"])
    assert summary.errors == 0
    assert summary.chunks_added == 4  # 2 articles * 2 langs
    assert summary.chunks_unchanged == 0
    assert summary.chunks_recomputed == 0

    m = manifest_mod.load(setup_fs / "corpus" / "manifests" / "ai_act.json")
    assert m is not None
    for article in m.articles:
        for _lang, entry in article.languages.items():
            assert entry.chunks  # non-empty
            assert entry.embedded_at is not None
            assert entry.embedding_model == "BAAI/bge-m3@test"


def test_idempotent_rerun(setup_fs: Path) -> None:
    build.run(corpus="ai_act", languages=["es", "en"])
    summary = build.run(corpus="ai_act", languages=["es", "en"])
    assert summary.chunks_added == 0
    assert summary.chunks_recomputed == 0
    assert summary.chunks_unchanged == 4


def test_model_change_triggers_rebuild(setup_fs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build.run(corpus="ai_act", languages=["es", "en"])
    # Change the model identifier — simulates a model upgrade
    monkeypatch.setattr(embeddings, "model_identifier", lambda: "BAAI/bge-m3@v2")
    summary = build.run(corpus="ai_act", languages=["es", "en"])
    assert summary.chunks_recomputed == 4
    assert summary.chunks_unchanged == 0


def test_force_rebuild_recomputes_everything(setup_fs: Path) -> None:
    build.run(corpus="ai_act", languages=["es", "en"])
    summary = build.run(corpus="ai_act", languages=["es", "en"], force_rebuild=True)
    assert summary.chunks_recomputed == 4
    assert summary.chunks_unchanged == 0


def test_missing_manifest_records_skip(setup_fs: Path) -> None:
    summary = build.run(corpus="gdpr", languages=["es"])
    assert "gdpr" in summary.skipped_corpora
    assert summary.errors >= 1


def test_article_with_only_one_language_skips_other_lang_cleanly(
    setup_fs: Path, tmp_path: Path
) -> None:
    """If an article exists with only ES but the build asks for both ES and EN,
    the EN branch must be a clean continue (no error, no chunk added for EN)."""
    # Modify the manifest to remove EN from article 1
    import json

    manifest_path = setup_fs / "corpus" / "manifests" / "ai_act.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    del m["articles"][0]["languages"]["en"]
    manifest_path.write_text(json.dumps(m), encoding="utf-8")

    summary = build.run(corpus="ai_act", languages=["es", "en"])
    assert summary.errors == 0
    # 2 articles × 2 langs - 1 missing = 3 chunks added
    assert summary.chunks_added == 3
