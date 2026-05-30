# 11. Observabilidad + análisis de costes

La observabilidad de RegulAItor se construyó en H11 (ADR-0012, squash `8378015`, tag `v0.1.1-h11`) bajo dos restricciones duras heredadas del MVP: (a) §18.8 de `CLAUDE.md` — *"Logs sin datos sensibles"* — el contenido del usuario y las citas no salen del proceso hacia terceros sin pasar por la *allowlist* de redacción (LangFuse Cloud es un tercero; ver `langfuse_client.py:25` que cita literalmente §18.8 / spec §3.3); (b) el *backend* H1–H5 (agentes, *prompts*, esquemas, *router*) es **read-only** desde H6 — la instrumentación es una preocupación de la capa de orquestación, nunca del agente. Sobre esta base se añadió en H15 (ADR-0016) un acumulador de coste real proceso-global que cerró la brecha "coste estimado, no medido" arrastrada desde H12/H13.

## 11.1. Logs estructurados con `case_id`

La trayectoria del *turno* — *chat* o documento — se materializa en una línea JSON por turno emitida por la propia orquestación (`src/regulaitor/orchestration/graph.py:241` `_log_turn`; `src/regulaitor/orchestration/document_graph.py` el equivalente documental). El registro es el **única fuente de verdad** para esta capa: alimenta a la vez el log local y la traza opcional a LangFuse, garantizando coherencia. La función auxiliar `_trace_record` (`graph.py:192-238`) construye el diccionario con campos categóricos, contadores y hashes:

| Campo | Tipo | Origen |
|---|---|---|
| `case_id` | string | propagado desde el caller (API / harness / UI) |
| `query_hash` | `sha256[:12]` | `hash12(state.query)` (`graph.py:196`) |
| `corpus`, `language` | string | parámetros del turno |
| `verdict` | string | `pass` / `requires_human_review` / `block` / `blocked_injection` / `no_answer` |
| `n_findings`, `n_citations`, `n_validated`, `n_blocked` | int | conteos del `AuditedAnswer` (`graph.py:209-212`) |
| `latency_ms_total` | int | `int((time.monotonic() - t0) * 1000)` (`graph.py:268`) |
| `reason_code` | string opcional | prefijo del `audited.reason` antes del primer `:` |
| `errors` | list[string] | categorías de error de pipeline (sin texto del usuario) |
| `council_triggered`, `council_verdict`, `council_diverges`, `n_judges_ok` | mixto | resumen H13 del *Council* |

El campo `query_hash` es la **primitiva de redacción canónica** (`hash12 = sha256[:12]`, `langfuse_client.py:115-117`) — la misma que usa el saneador documental, lo que garantiza correlación de logs sin filtrar texto.

## 11.2. Tracing opcional a LangFuse

LangFuse (`cloud.langfuse.com`, *free tier*; rechazado el *self-hosting* en ADR-0012 D2) se activa con la presencia simultánea de `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_HOST`. Si **cualquiera** falta, el módulo es **no-op total** y ni siquiera importa el SDK (`langfuse_client.py:110-112`): cero *overhead*, cero dependencia transitiva, comportamiento *byte-identical* al MVP.

### 11.2.1. Contrato de redacción aplicado en *runtime*

El egreso a un tercero exige una garantía operativa, no solo documental. El módulo expone una *allowlist* explícita (`langfuse_client.py:27-60`) con dos conjuntos:

- `_SAFE_META_KEYS` — claves categóricas / contadores (`case_id`, `corpus`, `verdict`, `n_findings`, `council_*`...).
- `_SAFE_KEY_SUFFIXES` — sufijos para valores derivados (`_sha256_12`, `_hash`, `_ms`, `_eur`, `_count`, `tokens_in`, `tokens_out`).

`_assert_safe_keys` (`langfuse_client.py:63-80`) se invoca en cada llamada a `TurnTrace.set_root()` y `.span()`; cualquier clave no autorizada produce `ValueError` **antes** de tocar el SDK. La verificación se hizo *end-to-end* contra LangFuse Cloud real: se inyectó un *canary* en la consulta y se confirmó su ausencia en el servidor (solo `query_sha256_12` y la metadata permitida aparecieron) — evidencia que figura en el ADR-0012 §"Positive" como punto de seguridad del Módulo 4.

### 11.2.2. Disciplina de no romper el *pipeline*

El enfoque A del *spec* H11 ("observability never breaks or slows the pipeline") se materializa en tres detalles del cliente:

1. **Cliente cacheado** (`langfuse_client.py:91-107`): un único `Langfuse()` se construye perezosamente con `threading.Lock` y se reutiliza entre turnos. El SDK abre *daemon threads* en construcción; cachearlo evita acumulación ilimitada de *threads*.
2. **`flush()` por turno** (`langfuse_client.py:183`) — drena la cola asíncrona sin bloquear el *request path*; los *threads* permanecen vivos para reutilización. `shutdown()` está registrado con `atexit` para cierre limpio.
3. **Toda excepción tragada con WARNING** (`langfuse_client.py:172-185`): cualquier fallo de LangFuse (inicialización o *flush*) se registra y se descarta — la observabilidad jamás propaga errores al usuario final.

### 11.2.3. Cableado a las dos superficies

Las dos rutas del producto envuelven su flujo principal en `trace_turn(...)`:

- *Chat*: `graph.py:258-287` envuelve `_compiled_graph().invoke(initial)` y emite root + sub-spans con la metadata de `_trace_record`.
- Documental: `document_graph.run_document()` aplica el mismo patrón. Los agentes H3–H5 quedan intactos (rechazado el *per-agent decorator* — violaría la frontera *backend read-only*).

## 11.3. Acumulador de coste real proceso-global (cierra brecha H12/H13)

H12 y H13 dejaron un agujero diagnosticado y registrado honestamente (ADR-0013 §"Negative / accepted"): el *harness* H8 reusado *hardcodea* una heurística de Sonnet — los tres *arms* del A/B H12 imprimieron literalmente el mismo "Total cost: 2.51 €", aunque la realidad era diferente por *arm*. Cada llamada al *router* ya computaba el coste real (`router.py:330-335` para Anthropic; `router.py:434-439` para OpenAI/Groq vía `cost_eur` con `config.PRICING` verificada), pero nada lo agregaba.

H15 (ADR-0016) cerró la brecha sin tocar el contrato del *router*: añadió un acumulador proceso-global (`router.py:147-174`):

```python
_cost_lock = threading.Lock()
_accumulated_cost_eur: float = 0.0

def _record_cost_eur(cost: float) -> None: ...
def reset_cost_accumulator() -> None: ...
def get_accumulated_cost_eur() -> float: ...
```

Cada *branch* de proveedor llama `_record_cost_eur(cost)` tras computar el coste real. El *harness* hace `reset_cost_accumulator()` antes de cada caso y `get_accumulated_cost_eur()` después — **el coste pasa de estimado a medido** sin alterar el valor de retorno de `complete()` (§22.18, byte-identical). El docstring de `reset_cost_accumulator` documenta honestamente la limitación: correcto solo bajo ejecución **secuencial** en un único proceso/hilo; si el *harness* se paraleliza, el patrón global debe sustituirse por contexto por-caso.

## 11.4. Coste por consulta — *chat*

El objetivo §17 #8 es ≤ 0.05 € por consulta con modelo abierto. Las medidas reales acumuladas en el linaje *paid* (todas con Sonnet 4.6 como modelo Analyst, *judge* Haiku 4.5) son:

| Hito | cost_per_chat_eur | Cohorte | Observaciones |
|---|---|---|---|
| v0.1.20 *paid baseline* | 0.0626 (ARM A) / 0.0595 (ARM B) | 64-case A/B (v1.0 vs v1.4) | Fuente: `evals/reports/v0.1.20/comparison.md` §5 |
| v0.1.22 *paid* (`probe.md:21` / `v0.1.22-prod-main.md:21`) | 0.063 (probe) / 0.061 (main) | H10 30-case + 2 seguridad | sobrebar +0.013 (probe) / +0.011 (main) — *overhead* Capa C |
| v0.1.25 *paid prod* (`v0.1.25-prod-main.md:21`) | 0.054 | H10 30-case main | sobrebar +0.004 — mismo *overhead* |

El *overhead* atribuible a la Capa C de Tier 2 (ADR-0027 D4: hasta 3 intentos con *feedback* específico ante `pydantic.ValidationError`) se documentó en ADR-0029 §"Negative" como **trade-off aceptado**: el +€0.004/caso es el precio del contrato de formato duro `minItems=1` sobre `Answer.findings` que la v1.5 garantiza, y la disciplina §22.22 prohíbe llamarlo "bajo el bar" cuando no lo está.

## 11.5. Coste por análisis documental

El objetivo §17 #9 es ≤ 0.50 € por análisis de 10 páginas. Las medidas reales:

| Hito | cost_per_doc_eur | Cohorte | Observaciones |
|---|---|---|---|
| v0.1.27 *paid probe* (`evals/reports/v0.1.27/doc-probe.md:22`) | 0.053 | 3 docs probe v1.0 doc_analyst | dentro de bar; coincide con estimación H5 |
| v0.1.28 *paid prod* (v1.6 doc_analyst, `evals/reports/v0.1.27/v0.1.28-doc-prod-main.md:22`) | 0.078 | 10 docs main | +47% vs baseline — *overhead* Capa C |

El salto +47% en v0.1.28 (ADR-0033) es estructuralmente el mismo mecanismo que el de *chat*: la v1.6 introduce el patrón *Finding-based refusal* en doc-mode, lo que dispara más reintentos de la Capa C cuando el segmento no soporta una `Finding` válida con cita. El coste se mantiene **muy por debajo** del bar 0.50 € — el margen es suficiente para sostener la disciplina §6 sin presión de coste.

## 11.6. Latencia — la advertencia §17 #7

El objetivo §17 #7 es p95 ≤ 12 s en MVP, ≤ 8 s en avanzado. Aquí la honestidad §22.22 obliga a separar dos magnitudes que tienden a confundirse:

- **`latency_p95_ms` del *eval*** (≈ 333–572 s en los *reports*) — es un **artefacto de *batch***: 40 casos secuenciales bajo *rate-limit* de Anthropic + *tenacity backoff* + Capa C reintentos. No es la SLA de producto, y `docs/cost_analysis.md:119` lo deja escrito explícitamente ("batch-bajo-rate-limit, NO SLA real de producto").
- **Latencia real per-query** (medible por *span* en LangFuse o vía `latency_ms_total` del log estructurado) — ≈ 15–60 s en *chat*: Retriever 1–3 s (embedding + reranker locales), Sonnet 10–40 s (la dominante), Auditor en milisegundos (es Python puro determinista, no llama LLM), Council opcional 5–20 s adicionales cuando se dispara.

Está sobre el objetivo 12 s aún en el caso mejor. Las palancas de optimización (*streaming*, `max_tokens` ajustado, Retriever paralelo, *router* a un modelo más rápido) están documentadas como *follow-up* H11/H15 sin haberse aplicado; la decisión consciente es priorizar **garantía §6** sobre latencia. Una medición limpia per-span es el entregable nativo de LangFuse — el *dashboard* lo expone directamente y `docs/runbook.md` describe cómo interpretarlo.

## 11.7. Presupuesto *paid* — *ledger* de 13+ hitos

El presupuesto Anthropic se ha gestionado caso a caso con la disciplina *cost-estimation* de la *memory* `feedback_cost_estimation_discipline.md` (probe min N=5, *cost ranges* low/expected/high=expected×1.5, NEVER recommend proceed si `budget < high`, no *paid run* sin *harness checkpoint per-case*). Los gastos acumulados desde H8 hasta v0.1.30, con sus desviaciones documentadas honestamente:

| Hito | Gasto real | Notas |
|---|---|---|
| H8 | ~€2.51 | *baseline* eval 40 casos |
| H12 | ~€4.65 (≈ $5) | A/B *contaminated* (Llama-Groq 19/40 errored) |
| H13 | ~€1.2–1.5 | Council 30-case (aproximación honesta — gap H12/H13) |
| H15 | ~€5.05 | A/B v1.0→v1.2; primera medición *real* vía acumulador router |
| H15.1 | ~€3.92 | auto-path + purity gate |
| H15.2 | €2.43 | *crash* mid-flight (`credit_balance_too_low` en caso ~24/30) |
| v0.1.20 | €7.83 | A/B v1.0 vs v1.4 64-case |
| v0.1.22 | €1.91 | cumulative-impact 1-arm vs cached |
| v0.1.23 | €1.76 | REVERT empíricamente refutado |
| v0.1.25 | €1.66 | CONFIRM Design H D2 (+0.33 verdict_match) |
| v0.1.27 | €0.16 | doc-mode *baseline* |
| v0.1.28 | €1.55 | doc-mode *triple-iteration* (1 SHIP + 2 REVERT) |
| v0.1.29 | €1.89 | all-blocked routing softening |
| v0.1.30 | €0.65 | corpus-side prepend REVERT |

El *crash* H15.2 (€2.43 evaporados antes de persistir el report del último caso porque el *harness* escribía atómicamente *solo al final*) fue la causa raíz que motivó `evals/checkpoint.py` en v0.1.8 — el *append_case + fsync* sobrevive a `SystemExit` / *OS kill* / OOM y elimina la clase de pérdida total.

## 11.8. Lo no implementado, documentado honestamente

- **langfuse-mcp** se difirió por decisión explícita del *project owner* (ADR-0012 §"Amendment during implementation Q6"): es el ítem de menor valor del hito (conveniencia para el asistente, cero impacto en *gate* o entregable de tesis).
- **OpenTelemetry / Prometheus avanzado** se mantienen en HX5 (alcance opcional §15.3): la trazabilidad real para defensa académica la cubre LangFuse + los logs estructurados; OTel/Prometheus añaden carga operativa sin valor diferencial para el TFM.
- **Atribución per-capability del coste cumulative** está sin medir (ADR-0029 §22.22 #6): un *ablation* factorial 64-arm sería *cost-prohibitive* a cualquier presupuesto razonable; v0.1.22 mide el paquete cumulative, no las partes.
- **Pérdida de coste en el `fallback hop`**: LangFuse registra solo el coste de la llamada que tuvo éxito (ADR-0013 §"Negative" I-2); cuando el *primary* falla y dispara *controlled fallback*, los tokens consumidos por el intento *primary* no se contabilizan.

## 11.9. Síntesis

La observabilidad de RegulAItor es deliberadamente **conservadora**: una capa orquestadora delgada con una *allowlist* explícita, un cliente cacheado a un tercero opt-in, y un acumulador de coste proceso-global que cierra la brecha estimate-not-measured. La disciplina §22.22 atraviesa todo el bloque: los costes se reportan como medidos cuando lo son y como estimados cuando lo son (cost_analysis.md y `evals/reports/*` distinguen explícitamente); la latencia del *eval* se etiqueta como *batch artifact*, no como SLA; el *ledger paid* incluye los gastos *contaminated* (Llama-Groq H12) y los *crashed* (H15.2) sin reescribir la historia. El sistema entra a H17 con un *dashboard* LangFuse real, un *runbook* operativo (`docs/runbook.md`) y un análisis de coste auditable — y con los *follow-ups* explícitamente abiertos (cost per-call hook completo en el *harness*, atribución per-capability, optimización de latencia per-span) sin venderlos como cerrados.
