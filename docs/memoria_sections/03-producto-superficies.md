# 03. Producto: tres superficies (chat + documental + API + MCP)

## 3.1 Marco general

RegulAItor expone su pipeline multi-agente a través de tres superficies funcionales más un servidor MCP propio para integración programática. La elección de superficies cumple el alcance §5 del CLAUDE.md: una herramienta de primera línea para consulta normativa y revisión documental, no un asesor jurídico. Cada superficie es un envoltorio fino sobre el mismo backend (Retriever → Analyst → Auditor → Council opcional); ninguna duplica lógica de validación de citas ni de bloqueo de respuestas. La invariante §6 "no citation, no answer" se aplica una sola vez, en el Auditor, sin variantes por superficie.

Las cuatro superficies son:

1. Chat normativo (Streamlit `tab_ask` + API `/ask`).
2. Análisis documental (Streamlit `tab_analyze` + API `/analyze`).
3. API REST FastAPI (`/ask`, `/analyze`, `/health`).
4. Servidor MCP local con cinco herramientas (`src/regulaitor/mcp_server/server.py`).

## 3.2 Chat normativo — Pestaña Pregunta y `/ask`

### 3.2.1 Flujo funcional

El usuario formula una pregunta en lenguaje natural, selecciona corpus (`auto`, `ai_act`, `gdpr`, `nis2`, `dora`) e idioma (`es`, `en`) y recibe una respuesta con citas verificadas inline. El corpus `auto` activa la ruta cross-corpus introducida en H15.1 (ADR-0017), que ejecuta retrieval multi-corpus con purity gate post-rerank.

En Streamlit (`src/regulaitor/ui_streamlit/tab_ask.py:30-69`) el flujo es:

- Formulario con `st.form` y `submit` explícito (un único `case_id` por intento; sin re-runs accidentales).
- Llamada a `orchestration.graph.run()` con un spinner que describe el pipeline visible ("Retriever → Analyst → Auditor").
- Persistencia mínima vía `st.session_state["last_chat_state"]`: única ranura, sin historial acumulado.
- Renderizado en `_render.chat_state()` (`src/regulaitor/ui_streamlit/_render.py:210-244`).

En API (`src/regulaitor/api/routes_ask.py:32-60`) el endpoint es `POST /ask`, autenticado con Bearer token (`HTTPBearer` + `hmac.compare_digest`, H7), rate-limited vía `slowapi` (default `30/minute`, configurable vía `REGULAITOR_RATE_LIMIT_ASK`), y delega en el mismo `run()` mediante `asyncio.to_thread` para no bloquear el event loop durante las llamadas a Sonnet (5-40 s típicos).

### 3.2.2 Elementos UI distintivos (R13 v0.1.32)

El renderizador comparte componentes con la pestaña documental:

- **Verdict badge prominente** (`_render.py:110-133`): pildora coloreada con accent semántico (PASS verde emerald-700, BLOCK rojo rose-700, REQUIRES_HUMAN_REVIEW ámbar-700) sobre fondo tintado. Sustituye al `st.success/error` por defecto para no dominar visualmente otras señales y mantener legibilidad WCAG (≥4.5:1 contraste declarado).
- **Corpus chips** (`_render.py:39-54`): paleta de cuatro colores por norma — AI Act Navy `#1E40AF`, GDPR Emerald `#047857`, NIS2 Violet `#6D28D9`, DORA Amber `#B45309`. Aparecen como prefijo en cada citación y como resumen de "Fuentes consultadas" sobre los findings (`_render.py:57-73`), surfaceando automáticamente la dimensión cross-corpus.
- **Auditor details env-gated**: el dataframe `audit_results` (article_exists, apartado_exists, text_normalized_match, reason) sólo se muestra si `REGULAITOR_SHOW_AUDIT_DETAILS` no es `false` (`_render.py:242`). Default abierto en el demo HF Spaces — evidencia visible de la §6 invariant funcionando; en despliegues productivos puede cerrarse para no exponer flags internos.
- **Council notice + expander**: si el Council advisory (H13) o vinculante (v0.1.19 monotonic-escalate; ADR-0025) diverge del Auditor, se renderiza un `st.warning` con expander mostrando los votos de los tres jueces.

### 3.2.3 Salida estructurada

`AuditedAnswer` (`src/regulaitor/citation/schemas.py`) consta de:

- `verdict`: `PASS | BLOCK | REQUIRES_HUMAN_REVIEW`.
- `reason`: cadena prefijada por categoría (`COUNCIL_BIND:...`, `quorum_invalid:...`, etc.).
- `answer.text`: prosa.
- `answer.findings[]`: lista de `Finding{text, citations[], severity}`. Desde v0.1.21 ADR-0027, esta lista no puede estar vacía si la respuesta no es un rechazo formal (Capa B Pydantic `min_length=1`).
- `audit_results[]`: para cada citación emitida, su resultado de validación con `failed_check` (campo aditivo v0.1.24 ADR-0031: 1=article_not_found, 2=apartado_not_found, 3=text_not_match, None=válida).

## 3.3 Análisis documental — Pestaña Analiza y `/analyze`

### 3.3.1 Pipeline siete pasos

Per §5.1 CLAUDE.md, el pipeline documental orquestado en `orchestration/document_graph.py::run_document` (`src/regulaitor/orchestration/document_graph.py:220-304`) ejecuta:

1. **Extraer**: `document.extractor.extract()` sobre PDF (`pypdfium2` + `pdfplumber`) o Markdown.
2. **Sanitizar**: `document.sanitizer.sanitize()` elimina texto invisible, metadatos sospechosos, márgenes y bloquea JavaScript embebido vía `DocumentBlockedError`. ADR-0007.
3. **Segmentar**: `document.segmenter.segment()` corta en `Segment{id, title, text}`. Heading-regex extendido en v0.1.14 (ADR-0019) cierra el deferral H15 de "0 segmentos" para PDFs con secciones numeradas castellanas (`1.`, `2.1.`, `3.1.1.`).
4. **Identificar corpus aplicable**: la lista de corpus se pasa como `Form` field; el primer elemento es la `primary_corpus` para retrieval por segmento (`document_graph.py:274`).
5. **Generar hallazgos por segmento**: bucle secuencial (`document_graph.py:276-278`) — no LangGraph compilado, decisión H5 para auditabilidad. Cada segmento atraviesa anti-injection → Retriever → Analyst (rol `document_analyst`, prompt v1.6 desde v0.1.28) → Auditor.
6. **Bloquear hallazgos sin cita válida**: el Auditor opera con la misma arquitectura §6.1 multi-capa que en chat (per-citation validator + Finding-Lenient aggregation + Turn-level routing modificado en v0.1.25/v0.1.29 + prompt-level explicit forbid v1.6).
7. **Emitir informe**: `DocumentReport` con métricas agregadas (`n_segments_pass/block/review`, `latency_ms_total`, `cost_eur_total`) y verdict global derivado por `_aggregate_document()` (`document_graph.py:72-132`).

### 3.3.2 Particularidades de la pestaña

`src/regulaitor/ui_streamlit/tab_analyze.py:44-108` incluye:

- **Latency advisory demo-mode** (R14 v0.1.32, `tab_analyze.py:50-56`): banner `st.info` informa que la demo pública corre en HF Spaces cpu-basic (2 vCPU, sin GPU) y que el BGE-M3 reranker tarda ~15-30 s por consulta de segmento. Recomienda PDFs ≤5 páginas. Para cargas reales: deploy GPU o ejecución local. Es un cambio puramente frontend; no altera el backend.
- **Detección MIME por magic bytes** (`tab_analyze.py:35-41`): `%PDF-` para PDF, extensión `.md/.markdown` para Markdown — defensa contra extensión-only.
- **Métricas en `st.columns(6)`** (`_render.py:257-268`): PASS, BLOCK, REVIEW, SKIPPED (por injection), LATENCY, COST €.
- **Per-segment expanders**: cada segmento se renderiza colapsado, etiquetado con `§<id> <title> · <emoji> <verdict>` (`_render.py:276-296`).

La limitación demo es explícita y documentada honestamente (§22.22): el test gold doc-mode de 4 segmentos en HF cpu-basic toma aproximadamente 20 minutos de wallclock; no es un fallo del pipeline sino el coste del rerank CPU-bound sin GPU.

### 3.3.3 Errores y comportamiento defensivo

- `ExtractionError` → `st.error` con mensaje sanitizado.
- `DocumentBlockedError` (sanitizer crítico, por ejemplo JavaScript embebido) → `verdict=REQUIRES_HUMAN_REVIEW` + `document_reason=sanitizer_critical:<categoría>` + log expandido.
- Injection detectado por segmento → `SegmentResult.skipped=True` sin pasar por LLM (`document_graph.py:142-152`), contabilizando a `n_segments_blocked_by_injection`.

## 3.4 API REST FastAPI

### 3.4.1 Endpoints

`src/regulaitor/api/main.py:42-91`:

- `POST /ask` (`routes_ask.py`): consulta chat; DTO `AskRequest{query, corpus, language, council}`; respuesta `AskResponse` con verdict, findings, citations, council_notice opcional.
- `POST /analyze` (`routes_analyze.py`): multipart con `file` + `corpus[]` + `language`; cap de tamaño `REGULAITOR_MAX_UPLOAD_BYTES` (10 MB default); rate-limit `5/minute` (default).
- `GET /health` (`routes_health.py`): readiness; verifica LanceDB (`connect()` + `count_rows() ≥ 1`), `ANTHROPIC_API_KEY` y `_API_TOKEN`. Devuelve 503 si alguno está degradado.

### 3.4.2 Seguridad transversal

- Autenticación Bearer obligatoria en `/ask` y `/analyze`; carga fail-fast en `lifespan`.
- Rate-limit `slowapi` por endpoint con valores leídos en cada request para permitir testing.
- Handlers globales (`main.py:79-87`): validación 422, injection 400, file-size 413, unsupported-media 415, backend-errors 500, generic-handler con redacción del mensaje original.
- CORS allowlist desde `REGULAITOR_CORS_ORIGINS` (vacío por defecto, safe-by-default no-browser).

## 3.5 Servidor MCP propio

Cinco tools registradas en `src/regulaitor/mcp_server/server.py:52-67` vía `FastMCP.add_tool()`, con esquemas JSON autoderivados de las firmas tipadas:

- `search_articles(query, corpus, language, top_k)` — retrieval LanceDB + BGE-M3 + reranker. Cuando `corpus="auto"`, dispara la ruta multi-corpus con purity gate (ADR-0017); `top_k` se ignora en esa ruta y rige `DEFAULT_CONFIG.top_k` (ADR-0018).
- `fetch_article(norma, articulo, language, apartado)` — lookup directo al corpus oficial; `NotFoundError` con hint útil si falta.
- `validate_citation(citation)` — interfaz canónica al validador §6 (`citation/validator.py`); siempre devuelve `AuditResult`, nunca lanza por contenido inválido.
- `extract_document(file_bytes, mime_type)` — wrapper sobre `document.extractor.extract`.
- `segment_document(text, max_tokens)` — segmenter sobre texto ya sanitizado fuera de banda.

El flujo end-to-end documental no se expone como tool MCP por diseño (spec H5 §4.10): sólo `run_document()` puede encadenar extract+sanitize+segment+loop, manteniendo la sanitización siempre obligatoria. El warmup (`server.py:31-42`) carga corpus con integrity check fail-closed y precalienta el reranker.

## 3.6 Despliegue actual

Demo público en Hugging Face Spaces (Streamlit SDK, cpu-basic) en `https://huggingface.co/spaces/enriro00/regulaitor` desde v0.1.32 (tag `v0.1.32-h16-deploy`, 2026-05-28). Índice LanceDB de 1569 chunks (AI Act 687 + GDPR 324 + NIS2 244 + DORA 314) horneado en imagen vía Git LFS; cold-start ~5 min documentado en `docs/H16_DEPLOY.md`. La API FastAPI no está expuesta públicamente en el demo (sólo Streamlit en el SDK); su despliegue Render/Fly.io queda como follow-up post-TFM con runbook ya escrito.
