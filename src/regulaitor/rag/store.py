"""LanceDB store for RAG chunks. Single global table partitioned by metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lancedb  # type: ignore[import-untyped]
import pyarrow as pa

from regulaitor.rag.schemas import ChunkRecord

DEFAULT_PATH = Path("corpus/indexes/regulaitor.lance")
TABLE_NAME = "chunks"

SCHEMA = pa.schema(
    [
        pa.field("chunk_id", pa.string(), nullable=False),
        pa.field("article_id", pa.string(), nullable=False),
        pa.field("norma", pa.string(), nullable=False),
        pa.field("articulo", pa.string(), nullable=False),
        pa.field("apartado", pa.string(), nullable=True),
        pa.field("language", pa.string(), nullable=False),
        pa.field("text", pa.string(), nullable=False),
        pa.field("text_normalized", pa.string(), nullable=False),
        pa.field("token_count", pa.int32(), nullable=False),
        pa.field("celex", pa.string(), nullable=False),
        pa.field("version", pa.string(), nullable=False),
        pa.field("source_format", pa.string(), nullable=False),
        pa.field("source_url", pa.string(), nullable=False),
        pa.field("hash", pa.string(), nullable=False),
        pa.field("embedding", pa.list_(pa.float32(), 1024), nullable=False),
        pa.field("embedding_model", pa.string(), nullable=False),
    ]
)


def connect(path: Path = DEFAULT_PATH) -> Any:
    """Open or create the chunks table at the given path.

    ``path`` is the directory of the LanceDB database (a directory, not a single
    file — LanceDB stores its data as a tree of arrow files).
    """
    path.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(path))
    if TABLE_NAME in db.list_tables().tables:
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=SCHEMA)


def upsert(records: list[ChunkRecord], table: Any) -> int:
    """Upsert by chunk_id. Existing rows with matching chunk_id are deleted first.

    Returns the number of rows written. Empty ``records`` returns 0 without any
    LanceDB call.
    """
    if not records:
        return 0
    chunk_ids = [r.chunk_id for r in records]
    quoted = ", ".join(f"'{cid}'" for cid in chunk_ids)
    table.delete(f"chunk_id IN ({quoted})")
    rows = [r.model_dump() for r in records]
    table.add(rows)
    return len(rows)


def delete_by_article(article_id: str, language: str, table: Any) -> int:
    """Delete all chunks belonging to a specific article in a specific language.

    Used when re-processing an article whose hash changed: the orchestrator
    deletes all old chunks first, then upserts fresh ones.

    Returns the count returned by LanceDB's delete (varies between 0 and N
    matching rows).
    """
    where = f"chunk_id LIKE '{article_id}.%.{language}' " f"OR chunk_id = '{article_id}.{language}'"
    result = table.delete(where)
    return int(result.num_deleted_rows) if result is not None else 0
