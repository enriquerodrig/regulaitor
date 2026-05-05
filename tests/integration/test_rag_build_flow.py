"""Integration test: rag.build.run end-to-end with REAL BGE-M3 + LanceDB.

Slow (~30s with cached model). Skips if model cache is missing — provide
a marker so CI cache always pre-populates before this runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.rag import build

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "rag"


@pytest.mark.slow
def test_real_build_against_mini_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifests_dir = tmp_path / "corpus" / "manifests"
    processed_dir = tmp_path / "corpus" / "processed"
    manifests_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)
    shutil.copy(FIX / "mini_manifest.json", manifests_dir / "ai_act.json")
    shutil.copy(FIX / "mini_processed_es.json", processed_dir / "ai_act_es.json")
    shutil.copy(FIX / "mini_processed_en.json", processed_dir / "ai_act_en.json")
    monkeypatch.chdir(tmp_path)

    summary = build.run(corpus="ai_act", languages=["es", "en"])
    assert summary.errors == 0
    assert summary.chunks_added == 4

    m = manifest_mod.load(manifests_dir / "ai_act.json")
    assert m is not None
    for article in m.articles:
        for _lang, entry in article.languages.items():
            assert len(entry.chunks) == 1
            assert entry.embedded_at is not None
            assert entry.embedding_model is not None
            assert entry.embedding_model.startswith("BAAI/bge-m3@")

    # Idempotent re-run
    summary2 = build.run(corpus="ai_act", languages=["es", "en"])
    assert summary2.chunks_unchanged == 4
    assert summary2.chunks_recomputed == 0
