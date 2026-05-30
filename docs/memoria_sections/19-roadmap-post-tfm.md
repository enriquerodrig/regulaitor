# 19. Roadmap post-TFM (producto real en mercado)

## 19.1 Encuadre: del artefacto académico al producto

El cierre del TFM en `v1.0.0` no agota el trabajo; lo congela en un estado defendible. La preferencia expresa del autor durante el ciclo H15-H16 es **track A "future product"**: tratar RegulAItor como cimiento de un producto real para PYMEs y boutiques de compliance europeas, en lugar de cerrar la línea con la defensa. Este apartado recoge los carry-forwards documentados a lo largo del linaje H0 → v0.1.32 (CLAUDE.md §15.3 + §16.4) y los organiza en bloques de trabajo coherentes con riesgo, dependencia y valor para el usuario final descrito en CLAUDE.md §4 (responsable de calidad, DPO o IT manager en PYME 50-500 empleados).

La regla §22.22 sigue aplicando aquí en clave honesta: este roadmap **no es un compromiso de ejecución**. Es la consolidación del backlog razonable post-defensa; cada bloque queda explícitamente etiquetado como deseable, recomendado o condicional, y la priorización real dependerá de evidencia post-deploy (tráfico real, feedback del primer cliente, restricciones de presupuesto).

## 19.2 HX1 — Clasificador de severidad LoRA

CLAUDE.md §10.4 + §15.3 + §22.17 anclan este bloque. La idea es fine-tunear Llama-3.1-8B con un adaptador LoRA sobre el campo `severity` del `Finding` (escala `info` / `low` / `medium` / `high`) para sustituir la asignación actual del Analyst — basada en heurísticas del prompt — por un clasificador determinista barato. La motivación es doble: bajar latencia (eliminar un round-trip a Sonnet sólo para severidad) y mejorar el `severity_match` aspiracional (medido 0.43 en `evals/reports/v0.1.29/v0.1.29-prod-main.md`, lejos del objetivo ≥0.80 §17 #7-extendido).

El bloque exige cumplir CLAUDE.md §22.17 ("No implementes LoRA antes de tener gold set y baseline"), satisfecho desde H8. La skill `lora-finetune-recipe` queda definida en §12.4.11 como receta reproducible; su activación se difiere a HX. Dependencias mínimas: dataset etiquetado ≥500 `Finding` reales (gold set actual aporta ~120; falta etiquetado in-corpus + datos sintéticos auditados); GPU runtime (HF Pro o servicio externo); pipeline de evaluación específico para severidad (matriz de confusión + macro-F1 + análisis por norma).

Riesgo principal: la severidad legal es **contextual al cliente** (un hallazgo "medium" para un fintech puede ser "high" para un hospital). La especificación HX1 debe contemplar fine-tunes per-vertical o feature de calibración por organización.

## 19.3 HX2 — Frontend Next.js triple superficie

CLAUDE.md §10.1 + §15.3 + §22.16 documentan la pieza. Streamlit cubrió el modo demo en H6 y la demo pública en H16 (`https://huggingface.co/spaces/enriro00/regulaitor`), pero arrastra limitaciones identificadas en el deep-review pre-H16 e iteración R8 + R11 (doc-mode parity multi-corpus colapsa al `corpus[0]`; warmup explícito necesario porque Streamlit carece de lifespan; theming limitado por la reescritura de headers del reverse proxy de HF — ver `docs/memoria_sections/16-despliegue.md` §16.2).

La especificación HX2 es Next.js 14+ con App Router, server components, Tailwind sobrio + shadcn/ui (skill `next-frontend-architect`, §12.4.14). Tres superficies coherentes:

1. **Chat**: equivalente moderno de `tab_ask`, con streaming de respuesta, chips de corpus dinámicos (R13 ya prototipó la idea en Streamlit) y panel de citas plegable con verdict badge prominente (R12 lineage).
2. **Análisis documental**: drag-and-drop multi-fichero, progreso por segmento (visible porque BGE-M3 en CPU es lento — ver `feedback_local_cpu_rerank_cost.md`), informe Markdown descargable y export PDF (skill `pdf` oficial Anthropic).
3. **Dashboard de cumplimiento**: agregado por cliente (multi-tenant; ver §19.7) con métricas de citation accuracy real, latencia p95, coste acumulado y tasa de bloqueo. Es el activo que diferencia "demo" de "producto".

WCAG 2.2 AA es requisito no negociable (CLAUDE.md §12.4.14); el TFM mismo no lo audita formalmente, pero la skill define el procedimiento. La regla §22.16 ("No implementes Next.js antes de cerrar Streamlit, evaluación y red team") queda satisfecha post-H17.

## 19.4 HX3 — Webhook + GitHub Action

Conector CI minimalista: una GitHub Action que, al abrir o actualizar un PR, llama a `/analyze` sobre la descripción y los ficheros tocados (o sobre un PRD adjunto) y publica como comentario los `Finding` con severidad `high` que afectan a normas AI Act / RGPD / NIS2 / DORA. El target son equipos producto que iteran rápido y quieren un primer filtro automático de "¿esta funcionalidad introduce un sistema de IA de alto riesgo que requiere DPIA?" antes de pasar a revisión legal humana.

La pieza es prima del Modo API (CLAUDE.md §5.3): reutiliza `POST /analyze` sin tocar el backend. Webhook genérico (Slack, Linear, GitHub) sigue el mismo patrón con autenticación HMAC mutua. Riesgo: el formato de la entrada (texto suelto vs PRD estructurado vs commit diff) condiciona qué tan útil es el output; debería empezar limitado a un formato (`.md` PRD) y ampliar tras feedback. La skill `secure-coding-checklist` (CLAUDE.md §12.3.10) cubre el endurecimiento del endpoint webhook.

## 19.5 HX4 — Servidor MCP externo en marketplace

El MCP server propio (CLAUDE.md §9, ADR-0005) vive embebido en `src/regulaitor/mcp_server/` y expone cinco tools (`search_articles`, `fetch_article`, `validate_citation`, `extract_document`, `segment_document`). Está validado por tests de contrato y ya consumible localmente. HX4 lo desacopla en un repositorio separado y lo publica en el MCP marketplace para que Claude Desktop, IDEs (Cursor, Continue, JetBrains MCP) y cualquier orquestador compatible puedan integrar RegulAItor como tool externo.

El valor para el usuario primario (CLAUDE.md §4) es que su equipo IT puede preguntar a su asistente de IA "¿qué artículo del AI Act regula la supervisión humana?" y obtener una respuesta del corpus oficial con cita verificada, sin abrir RegulAItor explícitamente. Riesgo principal: rate limiting + facturación; el marketplace expone el server a tráfico no autenticado de terceros, lo que requiere un capa de tokens por instalación (heredando el patrón Bearer de `src/regulaitor/api/auth.py:1`) y observabilidad de quién consume qué.

## 19.6 HX5 — Observabilidad avanzada con Prometheus + Grafana

H11 dejó la observabilidad en `LANGFUSE_*` opcional (ADR-0012) con egress redactado y no-op cuando las variables no están. HX5 añade el siguiente nivel: Prometheus para series temporales reales — citation accuracy diaria sobre tráfico (no sobre gold set), latencia p50/p95/p99 por endpoint, coste acumulado por modelo, tasa de bloqueo Auditor por corpus — y Grafana para visualización. Alertas configurables: tasa de bloqueo >0.3 sostenida durante 1h (potencial bug del Analyst); coste/día sobre umbral; latencia p95 sobre SLA.

Es el componente que cierra el dashboard de cumplimiento (§19.3 superficie 3) con datos reales y satisface el módulo M3 del Máster en su versión avanzada (CLAUDE.md §24 M3). La skill `cost-accounting` (§12.4.15) materializa la facturación por organización; se activará en H17 para el `docs/cost_analysis.md` académico pero su uso real es producto.

## 19.7 Endurecimiento de producción

Conjunto de tareas tactíticas, todas heredadas como carry-forwards documentados:

- **Split de autenticación en `/health`** (deep-review I3; carry-forward HX confirmado en este H17 cierre académico). El handler actual expone los mismos datos a no autenticados que a autenticados (presencia/ausencia de `anthropic_key`, `api_token`, estado LanceDB). La separación posible es `/health` público y minimalista (200 OK + versión) más `/health/detailed` detrás de `Depends(verify_token)` con check de LanceDB, Anthropic upstream y cache hit ratio. La nota S6.2 de `docs/pre_h16_review.md:45` apunta a la línea de ampliar `/health` con check upstream Anthropic con fail-open.

- **Multi-tenant token management**. Hoy `REGULAITOR_API_TOKEN` es un secreto único compartido (`src/regulaitor/api/auth.py:1`); para producto, reemplazarlo por tokens por organización con audit log persistente, scopes (`/ask`, `/analyze`, `/health/detailed`) y cuota mensual. Implica migrar metadatos a Postgres (CLAUDE.md §10.1 lo cita como condicional).

- **i18n completo**. RegulAItor opera hoy en ES + EN porque el corpus EUR-Lex está cargado en esos dos idiomas (manifests `corpus/manifests/*.json`). EUR-Lex publica multilingüe oficialmente; añadir FR, DE e IT cubre los mercados grandes restantes de la UE y satisface a las multinacionales con presencia transfronteriza. El sistema multilingüe ya está en su sitio (BGE-M3 es multilingüe por diseño); la tarea real es ingestar las versiones lingüísticas adicionales, validar el segmentador sobre titulares en cada idioma y traducir las plantillas de prompt (registradas bajo `src/regulaitor/agents/prompts/<agent>/<role>.vN.M.md` con changelog per CLAUDE.md §22.12).

- **GDPR DSR endpoints**. Ironía documentable: el sistema es primera línea de compliance pero su propia gestión de datos personales (logs de consultas con `case_id`, traces LangFuse opcionales) no expone los derechos de acceso, supresión y portabilidad del Capítulo III RGPD. Añadir `/gdpr/access`, `/gdpr/erasure`, `/gdpr/portability` autenticados por organización es trabajo de coherencia narrativa además de obligación legal.

- **Cost monitoring per-tenant**. La instrumentación de coste hoy es process-level (acumulador `models/router.py`, H15 D2; ADR-0013 + ADR-0016). Para producto, multiplicar por `org_id` y permitir budgets con cut-off automático antes de overrun.

- **SLA real**. Latencia p95 + uptime + RPO/RTO. El TFM declara objetivos §17 #7 (latencia p95 ≤8s avanzado) pero los mide en condiciones de batch eval con rate-limit interno. Producción real medida con LangFuse + Prometheus de §19.6 es lo que permite negociar SLA con clientes empresa.

- **Migración a Postgres**. SQLite cubre MVP académico (`src/regulaitor/api/`). Producto multi-tenant + audit log persistente + cuota por org necesita Postgres por concurrencia y por el patrón de queries (joins por `org_id`).

## 19.8 Expansión de corpus

Cuatro líneas paralelas, todas heredadas de CLAUDE.md §7 + H14:

1. **NIS2 y DORA enmiendas consolidadas**. H14 ingestó las base-acts (CELEX `32022L2555` y `32022R2554`) porque las versiones consolidadas estaban bloqueadas por el WAF CloudFront de EUR-Lex (ADR-0015 + ADR-0003 lineage). La consolidación se publica con desfase; en HX hay que reintentar periódicamente — programable como cron job que reusa el patrón Playwright headless de H14.

2. **EBA / ESMA technical standards**. DORA delega plazos de notificación de incidentes a RTS (artículo 19 y siguientes; H14 documentó "plazos 4h/24h/72h no están en art 19 sino delegados a RTS art 20"). Sin ese contenido, RegulAItor responde con generalidades sobre "los plazos los fija el RTS aplicable" en lugar de citar plazos concretos — limitación real medida en el gold case dora-003 (CLAUDE.md §H14 caja de errores corpus-ground del code-review).

3. **Directivas AML 4/5/6**. La línea de prevención de blanqueo es transversal a fintech / banca / cripto; cubre un caso de uso adyacente que reutiliza la misma arquitectura.

4. **Implementaciones jurisdiccionales**. España transpone NIS2 mediante RD pendiente y RGPD mediante LOPDGDD; Alemania, Francia e Italia tienen sus propias capas. El corpus español BOE es el primero natural (idioma, mercado primario del autor); requiere parser específico (BOE no usa el mismo HTML estructurado que EUR-Lex).

## 19.9 Doc-mode retrieval engineering

ADR-0035 §REVERT cerró el intento naïve de title-augmented corpus embeddings (v0.1.30); la lección documentada (`docs/adr/0035-title-augmented-corpus-embeddings.md:170-176`) es que **la ampliación de "amplitud" en retrieval — vía top_k, max_chunks_per_norma o vectores con prefijo de título — dispara el v1.6 doc_analyst a sobre-emitir y hunde la precisión**. El gap descriptive-doc-segment → obligation-corpus-article es fundamental al nivel de la embedding y no se cierra con prefijos.

Carry-forwards documentados como alternativas A-C en ADR-0035:

- **HyDE (Hypothetical Document Embeddings)**. Pedir al LLM que redacte una "respuesta regulatoria hipotética" del segmento, y usar esa hipótesis como query. Coste estimado +€0.005-€0.01 por query. Es la alternativa más prometedora porque opera en query-side (donde ya sabemos que el title-prepend ayudó, ADR-0033 T4-bis), no en corpus-side (donde sabemos que dilata).

- **Hybrid BM25 + dense**. Score fusion (RRF) de retrieval léxico clásico y semántico denso. Integración con `tantivy` o `rank-bm25`. Complementaria con HyDE.

- **Custom legal-pair reranker fine-tuned EUR-Lex**. Sustituir `bge-reranker-v2-m3` por un reranker propio entrenado sobre pares (segmento-corporativo, artículo-aplicable). Inversión ML alta; requiere bootstrapping con el gold set actual augmentado.

Pre-requisito común: **gold set documental N≥30**. El actual N=10 (`evals/gold_set.jsonl` doc-* casos) tiene ruido floor ~20% (lección v0.1.23 §REVERT), insuficiente para decidir con confianza alta. HX1-HX5 retrieval depende de tráfico real o de inversión específica en extender el gold a una decena de docs por sector (hospital, fintech, cloud, RRHH, ed-tech).

Infraestructura: HF Pro upgrade (~€9/mes) o GPU Render para acelerar BGE-M3 a inference rápido. Sin GPU, el reranker en CPU procesa cada segmento en ~15-30s sostenidos (`feedback_local_cpu_rerank_cost.md`).

## 19.10 Calibración del juez evaluador

ADR-0010 D1 dejó abierta la opción de cross-vendor judge migration (Haiku 4.5 → GPT-4o-mini vía OpenAI o Llama-3.3-70b vía Groq) para reducir bias de "modelo juez del mismo vendor que el modelo evaluado". ADR-0021 lo resolvió como "stay Haiku en v0.1.16; cross-vendor a HX post-TFM" para preservar continuidad de cache H10 y satisfacer §19 ("modelo juez distinto al de producción") literalmente (Haiku 4.5 ≠ Sonnet 4.6, clase distinta).

HX10 es la migración real: ejecutar el harness completo con GPT-4o-mini como juez, comparar contra Haiku 4.5 baseline en H10 cohort, documentar diferencias y proponer migración si la correlación es alta. Riesgo: invalida la curva de aprendizaje cacheada (H8 onward); coste de re-eval ≥€10 sobre 64 cases × 3 modelos × N corridas estadísticas.

## 19.11 Expansión del Council of Judges

H13 (ADR-0014) introdujo Council 3-jueces (Haiku / GPT-4o / Llama-3.3) con `AdvisoryMajorityPolicy` y `MonotonicEscalatePolicy`. El binding activo desde v0.1.19 (ADR-0025) es conservador (PASS→RHR sólo en unanimidad 3/3 BLOCK). HX puede explorar:

- **5+ jueces** con voting weighted por proveniencia (jurídico fine-tuned vs generalista).
- **Supermajority policies** (4/5, 3/5) más allá de la unanimidad estricta.
- **Council adversarial** donde un juez recibe explícitamente el prompt "encuentra el fallo en este razonamiento".

Requiere infraestructura router multi-LLM ya existente y presupuesto adicional por consulta (~3-5× el coste base).

## 19.12 Mantenimiento técnico continuo

Trabajo no negociable de cualquier producto vivo:

- **Anthropic SDK 1.0 migration**. El SDK Anthropic todavía vive en major 0.x al cierre del TFM; la migración a 1.0 cuando se publique requiere re-validar el flujo de tool_use, el patrón `_set_additional_properties_false_recursive` de Capa A (ADR-0029) y la integración del Router.

- **Python 3.13 support**. CLAUDE.md §10.1 fija 3.11. Migrar a 3.13 (o la versión LTS vigente cuando toque) implica re-correr la matriz de tests + verificar `pyproject.toml` y CI.

- **Real-traffic measurement loop**. Tráfico real con opt-in telemetría es lo que permite freshening del red team set (CLAUDE.md §18: el set actual es 50 casos sintetizados; los ataques reales evolucionan) y construir gold set documental N≥30 sin sesgo del autor.

- **HF token rotation post-demo** [pendiente] — `docs/memoria_sections/16-despliegue.md` §16.6 y memoria del usuario `v0.1.32_h16_deployed_H17_ready.md` lo declaran como MUST ROTATE. Es la única deuda de seguridad operativa heredada por H17.

## 19.13 Priorización tentativa

Sin compromiso, ordenado por valor-para-primer-usuario / coste-de-implementación / dependencia-de-tráfico-real:

1. Endurecimiento mínimo de producción (§19.7 split `/health` + multi-tenant tokens) — semanas 1-2 post-deploy.
2. Frontend Next.js triple superficie (§19.3) en cuanto haya un cliente piloto que justifique salir de Streamlit.
3. HX4 MCP server externo (§19.5) — bajo esfuerzo, alto valor de visibilidad en el ecosistema MCP.
4. Expansión de corpus EBA/ESMA (§19.8 línea 2) — necesario para responder DORA con cifras concretas.
5. Doc-mode retrieval HyDE (§19.9 alternativa A) — requiere gold set N≥30 primero.
6. Observabilidad Prometheus + Grafana (§19.6) — necesario para SLA y para dashboard de §19.3 superficie 3.
7. HX1 LoRA severidad — sólo cuando la severidad sea bottleneck demostrado en producción.
8. i18n FR / DE / IT — cuando entre primer cliente fuera ES.
9. HX5 + HX10 + HX11 — diferidos a vector de crecimiento concreto.

## 19.14 §22.22 honesto sobre este roadmap

Nada de lo anterior está validado empíricamente: son carry-forwards documentados a lo largo del linaje, no compromisos de scope ni promesas de calendario. El TFM se defiende sobre lo medido y entregado en `v1.0.0`. Cualquier ejecución HX dependerá de que exista contexto real (cliente piloto, presupuesto, demanda) y se medirá con la misma disciplina §22.22 que ha definido el linaje hasta v0.1.32. La frontera §6 ("no citation, no answer") es inviolable también en producto; cualquier HX que la roce — particularmente HX1 LoRA si llega a tocar la decisión final, HX9 expansión Council si modifica binding, HX retrieval si toca el validador — pasa por nuevo ADR, justificación de evolución interpretativa explícita (precedentes ADR-0024, ADR-0031, ADR-0032, ADR-0034) y validación pagada. La metodología sigue siendo la contribución también después del tribunal.
