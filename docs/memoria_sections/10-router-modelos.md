# 10. Router multi-LLM + modelos

RegulAItor canaliza toda invocación a un modelo de lenguaje a través de un único punto de entrada: `router.complete()` (src/regulaitor/models/router.py:193). Ningún agente importa directamente `anthropic`, `openai` o `groq`; la regla CLAUDE.md §22 item 13 ("Cada modelo accedido va por `router.py`. Ningún agente llama directamente a un modelo.") es invariante de arquitectura y queda verificable mediante una búsqueda trivial de imports prohibidos. Esta sección describe la evolución del router (H4 → H12 → H13 → H15), las seis modalidades expuestas, los helpers puros de traducción Anthropic↔OpenAI, el acumulador de coste process-level que cerró el hueco "estimado pero no medido" de H12/H13, y el hallazgo cualitativo que reforzó toda la línea de optimización posterior: la calidad uniformemente baja entre proveedores demostró que el techo es system-level (retriever + Auditor), no la elección de modelo.

## 1. De thin router a 5 modos (H4 → H12, ADR-0013)

En H4 el router era una capa fina con un único backend: `default`/`quality` enrutaban a Anthropic Claude Sonnet 4.6; el resto de modos respondía `NotImplementedError`. El `CompletionResult` ya era provider-agnostic, así que la extensión H12 sólo tocó `models/router.py` + `models/config.py` + helpers de traducción + tests; el backend H1-H5/graph/API/Streamlit/`evals/harness.py` quedó read-only (regression-zero documentada en ADR-0013 §Consequences "Backend H1–H5 untouched; prod default path regression-zero (env unset → byte-identical)").

ADR-0013 D2 fijó el lineup de cinco modos:

| Modo         | Proveedor  | Modelo                       | Justificación                                                    |
|--------------|------------|------------------------------|------------------------------------------------------------------|
| `default`    | Anthropic  | `claude-sonnet-4-6`          | Producción (Analyst + doc_analyst). H4 frozen baseline.          |
| `quality`    | Anthropic  | `claude-sonnet-4-6`          | Alias semántico de `default`.                                    |
| `cost`       | Groq       | `llama-3.3-70b-versatile`    | Open-weights vía inferencia low-cost.                            |
| `evaluation` | OpenAI     | `gpt-4o`                     | Proveedor independiente para A/B y peer review.                  |
| `fallback`   | OpenAI     | `gpt-4o-mini`                | Destino del fallback controlado one-hop.                         |

`models/config.py:30` mantiene `PRICING` con USD/1M tokens para los cinco IDs y `PRICING_SNAPSHOT_DATE = "2026-05-16"`; `cost_eur()` (config.py:44) convierte tokens reales a EUR usando un USD→EUR rate de 0.93 anclado al snapshot. La precisión es deliberadamente la del list-price del proveedor: `docs/cost_analysis.md` documenta los precios y deja la conversión auditable.

### 1.1 Diseño del fallback: estrechar a transport-only (T7 I-1)

El fallback controlado actúa **una sola vez**, exclusivamente cuando el modo activo no es `fallback` y la excepción primaria pertenece al conjunto `_FALLBACKABLE_ERRORS` (router.py:77). Este conjunto enumera exactamente 12 tipos de error transport/availability tomados de los tres SDKs: `RateLimitError`, `APIConnectionError`, `APITimeoutError`, `InternalServerError` por cada uno de los tres proveedores. El borrador original del plan H12 usaba un `except Exception` ancho; el review en dos fases (CLAUDE.md §22, disciplina de revisión consecuente) capturó T7 I-1 como Critical: un `except Exception` habría re-enrutado silenciosamente errores deterministas (BadRequestError, JSON malformado, ValidationError) a GPT-4o-mini, **corrompiendo la medición A/B** porque un fallo de Llama/GPT-4o se habría atribuido a GPT-4o-mini sin trazas. La narrowing a transport-only es uno de los catches más valiosos del linaje §22.22 (ADR-0013 §Decision D4 y §Consequences negativas).

El segundo intento (el hop al modo `fallback`) tampoco entra en bucle: si **también** falla, el manejador hace `raise primary_exc from None` y la excepción original sube limpia (router.py:234). El logger emite dos líneas estructuradas (`fallback_triggered=true` antes y `fallback_used=true` o el warning de doble fallo) que permiten reconstruir el evento desde LangFuse.

### 1.2 Override eval-only por entorno

`_resolve_mode()` (router.py:103) lee `REGULAITOR_ROUTER_MODE` y, si su valor pertenece a `_VALID_MODES` (derivado vía `typing.get_args(ModelChoice)` para evitar duplicación), sobreescribe el `model_choice` del caller. Un valor inválido produce WARNING y se ignora — un `.env` mal configurado nunca puede romper producción. Este seam es el que el A/B harness de H12 usaba para forzar arms sin tocar `graph.run()`, preservando la frontera read-only del backend.

## 2. Translation Anthropic↔OpenAI (helpers puros)

El Analyst (H4) habla Anthropic tool use. OpenAI y Groq usan el schema function-calling. La conversión vive en `models/_translate.py` como cuatro funciones puras, exhaustivamente unit-tested ($0):

- `tools_to_openai()` (_translate.py:15): `[{name, description, input_schema}]` → `[{"type":"function", "function":{name, description, parameters}}]`.
- `tool_choice_to_openai()` (_translate.py:34): `{"type":"tool","name":N}` → `{"type":"function","function":{"name":N}}`; los valores `"any"`/`"auto"` pasan tal cual.
- `messages_to_openai()` (_translate.py:46): convierte string content trivialmente; el bloque Anthropic `tool_use` (retry H8) se traduce a `assistant.tool_calls`; el bloque `tool_result` se traduce a `{"role":"tool", "tool_call_id":..., "content":...}`. La función **levanta `ValueError`** ante un block type desconocido (_translate.py:95): un dropped silently sería security-critical, así que la regla es "surface loudly" si el productor (el Analyst) introduce un tipo nuevo.
- `extract_openai_tool_use()` (_translate.py:99): extrae el primer tool call y parsea `arguments` (JSON string en OpenAI/Groq, ya dict en Anthropic).

El path Anthropic es bespoke en `_call_anthropic()` (router.py:279) por una razón documentada en el docstring: usa `client.messages.create` + `system=` kwarg + `response.content` block list, y retorna tool input ya como dict (`dict(block.input)`), por lo que los guards I1/I2 son estructuralmente inaplicables. **No unificar** estos paths fue una decisión explícita (ADR-0013 D4).

Los path OpenAI/Groq comparten `_call_openai_compatible()` (router.py:380), que protege dos invariantes adicionales:

- **I2**: `arguments` como JSON malformado → `RuntimeError` claro, **no se reintenta** (tenacity sólo cubre transport; mismo response defectuoso en cada attempt).
- **I1**: JSON válido pero no-objeto → `RuntimeError` (espejo del idiom del Analyst para evitar un `pydantic.ValidationError` confuso).

Cada `_call_*` lleva su propio decorador `@retry` de tenacity (stop_after_attempt(3), exponential 1-10s) que cubre **únicamente** los errores transient del SDK correspondiente (router.py:271, 459, 489). Esto da: 3 retries por SDK → si terminal → fallback one-hop → si terminal → propagación. El presupuesto temporal está acotado por construcción.

## 3. Modo `judge` y router de seis modos (H13, ADR-0014 D7)

ADR-0014 D7 añadió un sexto modo: `judge` → Anthropic Claude Haiku 4.5 (`claude-haiku-4-5-20251001`). Justificación: el Council de jueces (H13) y el LLM-as-judge de evals (H8) necesitan un modelo más barato que Sonnet pero del mismo "modelo class" (Anthropic) para preservar continuidad de cache (ADR-0010 D1 caveat resuelto explícitamente como "stay Haiku" en v0.1.16 ADR-0021; cross-vendor migration HX post-TFM). El modo `judge` se mapea en `_MODE_MAP` (router.py:99) sin cambios de dispatch — comparte el path `_call_anthropic` con `default`/`quality`. Es el único modo nuevo H13 (los 5 modos H12 quedaron regression-zero).

El Council de jueces (src/regulaitor/agents/council.py) usa tres modos distintos para garantizar independencia de proveedor (ADR-0014 D3):

- `judge` → Haiku 4.5 (Anthropic).
- `evaluation` → GPT-4o (OpenAI).
- `cost` → Llama-3.3-70b (Groq).

Un panel de 3 votos con 3 parámetros (parametric biases) distintos. Los fallos por juez degradan a `ok=False` y la run sigue (council.py:236 swallow + log); un panel parcial con 2 votos válidos sigue produciendo veredicto. El invariante "el Council nunca rompe el turno" es paramount (ADR-0014 D1).

## 4. Acumulador de coste process-level (H15, ADR-0016 enabler)

H12 y H13 documentaron honestamente (§22.22) un hueco de pipeline: aunque cada `CompletionResult` ya contenía el `cost_eur` real por llamada, el harness `evals/harness.py` (read-only en H12) reportaba un heurístico hardcoded de Sonnet (los infames "2.51 € idénticos a través de los arms" del A/B de H12) o un approx `~$1.2-1.5` (H13 Council). H15 cerró el hueco con un patrón mínimo localizado en el router (CLAUDE.md §22.18 — observability side-effect, contract byte-identical):

```python
_cost_lock = threading.Lock()
_accumulated_cost_eur: float = 0.0

def _record_cost_eur(cost: float) -> None: ...      # cada provider branch lo llama
def reset_cost_accumulator() -> None: ...           # harness lo llama antes de cada caso
def get_accumulated_cost_eur() -> float: ...        # harness lo lee al final
```

(src/regulaitor/models/router.py:147-174). El docstring de `reset_cost_accumulator()` documenta explícitamente la limitación: el patrón process-global es correcto sólo con casos secuenciales en un proceso/thread; si el harness se paraleliza alguna vez, hay que migrar a per-case context o per-thread accumulator. El lock protege el `+=`, no la aislación de runs. Este es el seam que permite a H15 y sucesivos reportar coste **medido** (€5.05 H15, €1.91 v0.1.22, €1.66 v0.1.25, €1.89 v0.1.29, €0.65 v0.1.30 REVERT) en lugar de estimado.

## 5. Hallazgo H12: el techo es system-level

El A/B real de H12 (40 casos chat × 3 arms: Sonnet baseline frozen + GPT-4o + Llama-Groq) produjo dos consecuencias documentadas honestamente en ADR-0013:

1. **Calidad uniformemente baja**: `verdict_match` 0.17-0.28 y `severity_match` 0.04-0.23 a través de los tres arms. La diferencia entre Sonnet, GPT-4o y Llama era pequeña frente a la distancia entre cualquiera de ellos y los objetivos §17. **Conclusión**: el techo de calidad es system-level (retriever + Auditor calibration), **no** la elección de modelo. Esto refuerza directamente el plan H15 (model swaps no rescatan auditing) y, posteriormente, todo el linaje v0.1.18 → v0.1.25 → v0.1.29 (calibration del Auditor + propagación de hierarchical containment + softening de routing).

2. **Caveat I-2 (Llama arm contaminado)**: ~19/40 casos del arm Llama fallaron porque (a) el free tier de Groq impone un cap de 100k TPD, y (b) los arms se ejecutaron secuencialmente, agotando los ~$5 de crédito OpenAI antes del final → el fallback a GPT-4o-mini **también falló**. El review T7 había anticipado este riesgo (I-2 risk register); el run empírico lo confirmó. El project owner rechazó re-correr con paid tier (§22.22, H11 precedent): el arm contaminado es en sí mismo un hallazgo honesto sobre el coste de operar con free tiers.

## 6. Lo que el router **no** hace (alcance honesto)

- **No selecciona modelo por contenido del prompt** (ni "router inteligente" tipo MoE-of-prompts). El `model_choice` viene del caller, modulado sólo por el override env.
- **No agrega coste cross-process ni cross-thread**. El acumulador es process-local.
- **No persiste trazas a LangFuse**: eso vive en `observability/langfuse_client.py` (ADR-0012). El router sólo emite logs estructurados; el envío externo es decisión de la capa de orquestación.
- **No cachea responses**. La cache de evals (judge-layer) vive en `evals/cache.py`; el chat graph siempre llama fresh (decisión H8 §22.22).
- **No oculta los errores deterministas**. Cualquier `BadRequestError`, `ValidationError` o `RuntimeError` (incluyendo I1/I2 sobre tool args) sube limpia. Esta disciplina es la que hizo que el bug de Capa A `additionalProperties=False` en `$defs` (v0.1.22) se manifestase como crash visible y no como degradación silenciosa (ADR-0029 §22.22 #3).

## 7. Tests y cobertura

El router está cubierto por tests unitarios $0 con SDKs mockeados (no se llaman APIs reales en CI):

- Tests del lineup (5 modos → mapping, 6º modo judge).
- Tests del override env (válido, inválido con WARNING, unset).
- Tests del fallback one-hop (transport-only triggera; deterministic propaga; doble fallo levanta original).
- Tests de los helpers `_translate` (translate fidelity sobre los 3 block types Anthropic; ValueError ante block desconocido; I1/I2 guards).
- Tests del acumulador (reset → llamadas → get; locking; reset entre casos).

La cobertura actual ≥85% (gate v0.1.26+) incluye todas las branches del router excepto los path `RuntimeError("API_KEY not set")` que sólo se ejercitan en mocks de error.

## 8. Cierre

El router cumple tres requisitos académicos del Máster simultáneamente: (i) Módulo 1 entrega el artefacto hand-built multi-provider con cost analysis; (ii) Módulo 2 lo usa como invariante de arquitectura ("toda llamada va por aquí"); (iii) Módulo 5 P4 documenta el cost discipline (router accumulator) y el A/B honesto (ADR-0013 §Consequences). La decisión de **no** adoptar litellm u otro SDK unificado fue deliberada y está en el §Alternatives de ADR-0013: una dependencia adicional con superficie de supply chain habría socavado el deliverable hand-built sin ganar capacidad relevante. El precio que se paga (mantener los helpers `_translate`) está acotado a ~110 LOC puros y a un set de tests exhaustivos.
