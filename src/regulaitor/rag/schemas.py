"""Pydantic v2 schemas for the RAG layer.

`Chunk` is what the chunker emits; `ChunkRecord` is what the LanceDB store persists
(adds the embedding vector and the embedding model identifier). `RagBuildSummary`
is the structured return of `rag.build.run()`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from regulaitor.corpus.schemas import Language, Norma, SourceFormat


class Chunk(BaseModel):
    """Output of the chunker. No embedding yet — that is filled in by the embedder."""

    chunk_id: str  # globally unique: "{norma}.{articulo}[.{apartado}].{lang}"
    article_id: str  # "{norma}.{articulo}[.{apartado}]"
    norma: Norma
    articulo: str
    apartado: str | None  # None when the chunk is the whole article (no split)
    language: Language
    text: str
    text_normalized: str  # lowercased, accents stripped, whitespace collapsed
    token_count: int  # BGE-M3 tokens (XLM-RoBERTa tokenizer)
    celex: str
    version: str
    source_format: SourceFormat
    source_url: str
    hash: str  # SHA256 of the article text (inherits from H1 LanguageEntry.hash)


class ChunkRecord(Chunk):
    """Chunk + embedding. Persisted in LanceDB."""

    embedding: list[float]  # 1024-dim BGE-M3 dense vector
    embedding_model: str  # e.g. "BAAI/bge-m3@<sha256>"


class RagBuildSummary(BaseModel):
    """Returned by `rag.build.run()` describing what happened in the build."""

    chunks_added: int = 0  # new chunks (article had none before)
    chunks_unchanged: int = 0  # skipped because hash + model unchanged
    chunks_recomputed: int = 0  # re-embedded because hash or model changed
    errors: int = 0
    skipped_corpora: list[str] = Field(default_factory=list)
