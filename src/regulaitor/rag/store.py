"""LanceDB store for RAG chunks. Single global table partitioned by metadata."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import lancedb
import pyarrow as pa

from regulaitor.rag.schemas import ChunkRecord

if TYPE_CHECKING:
    import lancedb.table

# Default LanceDB store directory. Resolution order (v0.1.26 H16 deploy-prep):
# 1. LANCEDB_PATH env (absolute path; HF Spaces / Render / Fly.io persistent volume)
# 2. fallback to <cwd>/corpus/indexes/regulaitor.lance (dev + CI)
# Production callers (rag.build.run, scripts.rag_build) run from the repo root,
# so the fallback resolves to <repo>/corpus/indexes/regulaitor.lance.
_LANCEDB_ENV = os.getenv("LANCEDB_PATH", "").strip()
DEFAULT_PATH = Path(_LANCEDB_ENV) if _LANCEDB_ENV else Path("corpus/indexes/regulaitor.lance")
TABLE_NAME = "chunks"

# Allowlist for path-segment characters in chunk IDs and language codes.
# Matches the deterministic format {norma}.{articulo}[.{apartado}].{lang}
# where each segment is alphanumeric, dot, hyphen, or underscore.
_SAFE_ID_PATTERN = re.compile(r"^[a-z0-9_.-]+$")

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


def connect(path: Path = DEFAULT_PATH) -> lancedb.table.Table:
    """Open or create the chunks table at the given path.

    ``path`` is the directory of the LanceDB database (a directory, not a single
    file — LanceDB stores its data as a tree of arrow files).
    """
    path.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(path))
    if TABLE_NAME in db.list_tables().tables:
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=SCHEMA)


def upsert(records: list[ChunkRecord], table: lancedb.table.Table) -> int:
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


def delete_by_article(article_id: str, language: str, table: lancedb.table.Table) -> int:
    """Delete all chunks belonging to a specific article in a specific language.

    Used when re-processing an article whose hash changed: the orchestrator
    deletes all old chunks first, then upserts fresh ones.

    Returns the count returned by LanceDB's delete (varies between 0 and N
    matching rows).

    Validates `article_id` and `language` against `_SAFE_ID_PATTERN` to prevent
    LanceDB filter injection. The orchestrator constructs both from typed
    schema fields (`Norma`, `Language`, `articulo`), so production callers
    always pass safe values. The guard is defensive against a future MCP tool
    or HTTP route forwarding user input to this function.
    """
    if not _SAFE_ID_PATTERN.match(article_id) or not _SAFE_ID_PATTERN.match(language):
        raise ValueError(f"Unsafe article_id or language: {article_id!r}, {language!r}")
    where = f"chunk_id LIKE '{article_id}.%.{language}' " f"OR chunk_id = '{article_id}.{language}'"
    result = table.delete(where)
    return int(result.num_deleted_rows) if result is not None else 0
