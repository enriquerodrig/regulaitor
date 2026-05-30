# Post-TFM Product Roadmap (detallado HX + production hardening)

## Encuadre

Este documento es la **proyección operativa post-defensa** del backlog consolidado en `docs/memoria_sections/19-roadmap-post-tfm.md`. La memoria académica organiza los carry-forwards por bloques temáticos (HX1–HX5 + endurecimiento + corpus + retrieval + jueces + mantenimiento); aquí los reagrupamos por **trimestre tentativo Q1–Q4 post-cierre `v1.0.0`**, con criterios de aceptación, dependencias y estimación esfuerzo (S=1–5d, M=1–3sem, L=3sem+).

Aplica §22.22: este roadmap **no es compromiso de ejecución**. Es priorización razonable sobre los carry-forwards documentados a lo largo del linaje H0 → v0.1.32. El ordenamiento real dependerá de evidencia post-deploy (tráfico real, primer cliente piloto, presupuesto). La frontera §6 ("no citation, no answer") es inviolable también en producto; cualquier HX que la roce pasa por nuevo ADR siguiendo los precedentes ADR-0024/0031/0032/0034.

Las referencias del tipo "deep-review" provienen del audit pre-H16 documentado en `docs/pre_h16_review.md` (§6 acumula los ítems 14–17 como carry-forwards a H17 / HX; §11 lista las nuevas tareas N1–N4 descubiertas post-review). La notación interna del audit usa códigos `H3.x`, `H4.x`, `H5.x`, `H6.x`, `A1 S*`, `A2 C*`, `A3 L*`, `A4 M*` (subagentes parallel), no `I3/I8/I11/I12`; cuando este roadmap menciona "deep-review I*" debe leerse como referencia laxa al backlog post-review, no a un código literal. Cuando un ítem está [pendiente] de medición lo etiquetamos explícitamente.

## Q1 — Foundation: endurecimiento de producción + saneo técnico

Objetivo del trimestre: dejar el sistema en estado **operable para un primer cliente piloto** sin comprometer §6 ni la disciplina §22.22. Sin paid runs salvo verificación post-fix.

### Q1.1 Split de autenticación en `/health` (deep-review I3) [S]

`src/regulaitor/api/auth.py:42` define `verify_token` como `Security(HTTPBearer)`. El handler `/health` (definido en `src/regulaitor/api/routes_health.py:46`) es `async def health()` y expone el mismo payload (LanceDB row count + presencia de claves API) a llamantes no autenticados que a autenticados; ese leak de estado interno a no-autenticados es el problema real, no event-loop starvation (la función ya es async y los checks son síncronos pero rápidos). La partición correcta:

- `GET /health` público: `200 OK` + `{"status": "ok", "version": "v1.0.0"}`. Async-drop, sin I/O.
- `GET /health/detailed` detrás de `Depends(verify_token)`: check de LanceDB (`rag/store.py` smoke query), upstream Anthropic (`models/router.py` ping con 1 token), cache hit ratio, RSS y latencia p95 últimas 1000 requests.

Criterio de aceptación: `pytest tests/integration/test_api_health.py` cubre ambos endpoints; contract test (`schemathesis`) re-corrido.

### Q1.2 Doc-mode multi-corpus UI parity (deep-review I8) [S]

El estado actual del modo documental en `ui_streamlit/tab_analyze.py` colapsa `corpus[]` al primer corpus emitido por el segmentador. Detectado en la iteración R8 + R11 del deploy H16 (`docs/memoria_sections/16-despliegue.md` §16.3, donde se documentan R1–R12; las rondas post-tag R13 / R14 viven en §16.4). Solución: propagar la lista completa al renderer y mostrar chips por corpus (precedente de R13 chat-mode). No toca backend.

### Q1.3 Redteam corpus expansion NIS2 / DORA (deep-review I11) [M]

`redteam/attacks.jsonl` contiene 50 ataques (CLAUDE.md §H9). El conteo por corpus es desproporcionado: el `grep -i nis2|dora` sobre el archivo da 0 ocurrencias literales — el set se autoró en H9 (pre-H14) y se centra en AI Act / RGPD. NIS2 y DORA aterrizaron en H14 (ADR-0015) pero no tienen su propia capa adversarial. Extender hasta ~80 ataques (objetivo avanzado CLAUDE.md §18):

- ≥10 ataques NIS2 (artículos 21/23/32/33: gestión riesgos, notificación, sanciones).
- ≥10 ataques DORA (artículos 5/8/17/19/20/28: gobernanza, riesgo TIC, notificación incidentes graves).
- ≥5 ataques cross-corpus (escenarios que mezclan obligaciones).

Re-run `make redteam` esperado pasar smoke ≥0.90 (gate §16.2 #4) sobre el set ampliado. Si baja, plan de calibración HX heredado.

### Q1.4 Trail completo `per_citation_audits` cross-Sonnet (deep-review I12) [S]

v0.1.29 Stage 1 reparó `evals/metrics.py` para restaurar `failed_check` en el trail (`docs/pre_h16_review.md` N2). Falta validar que el trail completo (todos los campos `AuditResult` + reasons normalizados) se persiste consistentemente entre runs Sonnet 4.6 cacheados y futuros runs Sonnet posteriores (drift API ~20% confirmado en v0.1.23 §REVERT). Acción: añadir test de schema-stability sobre `ChatCaseResult.per_citation_audits` que detecte drop silencioso de campos.

### Q1.5 truststore en `pyproject.toml` (verificación post-v0.1.26) [S]

`docs/pre_h16_review.md` §11 marca ítem 3 (`truststore in pyproject.toml`) como DONE en v0.1.26 (commit `fefb6f2`; el squash de v0.1.26 en main es `07dab21`). Verificación operativa: clone fresco + `uv sync` + `python -c "import truststore"` debe importar sin warning. Si falla → re-anclar versión `>=0.10` y documentar en runbook.

### Q1.6 Python 3.13 support [M]

CLAUDE.md §10.1 fija Python 3.11. Migración a 3.13:

1. Actualizar `pyproject.toml [project] requires-python = ">=3.11,<3.14"`.
2. Re-correr matriz CI con `3.11` + `3.12` + `3.13`.
3. Verificar `pydantic` v2 + `fastapi` + `langgraph` + `lancedb` compatibles.
4. Re-correr eval H10 30-case bajo 3.13 para detectar drift no obvio.

Riesgo principal: `pypdfium2` y `unstructured` arrastran wheels nativos; la disponibilidad de 3.13 puede retrasar la migración.

### Q1.7 Migración Anthropic SDK 1.x [M]

El SDK Anthropic está en major 0.x al cierre TFM. Cuando se publique 1.0:

1. Auditar `src/regulaitor/agents/analyst.py:31` (Capa A `_set_additional_properties_false_recursive` per ADR-0029 — recursive walker sobre el JSON-schema del tool `emit_answer`, sensible al SDK).
2. Validar tool_use con `strict: True` + `minItems: 1` (Capa A ADR-0027).
3. Re-correr probe N=5 chat-mode para detectar regresiones silenciosas.
4. Migración por feature flag (`REGULAITOR_ANTHROPIC_SDK_MAJOR`) si el equipo cliente está consumiendo v0.x.

### Q1.8 pip-audit Windows wrapper [S]

`docs/pre_h16_review.md` §6 ítem 7 (y §11 status table fila 7) quedó DEFERRED: SSL CryptoAPI CRL bloquea pip-audit en Windows (mismo bug que el discovered en v0.1.22 §22.22 #2 — CRYPT_E_NO_REVOCATION_CHECK 0x80092012). Solución operativa: wrapper PowerShell + `truststore.inject_into_ssl()` antes de invocar pip-audit; o documentación en runbook restringiendo pip-audit a CI Linux. Documentar en `docs/H16_DEPLOY.md`.

### Q1.9 HF token rotation [S]

Heredado de la memoria de usuario v0.1.32_h16_deployed_H17_ready: token HF leaked en chat durante el deploy iteración. Rotar token actual + actualizar secret en HF Spaces + revocar el leaked. Deuda de seguridad operativa única heredada por H17.

## Q2 — HX1 + HX2: clasificador severidad + frontend Next.js

### Q2.1 HX1 — LoRA severity classifier (skill `lora-finetune-recipe`) [L]

Pre-requisito CLAUDE.md §22.17: gold set + baseline (ambos satisfechos desde H8). Pipeline:

1. **Dataset**: gold set actual aporta ~120 `Finding` con severity; falta etiquetado in-corpus + datos sintéticos auditados para llegar a ≥500 ejemplos balanceados. Etiquetado cruzado por dos asesores (anotación independiente + κ Cohen).
2. **Modelo base**: Llama-3.1-8B-Instruct (CLAUDE.md §10.4) con LoRA r=16 alpha=32 sobre `q_proj/v_proj`.
3. **Eval**: matriz de confusión + macro-F1 por escala `info/low/medium/high` + análisis por norma. Target macro-F1 ≥0.70.
4. **Skill**: activar `lora-finetune-recipe` (CLAUDE.md §12.4.11) como receta reproducible en `notebooks/lora_severity.ipynb`.
5. **Integración**: `src/regulaitor/models/severity_classifier.py` (placeholder en §11 estructura objetivo); cableado opcional con feature flag `REGULAITOR_USE_LORA_SEVERITY`.

Riesgo principal: la severidad legal es contextual al cliente (medium para fintech ≠ medium para hospital). El diseño debe contemplar fine-tunes per-vertical o calibración por organización. **No tocar §6**: el clasificador asigna severidad, no decide validez de citas.

### Q2.2 HX2 — Frontend Next.js triple superficie (skills `next-frontend-architect` + `ui-style-guide`) [L]

CLAUDE.md §22.16 satisfecho post-H17. Especificación detallada en `docs/memoria_sections/19-roadmap-post-tfm.md` §19.3. Resumen ejecutable:

- **Stack**: Next.js 14+ App Router + React Server Components + Tailwind sobrio + shadcn/ui + WCAG 2.2 AA (no negociable).
- **Superficie 1 (chat)**: streaming respuesta, chips dinámicos de corpus (R13 prototipo Streamlit), panel citas plegable, verdict badge prominente (R12 lineage).
- **Superficie 2 (análisis documental)**: drag-and-drop multi-fichero, progreso por segmento (BGE-M3 CPU es lento — `feedback_local_cpu_rerank_cost.md`), informe Markdown descargable, export PDF (skill `pdf` oficial Anthropic).
- **Superficie 3 (dashboard de cumplimiento)**: agregados por cliente, métricas citation accuracy real, latencia p95, coste acumulado, tasa de bloqueo. Es el activo que distingue "demo" de "producto".

Audit accesibilidad: axe-core en CI + auditoría manual de keyboard navigation + contraste 4.5:1 mínimo. Skill `ui-style-guide` (§12.4.12) gobierna el sistema de diseño compartido entre Streamlit y Next.js.

## Q3 — HX3 + HX4: integración CI + MCP marketplace

### Q3.1 HX3 — GitHub Action / webhook conector [M]

Conector minimalista descrito en `docs/memoria_sections/19-roadmap-post-tfm.md` §19.4. Implementación:

1. **GitHub Action**: trigger `pull_request: [opened, synchronize]`; lee `description` + `*.md` tocados; llama `POST /analyze` con auth Bearer (token de organización per Q4); postea como comentario los `Finding` con severidad `high` que tocan AI Act / RGPD / NIS2 / DORA.
2. **Webhook genérico**: endpoint `POST /webhook/{provider}` con autenticación HMAC mutua; soporta Slack / Linear / GitHub events.
3. **Formato de entrada inicial**: limitado a `.md` PRD (la variedad PRD vs commit diff vs texto suelto condiciona la utilidad — empezar acotado).
4. **Endurecimiento**: skill `secure-coding-checklist` (§12.3.10) cubre HMAC + rate limit por origen + sanitización (mismo flujo que `document/sanitizer.py`).

Criterio aceptación: demo `regulaitor-action-demo` repo con PR que dispara el análisis y produce comentario en <60 segundos p95.

### Q3.2 HX4 — Servidor MCP externo en marketplace [M]

El MCP server interno (`src/regulaitor/mcp_server/`, 5 tools, ADR-0005) está validado con tests de contrato. HX4 lo desacopla a repo separado `regulaitor-mcp-server` y lo publica en el MCP marketplace:

1. Repo separado con package distribuible (`pip install regulaitor-mcp` + `npx -y regulaitor-mcp` wrappers).
2. Capa de tokens por instalación (heredando el Bearer pattern de `src/regulaitor/api/auth.py` — `_bearer = HTTPBearer(...)` en línea 21 + `verify_token` en línea 42); cada cliente recibe token + cuota.
3. Observabilidad: log por `token_hash` + métricas Prometheus de Q4.1 (qué tool, qué corpus, qué cliente).
4. Documentación: README en repo + entry en MCP marketplace + ejemplos integración Claude Desktop, Cursor, Continue.

Valor para usuario primario (CLAUDE.md §4): equipo IT pregunta a su asistente IA "¿qué artículo del AI Act regula supervisión humana?" y recibe respuesta del corpus oficial con cita verificada sin abrir RegulAItor. Riesgo: rate limiting + facturación bajo tráfico no autenticado del marketplace — mitigado por capa de tokens.

## Q4 — HX5 + production hardening completo

### Q4.1 HX5 — Prometheus + Grafana + alerting [M]

H11 dejó observabilidad opcional con LangFuse (ADR-0012). HX5 añade el siguiente nivel:

- **Métricas Prometheus**: citation accuracy diaria sobre tráfico real (no sobre gold set), latencia p50/p95/p99 por endpoint, coste acumulado por modelo / por org, tasa de bloqueo Auditor por corpus.
- **Grafana dashboards**: vista por organización (alimenta superficie 3 del frontend Q2.2), vista operacional global, vista §6 (tasa de RHR por Layer (c) sub-route).
- **Alertas**: tasa bloqueo >0.3 sostenida 1h, coste/día sobre umbral, latencia p95 sobre SLA, anomalía en distribución `failed_check` (canary de regresión del validator o cambio de comportamiento del Analyst).

### Q4.2 Multi-tenant token management + Postgres [M]

Hoy `REGULAITOR_API_TOKEN` es un secreto único compartido (declarado como `_API_TOKEN: str | None = None` en `src/regulaitor/api/auth.py:19` y cargado vía `load_api_token_or_raise()` en líneas 24–34 con `os.getenv("REGULAITOR_API_TOKEN")`). Para producto multi-tenant:

1. Tabla `tokens` con `token_hash`, `org_id`, `scopes` (`/ask`, `/analyze`, `/health/detailed`, `/webhook/*`), `quota_monthly`, `created_at`, `revoked_at`.
2. Audit log persistente por request (`request_id`, `token_hash`, `endpoint`, `cost_eur`, `verdict`, `latency_ms`).
3. Migración SQLite → Postgres (CLAUDE.md §10.1 condicional). Justificación: concurrencia + joins por `org_id` + cuota acumulada con cut-off automático antes de overrun.

Skill `secure-coding-checklist` gobierna el endurecimiento (rotación de secret, scopes mínimos, audit log inmutable).

### Q4.3 HF Pro upgrade o Render GPU deploy [S/M]

BGE-M3 + bge-reranker-v2-m3 en CPU procesan cada segmento documental en ~15-30s sostenidos (`feedback_local_cpu_rerank_cost.md`). GPU acelera inferencia ~10×. Decisión: HF Pro (~€9/mes para CPU upgrade + más RAM) o Render con GPU dedicada (más caro, escalable). Decisión condicional al volumen real post-piloto.

### Q4.4 Expansión de corpus consolidado [M/L]

Cuatro líneas paralelas heredadas de CLAUDE.md §7 + H14:

1. **Consolidadas NIS2 + DORA**: H14 ingestó base-acts porque CloudFront WAF bloqueaba consolidadas (ADR-0015 + ADR-0003 lineage). Cron Playwright headless reintentando periódicamente.
2. **EBA / ESMA technical standards**: DORA delega plazos a RTS publicadas por EBA. Sin ese contenido, gold case dora-003 mide la limitación (CLAUDE.md §H14 corpus-ground del code-review).
3. **Directivas AML 4/5/6**: línea fintech / banca / cripto; reutiliza arquitectura.
4. **Implementaciones jurisdiccionales**: España (LOPDGDD + RD transposición NIS2 cuando se publique) primero por idioma + mercado primario. Parser específico BOE (no comparte HTML estructurado con EUR-Lex). Después FR / DE / IT.

### Q4.5 Cross-vendor judge migration (Haiku → GPT-4o-mini o Llama) [M]

ADR-0021 D3 dejó esto como HX explícito. Ejecutar harness con GPT-4o-mini como juez, comparar contra Haiku 4.5 baseline en H10 cohort, documentar correlación. Coste estimado re-eval ≥€10 sobre 64 cases × 3 modelos × N corridas estadísticas. Riesgo: invalida cache H10-onwards.

### Q4.6 Council expansion 3→5 jueces + voting algorithms [M]

ADR-0014 ancla 3-jueces (Haiku + GPT-4o + Llama-3.3). HX:

- **5+ jueces** con voting weighted por proveniencia (jurídico fine-tuned vs generalista).
- **Supermajority policies** (4/5, 3/5) más allá de unanimidad estricta.
- **Council adversarial**: un juez recibe prompt "encuentra el fallo en este razonamiento".

Coste ~3-5× base por consulta. Si toca el binding (MonotonicEscalatePolicy → policies más laxas), pasa por nuevo ADR siguiendo precedente ADR-0025.

### Q4.7 Doc gold set N=10 → N≥30 [M]

Lección v0.1.23 §REVERT: doc gold set N=10 tiene ruido floor ~20%, insuficiente para decisiones high-confidence de retrieval engineering. Extensión ≥30 (preferentemente ≥50): 5 docs por sector × 6 sectores (hospital, fintech, cloud, RRHH, ed-tech, manufactura). Etiquetado por dos asesores independientes con κ Cohen reportado. Pre-requisito de Q4.8.

### Q4.8 Doc-mode retrieval engineering — HyDE / hybrid BM25 / custom reranker [L]

Carry-forward ADR-0035 §REVERT + alternativas A–C. Por orden de coste / promesa:

- **A. HyDE (Hypothetical Document Embeddings)**: LLM redacta respuesta regulatoria hipotética del segmento; se usa como query. Coste +€0.005-€0.01/query. Más prometedora porque opera en query-side (precedente exitoso v0.1.28 T4-bis title-prepend) no corpus-side (donde v0.1.30 dilata).
- **B. Hybrid BM25 + dense**: score fusion (RRF) léxico + semántico. Integración `tantivy` o `rank-bm25`. Complementaria con A.
- **C. Custom legal-pair reranker fine-tuned EUR-Lex**: sustituir `bge-reranker-v2-m3` por reranker propio. Inversión ML alta; requiere gold set N≥30 augmentado.

Cualquier alternativa pasa por probe N=5 (disciplina `feedback_cost_estimation_discipline.md`) antes de paid main A/B.

### Q4.9 i18n FR / DE / IT [M]

Sistema multilingüe en sitio (BGE-M3 multilingüe por diseño). Tarea: ingestar versiones lingüísticas adicionales de EUR-Lex, validar segmentador sobre titulares por idioma, traducir plantillas de prompt versionadas (CLAUDE.md §22.12). Activación cuando entre primer cliente fuera ES.

### Q4.10 GDPR DSR endpoints [S]

Ironía documentable: el sistema es primera línea compliance pero su gestión de datos personales (logs `case_id`, traces LangFuse) no expone derechos Capítulo III RGPD. Añadir `POST /gdpr/access`, `POST /gdpr/erasure`, `POST /gdpr/portability` autenticados por organización. Coherencia narrativa además de obligación legal.

## Open questions (validación de producto)

Nada del roadmap anterior tiene sentido sin estos tres ejes resueltos:

### Pricing model

- **€/mes per seat** (DPO + IT manager + responsable calidad = 3 seats típicos PYME 50-500): €29-€79/seat/mes (rango competitivo Iubenda / OneTrust SMB).
- **€ per query** (chat) + **€ per documento analizado**: €0.10-€0.50/query, €1-€5/doc; alineado con coste medido `cost_per_chat` €0.054 + `cost_per_doc` €0.078 ×3 margen ×escalado retry.
- **Tier híbrido** (subscription incluye N queries, overage per use): probablemente lo más alineado con uso real PYME.

Decisión condicional a entrevistas con 5-10 PYMEs piloto.

### Go-to-market

- **Direct**: marketing técnico (LinkedIn + comunidades compliance) + landing con demo viva (HF Spaces actual sirve).
- **Through compliance consultancies**: target secundario CLAUDE.md §4 (asesoría boutique que presta servicios a varias PYMEs). White-label opcional.
- **Marketplace MCP** (HX4 / Q3.2): canal pasivo de adquisición vía ecosistema Claude Desktop + IDEs.

Tracks compatibles; el orden depende de coste por adquisición medido en los primeros tres meses post-lanzamiento.

### Competitive landscape

- **Iubenda**: cookie consent + privacy policy generator; cubre RGPD básico para PYMEs digitales; no analiza documentos corporativos contra el corpus EUR-Lex.
- **OneTrust**: enterprise compliance suite; precio inaccesible PYME 50-500 y curva aprendizaje alta.
- **Custom in-house**: PYMEs grandes (>300 empleados) a veces tienen scripts Python con un LLM general-purpose; sin §6 ("no citation, no answer") + sin trazabilidad auditable.

RegulAItor compite por el segmento **PYME 50-500 + boutique compliance** que está fuera del alcance OneTrust y por encima de Iubenda. La pieza diferencial es la cita verificable invariante §6 + el modo análisis documental con sanitizer SSDLC.

## Priorización tentativa post-defensa

Mirror del orden tentativo de `docs/memoria_sections/19-roadmap-post-tfm.md` §19.13, sin compromiso:

1. **Q1 completo** (endurecimiento de producción + saneo técnico) — primeras 4-6 semanas post-deploy.
2. **Q2.2 frontend Next.js** en cuanto haya primer cliente piloto que justifique salir de Streamlit.
3. **Q3.2 HX4 MCP server externo** — bajo esfuerzo, alto valor visibilidad ecosistema MCP.
4. **Q4.4 expansión corpus EBA/ESMA** — necesario para responder DORA con cifras concretas.
5. **Q4.8 doc-mode HyDE** — requiere Q4.7 gold N≥30 primero.
6. **Q4.1 Prometheus + Grafana** — necesario para SLA y para superficie 3 del frontend.
7. **Q2.1 HX1 LoRA severidad** — solo cuando severidad sea bottleneck demostrado en producción.
8. **Q4.9 i18n FR / DE / IT** — cuando entre primer cliente fuera ES.
9. **Q4.5 cross-vendor judge** + **Q4.6 council expansion 5 jueces** + **Q4.10 GDPR DSR** — diferidos a vector de crecimiento concreto.

## §22.22 honesto sobre este roadmap

Nada de lo anterior está validado empíricamente: son carry-forwards documentados a lo largo del linaje, **no compromisos de scope ni promesas de calendario**. El TFM se defiende sobre lo medido y entregado en `v1.0.0`. Cualquier ejecución HX dependerá de que exista contexto real (cliente piloto, presupuesto, demanda) y se medirá con la misma disciplina §22.22 que ha definido el linaje hasta v0.1.32 (13 milestones consecutivos honestos + 2 REVERTs documentados, v0.1.23 y v0.1.30).

La frontera §6 ("no citation, no answer") es inviolable también en producto. Cualquier HX que la roce — particularmente Q2.1 LoRA si llega a tocar la decisión final, Q4.6 expansión Council si modifica binding, Q4.8 retrieval si requiere tocar `citation/validator.py` — pasa por nuevo ADR, justificación de evolución interpretativa explícita (precedentes ADR-0024 / ADR-0031 / ADR-0032 / ADR-0034) y validación pagada con probe N≥5 + main A/B siguiendo `feedback_cost_estimation_discipline.md`.

**La metodología sigue siendo la contribución también después del tribunal.**
