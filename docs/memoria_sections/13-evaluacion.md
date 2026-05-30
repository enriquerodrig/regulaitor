# 13. Evaluación: gold set, harness, métricas y umbrales duales

## 13.1 Encuadre y filosofía

La evaluación en RegulAItor no es una métrica ornamental al final del proyecto sino un **artefacto de primera clase del MVP**. El hito H8 (cerrado 2026-05-12, tag `v0.0.9-h8`, ADR-0010) introduce el harness reproducible, el gold set, las métricas custom y el informe markdown como entregables auditables. Desde entonces cada milestone con impacto en calidad ha sido medido contra el harness, y cuatro ADRs posteriores (0021 v0.1.16, 0024 v0.1.18, 0026 v0.1.20, 0029 v0.1.22) han evolucionado el instrumento de medida sin romper la continuidad de caché ni la comparabilidad histórica.

La filosofía heredada del invariante §6 ("no citation, no answer") se traduce en una norma de medida: **el informe muestra los caveats antes que los números**. Los umbrales aspiracionales §17 conviven con un mark intermedio derivado empíricamente; el juez del mismo proveedor que producción se reporta como limitación explícita; el coste se etiqueta como heurística cuando el harness no surface tokens reales (ADR-0010 §Negative). Esa disciplina narrativa, formalizada como **§22.22 honest framing** desde H15, es lo que permite que el linaje de 13 milestones consecutivos (v0.1.19 → v0.1.32) incluya REVERTs públicos (v0.1.23 + v0.1.30) sin perder credibilidad académica.

## 13.2 Gold set

### 13.2.1 Composición actual

El gold set canónico vive en `evals/gold_set.jsonl` (64 casos chat) más `evals/document_cases/*.expected.json` (10 casos documento, manifests pareados con PDFs sintetizados). La estratificación arrancó en H8 con 30 chat + 10 doc (ADR-0010 D3: 15/15 por corpus AI Act/GDPR; 10/3/2 verdict pass/RHR/block) y se ha extendido a lo largo del programa:

| Cohorte | Casos chat | Origen | Hito |
|---|---|---|---|
| `chat-001..030` | 30 | H8 estratificado (AI Act + GDPR) | H8 / ADR-0010 |
| `nis2-001..006` + `dora-001..006` + `xcorpus-001..002` | 14 | H14 ampliación corpus | H14 / ADR-0015 |
| `industry-c1..c5` + `industry-v1..v5` | 10 | v0.1.13 industry cross-corpus (precise + vague-real) | v0.1.13 |
| `industry-g1..g5` + `industry-gv1..gv5` | 10 | v0.1.15 gap-analysis (chat v1.3 prompt) | v0.1.15 / ADR-0020 |
| **Total chat** | **64** | | |
| Doc cases | 10 | H8 + H5 fixtures regenerados | H8 |

El conteo total se valida programáticamente:

```bash
$ grep -c "^{" evals/gold_set.jsonl
64
```

### 13.2.2 Schema y campos críticos

`evals/schemas.py:23-41` define `GoldCaseChat` con Pydantic v2 (`frozen=True`, `extra='forbid'` — un typo en el JSONL falla al cargar, no en runtime). Los campos relevantes:

- `entrada` (str, 1-2000 chars): la consulta en lenguaje natural.
- `corpus_esperado`: `CorpusSelector` (`ai_act` | `gdpr` | `nis2` | `dora` | `auto`).
- `articulos_esperados: list[str]`: lista de citas esperadas (vacía válida para `block` cases tras la enmienda H8 task 10 del ADR-0010).
- `severidad_esperada: Literal["info","low","medium","high"] | None`.
- `criterios_evaluacion: list[str]` (min_length=1): rúbricas que el juez evaluará.
- `expected_verdict: Literal["pass","block","requires_human_review"]`.
- `acceptable_verdicts: list[str] | None = None` — añadido en v0.1.24 (ADR-0031 O1).

El campo `acceptable_verdicts` es la única extensión retroactiva del schema chat desde H8. Lo introduce el ADR-0031 para resolver el patrón H15 C1 backstop: las 6 designated content safety cases (chat-014, chat-015, chat-029, chat-030, nis2-006, dora-006) admiten `["block", "requires_human_review", "pass"]` como veredictos content-safe equivalentes, porque la conducta correcta del sistema bajo el prompt v1.5 de Analyst es emitir un Finding-based refusal cuya rotulación verdict puede legítimamente caer en cualquiera de los tres. El `expected_verdict` canónico permanece como documentación de la preferencia, pero el match es multivaluado cuando el campo está presente.

```bash
$ grep -c "acceptable_verdicts" evals/gold_set.jsonl
6
```

`GoldCaseDoc` (`evals/schemas.py:43-55`) parea cada `pdf_path` con `expected_findings_articulos`, `expected_document_verdict`, `expected_n_segments` (con `n_segments_tolerance` para absorber variabilidad del segmentador). El cierre de la deferral H15 "0 segments" mediante `v0.1.14` (ADR-0019) permitió por primera vez que los 8 fixtures testeables cayeran dentro de tolerancia.

### 13.2.3 Autoría y limitaciones

La autoría sigue el patrón ADR-0010 D5 (hybrid skeleton + subagent draft + revisión humana en PR). Los 14 casos H14 fueron parcialmente corregidos en revisión (commit `26e6997`: nis2-005, dora-003, xcorpus-001 con corpus-ground incorrecto detectado por code-review). El gold set es **sintetizado, no público**; el caveat de cierre del informe lo declara verbatim (ADR-0010 §Negative): "no son benchmark público ni representan distribución real de queries de PYMEs".

## 13.3 Harness

### 13.3.1 Diseño y restricciones

`evals/harness.py` (~381 líneas) consume el chat graph (`orchestration.graph.run`) y el document graph (`orchestration.document_graph.run_document`) como cajas negras. El ADR-0010 D8 fija esta restricción ("no backend modification") por la misma razón que H6 Streamlit y H7 FastAPI: regresión-cero por construcción. Si el Analyst devuelve un schema inesperado, el harness captura `pydantic.ValidationError` y emite un sentinel rather than crashing (ADR-0010 amendment 5).

`load_gold_set` (`evals/harness.py:58-86`) admite filtrado por `case_ids: set[str] | None` — el mecanismo usado para corridas estratificadas como `v0120_main_chat_ids.txt`, `v0122_safety_adhoc_ids.txt` y los probes/main de cada milestone pago.

### 13.3.2 Cache hash-keyed (`evals/cache.py`)

El cache (`evals/cache.py:35-38`) usa `SHA256(model + prompt + temperature)` como clave. La función `cache_call` (`evals/cache.py:60-110`) es transparente: hit → coste cero; miss + `cache_only=False` → llamada live + persistencia; miss + `cache_only=True` → `RuntimeError` (modo `make eval-from-cache`). Estado actual del directorio:

```bash
$ ls evals/cache/ | wc -l
677
```

677 entradas JSON hash-keyed (no 381 — el conteo creció a lo largo del programa con cada arm de A/B pago). Cada entry persiste `request`, `response`, `timestamp`, `tokens_in`, `tokens_out`, `cost_eur`. El cache cubre **únicamente la capa judge** (ADR-0010 D7): los grafos H4/H5 NO son interceptados porque la captura per-call requeriría instrumentar el router (violando D8). Esta limitación se hizo dolorosamente visible en v0.1.18 T3 (ADR-0024 D3): el plan original asumía `make eval-from-cache` para re-render a coste cero; controller-verification descubrió que `--cache-only` cachea solo el juez y el chat graph sigue llamando al API real → pivote a `scripts/rerender_reports.py` puramente regex sobre markdown.

### 13.3.3 Checkpoint per-case (`evals/checkpoint.py`)

El desastre H15.2 T6 (€2.43 perdidos por crash mid-flight con credit exhaustion sin disk artifact persistido) motivó la introducción de `evals/checkpoint.py` en v0.1.8 (squash `91080ec`). El módulo proporciona `append_case` con `fsync` que sobrevive `SystemExit`, OS kill y OOM. Desde v0.1.8 todo paid run wrap-ea la chat-loop body en `try/except` y persiste por caso, no por reporte completo. Esta disciplina se incorporó como **regla dura de cost-estimation** en la memoria persistente (`feedback_cost_estimation_discipline.md`): no se autoriza paid run sin checkpoint shipped.

### 13.3.4 Juez Haiku 4.5 (`evals/judge.py`)

El juez es Anthropic `claude-haiku-4-5-20251001`, mismo vendor que producción Sonnet 4.6 pero distinta clase de modelo (`evals/judge.py:17`). El prompt versionado vive en `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md` (carga eager en `_load_judge_prompt`). El parser tolera fence markdown (`_strip_markdown_fence`, `evals/judge.py:34-48`) porque Haiku ocasionalmente envuelve JSON en ```` ```json ```` a pesar de la instrucción explícita.

El ADR-0010 D1 documenta el caveat de mismo proveedor como limitación de independencia. La deferral original ("migrar en H12") se cerró explícitamente en ADR-0021 D3 (v0.1.16) con un "stay" razonado: continuidad de cache, conocido-quantity behavior, single-API-key, y el coste de invalidar cache para confirmar correlación cross-vendor es prohibitivo bajo presupuesto $0. La migración cross-vendor a GPT-4o-mini o Llama-3.3-70b via Groq queda como HX post-TFM.

## 13.4 Métricas

### 13.4.1 Capa Ragas

`evals/metrics.py::_ragas_metrics_chat` (líneas 155-246) computa cuatro métricas estándar Ragas vía LangChain + HuggingFace embeddings (BGE-M3 mismo modelo que el retriever):

- `faithfulness`: claims de la respuesta apoyados por el contexto recuperado.
- `answer_relevancy`: alineación semántica respuesta vs query.
- `context_precision`: orden y relevancia de chunks recuperados.
- `context_recall`: cobertura del ground truth por el contexto.

Cada métrica corre como `evaluate()` one-row para mantener la composabilidad. `_safe_score` (líneas 232-239) blinda contra NaN que produce Ragas y que llevaría a `pydantic.ValidationError` (ADR-0010 amendment 3). La razón de pasar embeddings BGE-M3 explícitamente: sin override, Ragas cae a OpenAI por defecto, lo que requeriría una segunda API key (rechazado en H8 Q1).

Para doc-mode `_ragas_metrics_doc` (líneas 249-268) restringe a faithfulness — no existe un único retrieval context al nivel documento.

### 13.4.2 Capa custom

Las métricas custom de RegulAItor viven al lado de Ragas en `evals/metrics.py`:

- `compute_citation_metrics(emitted, expected)` (líneas 100-138): precision/recall sobre el conjunto de citas, **bajo el match jerárquico v0.1.18**.
- `extract_emitted_articles_chat/doc`: extracción de citas desde `ChatState.audited_answer` y `DocumentReport`.
- `_extract_severity_chat`: severidad del primer Finding (`None` si no hay findings).
- `compute_chat_metrics` (líneas 276-383): orquestación per-case que produce un `ChatCaseResult` frozen con verdict_match (incluyendo el branch `acceptable_verdicts` v0.1.24 en líneas 359-363), severity_match, citation metrics, Ragas metrics, criteria scores del juez, latency_ms, cost_eur, cache_hit y `per_citation_audits` (trail v0.1.21.1 D2 + corrección v0.1.29 T8 incluyendo `failed_check`).
- `aggregate(chat_results, doc_results)` (líneas 468-531): produce `AggregateMetrics`. Excluye casos con `expected=[]` del denominador de citation metrics (ADR-0010 amendment 10: "citation metrics don't apply when the gold expectation is 'system should refuse to cite'").

### 13.4.3 Citation match jerárquico (ADR-0024)

`evals/metrics.py::_citation_matches` (líneas 43-76) implementa la tabla de verdad introducida en v0.1.18 (ADR-0024 D1):

| expected | emitted | match | rationale |
|---|---|---|---|
| `"X"` | `"X"` | True | exact article-level |
| `"X"` | `"X.Y"` | True | article-expected matches any apartado of X |
| `"X.Y"` | `"X.Y"` | True | exact apartado-level |
| `"X.Y"` | `"X.Z"` | False | different apartados = different obligations |
| `"X.Y"` | `"X"` | False | apartado-expected requires apartado-specific match |
| `"X"` | `"W.Y"` | False | different article |

La asimetría es deliberada: un expected article-level (`chat-028` RGPD art 44 principio general; todos los casos H14/industry) es objetivo grueso que CUALQUIER apartado de ese artículo satisface. Un expected apartado-level (`chat-001` art 6.1 vs 6.2 — definiciones distintas) requiere match exacto. El defensa contra prefix-collision usa trailing-dot startswith (`"106.1".startswith("6.")` → False).

El cambio resolvió un confound de instrumento documentado en ADR-0017 (H15.1 §22.22 design-defect): bajo el match set-intersection previo, el holdout v1.2 puntuaba `citation_recall=0.00` no porque el Analyst fallara, sino porque emitía apartado-level (`"23.4"`) contra expected article-level (`"23"`). El flip retrospectivo al re-renderizar `holdout-v1.2-chat.md` con `scripts/rerender_reports.py`: `precision_mean 0.00 → 0.65` (+0.65) y `recall_mean 0.00 → 0.64` (+0.64). El instrumento, no la calidad, era el problema.

### 13.4.4 Latencia y coste (caveats §17)

`AggregateMetrics` (`evals/schemas.py:125-145`) reporta `chat_latency_p95_ms`, `doc_latency_p95_ms`, `latency_p95_ms` (combined), `cost_per_chat_eur`, `cost_per_doc_eur`, `cost_total_eur`, `cache_hit_rate`. Dos caveats permanentes:

- **Latencia contaminada por batch**: el `latency_p95_ms` (~572 s en H10) **NO es la SLA de producto**. Mide batch de 40 casos secuenciales bajo rate-limit + tenacity backoff. La latencia real de UNA query ≈ 15-60 s. El refactor H17 a LangFuse trace-based es el instrumento limpio (CLAUDE.md §17 #7 amendment).
- **Coste heurístico hasta H11**: ADR-0010 D7 admitió que H4/H5 no surface usage tokens al harness (heurística fija ~3000 in + 800 out por chat). El gap se cerró parcialmente en H15 con el acumulador process-level en `models/router.py`, pero el harness sigue reportando el coste por modelo del juez vía `cache.estimate_cost_eur` (precios `_PRICE_EUR_PER_M_TOKENS`: Sonnet 4.6 €2.76 / €13.80 per 1M; Haiku 4.5 €0.92 / €4.60).

## 13.5 Umbrales duales §17 (ADR-0021)

### 13.5.1 Estructura

`evals/report.py::_THRESHOLDS` (líneas 22-31) es la fuente única de verdad. Estructura 4-tuple `(metric, v0120_bar, aspirational, gated)`:

| Métrica | v0.1.20-bar | Aspiracional §17 | Gated |
|---|---|---|---|
| `faithfulness_mean` | 0.65 | 0.85 | True |
| `answer_relevancy_mean` | 0.55 | 0.85 | True |
| `context_precision_mean` | 0.55 | 0.80 | True |
| `context_recall_mean` | 0.0 | 0.80 | False (info) |
| `citation_precision_mean` | 0.25 | 0.90 | True |
| `citation_recall_mean` | 0.60 | 0.80 | True |
| `verdict_match_rate` | 0.35 | 0.85 | True |
| `severity_match_rate` | 0.35 | 0.80 | True |

El renderer (`evals/report.py:34-78`) genera una tabla de 4 columnas (Métrica | Valor | v0.1.20-bar | Aspiracional) con badges ✅/❌ separados para cada umbral. La sección `Caveats — v0.1.20-bar reading` (líneas 81-113) inserta cuatro bullets verbatim: aspiracional como dirección, derivation de la barra desde H10 + H15 v1.2, juez Haiku stays, latencia contaminada.

### 13.5.2 Derivation de la barra

ADR-0021 D2 documenta el anclaje de cada valor: midway H10 baseline ↔ H15 v1.2 30-case partial measurement (siempre con números reales en `evals/reports/latest.md` y `evals/reports/h15/candidate-v1.2.md`). Por ejemplo `faithfulness_mean=0.65` se posiciona entre el H10 baseline 0.54 y la mejora H15 v1.2 0.75; `citation_recall_mean=0.60` queda por encima del MVP floor §16.2 #5 (0.40, medido 0.44 ✅) y del H10 0.44, midway hacia H15 0.71.

### 13.5.3 Soft mark (ADR-0021 D4)

Las marcas son **soft**: `make eval` retorna exit 0 independientemente del veredicto. No existe `--gate` CLI. El razonamiento heredado de ADR-0010 D4 ("no LLM in CI; $7/PR insostenible") + la disciplina §22.22 (la acceptance ritual es narrativa-driven, no automated). El cierre v0.1.20 documenta en decisions_log "X/8 metrics passed bar; Y/8 below" y las flips de production-default se deciden en ese narrative, no por CI.

## 13.6 Validaciones pagas: el linaje §22.22

### 13.6.1 v0.1.20 — A/B v1.0 vs v1.4 (ADR-0026)

El primer paid validation bundled (€7.83 / ~$8.45 USD de $24.95 budget, ~14 h wall-clock). A/B 1-dim sobre 64 chat × 2 arms = 128 paid Analyst calls. ARM A = `REGULAITOR_ANALYST_PROMPT_VERSION` unset → v1.0; ARM B = env=`v1.4`. Doc-mode SKIPPED por falta de `document_analyst/system.v1.4.md` (D2 design-coherence catch).

**Resultado**: FLIP `v1.0 → v1.4` aprobado para el role `analyst` (`agents/analyst.py` env-unset branch). T7 hard safety floor PASS (redteam-smoke 0.92 bajo env v1.4 + 6/6 designated content cases manualmente content-safe). T6 H10 bar: v1.0 = **0/7** PASS; v1.4 = **6/7** PASS. T6.5 RHR root-cause diagnostic ($0 sobre checkpoints) confirmó wins **mecánicamente reales** (9 real flips vs ~2 regressions). El doc role retuvo v1.0 default en v0.1.20 (sin v1.4 doc prompt) — la ternary role-aware vive hoy en `analyst.py:125` (`default_version = "v1.5" if prompt_role == "analyst" else "v1.6"`, tras los flips posteriores de v0.1.21 a v1.5 chat y de v0.1.28 a v1.6 doc); el regression test asociado al estado actual es `test_document_analyst_role_defaults_to_v1_6_when_env_unset` en `tests/unit/test_analyst_prompt_env_seam.py`.

### 13.6.2 v0.1.22 — cumulative-impact CONDITIONAL CONFIRM (ADR-0029)

Metodología **1-arm fresh vs cached baseline**: ARM v0.1.22-prod sobre H10 30-case + 2 ad-hoc safety bajo estado producción post-v0.1.21.2 (v1.5 chat + Tier 1 Auditor quorum + Capa A+B+C + retrieval defaults + Council ON); baseline = v0.1.20 ARM B extraído $0 vía `scripts/v0122_extract_armb.py`. Coste paid €1.91 / ~$2.06 USD (probe €0.32 + main €1.30 + safety €0.29, ~16% del high €3.78).

Per-metric A/B (7 v0.1.20-bar): **4/7 PASS bar** (faithfulness 0.71 / answer_relevancy 0.74 / context_precision 0.78 / severity_match 0.40); **3/7 improve** (answer_relevancy +0.14, context_precision +0.11, severity_match +0.07); **3/7 regress** (faithfulness -0.05 sobre bar, citation_precision -0.08 bajo bar, citation_recall -0.09 bajo bar); **1/7 flat** (verdict_match 0.30 bajo bar 0.35). Veredicto agregado: pass=10 / RHR=16 / block=4.

**Per-citation 5-bucket mechanism** (T5 diagnostic vía `per_citation_audits` trail D2): Bucket A=0 (Capa A+B+C 100% efectivo contra empty-findings) + Bucket B=4 (deterministic pre-v0.1.21 BLOCK path) + **Bucket C=11/30 = 36.7%** (NEW Tier 1 quorum-triggered RHR — empíricamente resuelve la caveat §22.22 de ADR-0027 que dejaba la UPPER bound en [0..36]) + Bucket D=0 + Bucket E=15.

Decisión: **CONDITIONAL CONFIRM** per spec D4 third path — estado producción retenido (no flip extra; el package ya estaba shipped), capability arc v0.1.19→v0.1.21.2 empíricamente validado como safe-to-retain con performance mixta. ADR-0029 documenta 10 §22.22 disclosures verbatim (incluyendo el bug Capa A schema recursión silenciosa que rompió 100% RHR rate durante ~12h pre-fix).

### 13.6.3 v0.1.25 — partial-routing CONFIRM, el mayor lift (ADR-0032)

Paid €1.66 / ~$1.80 USD. Single src/ file (`agents/auditor.py`): helper `_all_blocked_findings_paraphrase_only` + 1-branch wiring en el partial-Findings sub-route de Layer (c). **Headline: verdict_match +0.33** (v0.1.22 0.40 → v0.1.25 0.73 sobre H10 30-case combined, post-O1 re-aggregation). 9/10 v0.1.22.1 H1-attributed cases flipped RHR → PASS como predicho por v0.1.24.1 Path B 8/10 dominance (vs v0.1.23 Design B 0/10 — la antítesis empírica del REVERT previo). **7/7 v0.1.20-bar PASS**.

### 13.6.4 v0.1.29 — D Mirror all-blocked CONFIRM (ADR-0034)

Paid €1.89. Reuso del mismo helper en el all-blocked sub-route. Verdict_match +0.08 (0.68 → 0.76 en H10 25-case main), on-forecast con la predicción ADR-0034 D4 (+0.033 a +0.10). chat-016 BLOCK → PASS como canonical case + 2 bonus flips. La pareja v0.1.25 (partial) + v0.1.29 (all-blocked) **exhausta la superficie LOW-MEDIUM §6 risk en Layer (c)**.

## 13.7 Reproducibilidad y limitaciones de honestidad

El comando canónico `make eval-from-cache` regenera `evals/reports/latest.md` desde cache sin coste. `make eval` corre full set y consume crédito. El bloque `Reproducibilidad` del informe lo declara verbatim (`evals/report.py:223-230`).

Limitaciones que el TFM debe defender abiertamente, no esconder:

1. Gold set sintetizado, no benchmark público (declarado en caveats final del informe).
2. Juez mismo proveedor que producción — Haiku 4.5 ≠ Sonnet 4.6 en clase de modelo, pero ambos Anthropic; HX post-TFM la migración cross-vendor.
3. Coste pre-H11 heurístico; medición real `cost_per_chat €0.054` actualmente sobre bar €0.05 por €0.004 (overhead Capa C retry per ADR-0027 D4).
4. Soft marks únicamente; CI no rompe; acceptance ritual narrative-driven en decisions_log.
5. Latencia contaminada por batch; SLA real per-query no instrumentada hasta H17 LangFuse refactor.
6. Per-capability cost attribution NO medida (factorial 64-arm cost-prohibitive); cada paid milestone mide el package cumulativo, no las partes (ADR-0029 disclosure #6).

El cumplimiento de estas declaraciones es lo que hace que el linaje 13-consecutive-§22.22 milestones, incluyendo 2 REVERTs documentados (v0.1.23 Auditor lenient quorum + v0.1.30 title-augmented embeddings), funcione como **evidencia metodológica** y no como ruido. La conversión repetida de mediciones (REVERT v0.1.23 → diagnóstico v0.1.24 → atribución v0.1.24.1 → CONFIRM v0.1.25 al layer correcto) es el ciclo científico que el TFM defiende: diagnose → intervene → measure → refute-or-confirm → revert-or-ship → document. La metodología es la contribución.
