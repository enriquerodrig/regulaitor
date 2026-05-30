# 06. Pipeline RAG

El pipeline RAG (Retrieval-Augmented Generation) de RegulAItor convierte el corpus normativo descrito en la sección anterior en un índice vectorial consultable que sostiene el invariante §6 "no citation, no answer". Esta sección documenta las cinco capas que lo componen — chunking estructural, embeddings BGE-M3, reranker cross-encoder, persistencia LanceDB y orquestación de recuperación — más las dos iteraciones de optimización (v0.1.6-h15.1 cross-corpus auto-path y la pareja v0.1.10/v0.1.11 de deduplicación) que llevaron la capacidad de recuperación de single-corpus a multi-corpus controlado. Cerramos con dos hallazgos honestos: el éxito asimétrico del title-prepend (query-side ayuda; corpus-side perjudica) y el coste de latencia del reranker en CPU.

## 6.1 Decisión arquitectónica de base (H2, ADR-0004)

H2 cerró el 2026-05-04 con la decisión de seis módulos en `src/regulaitor/rag/`, cada uno con una responsabilidad única (ADR-0004 §Decision / §Module layout):

- `schemas.py` — contratos Pydantic v2 (`Chunk`, `ChunkRecord`, `RagBuildSummary`).
- `embeddings.py` — singleton perezoso BGE-M3 + tokenizador nativo.
- `reranker.py` — singleton perezoso del cross-encoder bge-reranker-v2-m3.
- `chunking.py` — splitter híbrido a 1000 tokens BGE-M3, con fallback a `apartado`.
- `store.py` — tabla LanceDB global `chunks`, filtrada por metadatos.
- `build.py` — orquestador end-to-end: leer manifest → chunkear → embebir → upsert.

Tres elecciones de diseño foundationales (ADR-0004 §Local BGE-M3, single global table, native tokenizer):

1. **BGE-M3 local en lugar de API**: reproducibilidad bit-a-bit, coste por embedding cero, sin secretos en CI. Coste en disco ~3.3 GB en `~/.cache/huggingface/`, mitigado por `actions/cache` con clave en el hash de `uv.lock`.
2. **Tabla LanceDB única particionada por metadatos**: `chunk_id` es globalmente único por construcción (`{article_id}[.{apartado}].{lang}`); los filtros de metadata escalan bien al tamaño del proyecto (1569 filas tras H14, ADR-0015).
3. **Tokenizador nativo BGE-M3 reemplaza el proxy `tiktoken` de H1**: tanto `corpus/ingest._token_count` como `chunking.chunk_article` consultan los mismos tokens (`src/regulaitor/rag/embeddings.py:49-57`).

El reranker se trajo desde H3 a H2 para descargar H3 (que ya cargaba Retriever-Agent + MCP server + citation_validator) y porque el smoke test final de H2 gana fuerza académica al demostrar ranking end-to-end (ADR-0004 §Reranker lives in H2, not H3).

## 6.2 Chunking estructural por artículo

`src/regulaitor/rag/chunking.py:37` implementa una estrategia híbrida con un umbral duro de 1000 tokens BGE-M3 (`THRESHOLD_TOKENS`, línea 20):

- Si `token_count(article.text) <= 1000` o el artículo no tiene `paragraphs`, se emite un único chunk a nivel de artículo (`chunk_article` líneas 58-89).
- Si lo supera, se emite un chunk por `apartado`, cada uno con su propio `articulo`, `apartado`, `text`, `text_normalized`, `token_count` y metadatos de manifest (`celex`, `version`, `source_format`, `source_url`, `hash`) — líneas 91-112.

La regla CLAUDE.md §10.3 "no mezclar artículos distintos en el mismo chunk" se cumple por construcción: el bucle externo de `build.py:89` itera artículo por artículo, y `chunk_article` nunca cruza el límite del `ParsedArticle` recibido. La consecuencia empírica fue inesperada (ADR-0004 §Smoke validation): la spec de H2 estimó "~424-440 chunks" asumiendo que la mayoría de artículos cabrían en uno solo; la realidad fueron 1011 chunks (52 `LanguageEntry` se partieron en múltiples apartados; media ~3 chunks por entry). H14 (ADR-0015) llevó el total a 1569 chunks al añadir NIS2 y DORA. Esta granularidad fina mejora la precisión de la citación porque cada chunk se mapea a un `apartado` citable concreto — la base sobre la que se construyó el validator de §6.

`Chunk.text_normalized` (chunking.py:31-34) baja a minúsculas, elimina diacríticos (NFD + filtro `Mn`), unifica guiones tipográficos (U+2013 en-dash, U+2014 em-dash, U+2212 minus, U+2015 horizontal bar) a guión ASCII y colapsa espacios. Lo consume el validator de citas en su ruta exact-match (sección 07).

## 6.3 Embeddings BGE-M3

El modelo `BAAI/bge-m3` produce vectores densos de 1024 dimensiones, multilingües (cubre las dos lenguas oficiales del corpus, ES y EN, sin necesidad de modelos separados). Se carga como singleton perezoso (`embeddings.py:22-32`): la primera llamada paga el coste de cargar pesos desde `~/.cache/huggingface/`; las siguientes son O(1).

`embed(texts, batch_size=16)` (línea 35) devuelve `list[list[float]]` en el mismo orden que la entrada; lista vacía no carga modelo. `model_identifier()` (línea 60) construye el identificador canónico `BAAI/bge-m3@<sha256_short>` cuando el commit hash HF Hub está disponible, con fallback a `BAAI/bge-m3@v1.0`. Este identificador se persiste por `LanguageEntry` y dispara re-embedding automático cuando el modelo cambia (skip-condition en `build.run`: `not force_rebuild AND entry.chunks AND entry.embedding_model == current_model`, build.py:98).

**Coste medido de un rebuild completo**: ~1.5 horas de CPU sobre los 1569 chunks del corpus actual (medido en sesión 2026-05-28 durante la construcción del índice v0.1.30 antes del REVERT). Es coste $0 (BGE-M3 local) pero coste real en wall-clock, lo que motivó la disciplina de snapshot atómico antes de cualquier re-embed especulativo.

## 6.4 Reranker bge-reranker-v2-m3

El cross-encoder `BAAI/bge-reranker-v2-m3` re-puntúa pares `(query, passage)` después de la recuperación densa, produciendo un top-N más preciso (`reranker.py:27`). Misma estrategia de singleton perezoso que embeddings. La función `warmup()` (línea 45) se llama al final de `build.run()` (`build.py:180`) para que la primera query real en H3 no pague el cold-start.

**Coste real medido en CPU local** (memoria `feedback_local_cpu_rerank_cost.md` — disciplina dura registrada tras subestimaciones consecutivas en v0.1.9/v0.1.10/v0.1.12): cada llamada `rerank()` cuesta **15-30 segundos sostenidos** sobre 50 pasajes, no los 5-10 segundos que la spec inicial estimó. Para un diagnóstico de N llamadas, el presupuesto realista es `N × 30s + 60s warmup + margen ×1.5`; cualquier estimación >5 minutos exige rediseñar el experimento con 1-2 configuraciones críticas en lugar de barrido factorial. Esta regla evitó que v0.1.12 (top_k_auto) cayera en una medición empírica fallida y se aplicó como criterio de aceptación para v0.1.13+.

`rerank(query, passages, top_n=None)` devuelve `list[tuple[int, float]]` ordenado por score descendente; el índice referencia la posición original en `passages`, lo que permite recuperar metadatos del candidato denso correspondiente sin pasos adicionales.

## 6.5 LanceDB store

`src/regulaitor/rag/store.py` define el contrato de persistencia. La constante `DEFAULT_PATH` (líneas 18-24) tiene orden de resolución explícito desde v0.1.26 (deploy-prep H16):

1. Variable de entorno `LANCEDB_PATH` (absoluta — usada en HF Spaces, Render, Fly.io para apuntar a volúmenes persistentes).
2. Fallback a `<cwd>/corpus/indexes/regulaitor.lance` (dev y CI).

El schema PyArrow (`SCHEMA`, líneas 32-51) declara 16 campos incluyendo `embedding: list_(float32, 1024)` y `embedding_model: string`. Todos los campos estructurales del `Chunk` se persisten + el vector denso + el identificador del modelo que lo produjo, lo que permite la skip-condition de re-embedding documentada en §6.3.

`upsert(records, table)` (línea 67) implementa upsert por `chunk_id`: DELETE en batch (`chunk_id IN (...)`) seguido de ADD. `delete_by_article(article_id, language, table)` (línea 83) borra todos los chunks de un artículo en una lengua usando `LIKE` parametrizado; valida `article_id` y `language` contra `_SAFE_ID_PATTERN = re.compile(r"^[a-z0-9_.-]+$")` (línea 30) para prevenir inyección en el filtro LanceDB. La validación es defensiva — los callers actuales pasan tipos `Norma` y `Language` (Literals cerrados), pero protege contra futuras rutas MCP o HTTP que pudieran forwardar input de usuario.

## 6.6 RetrievalConfig y la evolución de los tuning levers

`src/regulaitor/rag/retrieval.py:28-68` define `RetrievalConfig`, dataclass `frozen=True` con seis palancas. Cada campo tiene una procedencia histórica trazable a un hito decimal:

```python
@dataclass(frozen=True)
class RetrievalConfig:
    pre_rerank: int = 50               # H15.1 ADR-0017
    top_k: int = 5                     # H15.1 ADR-0017
    purity_threshold: float = 0.6      # H15.1 ADR-0017
    query_normalize: bool = False      # H15.1 ADR-0017
    max_chunks_per_article: int | None = None  # v0.1.10
    max_chunks_per_norma: int | None = 2       # v0.1.11 (default activado en v0.1.21.2)
    top_k_auto: int | None = 12                # v0.1.12 (default activado en v0.1.21.2)
```

El validador `__post_init__` (líneas 70-120) refuerza tipos e invariantes (`top_k >= 1`, los caps opcionales >= 1 cuando no son None). El override por entorno está en `_config_from_env()` (línea 126): lee `REGULAITOR_RETRIEVAL_CONFIG` como JSON, registra warning + devuelve defaults ante cualquier error (JSON inválido, no-objeto, campo desconocido, tipo incorrecto, violación de constraint). El módulo carga `DEFAULT_CONFIG` una vez al import (línea 186) — el seam evaluation-only que cierra el §22.22 design-defect de H15.1 (ADR-0018, sección 06.8).

## 6.7 Pipeline de recuperación: `run()` y `run_auto()`

Existen dos puntos de entrada:

**`run(query, corpus, language, top_k=None, pre_rerank=None)`** (`retrieval.py:293`) — ruta explícita de un solo corpus. La `where_clause` interpola directamente `norma = '{corpus}'` y `language = '{language}'`; ambos son `Literal` cerrados (`Norma`, `Language`) tipados en el boundary de la función, por lo que no hay vector de inyección SQL. La construcción es **byte-identical** a `v0.1.6-h15.1` por construcción y verificada por el test de regresión `tests/unit/test_explicit_path_unchanged.py` (ADR-0017 §D3, ADR-0018). La resolución `top_k=None → DEFAULT_CONFIG.top_k` se hace **at call time** (no at function-definition-time): esto permite que la harness rebinde `DEFAULT_CONFIG` vía env al inicio del proceso y la ruta explícita consuma el override — exactamente lo que H15.1 no podía medir, motivando el fix quirúrgico de v0.1.7-h15.2 (ADR-0018).

**`run_auto(query, language, cfg)`** (`retrieval.py:344`) — ruta multi-corpus opt-in, gateada por `corpus="auto"` desde el grafo de orquestación:

1. Embebe la query (1 vector).
2. Recupera `cfg.pre_rerank` candidatos LanceDB filtrados solo por lengua (sin `norma`).
3. Llama al reranker sobre los `pre_rerank` pasajes.
4. Aplica opcionalmente `_apply_per_article_dedup` (cap por `(norma, articulo)`) — v0.1.10.
5. Aplica opcionalmente `_apply_per_norma_dedup` (cap por `norma`) — v0.1.11.
6. Si `cfg.top_k_auto` está fijado, construye `gate_cfg = replace(cfg, top_k=cfg.top_k_auto)` para que el purity gate y el output usen el override sin tocar `cfg.top_k` ni la ruta explícita — v0.1.12.
7. Aplica `_apply_purity_gate` (líneas 243-264).
8. Enriquece con metadatos de manifest por chunk (cada `RetrievedChunk` lleva su propia `version` y `source_url` resueltos por su propia `norma`).

El purity gate (`_apply_purity_gate`, línea 243) es el corazón del control no-leakage en la ruta auto. Lee la ventana `ranked[:cfg.top_k]`, calcula `counts = Counter(norma)`, y si `top_count / cfg.top_k >= cfg.purity_threshold` colapsa a una sola norma (preservando §22.18 no-leakage incluso en auto-path); en caso contrario devuelve la ventana multi-corpus. El denominador es siempre `cfg.top_k` (no `len(window)`): una ventana corta es evidencia más débil de dominancia, así que el gate es intencionadamente más estricto (ADR-0017 §D3).

## 6.8 Optimizaciones cross-corpus: v0.1.10 → v0.1.11 → v0.1.12

El caso canónico xcorpus-002 (medido en v0.1.9 mediante diagnóstico CPU local $0) reveló que `bge-reranker-v2-m3` exhibe **single-article dominance**: cuando un artículo coincide bien con la query, el reranker tiende a poner sus 5 párrafos consecutivos en posiciones 1-5, dejando fuera otras normas que el usuario necesita citar. La cascada de fixes:

- **v0.1.10 — per-article dedup cap** (`_apply_per_article_dedup`, retrieval.py:191): tope por clave `(norma, articulo)`. Algoritmo verificado (Call 4 con `cap=2` emitió 4 artículos NIS2 distintos vs baseline 5×nis2.23), pero **no arregló xcorpus-002**: el top-5 seguía siendo 5/5 NIS2 (diversificado por dentro de la norma → purity gate seguía colapsando). Hallazgo más profundo: el sesgo del reranker está a nivel **norma**, no solo a nivel artículo.
- **v0.1.11 — per-NORMA dedup cap** (`_apply_per_norma_dedup`, retrieval.py:218): **BREAKTHROUGH medido** 1/3 → 2/3 artículos esperados emergiendo (NIS2 art 23 + GDPR art 33 en xcorpus-002). Descubrimiento matemático crítico: `cap=2` (sub-threshold 2/5=0.4 < 0.6 default) fuerza multi-corpus; `cap=3` (boundary-exact 3/5=0.6 inclusive) sigue colapsando. NIS2 art 35 sigue perdido (los scores del reranker lo ponen por debajo de DORA 19/22 dentro del pre-rerank).
- **v0.1.12 — top_k_auto opt-in** (retrieval.py:66-68 + 397-402): permite que la ruta auto use un `top_k` mayor (default empíricamente fijado a 12 desde v0.1.21.2). Wiring algorítmicamente verificado por 9 unit tests con rerank mockeado; **medición empírica diferida** a la sesión de pago v0.1.20 por la regla de coste CPU rerank de §6.4.

**v0.1.21.2 (ADR-0028)** consolidó los hallazgos como defaults de producción: `max_chunks_per_norma=2` y `top_k_auto=12` pasaron a ser los valores por defecto en `RetrievalConfig`, con backward-compat vía `None` explícito. NO se hizo paid pre-flip; la validación cumulativa quedó para v0.1.22 (ADR-0029), donde el bundle entero v0.1.19→v0.1.21.2 se midió como un solo arm.

## 6.9 Title-prepend: la asimetría query-vs-corpus (v0.1.28 SHIP, v0.1.30 REVERT)

Dos intervenciones simétricas con resultados opuestos — el hallazgo científico no obvio que documentar como contribución de la memoria.

**v0.1.28 T4-bis title-prepend QUERY-side (SHIPPED)** — `orchestration/document_graph.py:161` modifica la query enviada al retriever en modo documento: `f"{seg.title}\n{seg.text}" if seg.title else seg.text`. La intuición: las segmentaciones descriptivas de un documento corporativo ("el sistema realiza supervisión humana de las decisiones automatizadas del personal") no alinean bien en BGE-M3 con los chunks corpus prescriptivos ("los proveedores garantizarán que los sistemas de IA de alto riesgo se diseñen y desarrollen de tal modo que personas físicas puedan vigilarlos..."). Prefijar el título del segmento ayuda al embedding de la query a capturar la identidad temática. **Resultado medido**: doc-mode citation_recall 0 → 0.33 sobre la cohorte N=10 (ADR-0035 §REVERT lessons #3 + CLAUDE.md §27 v0.1.28). El segmenter v0.1.14 (ADR-0019) hizo posible esta intervención al detectar finalmente los títulos de sección numerada en español ("3.1.1 Detalle") que H5 había dejado pendientes.

**v0.1.30 title-augmented embeddings CORPUS-side (REVERTED)** — mirror simétrico: prefijar `f"Artículo {chunk.articulo} - {parsed.title}\n\n{chunk.text}"` a la entrada del embedder en `rag/build.py`, dejando `Chunk.text` byte-unchanged (el validator de citas seguía leyendo el texto canónico). ADR-0035 con riesgo §6 evaluado como LOW. **Resultado medido en probe T5 (€0.65 sunk)**: doc-mode citation_recall 0.33 flat (target era ≥0.38); doc-001 regresión precision 0.50 → 0.00; mediana de expansión de citaciones 5x (doc-001: 1-2 → 12; doc-003: 1 → 19). T7 main SKIPPED por disciplina de coste — la evidencia del probe era estructuralmente clara y coincidía con el mecanismo del REVERT v0.1.28 T4-extra α+β (top_k=15 + max_chunks=5 que diluyó contexto y precision 0.17 → 0.00).

**Mecanismo atribuido (ADR-0035 §REVERT)**: las title-augmented embeddings surface significativamente más artículos topic-related → v1.6 doc_analyst emite Findings citando todos los surfaced → precision colapsa porque los artículos gold-specific no dominan el conjunto + la sobre-emisión diluye la señal. **Es el mismo mecanismo que v0.1.28 T4-extra α+β**: la expansión de breadth en la capa de retrieval-config (top_k, max_chunks_per_norma) y en la capa de embedding-vector (title-augmented) producen el mismo failure mode de over-citation. La conclusión es estructural a la combinación BGE-M3 + v1.6 doc_analyst, no estocástica a la intervención específica.

**Restauración atómica** (ADR-0035 §REVERT): `mv corpus/indexes/regulaitor.lance.pre-v0.1.30/ corpus/indexes/regulaitor.lance/` + `git checkout HEAD -- corpus/manifests/` + restauración del código en `rag/build.py`. Verificación: cosine sim 0.97 (NO 1.0) entre el índice live restaurado y el descartado → confirma que el revert es real (vectores distintos). El §6 invariant sostuvo throughout ambas direcciones (activación y revert): `citation/validator.py` + `citation/schemas.py` + auditor + finder-lenient + prompts byte-unchanged en los dos puntos del cycle. 0 fabricaciones detectadas en el probe (per-citation reasons todas válidas `text_not_in_apartado` o `article_not_found`).

**Carry-forwards a HX post-deploy** (ADR-0035 §REVERT lessons): (a) HyDE (Hypothetical Document Embeddings) como query-side reformulation con LLM; (b) hybrid BM25 + dense; (c) reranker fine-tuned sobre pares legales (regulatory-text → applicable-article). La asimetría query-prepend-helps / corpus-prepend-hurts queda registrada como hallazgo científico para H17 — el tipo de insight no-obvio que el método diagnose-intervene-measure-refute-revert-document produce honestamente.

## 6.10 Idempotencia y atomicidad del build

`rag/build.run()` (build.py:33) compone tres capas de idempotencia (ADR-0004 §Idempotency):

1. **HTTP layer** (heredada de H1): `If-Modified-Since` / `If-None-Match` cortan los rebuilds del corpus.
2. **Article layer** (heredada de H1): SHA256 hash por `(article, language)`. Hash igual → `LanguageEntry` preservada verbatim, incluyendo `chunks`, `embedded_at`, `embedding_model`.
3. **Embedding layer** (nueva en H2): chequeo conjunto `(hash, embedding_model)`. Cambio del modelo con hashes intactos dispara re-embedding; texto cambiado con modelo intacto re-embebe solo los artículos modificados.

Verificada empíricamente: la segunda invocación de `rag_build` reporta `chunks_added=0, chunks_recomputed=0, chunks_unchanged=1011` (ADR-0004 §Smoke validation, ahora 1569 tras H14). La atomicidad pasa por `corpus/manifest.save_atomic` (`<path>.tmp` + `os.replace`) para los manifests; el upsert LanceDB es DELETE-then-ADD dentro del mismo bloque `with table:`. Caveat documentado (`build.py:50-52`): si `store.upsert` tiene éxito pero `save_atomic` falla después (disco lleno), LanceDB tiene chunks nuevos y manifest está stale — el siguiente run re-embebe, recuperable, ventana pequeña.

## 6.11 Métricas y estado en producción

- **Filas en LanceDB**: 1569 (ai_act 687 + gdpr 324 + nis2 244 + dora 314) tras H14 (ADR-0015).
- **Disco**: ~32 MB para `corpus/indexes/regulaitor.lance/` post-H2; el tamaño post-H14 escala proporcionalmente.
- **Cobertura módulos `rag/`**: H2 cerró con 92.55% global (`chunking.py`, `embeddings.py`, `reranker.py`, `schemas.py`, `store.py` al 100% por archivo; `build.py` al 91%) — ADR-0004 §Consequences. La gate de proyecto sigue en ≥85% desde v0.1.26 (deploy-prep H16) y se mantiene ≥88.62% en v0.1.32-h16-deploy (CLAUDE.md §27).
- **Defaults producción v0.1.32**: `top_k=5`, `pre_rerank=50`, `purity_threshold=0.6`, `query_normalize=False`, `max_chunks_per_article=None`, `max_chunks_per_norma=2`, `top_k_auto=12`.

El pipeline RAG es el sustrato sobre el que se levantan las dos garantías de §6: el validator de citas tiene un corpus al que validar (chunks con `text` canónico + `text_normalized` para exact-match), y el Auditor tiene `RetrievedChunk` con `norma`, `articulo`, `apartado`, `source_url` y `version` para componer su política de tres capas. La sección 07 documenta cómo §6 se vuelve operativo a partir de esta capa.
