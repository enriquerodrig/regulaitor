"""Integration test: corpus.loader.warmup() raises RuntimeError on hash drift."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from regulaitor.corpus import loader


def test_warmup_detects_drift_in_real_processed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Copy real corpus to tmp_path so we can mutate without affecting the workspace
    src_manifests = Path("corpus/manifests")
    src_processed = Path("corpus/processed")
    dst_manifests = tmp_path / "manifests"
    dst_processed = tmp_path / "processed"
    shutil.copytree(src_manifests, dst_manifests)
    shutil.copytree(src_processed, dst_processed)

    # Tamper with the article-level text (which is what the manifest hashes,
    # see corpus/loader.py::_read_article_text and corpus/ingest.py::_sha256_hex).
    target = dst_processed / "ai_act_es.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data[0]["text"] = "TAMPERED"
    target.write_text(json.dumps(data), encoding="utf-8")

    loader.reset()
    monkeypatch.setattr(loader, "MANIFEST_DIR", dst_manifests)
    monkeypatch.setattr(loader, "PROCESSED_DIR", dst_processed)

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()

    loader.reset()
