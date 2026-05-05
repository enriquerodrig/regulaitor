"""Canonical retrieval pipeline: embed -> store query -> rerank -> enrich.

Single source of truth used by both the MCP search_articles tool and the
RetrieverAgent. Decisions log 2026-05-05 entry
"Arquitectura: helper comun con adapters finos".
"""

from __future__ import annotations

from regulaitor.citation.schemas import RetrievedChunk
from regulaitor.corpus import loader
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.rag import embeddings, reranker, store
from regulaitor.rag.build import INDEX_PATH

PRE_RERANK = 50


def run(
    query: str,
    corpus: Norma,
    language: Language,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve top-`top_k` chunks for `query` filtered by corpus + language.

    Internal pre-rerank candidate count is fixed at PRE_RERANK=50 (decisions
    log 2026-05-05 entry "Top-k en retrieval"). top_k is post-rerank.

    The `where` clause interpolates `corpus` and `language` directly. Both are
    closed `Literal` enums (`Norma`, `Language`) typed at the function
    boundary, so the values are not user-controlled strings -- no SQL
    injection vector. Pyright/mypy enforce the constraint upstream.
    """
    [query_vec] = embeddings.embed([query])

    table = store.connect(INDEX_PATH)
    where_clause = f"norma = '{corpus}' AND language = '{language}'"
    candidates = table.search(query_vec).where(where_clause).limit(PRE_RERANK).to_list()

    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=top_k)

    if not reranked:
        return []

    meta = loader.get_manifest_meta(corpus)

    return [
        RetrievedChunk(
            chunk_id=candidates[idx]["chunk_id"],
            norma=candidates[idx]["norma"],
            articulo=candidates[idx]["articulo"],
            apartado=candidates[idx]["apartado"],
            language=candidates[idx]["language"],
            text=candidates[idx]["text"],
            score=score,
            version=meta["version"],
            source_url=meta["source_url"],
        )
        for idx, score in reranked
    ]
