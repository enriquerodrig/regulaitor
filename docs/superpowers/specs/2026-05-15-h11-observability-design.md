# H11 — Observabilidad (LangFuse) + redteam reliability: design spec

- **Status:** Approved (brainstorming closed 2026-05-15)
- **Date:** 2026-05-15
- **Author:** enriquerodrig + Claude (subagent-driven)
- **Companion ADRs:** future 0012 (observability architecture). Related: 0010 (eval harness), 0011 (redteam runner — this milestone closes its deferred full run).
- **Implementation plan:** TBD via `superpowers:writing-plans` after this spec is approved.

## 1. Context

H11 es el primer hito del track avanzado (MVP H0-H10 cerrado en `v0.1.0-mvp`).
Objetivo: dar **observabilidad** al sistema (CLAUDE.md §10.5 + §16.3) y cerrar
la **deuda de fiabilidad de H9** (el full 50-attack redteam run quedó diferido
porque el runner colgó silenciosamente en un Anthropic API hang sin timeouts).

Estado de partida relevante:
- **No existe** `src/regulaitor/observability/` — el logging estructurado vive
  inline en `orchestration/graph.py:_log_turn` (chat) y `api/logging.py` (HTTP
  H7). CLAUDE.md §11 lo planeó como módulo pero nunca se creó.
- `langfuse` NO está en deps.
- `redteam/runner.py` es síncrono; `run_chat`/`run_document` bloquean. H9
  perdió el full run por hang silencioso (32+ min sin traceback).
- Gate §16.2 #4 cerró con evidencia smoke (0.92); el full run sobre 50 está
  marcado `<deferred to H11>` en security_report.md, decisions log §H9
  amendment 5, ADR 0011, CLAUDE.md §27.
- Caveat CLAUDE.md §17 #7: el `latency_p95_ms` del eval (~572s) NO es la SLA
  de producto — es batch secuencial bajo rate-limit. H11 mide la latencia
  limpia per-span.

## 2. Decisiones de brainstorming

Seis decisiones + un enfoque, cerradas 2026-05-15.

### Q1 — Scope: bundle vs split

**Decisión: bundle todo en H11.** Las 3 piezas (LangFuse observability,
redteam timeout, full rerun) están temáticamente alineadas como "madurez
operacional". B+C son baratas y cierran deuda H9. Un solo ciclo
spec→plan→impl. C (rerun) depende de B (timeout) — sin timeout vuelve a
colgar.

### Q2 — LangFuse hosting

**Decisión: LangFuse Cloud free tier.** `cloud.langfuse.com`, gratis hasta
~50k observations/mes (sobra para el volumen TFM: ~40 evals + demo). Cero
infra. Self-hosted docker-compose rechazado por sobre-ingeniería para el
volumen; reservado conceptualmente a H16 si alguna vez. Cloud-fallback dual
rechazado por YAGNI.

### Q3 — Redacción de datos en trazas

**Decisión: metadata-only.** Las trazas van a un tercero (LangFuse Cloud).
CLAUDE.md §18.8 = "logs sin datos sensibles". Un producto de compliance que
filtre documentos de cliente a un SaaS de observabilidad sería irónico.
Trazas con: case_id, span name, latency_ms, cost_eur, token counts, verdict,
n_findings, n_citations, corpus, hashes (sha256[:12]). **Cero texto crudo**
(ni query, ni documento, ni respuesta, ni cita). Reproduce el patrón SSDLC
de `sanitizer_log` + `api/logging`.

### Q4 — Estrategia de instrumentación

**Decisión: wrapper en orchestration layer.** Nuevo módulo
`observability/langfuse_client.py`. Envolver SOLO los entry points
`graph.run` y `document_graph.run_document` con context managers de span.
Sub-spans (retriever/analyst/auditor) derivados de la metadata que
`_log_turn` ya computa. Cambio mínimo: 2 archivos orchestration + 1 módulo
nuevo. **Agentes H3-H5 intactos** (no decorators per-agente — mayor blast
radius rechazado; router-only hook — visibilidad parcial rechazado).

### Q5 — Mecanismo de timeout redteam

**Decisión: ThreadPoolExecutor + future.result(timeout).** Cross-platform
(Windows dev + Linux CI). `signal.SIGALRM` rechazado (Unix-only, rompería
`make redteam` local). subprocess-per-attack rechazado (overhead reload
BGE-M3 inviable ×50).

### Q6 — Dashboard + langfuse-mcp

**Decisión: LangFuse native dashboard + runbook doc + langfuse-mcp.** Sin
código de dashboard propio (Streamlit custom rechazado — duplica lo que
LangFuse da gratis). Custom scores configurados desde harness/redteam.
`docs/runbook.md` documenta qué mirar + screenshots para memoria TFM.
`langfuse-mcp` añadido a `.mcp.json` (read-only, consulta trazas desde
editor) — comando exacto se propone antes de tocar `.mcp.json` (CLAUDE.md
§13 exige OK explícito).

### Enfoque de integración — A: no-op graceful + async batching

**Decisión: A.** Si no hay `LANGFUSE_*` en env → no-op total (lazy import,
cero latencia, tests/CI sin keys imperturbables). Si hay keys → SDK nativo
LangFuse con batching async en background thread (~0 latencia al request
path; flush on exit). Cualquier fallo de LangFuse (red, 5xx) → log WARNING,
swallow; la observabilidad NUNCA tumba el pipeline ni añade latencia.
Eager/synchronous flush (B) rechazado (añade 100-500ms a un producto ya
sobre target). OpenTelemetry genérico (C) rechazado (overkill; diferido a
HX5 si alguna vez Prometheus).

## 3. Arquitectura

### 3.1 File layout

```
src/regulaitor/observability/
├── __init__.py                 # NUEVO
└── langfuse_client.py          # NUEVO — único módulo de código nuevo

Tocados (instrumentación, NO lógica):
src/regulaitor/orchestration/graph.py            # wrap run() con trace_turn
src/regulaitor/orchestration/document_graph.py   # wrap run_document()
redteam/runner.py                                 # ThreadPoolExecutor timeout
pyproject.toml                                    # +langfuse>=2,<3 dep
.mcp.json                                         # +langfuse-mcp (OK explícito antes)
.env                                              # +LANGFUSE_* (NUNCA .env.example)

NUEVO docs:
docs/runbook.md                                   # CLAUDE.md §21.6 entregable
docs/adr/0012-observability-architecture.md

tests/unit/observability/test_langfuse_client.py  # NUEVO
tests/unit/redteam/test_runner.py                 # extend (timeout test)
```

### 3.2 `langfuse_client.py` API

```python
def is_enabled() -> bool:
    """True si LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY + LANGFUSE_HOST
    están todos presentes en os.environ. No importa el SDK langfuse aquí
    (lazy import dentro del enabled path)."""

@contextmanager
def trace_turn(
    *, kind: Literal["chat", "document"], case_id: str,
    corpus: str, language: str,
) -> Iterator[TurnTrace]:
    """No-op (nullcontext-like, yield un TurnTrace inerte) si not
    is_enabled(). Si enabled: abre trace LangFuse, yield TurnTrace
    acumulador; en __exit__ emite spans metadata-only + flush async.
    Cualquier excepción de LangFuse SDK → log WARNING + swallow.
    NUNCA propaga al pipeline ni añade latencia bloqueante."""
```

`TurnTrace` — acumulador in-memory que el orchestration layer rellena con
metadata por fase (retriever/analyst/auditor o sanitizer/injection/segmenter/
aggregate). Espeja lo que `_log_turn` ya computa.

### 3.3 Trace schema (metadata-only)

**Trace root** (`name="chat_turn"` | `"document_turn"`):
```
metadata: { case_id, corpus, language, query_sha256_12, verdict,
            n_findings, n_citations, cost_eur_total, latency_ms_total,
            cache_hit? }
```

**Sub-spans chat**:
| span | metadata |
|---|---|
| retriever | n_chunks, latency_ms, embedding_model |
| analyst | latency_ms, cost_eur, tokens_in, tokens_out, n_findings, retry_triggered |
| auditor | latency_ms, verdict, n_validated, n_blocked |

**Sub-spans document**: sanitizer (n_events, blocked_category|null),
injection (hit, pattern_name), segmenter (n_segments), per_segment_rollup
(n_pass/n_block/n_review), aggregate (document_verdict).

**Custom scores** (LangFuse scores API, números para dashboard):
- `citation_recall`, `verdict_match` → emitidos desde `evals/harness.py`
  durante el eval (no en producción runtime).
- `block_rate` → emitido desde `redteam/runner.py`.
- `latency_p95` → derivado nativo LangFuse sobre spans.

**Regla de redacción dura (test-enforced)**: un test valida que el payload
serializado del trace NO contenga substring de sentinels (query/doc/cita
ficticios). Mismo patrón que tests SSDLC de `api/schemas.py`.

### 3.4 Redteam runner timeout

```python
_CHAT_TIMEOUT_S = int(os.environ.get("REGULAITOR_REDTEAM_TIMEOUT_CHAT", "300"))
_DOC_TIMEOUT_S  = int(os.environ.get("REGULAITOR_REDTEAM_TIMEOUT_DOC", "900"))

def _run_with_timeout(fn, attack, timeout_s) -> AttackOutcome:
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, attack)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout:
            return AttackOutcome(
                attack_id=attack.id, blocked=False,
                actual_block_layer="none", actual_verdict="timeout",
                matches_expected=False, latency_ms=timeout_s * 1000,
                cost_eur=0.0,
                error=f"timeout: attack exceeded {timeout_s}s (likely Anthropic hang)",
            )
```

Semántica: un attack que cuelga el sistema NO es defensa exitosa
(`blocked=False`; CLAUDE.md §18 trata el hang como fallo/DoS implícito).
Doc timeout 900s (15 min) cubre el caso lento legítimo (~10-12 min H5
pipeline observado en H8/H9) y corta el hang real (H9 fue 32+ min). Thread
huérfano abandonado consume 1 Anthropic call (~$0.02-0.19) — aceptado vs
perder el run entero. Runner continúa con el resto.

### 3.5 Full 50-attack rerun

Con timeouts activos, `make redteam` (50 ataques) en bg. Cierra deuda H9:
gate §16.2 #4 pasa de "smoke 0.92" a "full block_rate medido sobre 50".
Coste ~$3.3 (~22 chat × $0.019 + ~15 doc-e2e × $0.193). Resultado →
`redteam/reports/latest.md` (commit) + poblar placeholders `<deferred>` en
`docs/security_report.md`, decisions log §H9 amendment 5, ADR 0011,
CLAUDE.md §27 H9 line. block_rate < 0.90 sobre full = señal H15
calibración, NO re-abre H9.

## 4. Testing

- `tests/unit/observability/test_langfuse_client.py`:
  - sin keys → `is_enabled()` False, `trace_turn` no-op, SDK no importado.
  - keys mockeadas → trace abierto, spans con metadata correcta, flush llamado.
  - redacción dura: sentinels NUNCA en payload serializado.
  - excepción SDK LangFuse → swallowed, pipeline OK, WARNING logueado.
- `tests/unit/redteam/test_runner.py` extend: `fn` con `sleep(2)` +
  `timeout_s=1` → outcome `verdict="timeout"`, `error` contiene "timeout",
  runner continúa.
- Regresión: `graph.run`/`document_graph.run_document` sin `LANGFUSE_*` →
  comportamiento idéntico al actual. CI sin keys → tracing no-op, verde.
- Coverage: `observability/` entra en subset gated (≥90%).

## 5. Out of scope (diferido)

- OpenTelemetry / Prometheus / Grafana → HX5.
- Alertas (PagerDuty/email sobre umbrales) → HX5.
- Self-hosted LangFuse → no (cloud free, Q2).
- Dashboard custom Streamlit → no (nativo, Q6).
- Per-agent decorators finos → no (orchestration wrapper, Q4).
- Latency *optimization* (streaming, max_tokens, retriever paralelo, router
  rápido) → H15. **H11 solo MIDE limpio, no optimiza.**
- Trazas full-content → no (metadata-only, Q3); override = decisión nueva.
- `cost-accounting` skill → no (es H17 per §12.5; H11 expone coste en
  dashboard, no análisis formal de curvas).

## 6. Entregables de cierre H11

- `src/regulaitor/observability/__init__.py` + `langfuse_client.py` + tests.
- Instrumentación `graph.py` + `document_graph.py` (orchestration wrap).
- redteam runner timeout + test.
- `redteam/reports/latest.md` con full 50-attack run.
- Placeholders `<deferred>` H9 poblados (security_report, decisions log §H9
  amendment 5, ADR 0011, CLAUDE.md §27 H9 line).
- `docs/runbook.md` (CLAUDE.md §21.6): setup LangFuse keys, qué paneles
  mirar, interpretación latency limpia vs eval-batch p95 (cierra caveat
  §17 #7), runbook operacional (block_rate cae / latencia sube / coste
  dispara).
- `.mcp.json` + langfuse-mcp (comando propuesto + OK explícito antes).
- `docs/adr/0012-observability-architecture.md`.
- `docs/technical_decisions_log.md §H11` (6 Qs + enfoque A + amendments).
- `docs/evidence_matrix.md` actualizado (Módulo 3 observability row +
  follow-ups; gate §16.2 #4 full).
- `CLAUDE.md §27` H11 closed + H12 next.
- Tag **`v0.1.1-h11`** (scheme post-MVP: patch bump por hito avanzado;
  MVP fue `v0.1.0-mvp`). *Confirmar al cierre; alternativa
  `v0.0.11-h11` continuando serie pre-MVP.*
- Memory rename `h10_closed_h11_starting.md` → `h11_closed_h12_starting.md`.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| LangFuse SDK version churn | pin `langfuse>=2,<3` |
| Free tier rate/volume limits | ~40 evals + demo << 50k/mes; límite documentado en runbook |
| Thread huérfano en timeout consume 1 Anthropic call | aceptado (§3.4); timeout generoso solo dispara en hang real |
| `langfuse` añade deps transitivas | revisar pip-audit tras añadir; documentar CVE ignores si aplica |
| Instrumentación rompe backend read-only | solo orchestration layer (entry points), agentes intactos; test de regresión sin keys |
| Full rerun vuelve a colgar | timeout §3.4 lo corta; report queda parcial con timeouts marcados, no hang infinito |
| Usuario olvida crear cuenta LangFuse | runbook paso-a-paso; sin keys el sistema funciona (no-op), solo no hay dashboard |

## 8. Definition of Done H11

1. `observability/langfuse_client.py` con `is_enabled()` + `trace_turn`,
   no-op sin keys, async batching con keys, graceful swallow.
2. `graph.py` + `document_graph.py` instrumentados (regresión cero sin keys).
3. redteam runner timeout + test verde.
4. Full 50-attack `redteam/reports/latest.md` committed; `block_rate_final`
   poblado en los 4 documentos con placeholder `<deferred>`.
5. `docs/runbook.md` + ADR 0012 + decisions log §H11 committed.
6. langfuse-mcp en `.mcp.json` (con OK explícito).
7. Tests verdes (incl. redacción dura); coverage `observability/` ≥90%.
8. CI 5 jobs verdes.
9. `evidence_matrix.md` + `CLAUDE.md §27` actualizados.
10. Tag `v0.1.1-h11` (o confirmado) + memory rename.

## 9. Referencias

- CLAUDE.md §10.5 (observabilidad avanzada), §16.3 (H11 roadmap), §13
  (langfuse-mcp), §18.8 (logs sin datos sensibles), §17 #7 (latency caveat),
  §21.6 (runbook), §12.5 (skills por hito).
- ADR 0010 (eval harness — custom scores source), ADR 0011 (redteam runner
  — this milestone closes its deferred full run).
- Memory `h10_closed_h11_starting.md` (MVP closure state + H11 boundary).
- Decisions log §H9 amendment 5 (full run deferral rationale).
