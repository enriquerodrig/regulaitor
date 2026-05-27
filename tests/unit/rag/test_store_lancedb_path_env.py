"""Tests for LANCEDB_PATH env override in rag.store.DEFAULT_PATH (v0.1.26 H16 deploy-prep).

The env var is read at MODULE IMPORT time; tests use importlib.reload to
re-trigger the os.getenv call after monkeypatching.
"""

from __future__ import annotations

import importlib
from pathlib import Path


def test_default_path_uses_fallback_when_env_unset(monkeypatch):
    monkeypatch.delenv("LANCEDB_PATH", raising=False)
    from regulaitor.rag import store

    importlib.reload(store)
    assert Path("corpus/indexes/regulaitor.lance") == store.DEFAULT_PATH


def test_default_path_honors_lancedb_env(monkeypatch):
    monkeypatch.setenv("LANCEDB_PATH", "/data/indexes")
    from regulaitor.rag import store

    importlib.reload(store)
    assert Path("/data/indexes") == store.DEFAULT_PATH


def test_default_path_strips_whitespace_in_env(monkeypatch):
    monkeypatch.setenv("LANCEDB_PATH", "  /opt/lancedb  ")
    from regulaitor.rag import store

    importlib.reload(store)
    assert Path("/opt/lancedb") == store.DEFAULT_PATH


def test_default_path_falls_back_on_whitespace_only_env(monkeypatch):
    monkeypatch.setenv("LANCEDB_PATH", "   ")
    from regulaitor.rag import store

    importlib.reload(store)
    assert Path("corpus/indexes/regulaitor.lance") == store.DEFAULT_PATH


def test_build_index_path_follows_store_default(monkeypatch):
    """build.INDEX_PATH must derive from store.DEFAULT_PATH so the env
    override applied to store propagates transitively to build + retrieval."""
    monkeypatch.setenv("LANCEDB_PATH", "/var/cache/lancedb")
    from regulaitor.rag import store

    importlib.reload(store)
    from regulaitor.rag import build

    importlib.reload(build)
    assert Path("/var/cache/lancedb") == build.INDEX_PATH
    assert build.INDEX_PATH == store.DEFAULT_PATH


def test_entrypoint_marker_matches_store_table_name():
    """Pin: docker-entrypoint.sh checks for `${INDEX_DIR}/chunks.lance` to decide
    whether to run the cold-start build. That marker must equal
    `store.TABLE_NAME + ".lance"` — if anyone renames the table or changes the
    marker, this test fires."""
    from regulaitor.rag import store

    entrypoint_path = Path(__file__).resolve().parents[3] / "docker-entrypoint.sh"
    contents = entrypoint_path.read_text(encoding="utf-8")
    expected_marker_fragment = f'/{store.TABLE_NAME}.lance"'
    assert expected_marker_fragment in contents, (
        f"docker-entrypoint.sh INDEX_MARKER must reference "
        f"`${{INDEX_DIR}}/{store.TABLE_NAME}.lance` "
        f"to match LanceDB's actual on-disk table dir. "
        f"If store.TABLE_NAME changes, update docker-entrypoint.sh accordingly."
    )
