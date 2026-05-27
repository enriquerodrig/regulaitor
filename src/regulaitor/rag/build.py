"""RAG build orchestrator.

Reads H1 manifests + corpus/processed/, calls the chunker and embedder,
upserts the LanceDB store, and extends each LanguageEntry of the manifests
with `chunks`, `embedded_at`, and `embedding_model`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus._targets import expand_targets
from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.rag import chunking, embeddings, reranker, store
from regulaitor.rag.schemas import ChunkRecord, RagBuildSummary

logger = logging.getLogger("regulaitor.rag.build")

CORPUS_ROOT = Path("corpus")
MANIFEST_DIR = CORPUS_ROOT / "manifests"
PROCESSED_DIR = CORPUS_ROOT / "processed"
# INDEX_PATH honors LANCEDB_PATH env (v0.1.26 H16 deploy-prep) via store.DEFAULT_PATH;
# falls back to corpus/indexes/regulaitor.lance when env is unset (dev + CI).
INDEX_PATH = store.DEFAULT_PATH


def run(
    corpus: Norma | Literal["all"] = "all",
    languages: list[Language] | Literal["all"] = "all",
    *,
    force_rebuild: bool = False,
) -> RagBuildSummary:
    """Run the RAG build pipeline.

    For each (corpus, language, article):
      - Skip when not force_rebuild AND entry.chunks (non-empty) AND
        entry.embedding_model == current_model. Increments `chunks_unchanged`.
      - Otherwise: chunk → embed → DELETE-by-article (if had chunks) → upsert
        LanceDB → update LanguageEntry with new chunks, embedded_at,
        embedding_model. Increments `chunks_added` (fresh) or
        `chunks_recomputed` (article had previous chunks).

    Manifests are written atomically per corpus via `manifest.save_atomic`.

    Atomicity caveat: if `store.upsert` succeeds but `save_atomic` fails after
    (e.g., disk full), the LanceDB has new chunks but the manifest is stale.
    The next run will re-embed — recoverable. The window is small.

    Returns a `RagBuildSummary` with cumulative counts across all processed
    corpora. The caller (CLI) decides exit code based on `summary.errors`.
    """
    summary = RagBuildSummary()
    corpora, langs = expand_targets(corpus, languages)
    table = store.connect(INDEX_PATH)
    current_model = embeddings.model_identifier()

    for c in corpora:
        # Snapshot accumulators at start of corpus to compute per-corpus deltas
        delta_added = summary.chunks_added
        delta_recomputed = summary.chunks_recomputed
        delta_unchanged = summary.chunks_unchanged

        manifest_path = MANIFEST_DIR / f"{c}.json"
        m = manifest_mod.load(manifest_path)
        if m is None:
            logger.error("manifest not found for %s; run `make ingest` first", c)
            summary.skipped_corpora.append(c)
            summary.errors += 1
            continue
        logger.info("manifest %s: loaded with %d articles", c, len(m.articles))

        # Cache processed articles per (corpus, lang) to avoid re-reading per article
        processed_cache: dict[Language, list[ParsedArticle]] = {}
        for lang in langs:
            processed_path = PROCESSED_DIR / f"{c}_{lang}.json"
            if not processed_path.exists():
                logger.error("processed file missing: %s", processed_path)
                summary.errors += 1
                continue
            processed_cache[lang] = _load_processed(processed_path)

        updated_articles = []
        for article in m.articles:
            updated_languages = dict(article.languages)
            for lang in langs:
                if lang not in processed_cache:
                    continue
                entry = article.languages.get(lang)
                if entry is None:
                    continue

                if not force_rebuild and entry.chunks and entry.embedding_model == current_model:
                    summary.chunks_unchanged += len(entry.chunks)
                    continue

                parsed = _find_article(processed_cache[lang], article.articulo)
                if parsed is None:
                    logger.error(
                        "article %s/%s not found in processed cache",
                        c,
                        article.articulo,
                    )
                    summary.errors += 1
                    continue

                chunks = chunking.chunk_article(
                    parsed,
                    norma=c,
                    language=lang,
                    celex=m.celex,
                    version=m.version,
                    source_format=m.source_format,
                    source_url=entry.source_url,
                    hash=entry.hash,
                )

                vectors = embeddings.embed([ch.text for ch in chunks])
                records = [
                    ChunkRecord(
                        **ch.model_dump(),
                        embedding=vec,
                        embedding_model=current_model,
                    )
                    for ch, vec in zip(chunks, vectors, strict=True)
                ]

                if entry.chunks:
                    store.delete_by_article(article.article_id, lang, table)
                    summary.chunks_recomputed += len(records)
                else:
                    summary.chunks_added += len(records)

                store.upsert(records, table)

                updated_languages[lang] = entry.model_copy(
                    update={
                        "chunks": [r.chunk_id for r in records],
                        "embedded_at": datetime.now(UTC),
                        "embedding_model": current_model,
                    }
                )
            updated_articles.append(article.model_copy(update={"languages": updated_languages}))

        new_chunks_total = sum(
            len(e.chunks) for art in updated_articles for e in art.languages.values()
        )
        new_embedded_total = sum(
            1
            for art in updated_articles
            for e in art.languages.values()
            if e.embedded_at is not None
        )
        new_stats = m.stats.model_copy(
            update={
                "chunks_total": new_chunks_total,
                "embedded_total": new_embedded_total,
            }
        )
        new_manifest = m.model_copy(update={"articles": updated_articles, "stats": new_stats})
        manifest_mod.save_atomic(manifest_path, new_manifest)

        # Compute per-corpus deltas for this log line
        per_corpus_added = summary.chunks_added - delta_added
        per_corpus_recomputed = summary.chunks_recomputed - delta_recomputed
        per_corpus_unchanged = summary.chunks_unchanged - delta_unchanged
        logger.info(
            "manifest %s: extended (added=%d recomputed=%d unchanged=%d)",
            c,
            per_corpus_added,
            per_corpus_recomputed,
            per_corpus_unchanged,
        )

    reranker.warmup()
    logger.info(
        "rag-build summary: added=%d recomputed=%d unchanged=%d errors=%d",
        summary.chunks_added,
        summary.chunks_recomputed,
        summary.chunks_unchanged,
        summary.errors,
    )
    return summary


def _load_processed(path: Path) -> list[ParsedArticle]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ParsedArticle(
            articulo=a["articulo"],
            title=a.get("title"),
            text=a["text"],
            paragraphs=[
                ParsedParagraph(apartado=p["apartado"], text=p["text"])
                for p in a.get("paragraphs", [])
            ],
        )
        for a in data
    ]


def _find_article(articles: list[ParsedArticle], articulo: str) -> ParsedArticle | None:
    return next((a for a in articles if a.articulo == articulo), None)
