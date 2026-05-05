# H2 RAG Base — Design Spec

- **Date:** 2026-05-04
- **Milestone scope:** This document designs the RAG base layer for RegulAItor. **H2 implements** chunker + embedder + reranker (load only) + LanceDB store + manifest extension. **H3 will implement** the Retriever-Agent that wraps this layer behind an MCP tool, plus the citation validator.
- **Approved decisions:** see `docs/technical_decisions_log.md` H2 section (entries from 2026-05-04).
- **Status:** approved by owner, ready for implementation plan.
- **Predecessor:** `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md`. H2 reads the manifests + processed/ that H1 produces.

---

## 1. Context

H1 closed with the four corpora ingested in Spanish and English: 424 `LanguageEntry` records across 212 unique articles, all with `chunks: []` and `embedded_at: None`. The H1→H2 boundary contract is: H1 delivers parsed-and-validated text; H2 turns that into a queryable vector index that downstream components (Retriever-Agent in H3, evaluation harness in H8) can consume without re-implementing chunking or embedding.

Without the work in H2, the project has no retrieval. Every later "no citation, no answer" claim collapses if a query cannot find the right article from a 212-article corpus. Equally, every academic claim about "RAG with multilingual cross-lingual alignment via BGE-M3" needs the embedder physically integrated, not just listed in a stack diagram.

The H1 spec §5 already pre-fixed two design choices that this spec inherits:

- Chunking is hybrid by token threshold (~1000 BGE-M3 tokens). Article-level if ≤ threshold; split by `apartado` (numbered paragraph) otherwise.
- Bilingual storage is one chunk per `(article, language)` joined by `article_id`. `chunk_id` format = `{article_id}[.{apartado}].{lang}`.

The remaining design surface — embedder local vs API, LanceDB schema, tokenizer swap, reranker scope, manifest update flow, embedding model versioning — was settled in the brainstorming session of 2026-05-04 and recorded in the technical decisions log.

---

## 2. Scope

### In scope (H2)

- Chunker (`rag/chunking.py`) producing `Chunk` records from `ParsedArticle` lists.
- Embedder (`rag/embeddings.py`) wrapping `BAAI/bge-m3` locally via `FlagEmbedding`. Exposes `embed(texts) → list[list[float]]` and `token_count(text) → int`.
- Reranker (`rag/reranker.py`) wrapping `BAAI/bge-reranker-v2-m3` locally. Loaded and warmed up in H2; the **active use** by the Retriever-Agent comes in H3, but the module ships ready.
- LanceDB store (`rag/store.py`) with single global table `chunks`, partitioned by metadata.
- Orchestrator (`rag/build.py`) reading H1 manifests and `corpus/processed/`, running the chunk → embed → upsert → manifest-extend pipeline.
- CLI (`scripts/rag_build.py`) wrapping the orchestrator. New Makefile target `make rag-build`.
- Schema extension: `LanguageEntry` adds `embedding_model: str | None` field.
- Tokenizer migration: `corpus/ingest.py` `_token_count` redirected from `tiktoken` to BGE-M3 native; `tiktoken` dependency removed; existing manifests refreshed via one-time `--force-reprocess` corpus run before the first `rag-build`.
- Test pyramid: unit + contract + integration (with stub embedder/reranker); coverage ≥ 90% on `src/regulaitor/rag/`.
- CI: HuggingFace cache key in workflow.

### Deferred to H3

- `Retriever-Agent` that consumes the RAG layer.
- MCP tool `search_articles(query, corpus, top_k)`.
- Citation validator initial version.
- Pydantic schemas for the agent contracts (`Citation`, `Finding`, `Answer`, `AuditResult`).

### Out of scope

- Multi-vector retrieval (BGE-M3 supports dense + sparse + multi-vector; we use dense only).
- Quantization (fp16, int8) — fp32 fits, perf is fine for the corpus size.
- Hybrid retrieval (BM25 + dense). Defer until H8 evaluation shows it's needed.
- Async/batched API for `embed`. The synchronous batched call in `FlagEmbedding` (`encode(batch_size=16)`) is sufficient for 427 chunks.
- A/B testing infrastructure for multiple embedders. The `embedding_model` field enables it later, but the orchestrator only writes one model at a time.

---

## 3. Approved decisions (recap)

| Decision | Choice | Source in log |
|---|---|---|
| Embedder | Local BGE-M3 via `FlagEmbedding` | "Embeddings BGE-M3 ejecutados localmente, no vía API" |
| LanceDB layout | Single table `chunks`, filter by metadata columns | "LanceDB con una única tabla `chunks`, particionada por metadata" |
| Tokenizer | Swap `tiktoken` → BGE-M3 (XLM-RoBERTa). Remove tiktoken from deps. | "Swap completo de tokenizer: tiktoken → BGE-M3 nativo" |
| Reranker scope | Full implementation in H2 (load + function). Active use in H3. | "Reranker (cross-encoder bge-reranker-v2-m3) entra completo en H2, no en H3" |
| Orchestrator | New `rag/build.py`, separate from `corpus/ingest.py`. New `make rag-build` target. | "Orquestador `rag/build.py` separado de `corpus/ingest.py`" |
| Embedding model versioning | New field `embedding_model: str | None` per `LanguageEntry`. Skip-condition is `hash AND model unchanged`. | "Versionado del modelo de embedding por `LanguageEntry`" |

---

## 4. Architecture

```
                        ┌──────────────────────────────────────┐
                        │  scripts/rag_build.py (CLI)          │
                        └────────────┬─────────────────────────┘
                                     │
                           [orchestrator: rag/build.py]
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       │                             │                             │
  rag/chunking.py             rag/embeddings.py             rag/reranker.py
   ParsedArticle →             texts → 1024-dim                 cross-encoder
   list[Chunk]                 BGE-M3 vectors                  bge-reranker-v2-m3
   (≤1000 tokens)              FlagEmbedding                   load + warmup in H2,
   tokenizer:                  local cache HF                   active use in H3
   XLM-RoBERTa
       │                             │                             │
       └─────────────────────────────┴─────────────────────────────┘
                                     │
                           [rag/store.py]
                            LanceDB write/query
                            single table "chunks"
                            metadata-filtered
                                     │
                                     ▼
                       [manifest extension]
                       corpus/manifest.save_atomic
                       extends H1 manifest with
                       chunks, embedded_at, embedding_model
```

### Boundary contract H1 → H2 → H3

After a successful H2 run:
- `corpus/manifests/{corpus}.json` (git-tracked) every `LanguageEntry` has `chunks: list[str]` populated, `embedded_at: datetime`, `embedding_model: str`.
- `corpus/indexes/regulaitor.lance` (git-ignored, local) contains a `chunks` table with one row per chunk, including the 1024-dim embedding column.
- `corpus/raw/` and `corpus/processed/` unchanged from H1.

H3 reads from `corpus/manifests/*.json` (for metadata) and from the LanceDB table (for vectors). H3 does not parse PDFs, does not re-embed, does not own the manifest write.

---

## 5. Components

All new modules live under `src/regulaitor/rag/`. No module in `rag/` imports from `agents/`, `mcp_server/`, `api/`, or `document/`. The `corpus/` package is allowed as a one-way dependency: `rag/` reads `corpus/manifests/`, `corpus/processed/`, and the `corpus.schemas` Pydantic types (read-only). The reciprocal dependency `corpus/ → rag/` exists only for `embeddings.token_count` (a pure function).

### 5.1 `rag/schemas.py`

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

from regulaitor.corpus.schemas import Norma, Language, SourceFormat

class Chunk(BaseModel):
    """Output of the chunker. No embedding yet."""
    chunk_id: str             # "ai_act.6.1.es" or "ai_act.6.es" if whole article
    article_id: str           # "ai_act.6.1" or "ai_act.6"
    norma: Norma
    articulo: str
    apartado: str | None      # None when chunk = whole article (no split)
    language: Language
    text: str
    text_normalized: str      # for citation_validator H3: lowercased, accents stripped, whitespace collapsed
    token_count: int          # BGE-M3 tokens
    celex: str
    version: str              # consolidation date
    source_format: SourceFormat
    source_url: str
    hash: str                 # SHA256 of the article text (inherits from H1 LanguageEntry.hash)

class ChunkRecord(Chunk):
    """Chunk + embedding. Persisted in LanceDB."""
    embedding: list[float]    # 1024-dim BGE-M3 dense
    embedding_model: str      # "BAAI/bge-m3@<sha256>"

class RagBuildSummary(BaseModel):
    """Returned by rag.build.run(). Mirrors corpus.IngestSummary in spirit."""
    chunks_added: int = 0       # newly created chunks (article had none before)
    chunks_unchanged: int = 0   # skipped because hash + model unchanged
    chunks_recomputed: int = 0  # re-embedded because hash or model changed
    errors: int = 0
    skipped_corpora: list[str] = []  # corpora skipped because manifest missing
```

### 5.2 `rag/embeddings.py`

```python
from FlagEmbedding import BGEM3FlagModel
from transformers import PreTrainedTokenizerFast

_MODEL: BGEM3FlagModel | None = None
_TOKENIZER: PreTrainedTokenizerFast | None = None
DEFAULT_MODEL = "BAAI/bge-m3"

def _ensure_loaded(model_name: str = DEFAULT_MODEL) -> BGEM3FlagModel:
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        _MODEL = BGEM3FlagModel(model_name, use_fp16=False)
        _TOKENIZER = _MODEL.tokenizer
    return _MODEL

def embed(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    model = _ensure_loaded()
    out = model.encode(texts, batch_size=batch_size, return_dense=True)
    return [vec.tolist() for vec in out["dense_vecs"]]

def token_count(text: str) -> int:
    _ensure_loaded()
    assert _TOKENIZER is not None  # noqa: S101 # nosec B101  # ensured by _ensure_loaded
    return len(_TOKENIZER.encode(text, add_special_tokens=False))

def model_identifier(model_name: str = DEFAULT_MODEL) -> str:
    """Return the canonical 'BAAI/bge-m3@<hash>' string for the loaded model.
    The hash is the snapshot hash from HF Hub cache (config.json or safetensors index).
    """
    # Implementation detail: read from `_MODEL.model.config._commit_hash` or
    # from the cache directory metadata. Spec leaves the exact mechanism to
    # implementation but pins the format.
    ...
```

`token_count` is the function that `corpus/ingest.py` will import to replace its `tiktoken`-based version. The first call lazily loads the model (~5 s); subsequent calls are O(text length).

### 5.3 `rag/reranker.py`

```python
from FlagEmbedding import FlagReranker

_RERANKER: FlagReranker | None = None
DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3"

def _ensure_loaded(model_name: str = DEFAULT_RERANKER) -> FlagReranker:
    global _RERANKER
    if _RERANKER is None:
        _RERANKER = FlagReranker(model_name, use_fp16=False)
    return _RERANKER

def rerank(
    query: str, passages: list[str], top_n: int | None = None
) -> list[tuple[int, float]]:
    """Score each passage against the query. Return list of (original_index, score)
    sorted by score descending. If top_n is set, truncate."""
    if not passages:
        return []
    model = _ensure_loaded()
    scores = model.compute_score(
        [(query, p) for p in passages], normalize=True
    )
    ranked = sorted(enumerate(scores), key=lambda kv: kv[1], reverse=True)
    return ranked[:top_n] if top_n else ranked

def warmup() -> None:
    """Force model load. Called once by rag/build.run() at end of build to
    eliminate cold-start latency on the first H3 query."""
    _ensure_loaded()
    rerank("warmup", ["dummy passage"], top_n=1)
```

### 5.4 `rag/chunking.py`

```python
from regulaitor.corpus.formex_parser import ParsedArticle
from regulaitor.corpus.schemas import Norma, Language, SourceFormat
from regulaitor.rag import embeddings
from regulaitor.rag.schemas import Chunk
import re
import unicodedata

THRESHOLD_TOKENS = 1000

def _normalize(text: str) -> str:
    """Lowercased, accents stripped, whitespace collapsed.
    For citation_validator H3 to do exact-match search."""
    s = unicodedata.normalize("NFD", text.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip()

def chunk_article(
    article: ParsedArticle,
    *,
    norma: Norma,
    language: Language,
    celex: str,
    version: str,
    source_format: SourceFormat,
    source_url: str,
    hash: str,
) -> list[Chunk]:
    article_id_base = f"{norma}.{article.articulo}"
    full_text = article.text
    full_tokens = embeddings.token_count(full_text)

    if full_tokens <= THRESHOLD_TOKENS or not article.paragraphs:
        # Single chunk = whole article
        chunk_id = f"{article_id_base}.{language}"
        return [Chunk(
            chunk_id=chunk_id,
            article_id=article_id_base,
            norma=norma, articulo=article.articulo, apartado=None,
            language=language,
            text=full_text,
            text_normalized=_normalize(full_text),
            token_count=full_tokens,
            celex=celex, version=version,
            source_format=source_format, source_url=source_url, hash=hash,
        )]

    # Article exceeds threshold: split by apartado
    out: list[Chunk] = []
    for p in article.paragraphs:
        article_id = f"{article_id_base}.{p.apartado}"
        chunk_id = f"{article_id}.{language}"
        out.append(Chunk(
            chunk_id=chunk_id,
            article_id=article_id,
            norma=norma, articulo=article.articulo, apartado=p.apartado,
            language=language,
            text=p.text,
            text_normalized=_normalize(p.text),
            token_count=embeddings.token_count(p.text),
            celex=celex, version=version,
            source_format=source_format, source_url=source_url, hash=hash,
        ))
    return out
```

Edge case: a single `apartado` exceeding 1000 tokens. The chunker emits the chunk anyway (no further split into sentences in H2; H8 evaluation may reveal we need it). A `logger.warning` is emitted with `(corpus, lang, articulo, apartado, tokens)` so we can audit later.

### 5.5 `rag/store.py`

```python
import lancedb
import pyarrow as pa
from pathlib import Path
from regulaitor.rag.schemas import ChunkRecord

DEFAULT_PATH = Path("corpus/indexes/regulaitor.lance")
TABLE_NAME = "chunks"

SCHEMA = pa.schema([
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
])

def connect(path: Path = DEFAULT_PATH) -> "lancedb.table.Table":
    """Open or create the chunks table."""
    db = lancedb.connect(str(path.parent))
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=SCHEMA)

def upsert(records: list[ChunkRecord], table: "lancedb.table.Table") -> int:
    """Upsert by chunk_id. Existing rows with matching chunk_id are deleted first.
    Returns the number of rows written."""
    if not records:
        return 0
    chunk_ids = [r.chunk_id for r in records]
    table.delete(f"chunk_id IN ({', '.join(repr(cid) for cid in chunk_ids)})")
    rows = [r.model_dump() for r in records]
    table.add(rows)
    return len(rows)

def delete_by_article(article_id: str, language: str, table) -> int:
    """Used when re-processing an article whose hash changed: delete all its chunks
    in that language before upserting fresh ones. Returns rows deleted."""
    where = (
        f"chunk_id LIKE '{article_id}.%.{language}' "
        f"OR chunk_id = '{article_id}.{language}'"
    )
    return table.delete(where)
```

### 5.6 `rag/build.py`

```python
from datetime import datetime, UTC
from pathlib import Path
from typing import Literal
import logging

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.schemas import Manifest, Norma, Language, LanguageEntry
from regulaitor.corpus._targets import expand_targets   # promoted from corpus/ingest._expand_targets
from regulaitor.rag import chunking, embeddings, reranker, store
from regulaitor.rag.schemas import Chunk, ChunkRecord, RagBuildSummary

logger = logging.getLogger("regulaitor.rag.build")

def run(
    corpus: Norma | Literal["all"] = "all",
    languages: list[Language] | Literal["all"] = "all",
    *,
    force_rebuild: bool = False,
) -> RagBuildSummary:
    summary = RagBuildSummary()
    corpora, langs = expand_targets(corpus, languages)
    table = store.connect()
    current_model = embeddings.model_identifier()

    for c in corpora:
        manifest_path = Path("corpus/manifests") / f"{c}.json"
        m = manifest_mod.load(manifest_path)
        if m is None:
            logger.error("manifest not found for %s — run `make ingest` first", c)
            summary.skipped_corpora.append(c)
            summary.errors += 1
            continue

        updated_articles = []
        for article in m.articles:
            updated_languages = dict(article.languages)
            for lang in langs:
                entry = article.languages.get(lang)
                if entry is None:
                    continue

                if not force_rebuild and entry.chunks and entry.embedding_model == current_model:
                    summary.chunks_unchanged += len(entry.chunks)
                    continue

                # Reload ParsedArticle from processed/
                parsed_article = _reload_one(c, lang, article.articulo)
                if parsed_article is None:
                    logger.error("processed file missing or article not found: %s/%s/%s",
                                 c, lang, article.articulo)
                    summary.errors += 1
                    continue

                chunks = chunking.chunk_article(
                    parsed_article,
                    norma=c, language=lang,
                    celex=m.celex, version=m.version,
                    source_format=m.source_format,
                    source_url=entry.source_url,
                    hash=entry.hash,
                )

                vectors = embeddings.embed([ch.text for ch in chunks])
                records = [
                    ChunkRecord(**ch.model_dump(), embedding=vec, embedding_model=current_model)
                    for ch, vec in zip(chunks, vectors, strict=True)
                ]

                if entry.chunks:
                    # Re-embedding existing article: clean up old chunks first
                    store.delete_by_article(article.article_id, lang, table)
                    summary.chunks_recomputed += len(records)
                else:
                    summary.chunks_added += len(records)

                store.upsert(records, table)

                updated_languages[lang] = entry.model_copy(update={
                    "chunks": [r.chunk_id for r in records],
                    "embedded_at": datetime.now(UTC),
                    "embedding_model": current_model,
                })
            updated_articles.append(article.model_copy(update={"languages": updated_languages}))

        new_manifest = m.model_copy(update={"articles": updated_articles})
        manifest_mod.save_atomic(manifest_path, new_manifest)
        logger.info("manifest %s: extended with chunks (%d added, %d recomputed, %d unchanged)",
                    c, summary.chunks_added, summary.chunks_recomputed, summary.chunks_unchanged)

    # Warm up reranker so the first H3 query is fast
    reranker.warmup()
    logger.info("rag-build summary: added=%d unchanged=%d recomputed=%d errors=%d",
                summary.chunks_added, summary.chunks_unchanged,
                summary.chunks_recomputed, summary.errors)
    return summary

def _reload_one(corpus: Norma, lang: Language, articulo: str):
    """Helper: load processed/<corpus>_<lang>.json, find the article, return ParsedArticle."""
    ...
```

### 5.7 `corpus/_targets.py` (refactor lift from `corpus/ingest.py`)

```python
"""Shared expansion of corpus and language wildcards. Promoted from
corpus/ingest._expand_targets in H1 to be reusable from rag/build.py in H2."""

from typing import Literal
from regulaitor.corpus.schemas import Norma, Language

ALL_NORMAS: tuple[Norma, ...] = ("ai_act", "gdpr", "nis2", "dora")
ALL_LANGUAGES: tuple[Language, ...] = ("es", "en")

def expand_targets(
    corpus: Norma | Literal["all"],
    languages: list[Language] | Literal["all"],
) -> tuple[list[Norma], list[Language]]:
    corpora: list[Norma] = list(ALL_NORMAS) if corpus == "all" else [corpus]
    langs: list[Language] = list(ALL_LANGUAGES) if languages == "all" else list(languages)
    return corpora, langs
```

`corpus/ingest.py` removes its private `_expand_targets` and imports from the new module. Tests for `_expand_targets` move with the function.

### 5.8 `scripts/rag_build.py`

```python
import argparse
import logging
import sys
from regulaitor.rag.build import run

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="regulaitor.rag_build")
    p.add_argument("--corpus", choices=["ai_act", "gdpr", "all"], default="all")
    p.add_argument("--lang", choices=["es", "en", "all"], default="all")
    p.add_argument("--force-rebuild", action="store_true",
                   help="Re-embed every chunk regardless of hash/model")
    p.add_argument("--verbose", "-v", action="store_true")
    return p

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    summary = run(
        corpus=args.corpus,
        languages="all" if args.lang == "all" else [args.lang],
        force_rebuild=args.force_rebuild,
    )
    print(summary.model_dump_json(indent=2))
    return 0 if summary.errors == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## 6. Data flow examples

### 6.1 First H2 build after H1 (clean slate)

```
$ make ingest                           # already done in H1
$ make rag-build
[build] manifest ai_act: loaded with 113 articles, all chunks empty
[build] embedder loading BAAI/bge-m3 from HF cache… 4.3s
[build] processing ai_act/es: 113 articles
  [chunk] 113 articles → ~113 chunks (number depends on which articles exceed 1000 BGE-M3 tokens)
  [embed] 113 chunks → 113 vectors of 1024-dim, batch=16, 8.1s
  [store] upserted 113 records into table "chunks"
[build] processing ai_act/en: ~113 articles → ~113 chunks → ~113 vectors → upsert
[build] processing gdpr/es: 99 articles → ~99-105 chunks depending on article length
[build] processing gdpr/en: 99 articles → ~99-105 chunks
[build] manifest extended for all 4 corpora; 424 LanguageEntry now have chunks, embedded_at, embedding_model
[build] reranker warmup: BAAI/bge-reranker-v2-m3 loaded, 0.6s
[build] summary: chunks_added=N, chunks_recomputed=0, chunks_unchanged=0, errors=0
       (N is the sum of chunks across all LanguageEntry; minimum 424 if no article exceeds threshold)
```

### 6.2 Idempotent re-run (no changes)

```
$ make rag-build
[build] embedder loading BAAI/bge-m3 (cache hit), 0.4s
[build] processing ai_act/es: skip 113 (hash + model match); skip 113 (en); skip 99+99 for gdpr
[build] manifest unchanged, no upsert
[build] reranker warmup, 0.6s
[build] summary: chunks_added=0, chunks_recomputed=0, chunks_unchanged=427, errors=0
```

### 6.3 Selective re-embed after model bump

Operator updates `pyproject.toml` to pin `FlagEmbedding>=2.0` (which loads a different BGE-M3 checkpoint). Running:

```
$ make rag-build
[build] current_model=BAAI/bge-m3@sha256:newhash...
[build] processing ai_act/es: model differs from manifest → re-embed all 113
  [embed] 113 chunks → 113 vectors (new model), 8.4s
  [store] delete_by_article + upsert per article (113 articles)
[build] same for ai_act/en, gdpr/es, gdpr/en
[build] summary: chunks_added=0, chunks_recomputed=427, chunks_unchanged=0, errors=0
```

### 6.4 Selective re-embed after corpus refresh (one article changed)

Operator runs `make ingest --force-fetch` (after EUR-Lex publishes a corrigendum) and one article's hash changes:

```
$ make rag-build
[build] processing ai_act/es: 112 unchanged, 1 hash differs (article 6)
  [chunk] article 6 → 1 chunk
  [embed] 1 chunk → 1 vector
  [store] delete_by_article(ai_act.6, es) + upsert
[build] summary: chunks_added=0, chunks_recomputed=1, chunks_unchanged=426, errors=0
```

---

## 7. Error handling

| Failure mode | Detection | Action |
|---|---|---|
| HF Hub unreachable on first model load | `OSError` from `FlagEmbedding` constructor | Exit 1 with message "HF Hub unreachable; check network or pre-download model with `huggingface-cli download BAAI/bge-m3`" |
| Manifest missing for a corpus | `manifest.load() → None` | Log error, append to `skipped_corpora`, continue with other corpora; exit 1 if any skipped |
| `processed/{corpus}_{lang}.json` missing | `FileNotFoundError` | Exit 1 with path; suggest re-running `make ingest` |
| Article in manifest but not in processed file | `_reload_one` returns None | Log error with `(corpus, lang, articulo)`, increment `summary.errors`, continue with other articles |
| LanceDB write fails (lock, disk full) | `lancedb` raises | Exit 1, do NOT call `manifest.save_atomic`; manifest remains pre-build state |
| Embedder returns wrong dimension | length check after `embed()` | Exit 1 with diagnostic; this catches misconfigured models early |

**Atomicity:**
- LanceDB `delete_by_article` + `upsert` per article is two operations. If `upsert` fails after `delete`, that article's chunks are temporarily missing from LanceDB. Mitigation: catch exceptions per article, log, continue. The orphan delete-without-upsert is recoverable by `--force-rebuild` next run.
- Manifest is written atomically via `save_atomic` after the entire corpora loop. If the loop aborts mid-corpus, the manifest is untouched.

---

## 8. Testing strategy

### 8.1 Test pyramid

| Level | What | Location | CI? |
|---|---|---|---|
| Unit | `chunking._normalize` (lowercase, accent strip, ws collapse) | `tests/unit/rag/test_chunking.py` | yes |
| Unit | `chunking.chunk_article`: ≤ threshold, > threshold, no paragraphs, single para > threshold | same | yes |
| Unit | `embeddings.token_count` returns positive ints (with mocked tokenizer) | `tests/unit/rag/test_embeddings.py` | yes |
| Unit | `embeddings.embed`: shape (N, 1024), batch logic (with mocked model) | same | yes |
| Unit | `reranker.rerank`: empty input, top_n truncation, score sort (with mocked model) | `tests/unit/rag/test_reranker.py` | yes |
| Unit | `store.connect` creates table with correct schema | `tests/unit/rag/test_store.py` | yes |
| Unit | `store.upsert` inserts new + replaces by chunk_id | same | yes |
| Unit | `store.delete_by_article` removes only chunks of that article+lang | same | yes |
| Unit | `corpus/_targets.expand_targets` (post-promotion) | `tests/unit/corpus/test_targets.py` | yes |
| Unit | `build.run`: skip path when hash + model match | `tests/unit/rag/test_build.py` (with stub embedder/reranker) | yes |
| Unit | `build.run`: re-embed when model differs | same | yes |
| Unit | `build.run`: re-embed when hash differs (simulate via altered processed file) | same | yes |
| Contract | `Chunk` and `ChunkRecord` Pydantic round-trip via hypothesis | `tests/contract/test_rag_schemas.py` | yes |
| Integration | `build.run` end-to-end with real BGE-M3 (mini fixture: 5 articles) — verify chunks created, manifest extended, LanceDB has records, re-run idempotent | `tests/integration/test_rag_build_flow.py` | yes (slow, ~30s with cached model) |
| Smoke (manual) | Full corpus build (424 entries) with timing | `scripts/smoke_rag_build.py` | no |

### 8.2 Mocking strategy

- Unit tests of `build.py` and `chunking.py` do **not** load BGE-M3. Two helpers:
  - `tests/conftest.py` exposes a `stub_embedder` fixture that replaces `embeddings.embed` and `embeddings.token_count` with deterministic stubs (e.g., `embed(["foo"]) → [[0.1]*1024]`, `token_count("foo") → 3`).
  - Same for reranker.
- The integration test does NOT mock — it uses real models. Marked with `@pytest.mark.slow`. CI runs it in the `test` job after the cache hit; if cache miss, it downloads the model once (~5 min on first run).

### 8.3 Coverage

- Target: ≥ 90% line coverage across `src/regulaitor/rag/` (matches the H1 gate).
- The 90% gate in `pyproject.toml` covers `src/regulaitor/corpus/` only (configured in H1). H2 extends the gate to also cover `src/regulaitor/rag/`. Practically: `--cov=src/regulaitor/rag --cov=src/regulaitor/corpus` in `addopts`, both with `--cov-fail-under=90`.

### 8.4 Fixtures

```
tests/fixtures/
├── formex/                   (existing from H1)
├── html/                     (existing from H1)
└── rag/                      (new)
    ├── mini_manifest.json    (synthetic manifest with 5 articles per corpus)
    └── mini_processed_es.json
    └── mini_processed_en.json
```

The synthetic manifest is hand-crafted, much smaller than the real ones (5 articles vs 113), and lets the integration test run in ~30s with a cached model.

---

## 9. Repository layout impact

```
src/regulaitor/
├── corpus/
│   ├── ingest.py             (modified: import token_count from rag/embeddings; remove _expand_targets, import from _targets)
│   ├── _targets.py           (NEW: shared expand_targets)
│   ├── schemas.py            (modified: LanguageEntry adds embedding_model: str | None)
│   └── ... (other corpus modules unchanged)
└── rag/                      (NEW package)
    ├── __init__.py
    ├── schemas.py            (Chunk, ChunkRecord, RagBuildSummary)
    ├── embeddings.py         (load BGE-M3, embed, token_count, model_identifier)
    ├── reranker.py           (load bge-reranker-v2-m3, rerank, warmup)
    ├── chunking.py           (_normalize, chunk_article)
    ├── store.py              (LanceDB schema, connect, upsert, delete_by_article)
    └── build.py              (orchestrator: run, _reload_one)

scripts/
└── rag_build.py              (NEW CLI)

tests/
├── unit/
│   ├── corpus/test_targets.py    (NEW)
│   └── rag/                      (NEW)
│       ├── test_chunking.py
│       ├── test_embeddings.py
│       ├── test_reranker.py
│       ├── test_store.py
│       └── test_build.py
├── contract/test_rag_schemas.py  (NEW)
├── integration/
│   └── test_rag_build_flow.py    (NEW)
└── fixtures/rag/                 (NEW)
```

`.gitignore` adjustments: `corpus/indexes/` is already gitignored from H1; the LanceDB store goes there.

`Makefile` additions:

```makefile
rag-build: ## chunk + embed + rerank-warmup + upsert LanceDB + extend manifest
	$(UV) run python -m scripts.rag_build --corpus all --lang all
```

---

## 10. New dependencies

| Package | Purpose | Pin |
|---|---|---|
| `FlagEmbedding` | embedder + reranker BGE-M3 | `>=1.3,<2.0` |
| `lancedb` | vector store | `>=0.16,<1.0` |
| `pyarrow` | LanceDB schema (transitive but pinned for reproducibility) | `>=18.0,<22.0` |
| `transformers` | XLM-RoBERTa tokenizer (transitive of FlagEmbedding) | unpinned (let FlagEmbedding decide) |
| `torch` | BGE-M3 backend (transitive) | unpinned (CPU build by default) |

**To remove:** `tiktoken` (no consumers after the swap).

CI `.github/workflows/ci.yml` adds `actions/cache@v4` over `~/.cache/huggingface` keyed by `${{ runner.os }}-hf-${{ hashFiles('uv.lock') }}-bgem3`. First CI run downloads the models (~3 GB) and warms cache; subsequent runs are cache hit.

---

## 11. New skills and MCPs (per ADR 0002)

H2 introduces **zero new skills, zero new MCPs**.

- `prompt-versioning` skill (originally scheduled H2-H3 in ADR 0002) is **deferred to H4** because no system prompts exist yet — H2 has no LLM calls, it only embeds and re-ranks.
- `fetch` MCP remains deferred to H3 (still not needed; `rag/` reads local files only).
- `mcp-server-time` not introduced (Python `datetime` covers `embedded_at` timestamps).

This zero-introduction is recorded in the H2 closure entry of the decisions log when H2 closes.

---

## 12. Open questions (settle during implementation)

1. **Exact format of `embedding_model` value.** The schema allows any string. The recommendation is `"BAAI/bge-m3@<sha256>"` where the hash is the snapshot hash from HF Hub cache. Implementation will probe `_MODEL.model.config._commit_hash` (private API of transformers) and fall back to the model name + version if the hash is unavailable. Document the fallback in code comments.
2. **`text_normalized` precise rules.** The spec says "lowercased, accents stripped, whitespace collapsed". Edge cases not specified: punctuation handling (kept? stripped?), digit normalization (kept), Unicode dashes vs hyphens. Implementation defaults: keep punctuation, keep digits as-is, collapse all dashes to ASCII `-`. The H3 citation_validator may refine this; for H2 the field is informational.
3. **LanceDB version compatibility.** lancedb 0.16+ may evolve schema serialization. Implementation will pin a specific minor (e.g., `0.16.x`) to ensure tests in CI match local. Bump minor explicitly when needed.
4. **Reranker batch size.** `compute_score` accepts batches. The default is 256 in FlagReranker. For H3 queries with 20-50 candidates this is fine; for H8 evaluation with potentially hundreds of candidates the default may need lowering for memory. Defer to H8 calibration.

---

## 13. Acceptance criteria for H2

H2 is "Done" when ALL of the following hold:

1. `uv run python -m scripts.rag_build --corpus all --lang all` against the H1-produced manifests + processed/ completes with exit 0.
2. The `chunks` table in LanceDB contains exactly N records, where N equals the sum of `len(chunks)` across all `LanguageEntry` of all 4 manifests. The expected lower bound is 424 (one chunk per `LanguageEntry` if no article exceeded threshold) and upper bound depends on how many articles split. The actual N is recorded verbatim in the H2 closure log entry.
3. Re-running the same command immediately produces `chunks_added=0, chunks_recomputed=0, chunks_unchanged=N` (idempotency proof).
4. All `LanguageEntry` in the 4 manifests have non-empty `chunks`, non-null `embedded_at`, and `embedding_model = "BAAI/bge-m3@<hash>"`.
5. The smoke retrieval query (the one in spec §6.1) returns 3 plausible AI Act articles with reranker scores > 0.5 for top results.
6. Unit + contract + integration tests pass with ≥ 90% coverage on `src/regulaitor/rag/` AND ≥ 90% on `src/regulaitor/corpus/` (existing).
7. CI lint + test + security jobs are green on the merge commit.
8. `pyproject.toml` no longer lists `tiktoken`; `corpus/ingest.py` imports `token_count` from `rag.embeddings`.
9. `corpus/_targets.py` exists and `_expand_targets` has been removed from `corpus/ingest.py`.
10. Smoke output and stats committed as a new H2 closure entry in `docs/technical_decisions_log.md`.
11. ADR 0004 (RAG architecture) drafted and merged.

---

## 14. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| HF Hub rate limits or downtime block model download | Low | First failure produces clear error; operator can pre-download via `huggingface-cli`. CI cache eliminates this for subsequent CI runs. |
| BGE-M3 OOM on CI runner (typical GitHub runner has 7 GB RAM) | Medium | Use `use_fp16=False` only locally; in CI try `use_fp16=True` if memory tight (model halves to ~1.5 GB). Add `--low-memory-mode` flag to CLI as escape hatch. |
| LanceDB schema serialization changes between versions | Low | Pin exact minor (`>=0.16,<0.17`); bump explicitly with CI verification. |
| Tokenizer divergence between cl100k (H1) and BGE-M3 (H2) breaks the chunker threshold logic | Very low | The 1000-token threshold has 8x slack vs BGE-M3's 8192 max context. Even with 30% divergence, no article in the current corpus exceeds threshold under BGE-M3 tokenizer (verified during decision §3 of the log). |
| `text_normalized` definition diverges between H2 chunker and H3 citation_validator | Medium | Spec §12 question 2 leaves room; H2 implements a minimal sane default and H3 refines if needed. The field is regenerated at H3 update via `--force-rebuild` if rules change. |
| First `make rag-build` takes too long on a clean clone (>10 min download) | High first time, low after | Document expected time in README. CI cache eliminates after first build. |
| Embedder produces NaN or zero vectors for some inputs | Very low (BGE-M3 is robust) | Add a sanity check after `embed()`: if any vector has L2 norm < 0.01 or contains NaN, raise. |

---

## 15. Implementation order (input to writing-plans skill)

Suggested sequence (refines in writing-plans):

1. Branch `feat/h2-rag-base` off main.
2. Add deps to `pyproject.toml`, remove `tiktoken`, `uv sync`. Update CI workflow with HF cache.
3. Promote `_expand_targets` → `corpus/_targets.expand_targets`. Update `corpus/ingest.py` to import. Tests follow.
4. Extend `LanguageEntry` schema with `embedding_model: str | None`. Existing tests still pass (default None compatible).
5. Implement `rag/schemas.py` (`Chunk`, `ChunkRecord`, `RagBuildSummary`).
6. Implement `rag/embeddings.py` (load model, `embed`, `token_count`, `model_identifier`). Unit tests with mocked model.
7. Implement `rag/reranker.py` (load model, `rerank`, `warmup`). Unit tests with mocked model.
8. Implement `rag/chunking.py` (`_normalize`, `chunk_article`). Unit tests with stub `token_count`.
9. Implement `rag/store.py` (LanceDB schema, `connect`, `upsert`, `delete_by_article`). Unit tests with tmp_path.
10. Implement `rag/build.py` (`run`, `_reload_one`). Unit tests with stubs.
11. Implement `scripts/rag_build.py` CLI. Unit tests for arg parsing.
12. Update `corpus/ingest.py` `_token_count` to call `rag.embeddings.token_count`. Verify cycle-free.
13. One-time `make ingest --force-reprocess --use-local-only` to refresh `tokens` in manifests (commit the diff).
14. Add contract tests (`tests/contract/test_rag_schemas.py`).
15. Add integration test (`tests/integration/test_rag_build_flow.py`).
16. Run smoke build against full corpus locally; capture timing and chunk count.
17. Commit smoke artefacts: updated 4 manifests with `chunks`/`embedded_at`/`embedding_model` populated. LanceDB store goes to `corpus/indexes/` (gitignored).
18. Draft ADR 0004 (RAG architecture).
19. Update `docs/technical_decisions_log.md` with H2 closure entry (real stats from smoke).
20. PR review, CI green, merge, tag `v0.0.3-h2`.

---

## 16. References

- `CLAUDE.md` §10.3 (RAG stack), §22 (operating rules).
- `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` — predecessor spec.
- `docs/superpowers/plans/2026-04-30-h1-corpus-ingest.md` — H1 implementation plan (references for patterns).
- `docs/technical_decisions_log.md` H2 section — 6 brainstorming decisions.
- `docs/adr/0001-project-scope.md`, `0002-skills-mcps-roadmap.md`, `0003-corpus-pipeline.md`.
- BGE-M3 paper: <https://arxiv.org/abs/2402.03216>.
- bge-reranker-v2-m3 model card: <https://huggingface.co/BAAI/bge-reranker-v2-m3>.
- LanceDB Python docs: <https://lancedb.github.io/lancedb/>.
