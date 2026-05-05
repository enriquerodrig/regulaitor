"""bge-reranker-v2-m3 cross-encoder wrapper.

The reranker re-scores `(query, passage)` pairs after dense retrieval, producing
a more accurate top-N. It is loaded lazily as a module-level singleton, same
pattern as `rag.embeddings`. Active use is by H3's Retriever-Agent; H2 only
loads it for warmup so the first H3 query has no cold-start latency.
"""

from __future__ import annotations

from typing import Any

from FlagEmbedding import FlagReranker

DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3"

_RERANKER: Any | None = None


def _ensure_loaded(model_name: str = DEFAULT_RERANKER) -> Any:
    global _RERANKER
    if _RERANKER is None:
        _RERANKER = FlagReranker(model_name, use_fp16=False)
    return _RERANKER


def rerank(
    query: str,
    passages: list[str],
    top_n: int | None = None,
) -> list[tuple[int, float]]:
    """Score each passage against `query`. Return list of `(original_index, score)`
    sorted by score descending. If `top_n` is set, truncate.

    Empty `passages` returns empty list without loading the model.
    """
    if not passages:
        return []
    model = _ensure_loaded()
    scores = model.compute_score([(query, p) for p in passages], normalize=True)
    ranked = sorted(enumerate(scores), key=lambda kv: kv[1], reverse=True)
    return ranked[:top_n] if top_n else ranked


def warmup() -> None:
    """Force the model to load and process one dummy query.

    Called by `rag.build.run()` at the end of a build so that the first real
    query (in H3) does not pay the cold-start cost.
    """
    _ensure_loaded()
    rerank("warmup", ["dummy passage"], top_n=1)
