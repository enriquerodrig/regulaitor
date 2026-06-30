"""Unit tests for rag.store. Uses a tmp_path-rooted LanceDB for isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaitor.rag import store
from regulaitor.rag.schemas import ChunkRecord


def _chunk_record(
    chunk_id: str = "ai_act.1.es",
    embedding: list[float] | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        article_id=chunk_id.rsplit(".", 1)[0],
        norma="ai_act",
        articulo="1",
        apartado=None,
        language="es",
        text="x",
        text_normalized="x",
        token_count=1,
        celex="32024R1689",
        version="2024-07-12",
        source_format="pdf",
        source_url="file:///x",
        hash="sha256:abc",
        embedding=embedding or [0.1] * 1024,
        embedding_model="BAAI/bge-m3@v1.0",
    )


def test_connect_creates_table_with_correct_schema(tmp_path: Path) -> None:
    table = store.connect(tmp_path / "test.lance")
    assert "chunk_id" in [f.name for f in table.schema]
    assert "embedding" in [f.name for f in table.schema]


def test_connect_idempotent_returns_same_table(tmp_path: Path) -> None:
    p = tmp_path / "test.lance"
    table1 = store.connect(p)
    table1.add([_chunk_record().model_dump()])
    table2 = store.connect(p)
    rows = list(table2.search().limit(10).to_list())
    assert len(rows) == 1


def test_upsert_inserts_new_records(tmp_path: Path) -> None:
    table = store.connect(tmp_path / "t.lance")
    n = store.upsert([_chunk_record("ai_act.1.es"), _chunk_record("ai_act.2.es")], table)
    assert n == 2
    rows = list(table.search().limit(10).to_list())
    assert len(rows) == 2


def test_upsert_replaces_existing_chunk_id(tmp_path: Path) -> None:
    table = store.connect(tmp_path / "t.lance")
    store.upsert([_chunk_record("ai_act.1.es", embedding=[0.0] * 1024)], table)
    store.upsert([_chunk_record("ai_act.1.es", embedding=[1.0] * 1024)], table)
    rows = list(table.search().limit(10).to_list())
    assert len(rows) == 1
    assert rows[0]["embedding"][0] == pytest.approx(1.0)


def test_upsert_empty_returns_zero(tmp_path: Path) -> None:
    table = store.connect(tmp_path / "t.lance")
    assert store.upsert([], table) == 0


def test_delete_by_article_removes_only_matching(tmp_path: Path) -> None:
    table = store.connect(tmp_path / "t.lance")
    store.upsert(
        [
            _chunk_record("ai_act.1.es"),
            _chunk_record("ai_act.1.en"),
            _chunk_record("ai_act.2.es"),
        ],
        table,
    )
    deleted = store.delete_by_article("ai_act.1", "es", table)
    assert deleted == 1
    rows = list(table.search().limit(10).to_list())
    chunk_ids = sorted(r["chunk_id"] for r in rows)
    assert "ai_act.1.es" not in chunk_ids
    assert "ai_act.1.en" in chunk_ids
    assert "ai_act.2.es" in chunk_ids


def test_delete_by_article_rejects_unsafe_input(tmp_path: Path) -> None:
    """delete_by_article must validate inputs to prevent LanceDB filter injection."""
    table = store.connect(tmp_path / "t.lance")
    with pytest.raises(ValueError, match="Unsafe"):
        store.delete_by_article("ai_act.1' OR 1=1 --", "es", table)
    with pytest.raises(ValueError, match="Unsafe"):
        store.delete_by_article("ai_act.1", "es' OR 1=1 --", table)


def test_connect_create_false_raises_on_missing_store(tmp_path: Path) -> None:
    """obs-02: read-only connect never materialises a store/table; missing → raise."""
    missing = tmp_path / "does-not-exist.lance"
    with pytest.raises(FileNotFoundError):
        store.connect(missing, create=False)
    assert not missing.exists()  # the read-only probe did not mkdir


def test_connect_create_false_raises_on_missing_table(tmp_path: Path) -> None:
    """A LanceDB dir that exists but has no `chunks` table → FileNotFoundError."""
    empty = tmp_path / "empty.lance"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        store.connect(empty, create=False)


def test_connect_create_false_opens_existing_table(tmp_path: Path) -> None:
    """When the table exists, read-only connect opens it normally."""
    path = tmp_path / "t.lance"
    store.connect(path)  # create=True: materialise the table
    table = store.connect(path, create=False)
    assert table.count_rows() == 0
