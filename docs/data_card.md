# Data Card — RegulAItor

**Versión:** 1.0.0 (alineada con tag `v0.1.32-h16-deploy`)
**Fecha:** 2026-05-29
**Estructura:** Pushkarna et al. (2022), *Data Cards: Purposeful and Transparent Dataset Documentation for Responsible AI*.
**Datasets cubiertos:** 4 — (1) corpus normativo, (2) gold set de evaluación, (3) red team set, (4) eval reports históricos.

---

## Resumen bilingüe

### Resumen — ES

RegulAItor consume y produce cuatro datasets diferenciados. El corpus normativo agrupa **nueve** instrumentos europeos (AI Act, RGPD, NIS2, DORA + 2 RTS de DORA + AMLR, MiCA, TFR) descargados de EUR-Lex en ES + EN (PDF para el MVP, HTML para las expansiones HX), parseados, chunkeados por artículo y embebidos con `BAAI/bge-m3` (**2167 chunks**). El gold set (64 chat + 10 documentos) sintetiza preguntas y casos documentales por el autor para evaluar precision/recall de citación y verdict matching. El red team set añade 50 ataques manualmente diseñados sobre los 10 escenarios §18 (CLAUDE.md). Los eval reports históricos son artefactos por hito que sustentan la afirmación §22.22 "nunca presentar como medido lo que no se ha medido".

### Abstract — EN

RegulAItor relies on four distinct datasets. The normative corpus bundles **nine** European instruments (AI Act, GDPR, NIS2, DORA + 2 DORA RTS + AMLR, MiCA, TFR) fetched from EUR-Lex in ES + EN (PDF for the MVP, HTML for the HX expansions), parsed, article-chunked, and embedded with `BAAI/bge-m3` (**2167 chunks**). The gold set (64 chat + 10 document cases) is hand-synthesized by the project owner to measure citation precision/recall and verdict matching. The red team set adds 50 manually authored attacks covering the 10 scenarios in CLAUDE.md §18. Historical eval reports are per-milestone artifacts that anchor the §22.22 "never claim as measured what was not measured" honesty discipline.

---

## Dataset 1 — Corpus normativo (9 instrumentos: AI Act, RGPD, NIS2, DORA, DORA-RTS ×2, AMLR, MiCA, TFR)

### Descripción

Nueve instrumentos jurídicos europeos consumidos como fuente única de verdad por el `RetrieverAgent` y el `citation/validator.py` (los 4 del MVP + las expansiones HX: 2 RTS de DORA en Fase 3 y AMLR/MiCA/TFR en Fase 6):

| Corpus | CELEX | Versión | Artículos | Chunks |
|---|---|---|---|---|
| AI Act (Regl. (UE) 2024/1689) | `32024R1689` | 2024-07-12 | 113 | 687 |
| RGPD (Regl. (UE) 2016/679) | `02016R0679-20160504` | 2016-05-04 (consolidada) | 99 | 324 |
| NIS2 (Directiva (UE) 2022/2555) | `32022L2555` | 2022-12-27 (base act) | 46 | 244 |
| DORA (Regl. (UE) 2022/2554) | `32022R2554` | 2022-12-27 (base act) | 64 | 314 |
| DORA RTS Plazos (Regl. Deleg. (UE) 2025/301) | `32025R0301` | 2025-02-20 | 7 | 14 |
| DORA RTS Clasificación (Regl. Deleg. (UE) 2024/1772) | `32024R1772` | 2024-06-25 | 13 | 26 |
| AMLR (Regl. (UE) 2024/1624) | `32024R1624` | 2024-06-19 | 90 | 180 |
| MiCA (Regl. (UE) 2023/1114) | `32023R1114` | 2023-06-09 | 149 | 298 |
| TFR (Regl. (UE) 2023/1113) | `32023R1113` | 2023-06-09 | 40 | 80 |
| **Total** | — | — | **621** | **2167** |

Fuente: `corpus/manifests/*.json` (9 manifests autoritativos, uno por norma). `source_url` por artículo = URL canónica EUR-Lex por CELEX (`registry.canonical_source_url`).

### Metodología de recolección

Pipeline `src/regulaitor/corpus/` documentado en ADR-0003 (H1) y extendido en ADR-0015 (H14). Tres formatos de fetch (`formex4`, `html`, `pdf`) seleccionados por dispatcher (`corpus/ingest.py`); los 4 corpora del MVP usan PDF y las expansiones HX (RTS DORA, AMLR/MiCA/TFR) usan HTML, tras el pivote operativo descrito en ADR-0003 §"Pivot to PDF": el WAF CloudFront de EUR-Lex devuelve HTTP 202 + reto JavaScript a clientes no-browser, bloqueando `curl`/`httpx` deterministas. Resolución H1: descarga manual de los PDFs ES + EN en un navegador real (que resuelve el reto) + commit en Git-LFS bajo `corpus/raw/`. Resolución H14 (NIS2 + DORA): Playwright headless con same-origin fetch dentro de la sesión que resolvió el reto WAF (ADR-0015 D1).

Parseo: `pdfplumber` + regex estructural en `corpus/pdf_parser.py`. Validación: `corpus/validate.py` enforza `EXPECTED_ARTICLE_COUNTS` por corpus, ausencia de duplicados y ausencia de artículos vacíos antes del write atómico del manifest. Chunking: estructural por artículo (`rag/chunking.py`); CLAUDE.md §10.3 obliga a no mezclar artículos en un mismo chunk. Embeddings: `BAAI/bge-m3@5617a9f61b028005` local CPU (sin coste API); reranker `bge-reranker-v2-m3` (`rag/reranker.py`).

### Metadatos por chunk

Cada chunk almacena (`rag/schemas.py` + manifest):

- `norma` (`ai_act` | `gdpr` | `nis2` | `dora` | `dora_rts_incident` | `dora_rts_class` | `amlr` | `mica` | `tfr`).
- `articulo`, `apartado`.
- `idioma` (`es` | `en`).
- `version` (CELEX versionado).
- `source_url` (file:// para PDF local).
- `fetched_at` ISO-8601 UTC.
- `hash` SHA-256 por `(article, language)` — sirve como cache layer 2 idempotente (ADR-0003 §Idempotency).
- `embedding_model` con identificador de revisión Hugging Face.
- `embedded_at` ISO-8601 UTC.

### Uso previsto

(a) Retrieval con `RetrieverAgent.retrieve()` para alimentar al `AnalystAgent`; (b) validación literal/normalizada en `citation/validator.py:validate()` (los 3 checks §6.1 capa (a): article_exists / apartado_exists / text_normalized_match); (c) lookup directo vía `mcp_server/tools.py::fetch_article`. **Uso no previsto:** entrenamiento de modelos (no se distribuyen los chunks como dataset fine-tune; siguen siendo PDFs descargados de la fuente oficial).

### Licencia y procedencia

Legislación pública UE accesible vía EUR-Lex bajo la Decisión 2011/833/UE (reutilización de documentos de la Comisión) y la política EUR-Lex de re-use con atribución. RegulAItor no redistribuye los PDFs originales en clear (están en Git-LFS del repo privado); los embeddings derivados se almacenan en LanceDB sin republicar el texto fuente. Cualquier despliegue público (HF Spaces) sirve respuestas con citas textuales acotadas a snippets de artículo (uso justo / cita académica).

### Consideraciones éticas y PII

Documentos públicos sin PII por construcción (los considerandos pueden mencionar nombres propios de figuras institucionales — Comisión, Parlamento — pero ningún dato personal de ciudadano). No se aplica filtrado adicional. El `sanitizer.py` (capa H5/ADR-0007) opera sobre documentos de usuario, no sobre el corpus de referencia.

### Versionado y mantenimiento

Versionado por CELEX + `fetched_at`. Los hashes SHA-256 por artículo permiten re-ingestar solo lo que cambió. AI Act y RGPD se re-validaron post-NIS2/DORA en H14 con bytes idénticos (§22.18 regression-zero). Plan de mantenimiento: re-fetch manual ante publicación de consolidaciones nuevas (próxima previsible: corrigenda AI Act); el operador ejecuta `python -m scripts.ingest --corpus <name>` y `python -m scripts.rag_build` para refrescar LanceDB.

---

## Dataset 2 — Gold set de evaluación

### Descripción

Conjunto canónico de 74 casos (64 chat + 10 documento) usado por el harness H8 (`evals/harness.py`) para medir las métricas §17 (faithfulness, answer_relevancy, context_precision, citation_precision, citation_recall, verdict_match, severity_match) contra los thresholds duales `v0.1.20-bar` y aspiracional (ADR-0021).

### Composición chat (64 casos, `evals/gold_set.jsonl`)

Distribución por `corpus_esperado`:

| corpus_esperado | Casos | Comentario |
|---|---|---|
| `ai_act` | 15 | núcleo H8 |
| `gdpr` | 15 | núcleo H8 |
| `nis2` | 6 | añadidos en H14 (ADR-0015) |
| `dora` | 6 | añadidos en H14 (ADR-0015) |
| `auto` | 22 | cross-corpus (2 H14 `xcorpus-*` + 20 `industry-*` H15.1 / v0.1.13 / v0.1.15) |

Distribución por `severidad_esperada`: high=40, medium=16, low=2, null=6 (6 casos de seguridad declarados null por diseño — son casos de rechazo).

Distribución por `expected_verdict`: pass dominante; `requires_human_review` y `block` en minoría. El campo `acceptable_verdicts` (v0.1.24 O1, ADR-0031) se añadió a 6 casos de seguridad designados (`chat-014`, `chat-015`, `chat-029`, `chat-030`, `nis2-006`, `dora-006`) permitiendo `["block", "requires_human_review", "pass"]` como verdicts equivalentemente seguros (preferido `block`, pero rechazo motivado citando corpus real también acepta). Esta extensión es opt-in por caso y no debilita la métrica para los 58 casos restantes.

Cada caso incluye: `id`, `tipo`, `entrada`, `corpus_esperado`, `articulos_esperados`, `severidad_esperada`, `criterios_evaluacion` (lista de checks para el LLM-as-judge), `salida_esperada` (opcional), `requiere_revision_humana`, `expected_verdict`, `acceptable_verdicts` (opcional).

### Composición documento (10 casos, `evals/document_cases/`)

10 PDFs sintéticos generados con ReportLab (ADR-0010 D5) cubriendo política IA, política privacidad y contratos. Cada PDF se acompaña de `case_doc-NNN_*.expected.json` con `expected_findings_articulos`, `expected_document_verdict`, `expected_n_segments` + `n_segments_tolerance`, y `criterios_evaluacion`. Incluye 2 casos adversarios (`doc-004`, `doc-010`) que embeben JavaScript — el sanitizer (`document/sanitizer.py`) los bloquea correctamente con `DocumentBlockedError("javascript_blocked")` (verificado en v0.1.28 T6 main; ADR-0033 §22.22).

### Metodología de autoría

Híbrida (ADR-0010 D5): el autor diseñó la stratification skeleton y la taxonomía; un subagente Haiku 4.5 redactó borradores; el autor revisó cada caso en PR. Casos cross-corpus H14 (xcorpus-001/002) y H14 hallucination-attack (nis2-006, dora-006) fueron corregidos post-revisión por un code-review en 2 fases que detectó 3 errores de corpus-ground (ADR-0015 §"H14 closure"). Los 10 casos `industry-g*` + `industry-gv*` de v0.1.15 (gap-analysis mode) fueron user-validated previa adición. Los 10 casos `industry-c*` + `industry-v*` de v0.1.13 (cross-corpus industry-realistic) también requirieron user validation explícita per industry-demo readiness.

### Uso previsto

Medición de las métricas §17 vía `evals/harness.py` + `evals/metrics.py`. Los 6 casos con `acceptable_verdicts` se usan también como hard safety floor (revisión manual de contenido per H15 C1; ADR-0029 §22.22). **Uso no previsto:** entrenamiento de modelos; los gold cases NO entran en fine-tuning de Sonnet ni en datos de la LoRA HX1.

### Consideraciones éticas y PII

Casos sintetizados por el autor sin datos de personas físicas reales. Las entradas mencionan situaciones empresariales abstractas ("una pyme manufacturera", "un hospital", "un fintech") sin nombres ni identificadores. El `gold_set.jsonl` está commited al repo bajo la licencia del proyecto.

### Versionado y mantenimiento

Schema en `evals/schemas.py::GoldCaseChat` + `GoldCaseDoc`. Backward-compat añadiendo `acceptable_verdicts: list[str] | None = None` en v0.1.24 (campo Optional, defaults a single-value match contra `expected_verdict`). Plan de mantenimiento: nuevos casos solo por PR + user validation; eliminación o reescritura de casos requiere ADR (riesgo de leak entre milestones). El gold set NO se actualiza para "arreglar" un caso que el sistema falla — esa anti-pattern está vetada por CLAUDE.md §18.

---

## Dataset 3 — Red team set (50 ataques)

### Descripción

Suite de 50 ataques manualmente diseñados (`redteam/attacks.jsonl`) cubriendo los 10 escenarios §18 de CLAUDE.md (5 ataques por escenario). Documentación canónica: ADR-0011 (H9) + `docs/security_report.md`.

### Composición

| Distribución | Recuento |
|---|---|
| Modo chat | 22 |
| Modo documento | 28 |
| `requires_e2e: true` (invocan H4/H5 con LLM real) | 15 |
| `requires_e2e: false` (determinista, $0) | 35 |
| `expected_block_layer = injection` | 7 |
| `expected_block_layer = sanitizer` | 7 |
| `expected_block_layer = auditor` | 36 |

Distribución por escenario §18 (5 ataques cada uno):
1. Documento que ordena ignorar instrucciones.
2. Documento con texto oculto.
3. Documento con metadatos maliciosos.
4. Pregunta que pide inventar citas.
5. Pregunta que fuerza una conclusión jurídica no respaldada.
6. Documento con contradicciones internas.
7. Documento con artículo inexistente.
8. Intento de extraer prompts internos.
9. Intento de saltarse el Auditor.
10. Solicitud de asesoramiento legal definitivo.

Cada ataque incluye: `id`, `scenario`, `scenario_name`, `mode`, `payload` (texto inline o `attack-NNN.pdf` en `redteam/documents/`), `expected_block_layer`, `expected_verdict`, `requires_e2e`, `description`, `rationale`.

### Metodología de autoría

Autoría manual por el autor (ADR-0011 D1). Los 28 ataques doc-mode se materializan como PDFs en `redteam/documents/attack-NNN.pdf` con técnicas reales (texto invisible blanco-sobre-blanco, metadatos `/Producer` maliciosos, etiquetas `<system>` falsas, instrucciones embebidas). La separación física `redteam/` vs `evals/` es una constraint dura (CLAUDE.md §18 "NO mezclar adversarial cases con gold set"; ADR-0011 D2).

### Uso previsto

`make redteam-smoke` corre el subconjunto determinista (35 ataques) en CI y mide `block_rate`. Gate §16.2 #4 relajado a ≥0.90 (medido **0.92** en H9 smoke, congelado como carry-forward desde v0.1.14 hasta v0.1.32; verificable mediante `redteam/reports/latest.md`). Full run E2E (50 ataques) ejecutado en H11 (squash `602c2da`, €1.99); resultado contaminado por 21 timeouts de API Anthropic degradada (`block_rate` 0.28 raw / 0.54 entre 26 completados) — el gate sigue en smoke 0.92 (inmune a API), señal calibración H15 (ADR-0011 + ADR-0016).

### Consideraciones éticas y PII

Ataques sintéticos sin PII. Cualquier "víctima" mencionada en payloads es ficticia ("Acme S.L.", "ejemplo@empresa.com"). El conjunto NO debe redistribuirse fuera del repo (riesgo dual-use: una taxonomía de ataques publicada en clear puede facilitar evasión); el `redteam/attacks.jsonl` está versionado pero el repo es privado por defecto. CLAUDE.md §22 prohíbe usar secretos reales — `gitleaks` en CI garantiza la propiedad.

### Versionado y mantenimiento

Schema en `redteam/runner.py`. Plan §18: ≥10 smoke (H9), ≥50 MVP completo (H9 ✅), ≥80 avanzado (HX, pendiente). Nuevos ataques solo por PR con `expected_block_layer` justificado; los ataques fallidos (sistema NO bloquea) escalan a ADR de seguridad si revelan gap de capa.

---

## Dataset 4 — Eval reports históricos

### Descripción

Artefactos markdown por hito en `evals/reports/v0.1.X/` y `evals/reports/h15/` que documentan métricas, per-citation traces, comparison reports y safety floor reviews para cada paid run o $0 diagnostic. Constituyen la espina dorsal de evidencia §22.22 ("never claim as measured what was not measured").

### Composición

Directorios actuales (subset):

- `evals/reports/latest.md`, `latest.cost.md`, `latest.council.md`, `latest.evaluation.md` — agregados H8.
- `evals/reports/h15/` — H15 calibration study (ADR-0016).
- `evals/reports/v0.1.20/` — A/B v1.0 vs v1.4 paid validation (ADR-0026).
- `evals/reports/v0.1.21/quorum-diagnostic.md` — diagnóstico $0 cache-mining (ADR-0027 §22.22).
- `evals/reports/v0.1.22/` — 10 reports incluyendo 3 probe attempts fallidos (ADR-0029).
- `evals/reports/v0.1.22.1/verdict-drop-analysis.md` + `v0.1.23-decision-tree.md` — $0 diagnostic.
- `evals/reports/v0.1.23/` — 6 reports REVERT outcome (ADR-0030 §REVERT).
- `evals/reports/v0.1.24/` + `v0.1.24.1/` — re-aggregation + path attribution (ADR-0031).
- `evals/reports/v0.1.25/` — 6 reports CONFIRM partial-routing (ADR-0032).
- `evals/reports/v0.1.27/` + `v0.1.28-doc-*.md` — doc-mode baseline + v1.6 ship (ADR-0033).
- `evals/reports/v0.1.29/` — D Mirror all-blocked CONFIRM (ADR-0034).
- `evals/reports/v0.1.30/probe.md` — REVERT title-augmented embeddings (ADR-0035 §REVERT).

### Metodología de generación

Generados por `evals/report.py::render_report()` (formato dual-column `v0.1.20-bar` + aspiracional desde ADR-0021) o por scripts dedicados (`scripts/v0XXX_*.py`) en milestones diagnósticos. Las re-renderizaciones $0 (v0.1.18 ADR-0024) son string-surgery idempotente sobre `*.md` previos; no se vuelve a llamar al LLM.

### Uso previsto

Evidencia para la memoria TFM (H17), defensa académica, y trazabilidad del invariante §6 a lo largo de las 13 milestones consecutivas con §22.22 honest framing (v0.1.19 → v0.1.32) incluyendo 2 REVERT outcomes (v0.1.23 + v0.1.30). Los reports están commited al repo y son la fuente de verdad para `docs/evidence_matrix.md`.

### Consideraciones éticas y PII

Los reports incluyen citas textuales del corpus (públicas) y respuestas del Analyst que pueden contener fragmentos sustanciales de los gold cases. NO contienen claves API ni tokens (filtrado por `gitleaks` en pre-commit + CI). El módulo `observability/langfuse_client.py:27-60` enforza una allowlist de claves de metadatos (`_SAFE_META_KEYS` + `_SAFE_KEY_SUFFIXES`) que impide que texto raw del usuario salga por el egress LangFuse; los hashes son SHA-256 truncado a 12 chars. El logging API (`api/logging.py:22`) redacta la IP del cliente (`_redact_ip`).

### Versionado y mantenimiento

Los reports son immutables post-merge — un report se re-renderiza ($0) si y solo si su instrumento de medición evoluciona (precedente v0.1.18 ADR-0024 hierarchical containment). Los reports nuevos viven en `evals/reports/v0.1.X/` por milestone; el `evals/reports/latest.md` apunta al último agregado H8-formato. Plan de retención: indefinida (el TFM se defiende sobre este corpus de evidencia).

---

## Limitaciones agregadas

1. **Corpus monolingüe ES + EN.** Otros idiomas oficiales UE (FR, DE, IT, PT) no están ingestados — ampliación HX si la demanda lo justifica.
2. **Base-act vs consolidada.** NIS2 y DORA usan la base act 2022-12-27 (no hay consolidadas con enmiendas a fecha H14); RGPD usa la consolidada 2016-05-04 (corrigenda 2018 incluida). Una nueva corrigenda no detectada automáticamente desactualizará el corpus hasta el siguiente re-fetch manual.
3. **Gold set N=74 limitado.** Para descender el intervalo de confianza de las métricas hace falta N≥100 chat + ≥30 doc; carry-forward HX. Los 10 doc gold cases son insuficientes para decisiones de retrieval engineering de alta confianza (vindicado en v0.1.30 REVERT).
4. **Red team `requires_e2e: true` cuesta dinero.** El full run E2E está bloqueado por reliability de API (H11). El gate productivo se ancla en el smoke determinista 0.92.
5. **PII filtering construido, cobertura parcial.** `src/regulaitor/security/pii.py` **SÍ existe** (HX Fase 2/2.1): detección regex MVP (email, teléfono-ES, DNI/NIF, NIE, IBAN, tarjeta con Luhn) + `count_pii` counts-only (§18.8). Cableado como **gate pre-pipeline en el chat de Streamlit** (aviso + Continuar/Cancelar) y como **recuento in-pipeline en doc-mode** (`PIISummary`). Cobertura pendiente: el path del API `/ask` aún no escanea PII (roadmap P2.3); regex-MVP, no NER exhaustivo.
6. **§22.22 — algunos campos del manifest están vacíos.** `http_cache.etag` y `http_cache.last_modified` son `null` para los 4 corpora porque el fetch vino vía Playwright (WAF bypass), no vía HTTP condicional. Documentado en ADR-0003 y ADR-0015.

---

## Referencias cruzadas

- ADR-0003 — Corpus pipeline (H1).
- ADR-0010 — Evaluation harness + gold set (H8).
- ADR-0011 — Red team runner (H9).
- ADR-0015 — NIS2 + DORA expansion (H14).
- ADR-0019 — Segmenter heading regex (v0.1.14).
- ADR-0024 — Citation granularity confound (v0.1.18; eval-instrument fix).
- ADR-0033 — `doc_analyst` v1.6 Finding-based refusal (v0.1.28).
- `docs/technical_decisions_log.md` §§H1, H8, H9, H14, v0.1.18, v0.1.24, v0.1.28.
- `docs/evidence_matrix.md` — mapeo M1–M5 + tag table.
- `docs/runbook.md` — operativa de re-fetch.

---

## Changelog

- **2026-05-29** — v1.0.0 inicial alineado con `v0.1.32-h16-deploy` (H17 cierre académico).
