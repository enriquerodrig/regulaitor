# Model Card — RegulAItor

**Versión del sistema:** v0.1.32 (H16 desplegado, 2026-05-28)
**Fecha del documento:** 2026-05-29
**Tag de referencia:** `v0.1.32-h16-deploy`
**Demo público:** https://huggingface.co/spaces/enriro00/regulaitor
**Convenciones:** Mitchell et al. 2019 (*Model Cards for Model Reporting*) + Google Model Card Toolkit.

---

## Abstract (EN)

RegulAItor is a multi-agent EU regulatory compliance service whose core invariant is "no citation, no answer" (CLAUDE.md §6). It is not a single model: it composes seven third-party models (one Sonnet-class LLM, one Haiku-class LLM, two open-weights local components, one open-weights hosted model and two OpenAI models) behind a custom router (`src/regulaitor/models/router.py`). This document audits each model's intended use within the system, its measured contribution to the v0.1.20-bar metrics (`docs/v0120_bar_thresholds.md`), and its known limitations. No claim is made beyond what was measured under the milestones documented in `docs/technical_decisions_log.md`.

## Abstract (ES)

RegulAItor es un servicio multi-agente de cumplimiento normativo europeo cuyo invariante central es "sin cita verificable, no hay respuesta" (CLAUDE.md §6). No es un modelo único: orquesta siete modelos de terceros (un LLM clase Sonnet, un LLM clase Haiku, dos componentes open-weights locales, un modelo open-weights alojado y dos modelos de OpenAI) tras un router propio (`src/regulaitor/models/router.py`). Este documento audita cada modelo bajo su uso previsto dentro del sistema, su contribución medida a las métricas de la columna v0.1.20-bar (`docs/v0120_bar_thresholds.md`) y sus limitaciones conocidas. No se afirma nada más allá de lo medido en los hitos documentados en `docs/technical_decisions_log.md`.

---

## 1. Modelos integrados — inventario

Todos los identificadores y precios están normalizados en `src/regulaitor/models/config.py:18-38` (fecha de snapshot `PRICING_SNAPSHOT_DATE = "2026-05-16"`).

| Modo router | Modelo | Proveedor | Rol en el sistema | Localización |
|---|---|---|---|---|
| `default`/`quality` | `claude-sonnet-4-6` | Anthropic | Analyst-Agent (chat) + Document-Analyst (doc) | API hospedada |
| `judge` | `claude-haiku-4-5-20251001` | Anthropic | LLM-as-judge (evals H8) + Council judge | API hospedada |
| `cost` | `llama-3.3-70b-versatile` | Groq | Council judge (diversidad multi-proveedor) | API hospedada (open-weights) |
| `evaluation` | `gpt-4o` | OpenAI | Council judge (diversidad multi-proveedor) | API hospedada |
| `fallback` | `gpt-4o-mini` | OpenAI | Fallback transport-error one-hop | API hospedada |
| (no router) | `BAAI/bge-m3` | BAAI / HuggingFace | Embeddings 1024-dim (retriever + Ragas) | Local (CPU/GPU) |
| (no router) | `BAAI/bge-reranker-v2-m3` | BAAI / HuggingFace | Cross-encoder reranking | Local (CPU/GPU) |

Invariante de routing (CLAUDE.md §22.13): ningún agente llama a un modelo directamente; todo pasa por `router.complete()` (`src/regulaitor/models/router.py:193-240`). BGE-M3 y el reranker son la excepción documentada porque no son modelos generativos.

---

## 2. claude-sonnet-4-6 — Analyst-Agent + Document-Analyst (producción)

### Intended use
- Genera el `Answer` JSON estructurado del Analyst-Agent (`src/regulaitor/agents/analyst.py`) en modo chat con el prompt `prompts/analyst/system.v1.5.md` (default desde v0.1.20, ADR-0026).
- Genera los `Finding` por segmento del Document-Analyst con el prompt `prompts/document_analyst/system.v1.6.md` (default desde v0.1.28, ADR-0033).
- Razona sobre el contexto recuperado y debe emitir citas candidatas (artículo + apartado + texto). **No** decide si la respuesta sale al usuario — esa decisión es del Auditor-Agent (CLAUDE.md §8.3).

### Out-of-scope use
- No emite veredictos de validez. La autoridad de bloqueo es el Auditor mecánico (`src/regulaitor/agents/auditor.py`), nunca este modelo.
- No produce asesoramiento jurídico definitivo (limitación visible en UI y CLAUDE.md §3).
- No se usa como juez en evaluaciones (sería echo-chamber; ADR-0010 D1).

### Métricas medidas (v0.1.25-prod sobre H10 30-case combined cohort, post-O1)
- `verdict_match`: 0.73 (v0.1.20-bar 0.35 ✅).
- `faithfulness`: 0.71 (v0.1.20-bar 0.65 ✅).
- `citation_recall`: 0.68 (v0.1.20-bar 0.60 ✅).
- `cost_per_chat`: €0.054 (soft bar €0.05; overhead de Capa C retry per ADR-0027 D4).
- Latencia p95 por turno: ~15-60 s en producción, dominada por la llamada Sonnet (CLAUDE.md §17 nota 7).

### Limitaciones y consideraciones de sesgo
- **Modelo cerrado**: no hay tarjeta de datos de entrenamiento pública detallada; se documenta lo afirmado por Anthropic (entrenado hasta principios 2026; *constitutional AI*). El proyecto no puede auditar el corpus de entrenamiento.
- **Schema-adherence histórica**: hasta v0.1.21 el Analyst emitía ocasionalmente `findings=[]` con texto sustantivo (mecanismo "prose-without-findings", ver `docs/no_answer_residual_diagnosis.md`). Mitigado por Tier 2 Capa A+B+C (ADR-0027) + Hard Rule 9 del prompt v1.4/v1.5.
- **Sesgo de paráfrasis sobre texto literal**: tendencia a parafrasear citas en lugar de copiar el texto del corpus, generando fallos de Check 3 del validator. Mitigado a nivel de agregación por Layer (c) del §6.1 (ADR-0032 + ADR-0034), no a nivel del modelo.
- **Idioma**: validado principalmente en español (chat + UI ES); el prompt soporta inglés pero la evaluación está pesada hacia ES.

### Impacto ambiental
- API hospedada por Anthropic. RegulAItor no opera el cómputo. El consumo per-query se estima en el rango habitual de los modelos Sonnet-class (no se publica TFlops/query oficial por el proveedor).
- Coste real medido acumulado del proyecto: ~€38.5 / ~$41.5 USD en 13 paid milestones (H8 → v0.1.32) — ver `docs/cost_analysis.md` §1 ledger y entradas §H15.X en `docs/technical_decisions_log.md`.

### Licencia y términos
- API comercial sujeta a Anthropic *Commercial Terms of Service*. RegulAItor consume vía `ANTHROPIC_API_KEY` (`src/regulaitor/models/router.py:184-190`).

---

## 3. claude-haiku-4-5-20251001 — LLM-as-judge + Council judge

### Intended use
- Juez único en H8 evaluation harness (`scripts/evaluate.py` + `evals/harness.py`) — califica `criterios_evaluacion` del gold set sobre el output del Analyst (ADR-0010 D1).
- Una de las tres voces del Council of Judges (ADR-0014 D3 + D7), llamado vía el modo `judge` añadido en H13.
- Posible modo `cost` futuro para chat de bajo coste (no activado en producción a v0.1.32).

### Out-of-scope use
- No se usa como Analyst de producción (el `default` mode mapea a Sonnet 4.6, no a Haiku).
- No se usa para validar citas individuales — esa validación es mecánica (`src/regulaitor/citation/validator.py`), nunca un LLM.

### Métricas medidas
- **Tasa de paso del fence-stripping**: ~100% tras la corrección de `_strip_markdown_fence` en `evals/judge.py` (ADR-0010 amendment 4). Haiku ocasionalmente envuelve JSON en ` ```json ` fences a pesar del prompt.
- **Cache hit ratio**: 100% en re-runs con `make eval-from-cache` (ADR-0010 D7, cache SHA256 hash-keyed en `evals/cache/`).
- Coste agregado: parte del ~€38.5 acumulado; no desglosado por capa juez vs Analyst en el harness H8 (gap conocido, ADR-0029 §22.22 #10; ver `docs/cost_analysis.md` §2 "Lo que el acumulador NO captura").

### Limitaciones y consideraciones de sesgo
- **Mismo proveedor que el Analyst de producción**: Haiku y Sonnet son ambos Anthropic. Esto debilita la afirmación de "juez independiente" (CLAUDE.md §19, ADR-0010 D1 + ADR-0021). Documentado, no oculto. Migración cross-vendor a GPT-4o-mini o Llama vía Groq diferida a HX post-TFM (ADR-0021).
- **Modelo cerrado**: misma limitación de auditoría de datos de entrenamiento que Sonnet.
- **Heurística de fence**: el modelo no respeta consistentemente "responde solo JSON puro", lo que motivó el helper post-hoc.

### Impacto ambiental y licencia
- API hospedada. Coste por 1M tokens (a `PRICING_SNAPSHOT_DATE=2026-05-16`): $1.0 input / $5.0 output (`src/regulaitor/models/config.py:32`).
- Mismos términos comerciales que Sonnet (`ANTHROPIC_API_KEY`).

---

## 4. BAAI/bge-m3 — Embeddings retriever + Ragas

### Intended use
- Codifica chunks del corpus (**2167 filas** en LanceDB tras las expansiones HX; AI Act 687 + GDPR 324 + NIS2 244 + DORA 314 + DORA-RTS 14+26 + AMLR 180 + MiCA 298 + TFR 80) y queries del usuario en vectores densos 1024-dim (`src/regulaitor/rag/embeddings.py:35-46`).
- Backend de embeddings para Ragas metrics (`faithfulness`, `context_precision`, `answer_relevancy`) — añadido como dependencia tras ADR-0010 amendment 8 para evitar segundo API key (HuggingFace local en lugar de OpenAI embeddings).
- Provee el tokenizer XLM-RoBERTa usado por `rag.chunking` y `corpus.ingest` para conteo de tokens (`embeddings.py:49-57`).

### Out-of-scope use
- No es modelo generativo. No produce texto.
- No se usa para reranking — eso es responsabilidad del cross-encoder específico (sección 5).

### Métricas medidas
- `context_precision`: 0.78 (v0.1.20-bar 0.55 ✅) en v0.1.22-prod H10 cohort.
- Indexa 2167 chunks (9 corpus) en LanceDB local (`corpus/indexes/regulaitor.lance`) sin coste API.
- Throughput local: ~CPU; batch_size=16 por defecto (`embeddings.py:35`).

### Limitaciones y consideraciones de sesgo
- **Brecha semántica descriptivo→obligación**: en doc-mode, segmentos descriptivos de políticas internas no recuperan eficientemente artículos normativos de obligación. Confirmado empíricamente por v0.1.30 REVERT (ADR-0035 §REVERT) — la asimetría es que el prefijo de título ayuda en query-side (v0.1.28 T4-bis) pero perjudica en corpus-side (re-embed con título prepended causa sobre-emisión de citas). Hallazgo científico documentado para H17 memoria.
- **Multilingüe pero sesgado hacia inglés**: BGE-M3 fue entrenado sobre múltiples idiomas; el corpus EUR-Lex se ingesta en ES+EN. No se ha medido equidad cross-language sistemática.
- **Dominio general, no jurídico**: no es un encoder fine-tuned sobre derecho. Reranker custom legal sería candidato HX (ADR-0035 §Alternatives).

### Impacto ambiental
- **Local CPU/GPU**: el cómputo lo realiza la máquina del operador. Ingestión completa de los 9 corpus tarda ~1.5h en CPU (medido en T3 v0.1.30, ADR-0035). Servir queries online es ms-scale por query.
- No hay coste API recurrente. Pesos descargados de HuggingFace Hub (~2.5 GB) bajo licencia MIT.

### Licencia
- Modelo y pesos: **MIT License** (BAAI). Pre-entrenamiento documentado en el artículo *M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation* (Chen et al., 2024).

---

## 5. BAAI/bge-reranker-v2-m3 — Cross-encoder reranker

### Intended use
- Re-puntúa `(query, passage)` tras la búsqueda densa BGE-M3, mejorando el top-N final del retriever (`src/regulaitor/rag/reranker.py:27-42`).
- Singleton lazy-loaded con `use_fp16=False` por defecto (compatibilidad CPU).

### Out-of-scope use
- No genera texto. No clasifica severidad. No valida citas.

### Métricas medidas
- Mejora `context_precision` vs sola búsqueda densa (medición indirecta; ablation explícita diferida a HX).
- Latencia per-call CPU: ~15-30 s sostenidos para N=10 pasajes (`feedback_local_cpu_rerank_cost.md`), no 5-10s como subestimaciones iniciales — disciplina aprendida tras v0.1.9/v0.1.10/v0.1.12.

### Limitaciones y consideraciones de sesgo
- **Single-article dominance failure mode**: en xcorpus-002 (v0.1.9 diagnostic), el reranker posiciona 5 párrafos del mismo NIS2 art 23 más alto que GDPR art 33 y NIS2 art 35, aunque ambos están en el pool denso. Mitigado parcialmente por purity gate + per-NORMA cap (v0.1.11 BREAKTHROUGH 1/3→2/3); el techo del propio reranker se carry-forward a HX.
- **CPU-bound**: en deploy HF Spaces el cold-start dominante es la carga del reranker + embedder + LanceDB (~5 min observados, v0.1.32-h16-deploy).

### Impacto ambiental y licencia
- Local CPU/GPU, mismo perfil que BGE-M3.
- Licencia: **MIT License** (BAAI).

---

## 6. meta-llama/Llama-3.3-70b-versatile (vía Groq) — Council judge

### Intended use
- Tercera voz del Council of Judges (modo `cost` del router, ADR-0014 D3). Provee diversidad de proveedor (open-weights, no Anthropic, no OpenAI) para la suite advisory.

### Out-of-scope use
- No es Analyst de producción (el A/B H12 mostró calidad uniformemente baja Sonnet/GPT-4o/Llama → la palanca dominante es system-level, ADR-0013 Consequences).
- No se usa como Auditor — el Auditor es mecánico.

### Métricas medidas
- **A/B H12 (40-case gold set)**: `verdict_match` 0.17-0.28, `severity_match` 0.04-0.23 (banda Sonnet/GPT-4o/Llama; ADR-0013). Hallazgo: el techo es system-level, no de modelo.
- **Contaminación documentada** (ADR-0013 + ADR-0014): cap free-tier Groq 100k tokens/día se agotó en runs secuenciales → fallback one-hop a GPT-4o-mini absorbió ~19/40 panels en H12 y ~6/21 en H13. Aceptado §22.22, no re-run.

### Limitaciones y consideraciones de sesgo
- **Open-weights pero hosted**: el modelo es open-weights (publicado por Meta bajo Llama 3.3 Community License), pero el cómputo lo provee Groq con su propio TLS/rate-limit/serving stack.
- **Free-tier rate cap**: 100k TPD insuficiente para evals densas sin pagar tier (no presupuestado en MVP).
- **Cobertura de idioma**: Llama 3.3 es mayoritariamente multilingüe; no se ha medido específicamente equidad ES vs EN para tareas legales.

### Impacto ambiental y licencia
- Cómputo en infraestructura Groq. Coste por 1M tokens: $0.59 input / $0.79 output (`src/regulaitor/models/config.py:35`).
- Pesos: **Llama 3.3 Community License Agreement** (Meta). Sujeto a aceptación de la licencia y prohibiciones específicas (uso militar, etc.).

---

## 7. gpt-4o + gpt-4o-mini (OpenAI) — Council judge + Fallback

### Intended use
- `gpt-4o` (modo `evaluation`): segunda voz del Council of Judges (ADR-0014 D3).
- `gpt-4o-mini` (modo `fallback`): destino del fallback controlled one-hop ante errores transport en cualquier provider primario (`router.py:77-90`, `_FALLBACKABLE_ERRORS` estrechado a 12 tipos transport tras T7 I-1 review, ADR-0013).

### Out-of-scope use
- No son Analyst de producción.
- `gpt-4o-mini` **no** absorbe errores deterministas (BadRequestError, malformed tool args) — esos propagan loudly por diseño para no corromper la medición A/B (ADR-0013 D4).

### Métricas medidas
- A/B H12 banda Sonnet/GPT-4o/Llama: ver sección 6. GPT-4o no mejora la calidad sistémica → reforzó la hipótesis system-level que motivó H15.
- Fallback `latency_ms` añade ~1-2 s al turno cuando dispara (raro en producción; no medido sistemáticamente).

### Limitaciones y consideraciones de sesgo
- **Modelo cerrado**, sin acceso a datos de entrenamiento ni a la receta de fine-tuning de OpenAI.
- **Coste OpenAI** (`config.py:33-34`): $2.50/$10.0 (gpt-4o), $0.15/$0.60 (gpt-4o-mini) per 1M tokens.
- **Contaminación en H12**: el cap free-tier de OpenAI ($5 inicial) se agotó en runs secuenciales, haciendo que la propia fallback también fallara — I-2 empíricamente demostrado (ADR-0013).

### Licencia
- API comercial OpenAI, sujeta a sus *Usage Policies*. `OPENAI_API_KEY` requerido solo si se activan modos `evaluation` o `fallback` (`router.py:356-365`; fail-fast si falta).

---

## 8. Consideraciones transversales

### 8.1 Sobre la afirmación "no citation, no answer" (CLAUDE.md §6)
Ningún modelo de esta tarjeta tiene autoridad para emitir respuesta sin pasar por:
- (a) `citation/validator.py` per-citation strict 3-checks (BYTE-EQUIVALENT semantics desde H4, ADR-0031).
- (b) Finding-Lenient aggregation (`auditor.py` línea ~61, BYTE-UNCHANGED desde v0.1.21).
- (c) Turn-level aggregation policy (modificada en ADR-0027, ADR-0032, ADR-0034 — Layer (c) §6.1).
- (d) Prompt-level explicit forbid (Hard Rule 4 inviolable en `system.v1.5.md` chat + `system.v1.6.md` doc, ADR-0033).
La fabricación de artículo o apartado **nunca** puede pasar por construcción del helper compartido `_all_blocked_findings_paraphrase_only`.

**Límite del enforcement mecánico (claim-support boundary; auditoría pre-piloto sec6-02).** Las capas (a)-(c) verifican que la *cita exista* en el corpus (el texto citado aparece literal/normalizado en el artículo/apartado declarado, y que artículo + apartado existen). **No** verifican mecánicamente que la cita *apoye* la afirmación del Finding (§6 check 4, "la cita apoya la afirmación"): esa correspondencia afirmación↔cita la cubren el prompt del Analyst (capa (d)), el Council advisory para severidad alta (ADR-0014; binding ON desde v0.1.19 solo en dirección conservadora) y la métrica Ragas *faithfulness* en evals — ninguno es un gate duro de *entailment* semántico. **Implicación para el piloto**: un veredicto `pass` garantiza que toda cita emitida es real y existe en el corpus, **no** que el razonamiento jurídico sea correcto o completo. RegulAItor es una herramienta de primera línea con cita verificable, no un sustituto del criterio de un asesor (CLAUDE.md §3). Un checker de *entailment* semántico (NLI) que convierta el check 4 en gate duro queda como carry-forward HX — desproporcionado pre-piloto sin usuarios. Nota complementaria: el matching de texto de la capa (a) es por substring normalizado, por lo que una cita de un token trivial puede validar aunque aporte poca evidencia (gap de precisión documentado en la auditoría pre-piloto sec6-01 + `tests/unit/citation/test_validator.py::test_known_gap_trivial_substring_citation_validates`); la fabricación sigue bloqueada (checks 1/2).

### 8.2 Bias y limitaciones de cobertura
- **Sub-representación**: el gold set tiene 64 chat + 10 doc cases (CLAUDE.md §27 v0.1.15 + v0.1.27). No es estadísticamente representativo del universo de consultas reales — apto para defensa académica TFM, **no** para garantía de producción a escala.
- **PYME europea 50-500 empleados** es el usuario primario (CLAUDE.md §4); validación con usuarios no-técnicos no realizada.
- **Idiomas medidos**: ES principalmente, EN puntualmente. Otros idiomas EU no validados.

### 8.3 Coste y latencia
Ver `docs/cost_analysis.md` para el modelo analítico list-price y la captura honesta del gap "estimate vs measured" (cerrado por router accumulator H15, `router.py:147-174`).

### 8.4 Auditabilidad
- Todos los prompts versionados en `src/regulaitor/agents/prompts/<agent>/<role>.vN.M.md` (CLAUDE.md §22.12).
- Todas las llamadas pasan por `router.complete()` (CLAUDE.md §22.13).
- LangFuse opcional via `LANGFUSE_*` envs (ADR-0012); redacción allowlist en egress.

### 8.5 Modelos no incluidos (carry-forward)
- **Severity classifier fine-tuned LoRA sobre Llama-3.1-8B**: planeado en HX1 (CLAUDE.md §15.3); no entrenado a v0.1.32.
- **HyDE / hybrid BM25 / custom legal reranker**: carry-forward HX post-TFM tras v0.1.30 REVERT (ADR-0035).

---

## 9. Referencias

- CLAUDE.md §6 (invariante "no citation, no answer"), §6.1 (four-layer architecture), §8 (agentes), §10.4 (router), §22.13 (invariante de routing).
- ADR-0010 (`docs/adr/0010-evaluation-harness.md`) — judge = Haiku 4.5 + caveat mismo proveedor.
- ADR-0013 (`docs/adr/0013-router-multi-llm.md`) — router 5 modos + A/B H12 + contaminación honesta.
- ADR-0014 (`docs/adr/0014-council-of-judges.md`) — Council of Judges + modo `judge` añadido.
- ADR-0021, ADR-0026, ADR-0027, ADR-0029, ADR-0031, ADR-0032, ADR-0033, ADR-0034, ADR-0035 — evolución interpretativa §6 y prompts.
- `docs/technical_decisions_log.md` §H8, §H12, §H13, §v0.1.20 … §v0.1.32.
- `docs/cost_analysis.md` — modelo list-price + captura real router accumulator.
- `docs/v0120_bar_thresholds.md` — derivación dual-layer §17.
- `docs/no_answer_residual_diagnosis.md` — v0.1.17/v0.1.17.1 mecanismos de no-answer.
- `src/regulaitor/models/router.py`, `src/regulaitor/models/config.py`, `src/regulaitor/rag/embeddings.py`, `src/regulaitor/rag/reranker.py`.
- Mitchell M. et al. (2019). *Model Cards for Model Reporting*. FAT* '19.
- Chen J. et al. (2024). *M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation*.

---

**Disciplina §22.22 aplicada**: ninguna métrica de esta tarjeta es proyección. Cada cifra cita el milestone donde fue medida; ausencias se marcan explícitamente (`[pendiente]` o "no medido sistemáticamente"). 13 hitos consecutivos con framing honesto en `docs/technical_decisions_log.md` respaldan esta tarjeta.
