"""Canonical retrieval pipeline: embed -> store query -> rerank -> enrich.

Single source of truth used by both the MCP search_articles tool and the
RetrieverAgent. Decisions log 2026-05-05 entry
"Arquitectura: helper comun con adapters finos".
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from regulaitor.citation.schemas import RetrievedChunk
from regulaitor.corpus import loader
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.rag import embeddings, reranker, store
from regulaitor.rag.build import INDEX_PATH

logger = logging.getLogger("regulaitor.rag.retrieval")

PRE_RERANK = 50


@dataclass(frozen=True)
class RetrievalConfig:
    """H15.1 tuning levers. Frozen defaults == v0.1.5-h15 behaviour so the
    explicit-corpus path is provably unchanged; the `auto` path and any tuned
    value are the A/B variable (ADR-0017). `query_normalize` stays deterministic
    (no LLM — preserves the LLM-free-retriever principle).

    v0.1.10 (xcorpus-002 follow-up, motivated by single-article dominance):
    ``max_chunks_per_article`` caps the number of chunks per (norma, article)
    key in the reranked list BEFORE the purity gate fires. Default `None` =
    no cap = backward-compat with v0.1.9. Opt-in via env override or explicit
    config; see ``docs/xcorpus_002_investigation.md``.
    """

    pre_rerank: int = PRE_RERANK  # 50
    top_k: int = 5
    purity_threshold: float = 0.6  # auto path only; >= is inclusive
    query_normalize: bool = False  # default identity == current behaviour
    max_chunks_per_article: int | None = None  # v0.1.10; None == no cap == v0.1.9 behaviour

    def __post_init__(self) -> None:
        if not isinstance(self.pre_rerank, int) or isinstance(self.pre_rerank, bool):
            raise TypeError(f"pre_rerank must be int, got {type(self.pre_rerank).__name__}")
        if not isinstance(self.top_k, int) or isinstance(self.top_k, bool):
            raise TypeError(f"top_k must be int, got {type(self.top_k).__name__}")
        if self.top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {self.top_k}")
        if not isinstance(self.purity_threshold, int | float) or isinstance(
            self.purity_threshold, bool
        ):
            raise TypeError(
                f"purity_threshold must be float, got {type(self.purity_threshold).__name__}"
            )
        if not isinstance(self.query_normalize, bool):
            raise TypeError(
                f"query_normalize must be bool, got {type(self.query_normalize).__name__}"
            )
        # v0.1.10 — max_chunks_per_article validation: None OR positive int.
        if self.max_chunks_per_article is not None:
            if not isinstance(self.max_chunks_per_article, int) or isinstance(
                self.max_chunks_per_article, bool
            ):
                raise TypeError(
                    "max_chunks_per_article must be int or None, "
                    f"got {type(self.max_chunks_per_article).__name__}"
                )
            if self.max_chunks_per_article < 1:
                raise ValueError(
                    f"max_chunks_per_article must be >= 1, got {self.max_chunks_per_article}"
                )


_KNOWN_FIELDS = frozenset(RetrievalConfig.__dataclass_fields__)


def _config_from_env() -> RetrievalConfig:
    """Read REGULAITOR_RETRIEVAL_CONFIG and return a frozen RetrievalConfig.

    Eval-only env-override seam (ADR-0017), mirroring the
    REGULAITOR_ANALYST_PROMPT_VERSION pattern (ADR-0016 / analyst.py __init__).

    - Unset or empty string -> RetrievalConfig() defaults (production-byte-identical).
    - Valid JSON object with a subset of known fields -> apply overrides, keep
      defaults for unspecified fields.
    - Invalid cases -> WARNING + RetrievalConfig() defaults, never raises:
        * malformed JSON (JSONDecodeError)
        * non-dict JSON (e.g. list, int, string)
        * unknown key not in RetrievalConfig.__dataclass_fields__
        * wrong type for a field (TypeError raised by __post_init__)
        * value violating a constraint (ValueError raised by __post_init__,
          e.g. top_k < 1)
    """
    raw: str | None = os.environ.get("REGULAITOR_RETRIEVAL_CONFIG")
    if not raw:
        return RetrievalConfig()

    parsed: Any
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "REGULAITOR_RETRIEVAL_CONFIG=%r is not valid JSON (%s); using defaults",
            raw,
            exc,
        )
        return RetrievalConfig()

    if not isinstance(parsed, dict):
        logger.warning(
            "REGULAITOR_RETRIEVAL_CONFIG=%r must be a JSON object (got %s); using defaults",
            raw,
            type(parsed).__name__,
        )
        return RetrievalConfig()

    unknown = set(parsed) - _KNOWN_FIELDS
    if unknown:
        logger.warning(
            "REGULAITOR_RETRIEVAL_CONFIG=%r contains unknown field(s) %s; using defaults",
            raw,
            sorted(unknown),
        )
        return RetrievalConfig()

    try:
        return RetrievalConfig(**{k: parsed[k] for k in parsed})
    except (TypeError, ValueError) as exc:
        logger.warning(
            "REGULAITOR_RETRIEVAL_CONFIG=%r produced invalid RetrievalConfig (%s); using defaults",
            raw,
            exc,
        )
        return RetrievalConfig()


DEFAULT_CONFIG: RetrievalConfig = _config_from_env()

_T = TypeVar("_T")


def _apply_per_article_dedup(
    ranked: list[tuple[str, str, _T]], max_per_article: int
) -> list[tuple[str, _T]]:
    """v0.1.10 — cap chunks per (norma, article) key in best-first order.

    Pure helper. Input is `(norma, article, payload)` triples best-first
    (as the reranker emits them); output is `(norma, payload)` pairs ready to
    be passed to `_apply_purity_gate`. Preserves order; drops chunks beyond the
    cap for any given (norma, article) key.

    Motivated by the v0.1.9 xcorpus-002 diagnostic: standard bge-reranker-v2-m3
    can emit several paragraphs of the same article at the top of its ranking
    (the "single-article dominance" failure mode), starving cross-corpus
    queries of articles from other corpora the user actually needs cited. The
    cap is the surgical, deterministic, $0 corrective step. See
    `docs/xcorpus_002_investigation.md`.
    """
    seen: Counter[tuple[str, str]] = Counter()
    out: list[tuple[str, _T]] = []
    for norma, article, payload in ranked:
        key = (norma, article)
        if seen[key] < max_per_article:
            seen[key] += 1
            out.append((norma, payload))
    return out


def _apply_purity_gate(
    ranked: list[tuple[str, _T]], cfg: RetrievalConfig
) -> tuple[list[tuple[str, _T]], list[Norma]]:
    """Deterministic post-rerank corpus purity gate (ADR-0017).

    `ranked` is the reranked list best-first as (norma, payload). share(norma)
    = count of that norma among the top-`cfg.top_k` divided by `cfg.top_k`.
    If max share >= cfg.purity_threshold -> collapse to that norma (no-leakage
    restored); else -> return the top-`cfg.top_k` multi-corpus. Returns
    (kept_pairs_best_first, sorted_resolved_normas).
    The denominator is always cfg.top_k (not len(window)): a short candidate pool is weaker
    dominance evidence, so the gate is intentionally stricter — count-based, not relative.
    """
    if not ranked:
        return [], cast(list[Norma], [])
    window = ranked[: cfg.top_k]
    counts = Counter(n for n, _ in window)
    top_norma, top_count = counts.most_common(1)[0]
    if top_count / cfg.top_k >= cfg.purity_threshold:
        kept = [(n, p) for (n, p) in ranked if n == top_norma][: cfg.top_k]
        return kept, cast(list[Norma], [top_norma])
    return window, cast(list[Norma], sorted(counts))


def _enrich(candidates: list[dict], reranked: list[tuple[int, float]]) -> list[RetrievedChunk]:
    """Shared candidates -> RetrievedChunk tail. Manifest meta is resolved
    PER chunk by that chunk's own `norma` (a multi-corpus `run_auto` result
    mixes normas — a DORA chunk must carry DORA's version/url, a NIS2 chunk
    NIS2's). For the explicit single-corpus `run()` all chunks share `corpus`,
    so per-chunk resolution is behaviour-neutral vs the prior single call."""
    out: list[RetrievedChunk] = []
    for idx, score in reranked:
        c = candidates[idx]
        meta = loader.get_manifest_meta(c["norma"])
        out.append(
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                norma=c["norma"],
                articulo=c["articulo"],
                apartado=c["apartado"],
                language=c["language"],
                text=c["text"],
                score=score,
                version=meta["version"],
                source_url=meta["source_url"],
            )
        )
    return out


def run(
    query: str,
    corpus: Norma,
    language: Language,
    top_k: int | None = None,
    pre_rerank: int | None = None,
) -> list[RetrievedChunk]:
    """Explicit-corpus retrieval. Production-byte-identical to v0.1.6-h15.1 when
    `REGULAITOR_RETRIEVAL_CONFIG` is unset (the env default). `corpus` is one of
    the four norms — never "auto" (the graph routes "auto" to run_auto).

    Resolution of `top_k` / `pre_rerank` (H15.2, ADR-0018 — closes the §22.22
    design-defect disclosed POST-SPEND in H15.1-T10/T11):
      - `top_k=None` -> `DEFAULT_CONFIG.top_k` (default 5) resolved AT CALL TIME.
      - `pre_rerank=None` -> `DEFAULT_CONFIG.pre_rerank` (default 50) resolved
         AT CALL TIME.
      - Explicit non-None values win (per-call override, backward-compatible).

    Call-time resolution (NOT function-definition-time capture) lets the eval
    harness rebind `DEFAULT_CONFIG` via `REGULAITOR_RETRIEVAL_CONFIG` env at
    process start and have the explicit-corpus path consume those values — this
    is exactly what H15.1's 30-calibration A/B was structurally unable to
    measure (the §22.22 defect this milestone closes).

    The `where` clause interpolates `corpus` and `language` directly. Both are
    closed `Literal` enums (`Norma`, `Language`) typed at the function
    boundary, so the values are not user-controlled strings -- no SQL
    injection vector. Pyright/mypy enforce the constraint upstream. The
    construction is byte-identical character-for-character to v0.1.6-h15.1
    under any env state — the no-leakage-critical §22.18/H14 invariant
    (asserted by T6 `tests/unit/test_explicit_path_unchanged.py` for env-unset
    and by `tests/unit/test_explicit_config_wired.py` for env-set).
    """
    effective_top_k = top_k if top_k is not None else DEFAULT_CONFIG.top_k
    effective_pre_rerank = pre_rerank if pre_rerank is not None else DEFAULT_CONFIG.pre_rerank

    [query_vec] = embeddings.embed([query])

    table = store.connect(INDEX_PATH)
    where_clause = f"norma = '{corpus}' AND language = '{language}'"
    candidates = table.search(query_vec).where(where_clause).limit(effective_pre_rerank).to_list()

    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=effective_top_k)

    if not reranked:
        return []

    return _enrich(candidates, reranked)


def run_auto(
    query: str, language: Language, cfg: RetrievalConfig
) -> tuple[list[RetrievedChunk], list[Norma]]:
    """H15.1 cross-corpus path (ADR-0017): multi-corpus retrieve -> rerank ->
    (v0.1.10 optional per-article dedup) -> post-rerank purity gate.
    Returns (chunks, resolved_normas).

    v0.1.10 (xcorpus-002 follow-up): when `cfg.max_chunks_per_article` is set,
    the reranked list is deduplicated to at most N chunks per (norma, article)
    key BEFORE the purity gate fires. Backward-compat default `None` skips this
    step entirely (v0.1.9 behaviour). See `docs/xcorpus_002_investigation.md`.
    """
    [query_vec] = embeddings.embed([query])

    table = store.connect(INDEX_PATH)
    where_clause = f"language = '{language}'"
    candidates = table.search(query_vec).where(where_clause).limit(cfg.pre_rerank).to_list()

    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=cfg.pre_rerank)

    if not reranked:
        return [], []

    # v0.1.10 — optional per-article dedup BEFORE the purity gate. When
    # `cfg.max_chunks_per_article is None` (the backward-compat default), the
    # dedup is skipped entirely and the construction below collapses to the
    # exact v0.1.9 expression.
    if cfg.max_chunks_per_article is not None:
        ranked_triples = [
            (candidates[idx]["norma"], candidates[idx]["articulo"], (idx, score))
            for idx, score in reranked
        ]
        ranked_pairs = _apply_per_article_dedup(ranked_triples, cfg.max_chunks_per_article)
    else:
        ranked_pairs = [(candidates[idx]["norma"], (idx, score)) for idx, score in reranked]

    kept, resolved = _apply_purity_gate(ranked_pairs, cfg)
    enriched = _enrich(candidates, [p for _, p in kept])
    return enriched, resolved
