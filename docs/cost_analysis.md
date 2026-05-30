# RegulAItor — Análisis de costes acumulado (H8 → v0.1.32)

**Última actualización:** 2026-05-29 (post v0.1.32 H16 deploy)
**Snapshot de precios:** `src/regulaitor/models/config.py:PRICING_SNAPSHOT_DATE = "2026-05-16"`
**Conversión USD→EUR:** 0.93 (snapshot del mismo día)
**Cobertura:** 13 hitos de pago + H16 infra ($0) + H17 cierre académico ($0 esperado)
**Disciplina §22.22:** cifras presentadas distinguen explícitamente *medido per-run*, *list-price analítico*, y *aproximación honesta*. No se infla nada.

> **Lectura obligada antes de citar cualquier número.** Este documento integra dos regímenes de medición que conviven en el repo:
>
> 1. **H8 → H13: cost analítico** sobre precio de lista y perfil de tokens fijo. El harness reusado de H8 imprimía cost hardcodeado por modelo de producción (ver §H12 más abajo y ADR-0013). Las cifras de €/consulta para esa franja son list-price, NO medidas per-run.
> 2. **H15 → v0.1.32: cost medido per-run** vía acumulador process-level añadido en `src/regulaitor/models/router.py` (uno de los dos backend seams deliberados de H15 per ADR-0016; el comentario en `router.py:140` lo etiqueta como "H15 / ADR 0016"). A partir de H15 cada milestone reporta el spend REAL agregado de las llamadas Anthropic durante el paid run, no estimación.

## 1. Ledger acumulado por hito (paid runs)

Tabla canónica de gasto medido (o aproximado cuando se especifica). Conversión a USD usa 1 EUR ≈ 1.08 USD (snapshot 2026-05-16 inverso a 0.93).

| Hito | Fecha cierre | Spend (€) | ~USD | Régimen | Cohort / propósito |
|---|---|---|---|---|---|
| H8 (eval baseline) | 2026-05-12 | 2.51 | 2.71 | analítico+real mixto | 30 chat + 10 doc gold set; Sonnet 4.6 + Haiku 4.5 juez. Cost de Sonnet hardcoded en harness; juez sí medido. |
| H11 (red team full) | 2026-05-16 | 1.99 | 2.15 | real (Anthropic) | 50 ataques completos sobre runner Anthropic; 21 timeouts API degradada (decisions §H11). |
| H12 (router A/B contaminado) | 2026-05-17 | ~$5 (≈ €4.65) | ~$5 | parcial (degradado) | 3 arms (Sonnet/GPT-4o/Llama-Groq); Llama 19/40 errored (ADR-0013 I-2 empírico). |
| H13 (Council 3-judge) | 2026-05-18 | ~1.2–1.5 | ~1.3–1.6 | aproximación | T14 forced-Council 30 casos; 9 skipped por flakiness; coste NOT per-run-measured (gap H12→H15). |
| H15 (calibración v1.0→v1.2 A/B) | 2026-05-19 | 5.05 | 5.46 | **medido** (acumulador) | 30 chat candidate + holdout 14 cross-corpus; primera milestone con router acumulador. |
| H15.1 (auto cross-corpus paid) | 2026-05-20 | 3.92 | 4.23 | medido | Probe 0.16 + cand-1 1.48 + cand-2 1.53 + holdout 0.75; ahorro €1.85 vs H15 (no re-baseline). |
| H15.2 (eval rede-design CRASH) | 2026-05-20 | 2.43 | 2.62 | medido | Cand-1 probe €0.19 persisted; full crashed mid-flight en case ~24/30 por `credit_balance_too_low`; €2.24 sunk sin disk artifact. |
| v0.1.20 (v1.0 vs v1.4 A/B) | 2026-05-24 | 7.83 | 8.45 | medido | 64-chat ARM A v1.0 + ARM B v1.4; per-case mean €0.0626 (ARM A) / €0.0595 (ARM B) per `evals/reports/v0.1.20/comparison.md`. |
| v0.1.22 (cumulative CONFIRM) | 2026-05-25 | 1.91 | 2.06 | medido | Probe €0.32 + main €1.30 + safety adhoc €0.29; bajo €3.78 high-extrapolation (16% del forecast). |
| v0.1.22.1 (verdict diagnostic) | 2026-05-25 | 0 | 0 | n/a | $0 cache-mining, sin paid. |
| v0.1.23 (Auditor lenient REVERT) | 2026-05-26 | 1.76 | 1.89 | medido | T4 probe €0.31 + T5 main €1.45; on-forecast -7% vs €1.90 expected; REVERT documentado en ADR-0030 §REVERT. |
| v0.1.24 (gold alignment + decomposition) | 2026-05-26 | 0 | 0 | n/a | $0 re-aggregation sobre cache. |
| v0.1.24.1 (per-Finding path diagnostic) | 2026-05-26 | 0 | 0 | n/a | $0 cross-version comparison. |
| v0.1.25 (partial-routing CONFIRM) | 2026-05-26 | 1.66 | 1.79 | medido | T4 probe €0.30 + T5 main €1.36; verdict_match +0.33 (LARGEST en lineage); 7/7 v0.1.20-bar PASS. |
| v0.1.26 (H16 deploy-prep) | 2026-05-27 | 0 | 0 | n/a | Infra Docker + truststore + LANCEDB_PATH + CORS + cov-gate 85%; $0. |
| v0.1.27 (doc-mode baseline) | 2026-05-27 | 0.16 | 0.17 | medido | N=3 probe doc; per-doc €0.053; NEW finding §6 placeholder bug (v1.0 doc_analyst). Ver `evals/reports/v0.1.27/doc-probe.md`. |
| v0.1.28 (doc fix triple-iteration) | 2026-05-27 | 1.55 | 1.67 | medido | 5 paid runs: probe €0.28 + α+β REVERTED €0.28 + T4-bis €0.16 + T4-bis-v2 REVERTED €0.29 + main €0.55. |
| v0.1.29 (all-blocked CONFIRM) | 2026-05-27 | 1.89 | 2.04 | medido | T5 probe-1 €0.14 sunk (LANCEDB_PATH bug) + probe-2 €0.31 + main €1.44; verdict_match +0.08 on H10 main 25-case. |
| v0.1.30 (title-augmented REVERT) | 2026-05-28 | 0.65 | 0.70 | medido | T5 probe; T7 main SKIPPED per cost-discipline (~€1.40 ahorrado). |
| v0.1.32 (H16 HF Spaces deploy) | 2026-05-28 | 0 | 0 | n/a | Infra-only; LFS + Lance baked-in; cold-start ~5 min. |
| **Total acumulado** | | **~€39.3** | **~$42.4** | mixed | 13 paid milestones + 5 $0 + 2 infra. Suma del ledger arriba (H12 = €4.65 midpoint de "~$5"; H13 = €1.35 midpoint de "~€1.2-1.5"; resto medido). |

Fuente cruda: CLAUDE.md §27 (cada hito documenta su spend); `evals/reports/<milestone>/` para detalles por probe/main; `docs/technical_decisions_log.md` para los aproximados pre-H15.

## 2. Per-query y per-doc reales (post-acumulador H15)

### 2.1 Chat (consulta normativa)

| Versión / cohort | €/chat (medido) | Fuente | Comentario |
|---|---|---|---|
| H8 frozen (Sonnet 4.6) | 0.0195 (list-price) | `config.PRICING` × 3000/800 tokens | Analítico, no medido. |
| v0.1.20 ARM A (v1.0) | 0.0626 | `evals/reports/v0.1.20/comparison.md` §5 | Per-case mean sobre 64 cases medido. |
| v0.1.20 ARM B (v1.4) | 0.0595 | misma fuente | -€0.003 vs v1.0. |
| v0.1.22 prod (Tier 1 + Capa A+B+C) | 0.054 | decisions §v0.1.22 §22.22 #7 | +€0.013 sobre soft bar €0.05; overhead Capa C retry (ADR-0027 D4). |
| v0.1.25 prod (Design H D2) | 0.054 | decisions §v0.1.25 §22.22 #3 | Mismo magnitude que v0.1.22; D2 no añade coste. |

**Bar §17 #8 = €0.05 con modelo abierto.** Cumplimiento parcial: el bar aplica al *open-model deployment* (Llama-Groq vía router cost-mode); con Anthropic Sonnet + Capa C el coste real es €0.054 (~+8% sobre bar). Migración cross-vendor del juez Haiku → GPT-4o-mini o Llama vía Groq es trabajo HX post-TFM (carry de ADR-0010 D1 + ADR-0021).

### 2.2 Doc analysis (10p)

| Versión / cohort | €/doc (medido) | Fuente | Comentario |
|---|---|---|---|
| H8 frozen (Sonnet 4.6) | 0.1953 (list-price) | `config.PRICING` × 30000/8000 tokens | Analítico. |
| v0.1.27 baseline (v1.0 doc_analyst) | 0.053 | `evals/reports/v0.1.27/doc-probe.md` | N=3; bajo el bar §17 #9 = €0.50. |
| v0.1.28 prod (v1.6 doc_analyst) | 0.078 | decisions §v0.1.28 §22.22 medición | +47% Capa C retry overhead; sigue bajo bar €0.50. |

**Bar §17 #9 = €0.50 por 10 páginas.** Cumplimiento HOLGADO: doc-mode v1.6 sale a €0.078 (~15% del bar). El margen permite añadir Capa C overhead, judge cost del Council, y aún sigue 5x por debajo del techo.

## 3. Régimen de medición — qué se mide y qué no

El acumulador process-level en `src/regulaitor/models/router.py` (uno de los dos backend seams deliberados de H15 — el otro es `REGULAITOR_ANALYST_PROMPT_VERSION` en `agents/analyst.py`; ambos documentados en ADR-0016) intercepta cada llamada que retorna `CompletionResult.cost_eur` y la suma a un contador process-scoped. El reporte de cada paid milestone publica ese acumulado al cierre.

**Lo que el acumulador SÍ mide:** input + output tokens × `config.PRICING[model_id]` × USD→EUR para todas las llamadas Anthropic (Analyst + Auditor cuando usa LLM-judge interno + Council 3-judge cuando binding ON). El juez Haiku 4.5 del eval también queda agregado porque va vía el mismo router.

**Lo que el acumulador NO captura (carry-forward para H17):**

- **Cost OpenAI/Groq cuando se ejecuta en arms separados** (caso H12): cada arm tiene su propio acumulador process-level; comparación cross-arm requiere ejecutar `scripts/v0120_compare.py` que NO agrega aún. v0.1.20 reporte cita per-arm correctamente.
- **Cost embebido en infra deploy** (HF Spaces compute, Render/Fly hosting): trackeado aparte como gasto operacional fijo, NO per-query.
- **Cost de las llamadas locales BGE-M3 + reranker** (`bge-reranker-v2-m3`): correr en CPU local en H16 deploy = $0 marginal (HuggingFace model cards descargados una vez vía HF_HUB_OFFLINE en deploy).
- **Cost del juez Haiku 4.5 del eval cuando se cachea** (`evals/cache/` hash-keyed; cache hits no consumen API).

**Gap honesto carry desde ADR-0029 §22.22 #10:** harness $8.46 vs Anthropic console $11.95 en v0.1.22 = gap ~$3.50 atribuido a (a) juez Haiku layer no agregado en harness al 100%, (b) varianza EUR/USD intra-sesión, (c) posibles dev/test calls fuera del runner. v0.1.29 LANCEDB_PATH config bug también consumió €0.14 que SÍ están en el acumulador pero NO produjeron evidencia evaluable (probe 1 sunk).

## 4. Curvas de escala — proyección a producción

Asumiendo el régimen actual (Anthropic Sonnet 4.6 + Capa C overhead + Council binding ON + Haiku juez):

| Volumen mensual | Chat (€/mes) | Doc 10p (€/mes) | Mixed 80/20 (€/mes) | ~USD/mes |
|---|---|---|---|---|
| 1.000 consultas | 54 | 78 | 59 | ~64 |
| 10.000 consultas | 540 | 780 | 588 | ~635 |
| 100.000 consultas | 5.400 | 7.800 | 5.880 | ~6.350 |
| 1.000.000 consultas | 54.000 | 78.000 | 58.800 | ~63.500 |

**Mixed 80/20** = perfil PYME esperado per CLAUDE.md §4 (80% chat consultas normativas + 20% doc análisis).

**Linearidad:** la API Anthropic facture per-token sin discount tiers públicos hasta enterprise volume (>$10K/mes); la proyección es lineal hasta ~100K consultas/mes. Más allá habría que renegociar pricing o migrar parcialmente a open-models.

**Sensibilidad al modelo (con cross-vendor migration HX):**

- Juez Haiku → GPT-4o-mini reduciría coste juez ~3-5x (Haiku $1/$5 per M vs GPT-4o-mini $0.15/$0.60 per M; per `config.PRICING`). Cost por consulta caería de ~€0.054 a ~€0.04. Carry de ADR-0010 D1 resuelto como "stays Haiku in v0.1.16; migration HX post-TFM" (ADR-0021).
- Analyst Sonnet → Llama-Groq reduciría Analyst-side ~5-9x (Llama $0.59/$0.79 per M vs Sonnet $3/$15 per M). PERO H12 evidenció que la calidad NO depende del modelo (verdict_match 0.17–0.28 uniforme cross-vendor); migrar Analyst SIN antes calibrar retriever (H15) tira la garantía §6. v0.1.25 D2 cierra el partial-routing en el Auditor; cross-vendor Analyst sigue HX.

## 5. Hosting — cost fijo operacional

| Plataforma | Cost mensual | Estado | Comentario |
|---|---|---|---|
| HF Spaces (CPU básico, Streamlit SDK) | $0 | **VIVO** v0.1.32 | Demo TFM público; cold-start ~5 min con LFS baked-in (1569 Lance rows + BGE-M3 + reranker). Sin GPU. |
| Render Starter (512MB) | ~$7/mes | preparado | Docker compose runbook en `docs/H16_DEPLOY.md`; CORS configurable vía `REGULAITOR_API_CORS_ORIGINS`. |
| Fly.io shared-cpu-1x | ~$5-15/mes | preparado | Mismo Dockerfile multi-stage; LANCEDB_PATH env mount. |
| Render Pro + GPU (doc-mode escala) | ~$50-200/mes | **pendiente** | Necesario para doc-mode N>50/día por embedding+rerank latency; HX post-deploy según traffic real. |

HF Spaces free tier es suficiente para demostración TFM (single-user, on-demand). Para producción real una PYME pagaría hosting fijo (~€7-20/mes Render o Fly.io) + API consumption variable (tabla §4).

## 6. Lecciones de coste burned-in (origen empírico)

1. **Discipline de probe size N=5 mínimo** (post v0.1.8 + `feedback_cost_estimation_discipline.md`): después del H15.2 crash (€2.43 lost con 0 artifact persisted) se enforzó que ningún paid run autorizado hasta harness checkpoint per-case shipped (commit `91080ec`). Aplicado consistentemente v0.1.20 → v0.1.30.
2. **Cost ranges low/expected/high donde high = expected × 1.5** (mismo feedback file). v0.1.22 ejecutó dentro de €1.91 vs €3.78 high-extrapolation (16% del forecast); v0.1.23 -7% vs €1.90 expected; v0.1.25 on-forecast vs €1.82.
3. **SKIP/PROCEED gate explícito**: spec §D3 en cada paid milestone exige decisión `SKIP-vs-PROCEED` documentada en report propio (ej `evals/reports/v0.1.20/skip-proceed-decision.md`). v0.1.30 T7 main SKIPPED por refutación estructural en probe = €1.40 ahorrado.
4. **Latency NO es cost-relevant directamente, pero saturar Anthropic rate limit sí**: `latency_p95_ms` del eval (~333-572s) es batch-bajo-rate-limit, NO SLA real de producto (CLAUDE.md §17 #7). Pero retries por 429 SÍ inflan cost: Capa C 3-attempt retry per ADR-0027 D4 explica el +€0.013/chat overhead post-v0.1.21.
5. **Cross-vendor budget independiente**: H12 demostró que arms secuenciales compartiendo un único OpenAI credit pool causan fallback Llama-Groq a fallar también cuando GPT-4o-mini agotó. Cualquier re-run multi-vendor necesita budget separado.

## 7. Carry-forwards de cost para H17 (cierre académico)

- **Acumulador process-level → per-call hook**: el acumulador current SUMA cost pero NO desglosa por phase (Analyst vs Auditor vs Council vs juez). H17 podría añadir tagging por `phase` en `CompletionResult` para tabular cost per-component.
- **Cross-vendor migration empírica del juez** (HX post-TFM): migrar Haiku 4.5 → GPT-4o-mini requiere re-cachear el eval pipeline (cache hash-keyed por modelo) — work substancial; deferido per ADR-0021.
- **Cost atribuible por capacidad** (carry de ADR-0029 §22.22 #6): factorial 64-arm A/B sobre v0.1.19→v0.1.25 stack sería ~$300+ USD prohibitivo; H17 documenta cumulative-impact en lugar de per-capability attribution. [pendiente] si TFM tribunal pide breakdown granular.
- **HF Spaces cold-start cost reputacional**: ~5 min cold-start desincentiva trial; HF Spaces "always-on" cuesta ~$9/mes per Space. Decisión a tomar pre-defensa: pagar always-on durante semana de presentación.

## 8. Honestidad final (§22.22)

- **Total acumulado ~€39.3 / ~$42.4** es el cifra defendible para "spend total del TFM en LLM calls" (suma del ledger §1 con H12/H13 midpoints; resto medido per-run). NO incluye coste eléctrico local de BGE-M3 + reranker (despreciable, CPU laptop), NI tiempo humano del autor.
- **Bar §17 #8 (€0.05/chat) está MARGINALMENTE incumplido** en producción Anthropic (€0.054); cumplido en proyección open-model HX.
- **Bar §17 #9 (€0.50/doc 10p) está holgadamente cumplido** (€0.078 = 15% del bar).
- **2 REVERTs en lineage (v0.1.23 €1.76 + v0.1.30 €0.65 = €2.41) son cost honesto de método científico**: comprar la refutación empírica es el coste de la disciplina diagnose-intervene-measure-refute-revert-document; no se contabiliza como "perdido" sino como "evidence purchased for §22.22 narrative". El total cumulative ~€39.3 incluye esos €2.41.
- **H15.2 €2.24 sunk sin artifact** es el caso atípico no recuperable; condujo a la disciplina checkpoint per-case v0.1.8 que previene recurrencia.

## Referencias

- `src/regulaitor/models/config.py` — `PRICING` dict + `PRICING_SNAPSHOT_DATE` + `cost_eur()`.
- `src/regulaitor/models/router.py` — acumulador process-level (H15 seam D2).
- `evals/reports/v0.1.20/comparison.md` — primer reporte con per-case mean medido.
- `evals/reports/<milestone>/probe.md` + `main.md` para cada paid milestone v0.1.22 → v0.1.30.
- `docs/technical_decisions_log.md` §H8 → §v0.1.32 — narrativa per-hito con spend.
- CLAUDE.md §17 #8-9 — bars cost.
- ADR-0010 D1 — judge stays Haiku 4.5; cross-vendor HX.
- ADR-0013 — router multi-LLM + I-2 fallback contamination empírica.
- ADR-0021 — dual-layer §17 thresholds (v0.1.20-bar vs aspirational).
- ADR-0027 D4 — Capa C 3-attempt retry overhead origen.
- ADR-0029 §22.22 #10 — gap harness vs Anthropic console (~$3.50 v0.1.22).
- ADR-0030 §REVERT + ADR-0035 §REVERT — cost honesto de refutación empírica.
- `feedback_cost_estimation_discipline.md` — 4 hard rules post-H15.2 crash.
- `docs/H16_DEPLOY.md` — runbook hosting opciones (HF Spaces / Render / Fly.io).
