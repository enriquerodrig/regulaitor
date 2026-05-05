# ADR 0004 — RAG base architecture

- **Status:** Accepted
- **Date:** 2026-05-04 (H2 closure)
- **Deciders:** Project owner.
- **Supersedes:** none. **Refines:** open questions §12 of the H2 spec (`docs/superpowers/specs/2026-05-04-h2-rag-base-design.md`).
- **Companion ADRs:** 0003 (corpus pipeline), 0002 (skills/MCPs roadmap).

## Context

H2 needs to turn the H1 corpus (4 manifests + parsed articles in two languages, 424 `LanguageEntry` slots) into a queryable vector index that downstream components can consume — the Retriever-Agent in H3, the citation validator, and the evaluation harness in H8. Without this layer, every later "no citation, no answer" claim collapses, because the Auditor has nothing to validate against.

The H2 design spec deliberately deferred several questions to brainstorming: local vs. API embeddings, single vs. per-corpus LanceDB tables, when to swap the H1 `tiktoken` proxy for the BGE-M3 native tokenizer, where the reranker lives (H2 or H3), how the orchestrator relates to `corpus/ingest`, and how to detect embedding-model upgrades. This ADR records the architecture that emerged from brainstorming + the H2 implementation, validated by a real smoke run against the AI Act + GDPR corpora.

## Decision

### Module layout

Six modules under `src/regulaitor/rag/`, each with one clear responsibility:

| Module | Responsibility | Public surface |
|---|---|---|
| `schemas.py` | Pydantic v2 contracts for chunks. | `Chunk`, `ChunkRecord`, `RagBuildSummary` |
| `embeddings.py` | BGE-M3 lazy singleton; dense embedding + token count. | `embed`, `token_count`, `model_identifier`, `warmup` |
| `reranker.py` | bge-reranker-v2-m3 lazy singleton. | `rerank(query, passages, top_n)`, `warmup` |
| `chunking.py` | Hybrid splitter by 1000 BGE-M3 tokens, fall back to `apartado`. | `chunk_article`, `THRESHOLD_TOKENS` |
| `store.py` | LanceDB single global table `chunks`, filtered by metadata. | `connect`, `upsert`, `delete_by_article`, `INDEX_PATH`, `SCHEMA` |
| `build.py` | Orchestrator: read manifest → chunk → embed → upsert → extend manifest. | `run`, `RagBuildSummary` |

The CLI entry point is `python -m scripts.rag_build`, separate from `python -m scripts.ingest`. The two pipelines are wired in series via `make rag-build` (extending `make ingest`).

### Local BGE-M3, single global table, native tokenizer

Three foundational choices, each with its own decisions-log entry:

- **Local BGE-M3 (FlagEmbedding) instead of an API:** reproducibility bit-for-bit, zero per-embedding cost, no secrets in CI. Disk cost ~3.3 GB on `~/.cache/huggingface/`, mitigated by `actions/cache` keyed on `uv.lock` hash.
- **Single LanceDB table `chunks` partitioned by metadata:** `chunk_id` is globally unique by design (`{article_id}[.{apartado}].{lang}`), and LanceDB metadata filters scale fine for our size (~1k–10k chunks). Cross-corpus queries become trivial; per-corpus tables would require a query-time fan-out we don't need.
- **BGE-M3 native tokenizer (XLM-RoBERTa) replaces the H1 `tiktoken` proxy:** `corpus/ingest._token_count` now delegates to `rag.embeddings.token_count`, ensuring the chunking threshold check and the embedder use the same units. `tiktoken` is removed from runtime dependencies.

### Reranker lives in H2, not H3

The cross-encoder `bge-reranker-v2-m3` (~600 MB) is loaded as a lazy singleton in `rag/reranker.py` and is warmed up at the end of `rag/build.run`. H3's Retriever-Agent calls `rerank(...)` directly without paying a cold-start cost on first query.

This deviates from the original spec, which scoped the reranker to H3. Bringing it forward avoids inflating H3 (already dense with Retriever-Agent + MCP server + schemas + citation validator) and makes H2's smoke test academically stronger by demonstrating end-to-end ranking quality.

### Orchestrator separated from `corpus/ingest`

`rag/build.py` is a separate orchestrator from `corpus/ingest.py` (which produced the H1 artefacts). Both read and write the same manifest files via `corpus/manifest.save_atomic`, but neither imports the other. The two CLIs are stitched together by `make rag-build` (which depends on `make ingest`).

This keeps the corpus layer decoupled from LanceDB and BGE-M3. If we ever swap LanceDB for another vector store (e.g. Qdrant), only `rag/store.py` and `rag/build.py` change; the corpus pipeline is untouched.

### Embedding model versioning per `LanguageEntry`

`LanguageEntry` gains a new field `embedding_model: str | None`. `rag/build.run` writes the current `embeddings.model_identifier()` into this field after embedding succeeds. The skip-condition for re-embedding is:

```
not force_rebuild AND entry.chunks AND entry.embedding_model == current_model
```

When the project bumps BGE-M3 (or swaps to a finetune), the next `make rag-build` automatically re-embeds every entry whose stored model identifier doesn't match — no manual intervention. Per-entry granularity (rather than a global `embedding_model_version` field) supports mixed scenarios: e.g. EN re-embedded with v2 while ES still on v1 during a staged rollout.

### Idempotency

Three layers, composable:

1. **HTTP layer** (inherited from H1): unchanged. `make ingest` re-runs are short-circuited by `If-Modified-Since` / `If-None-Match`.
2. **Article layer** (inherited from H1): SHA256 hash per `(article, language)`. When the hash matches, the previous `LanguageEntry` is preserved verbatim — including `chunks`, `embedded_at`, `embedding_model`.
3. **Embedding layer** (new in H2): `(hash, embedding_model)` joint check. A model swap with unchanged hashes still triggers re-embedding; an unchanged model on changed text re-embeds only the changed articles.

Verified empirically by Task 13 smoke run: second invocation of `rag_build` reports `chunks_added=0, chunks_recomputed=0, chunks_unchanged=1011`.

### Atomicity

All disk writes go through `corpus/manifest.save_atomic` (`<path>.tmp` + `os.replace`). LanceDB `upsert` is implemented as DELETE-then-ADD inside a single `with table:` block; failures leave the previous state intact.

### Schema (`Chunk`, `ChunkRecord`, LanceDB)

`Chunk` (Pydantic) carries the structural metadata (norma, language, article_id, apartado, chunk_id, text, hash, tokens). `ChunkRecord(Chunk)` extends it with `embedding: list[float]` and `embedding_model: str` for LanceDB persistence. The PyArrow schema in `store.SCHEMA` has 16 fields including `embedding: list_(float32, 1024)`.

`fecha_ingesta` per chunk (mentioned in CLAUDE.md §7) is satisfied transitively: `chunk.article_id → manifest.LanguageEntry.fetched_at / embedded_at`. Duplicating the timestamp on every chunk would be DRY-violating and complicate idempotency. The Auditor (H4) reads timestamps via the manifest, not via LanceDB.

## Alternatives considered

- **API-based embeddings (Voyage / Cohere / Together):** rejected for reproducibility (vendor can change model silently) and CI secrets management.
- **Per-corpus LanceDB tables:** rejected; `chunk_id` already encodes corpus, metadata filters scale fine for our size, and cross-corpus queries become a query-time fan-out we don't need.
- **Reranker deferred to H3:** rejected to avoid inflating H3 (already dense) and to make H2's smoke stronger.
- **Single orchestrator extending `corpus/ingest`:** rejected; would couple the ingestion layer to LanceDB and BGE-M3.
- **Global `embedding_model_version` field at manifest top-level:** rejected; cannot represent mixed states (e.g. partial re-embed during a model swap).
- **Duplicating `fetched_at` / `embedded_at` per chunk:** rejected; not DRY, breaks idempotency clarity, conceptual noise.
- **`tiktoken` proxy retained for H2:** rejected; the chunking threshold and the embedder must agree on token counts. A proxy that's "close enough" is technical debt that surfaces as off-by-one chunk splits at the boundary.

## Smoke validation (Task 13, 2026-05-04)

- 4 manifests extended (`ai_act_{es,en}`, `gdpr_{es,en}`).
- LanceDB table `chunks` with **1011 rows**: `ai_act` 687 (es 361, en 326), `gdpr` 324 (es 172, en 152). Counts match the manifests row-for-row.
- **Chunking observation:** the spec estimated "~424–440 chunks" assuming most articles fit in one chunk. The real number is 2.4× higher: 52 `LanguageEntry` slots (32 in AI Act, 20 in GDPR) split into multiple `apartado`-level chunks, with an average of ~3 chunks per `LanguageEntry` overall. This is correct behaviour per spec §6 — the 1000-token threshold is more selective than the original estimate predicted, especially in AI Act articles with multiple apartados of regulatory detail. **Implication for retrieval (H3):** finer chunks improve retrieval precision (each chunk corresponds to a single citable apartado in long articles), so this is a feature, not a regression.
- **Idempotency confirmed:** re-running `rag_build` immediately reports `chunks_added=0, chunks_recomputed=0, chunks_unchanged=1011`.
- **Disk:** 32 MB for `corpus/indexes/regulaitor.lance/` (gitignored).

## Consequences

### Positive

- Each module is independently testable; H2 closes at **92.55% global coverage**, with `chunking.py`, `embeddings.py`, `reranker.py`, `schemas.py`, `store.py` all at 100% per-file coverage and `build.py` at 91%.
- Re-runs are cheap: skip-condition on `(hash, embedding_model)` short-circuits unchanged entries; second invocation completes in ~3 s wall-clock.
- `make ingest && make rag-build` is the visible reproducible pipeline a TFM reviewer can run end-to-end.
- Adding NIS2 / DORA in H14 means updating constants (`CELEX`, `VERSION`, `EXPECTED_ARTICLE_COUNTS`) and dropping their PDFs in `corpus/raw/`; no `rag/` change is needed.
- Model upgrades are automatic: bump `FlagEmbedding` or swap to a finetune in `pyproject.toml`, run `make rag-build`, and the orchestrator detects the model identifier mismatch and re-embeds without manual intervention.

### Negative

- HF Hub model downloads (~3 GB total) on first build / first CI run. Mitigated by `actions/cache` keyed on `uv.lock` hash; planned in H2's CI workflow extension.
- Reranker adds ~600 MB to disk and ~50–150 ms latency per ranked query in CPU. Acceptable within the latency p95 ≤ 12 s target (CLAUDE.md §17), and warmup is amortised at build time.
- `transformers` is pinned `<5.0` because `FlagEmbedding 1.4.0` calls `tokenizer.prepare_for_model`, which was removed in `transformers 5.x`. When upstream `FlagEmbedding` releases a fix, lift the pin.
- The `--corpus all` flag in `rag_build` reports `errors=2` for missing `nis2` / `dora` manifests (out of scope until H14). Cosmetic; will resolve when those manifests exist.
- The H2 chunk count (1011) significantly exceeds the spec's estimate (~424–440). Documentation and downstream design intuitions calibrated on the old number need updating; H3's retriever should plan for top-k against ~1k–1.2k chunks per build, not ~400.

## References

- `docs/superpowers/specs/2026-05-04-h2-rag-base-design.md` — H2 design spec.
- `docs/superpowers/plans/2026-05-04-h2-rag-base.md` — H2 implementation plan.
- `docs/technical_decisions_log.md` H2 section, in particular the closure entry "H2 cerrado" and the six decisions that led to this architecture.
- `docs/adr/0003-corpus-pipeline.md` — predecessor; H1 boundary contract.
- `docs/adr/0002-skills-mcps-roadmap.md` — companion; reranker introduction lifted from H3 to H2.
- `corpus/manifests/ai_act.json`, `corpus/manifests/gdpr.json` — boundary contract to H3, populated by Task 13.
- `src/regulaitor/rag/` — module implementations.
- `corpus/indexes/regulaitor.lance/` — concrete LanceDB output (gitignored, build artefact).
