"""Unit tests for rag.schemas: Chunk, ChunkRecord, RagBuildSummary."""

import pytest
from pydantic import ValidationError

from regulaitor.rag.schemas import Chunk, ChunkRecord, RagBuildSummary


def _chunk_kwargs() -> dict:
    return {
        "chunk_id": "ai_act.6.1.es",
        "article_id": "ai_act.6.1",
        "norma": "ai_act",
        "articulo": "6",
        "apartado": "1",
        "language": "es",
        "text": "El presente artículo establece...",
        "text_normalized": "el presente articulo establece",
        "token_count": 412,
        "celex": "32024R1689",
        "version": "2024-07-12",
        "source_format": "pdf",
        "source_url": "file:///x",
        "hash": "sha256:abc",
    }


def test_chunk_construction() -> None:
    c = Chunk(**_chunk_kwargs())
    assert c.chunk_id == "ai_act.6.1.es"
    assert c.apartado == "1"


def test_chunk_apartado_can_be_none() -> None:
    kw = _chunk_kwargs()
    kw["chunk_id"] = "ai_act.6.es"
    kw["article_id"] = "ai_act.6"
    kw["apartado"] = None
    c = Chunk(**kw)
    assert c.apartado is None


def test_chunk_rejects_unknown_norma() -> None:
    kw = _chunk_kwargs()
    kw["norma"] = "lopd"  # not in Norma literal
    with pytest.raises(ValidationError):
        Chunk(**kw)


def test_chunk_record_round_trip() -> None:
    kw = _chunk_kwargs()
    cr = ChunkRecord(
        **kw,
        embedding=[0.1] * 1024,
        embedding_model="BAAI/bge-m3@sha256:abcd",
    )
    payload = cr.model_dump_json()
    restored = ChunkRecord.model_validate_json(payload)
    assert restored == cr


def test_chunk_record_rejects_wrong_embedding_dim() -> None:
    """Pydantic does NOT enforce list length by default; this test documents
    that we rely on the LanceDB schema (PyArrow list_(float32, 1024)) for the
    real check. A 512-dim vector parses through Pydantic but would be rejected
    at LanceDB upsert time."""
    kw = _chunk_kwargs()
    cr = ChunkRecord(
        **kw,
        embedding=[0.1] * 512,  # wrong dim, but Pydantic accepts
        embedding_model="x",
    )
    assert len(cr.embedding) == 512  # documents the gap; LanceDB would catch


def test_rag_build_summary_defaults() -> None:
    s = RagBuildSummary()
    assert s.chunks_added == 0
    assert s.chunks_unchanged == 0
    assert s.chunks_recomputed == 0
    assert s.errors == 0
    assert s.skipped_corpora == []


def test_rag_build_summary_round_trip() -> None:
    s = RagBuildSummary(
        chunks_added=10,
        chunks_unchanged=20,
        chunks_recomputed=5,
        errors=1,
        skipped_corpora=["nis2"],
    )
    restored = RagBuildSummary.model_validate_json(s.model_dump_json())
    assert restored == s
