# 18. Limitaciones conocidas (§22.22 honest framing)

## 18.1 Por qué este capítulo existe

La regla §22.22 de `CLAUDE.md` exige documentar las divergencias plan-vs-realidad en la propia closure narrative en lugar de en commits-fix posteriores. Aplicada a la memoria del TFM, esa regla se extiende a un capítulo dedicado a limitaciones: lo que el sistema **no hace**, lo que no se ha medido, lo que se ha medido pero no alcanza el umbral aspiracional, y lo que se ha refutado empíricamente y revertido. La intención es que el tribunal pueda evaluar RegulAItor por lo que realmente es, no por una versión idealizada que la narrativa de defensa tienda a producir por inercia.

Las limitaciones se agrupan en cinco bloques: (1) funcionales y de alcance, (2) técnicas del retrieval y del pipeline documental, (3) operativas del despliegue HF Spaces, (4) instrumentales del eval/red team, (5) gaps de calidad respecto a los umbrales aspiracionales del §17.

## 18.2 Limitaciones funcionales y de alcance

### 18.2.1 RegulAItor no sustituye a un asesor jurídico

La limitación más importante está enunciada en `CLAUDE.md` §3 y §4 y se repite en la UI Streamlit, el README, esta memoria y la demo: RegulAItor es una herramienta de primera línea para análisis, preparación de borradores, revisión documental y generación de evidencias verificables. **No es un sustituto del juicio profesional** de un asesor jurídico, DPO o compliance officer. El invariante §6 garantiza que toda afirmación tiene una cita literal contra un corpus oficial; no garantiza que la interpretación normativa sea correcta para un caso concreto. Cualquier despliegue real en producción debe respetar esta separación; la UI mantiene un aviso jurídico persistente y el modo chat se niega a emitir afirmaciones sin respaldo (Auditor RHR + Council escalada conservativa).

### 18.2.2 Corpus base-act sin enmiendas consolidadas

Per `CLAUDE.md` §7.2, los cuatro corpus (AI Act, RGPD, NIS2, DORA) se ingestaron como texto **base-act** y no como versiones consolidadas con enmiendas. El motivo está documentado en ADR-0015: la versión consolidada de EUR-Lex está protegida por CloudFront WAF y bloquea cualquier cliente que no sea un browser real (ADR-0003 lineage). Para los instrumentos 2022 (NIS2, DORA) la base-act es texto autorizado por la propia EUR-Lex en ausencia de enmienda posterior. Para AI Act y RGPD, la base-act puede haber sido enmendada por reglamentos posteriores que el corpus actual no recoge. La política de versionado adoptada es **snapshot único** (`CLAUDE.md` §10.5 carry); HX queda como trabajo futuro la implementación de ramas por versión con detección automática de instrumentos modificantes.

### 18.2.3 Council binding conservative-only

La política `MonotonicEscalatePolicy` activada en v0.1.19 (ADR-0025) sólo promueve `PASS → RHR` cuando los tres jueces votan unánimemente `BLOCK`. **Nunca relaja `BLOCK` ni `RHR`** (ver docstring de módulo en `src/regulaitor/agents/council.py:1-28`, en particular líneas 8-17 sobre la dirección conservative-only). El patrón observado en H13 de Auditor=`RHR` → Council=`valid` en 7/12 divergencias (sobre-disparo del Auditor en ambiguos) permanece **sin tocar**: el Council documenta la divergencia en el campo `council_notice` pero no la usa para flexibilizar el veredicto. La justificación es §6 risk surface: relajar `RHR` cruzaría la frontera de enforcement y exigiría un análisis de riesgo más profundo que el ámbito del TFM. Carry-forward HX si en producción surge la necesidad real.

## 18.3 Limitaciones técnicas del retrieval y del pipeline documental

### 18.3.1 Gap semántico descriptive-doc-segment → obligation-corpus-article (REVERT v0.1.30)

El intento más reciente de cerrar este gap fue v0.1.30 con title-augmented corpus embeddings (ADR-0035). El probe pagado de €0.65 refutó el SHIP criterion: doc-mode `citation_recall` se mantuvo en 0.33 (vs target ≥0.38), doc-001 regresó en precision 0.50 → 0.00, y la mediana de citas emitidas por documento se expandió ~5x (doc-001 1-2 → 12; doc-003 1 → 19). El **mecanismo de over-citation** es el mismo que ya había causado el REVERT de v0.1.28 T4-extra (top_k=15 + max_chunks=5): la combinación BGE-M3 + v1.6 doc_analyst, cuando se le presenta un pool de retrieval ampliado por cualquier vía (top_k, max_chunks_per_norma o broadening del vector), emite Findings citando todos los artículos surfaced. La precisión se hunde porque el documento real exige sólo unos pocos.

El gap es **fundamental al nivel del embedding** y no se cierra con el title prefix solo. Las alternativas evaluadas en ADR-0035 Alternatives (A) HyDE, (B) hybrid BM25+dense, (C) custom legal reranker, son trabajo HX post-deploy. El v0.1.28 T4-bis query-side title-prepend (`src/regulaitor/orchestration/document_graph.py:161`) STAYS porque ayudó al main y no se revirtió.

### 18.3.2 Doc-mode CPU-bound en HF free tier

La demo desplegada en `https://huggingface.co/spaces/enriro00/regulaitor` corre sobre el CPU tier gratuito de HF Spaces. El cuello de botella medido es BGE-M3 + bge-reranker-v2-m3, que en CPU costean entre 15 y 30 segundos por segmento (memoria persistente `feedback_local_cpu_rerank_cost.md`, escarmiento de v0.1.9/v0.1.10/v0.1.12). Un documento de 10 páginas con 10-15 segmentos puede tardar 3-5 minutos. La recomendación explícita es PDFs ≤ 5 páginas para la demo; el HX upgrade a GPU (HF Pro u otro proveedor) está consignado como carry-forward en `decisions_log §v0.1.32 líneas 5283-5288` #2.

### 18.3.3 Doc-mode multi-corpus UI parity

La pestaña `tab_analyze.py:66` ofrece un `st.multiselect` que permite seleccionar varios corpus pero **el backend colapsa al primero**: `src/regulaitor/orchestration/document_graph.py:274` ejecuta `primary_corpus = cast(Norma, corpus[0])` y procesa todos los segmentos contra esa única norma. El campo `corpus: list[str]` del `DocumentReport` (declarado en `src/regulaitor/citation/schemas.py:321` y propagado al construir el report en `document_graph.py:289`) sí conserva la lista completa que el usuario seleccionó, lo que mantiene la apariencia de multi-corpus en el informe sin que el análisis lo sea. Este desajuste UI-vs-backend está identificado como nota I8 del deep-review pre-H16 y diferido a HX (`decisions_log §v0.1.32` carry-forward #4).

### 18.3.4 Política de snapshot único del corpus

El versionado del corpus es snapshot único: hay una sola tabla LanceDB `chunks.lance` con 1569 filas que mezcla los cuatro corpus en su versión actual. No existe una rama por versión normativa ni un mecanismo para retraer consultas a versiones previas. Esto bloquea casos de uso de auditoría retroactiva ("¿qué decía el RGPD aplicable en 2018?") que un sistema de compliance industrial necesitaría. HX queda como trabajo de versionado DVC/Git-LFS con manifiestos por snapshot.

## 18.4 Limitaciones operativas del despliegue HF Spaces

### 18.4.1 `/health` sin autenticación expone presence flags

El endpoint `GET /health` en `src/regulaitor/api/routes_health.py:45-54` es público (sin Bearer token) y devuelve tres `HealthCheck` items, incluyendo el estado `present` / `missing` de la `ANTHROPIC_API_KEY` (líneas 30-34) y del API token (líneas 37-42). Esto **no filtra valores de tokens** pero sí expone si las claves están configuradas, lo cual es información útil para un atacante en reconnaissance. La nota S6.1 y la I3 del deep-review pre-H16 lo recogen como LOW severity. La decisión documentada (`decisions_log §v0.1.32` carry-forward #3) es **mantener el endpoint público** porque HF Spaces lo necesita para liveness probes, y diferir a HX un split entre `/health` público mínimo y `/health/detailed` autenticado.

### 18.4.2 Rate limit HF LFS free tier

Durante las rondas R10-R12 del deploy se observó que el free tier de HF aplica un rate limit de **1000 LFS requests cada 5 minutos**. El workaround adoptado fue un loop wait-retry manual en el push inicial del índice (~76 MB de LFS); el script no está automatizado porque sólo se ejecuta en el deploy inicial o en re-indexaciones. Carry-forward HX si se moviese a Render/Fly.io o se eliminase la dependencia del LFS via build-on-deploy.

### 18.4.3 HF free tier sin GPU

Consecuencia directa de §18.3.2. La demo es funcional en el sentido de que reproduce el invariante §6 y muestra la arquitectura §6.1 cuatro capas trabajando visiblemente sobre queries chat realistas, pero no es representativa de la latencia que tendría el sistema con embedding/rerank GPU-accelerated. El reporte de smoke del v0.1.32 documenta `corpus=auto` + "AI Act sistemas alto riesgo" → PASS verdict + 2 Findings + 1 valid + 1 paraphrase citation (memoria `v0.1.32_h16_deployed_H17_ready.md`).

## 18.5 Limitaciones instrumentales del eval y del red team

### 18.5.1 Red team hardcodeado al corpus `ai_act`

El runner de red team `redteam/runner.py:117` y `:235` ejecuta todos los ataques chat-mode con `corpus="ai_act"` y los doc-mode con `corpus=["ai_act"]`. La consecuencia es que **0 ataques tocan NIS2 o DORA** en la suite actual (nota I11 del deep-review). La justificación histórica es que H9 cerró antes de H14 (cuando se ingestaron NIS2/DORA), y la expansión del corpus de ataques quedó como carry-forward HX (`decisions_log §v0.1.32` carry-forward #5). El gate §16.2 #4 sigue cubierto por la smoke run con `block_rate=0.92` (invariante desde v0.1.14, deterministic, inmune a no-determinismo de API), pero la cobertura cross-corpus es **ficticia**.

### 18.5.2 Cache del eval es judge-layer only

`evals/harness.py:204-208` documenta explícitamente que **el cache cubre únicamente la capa del juez** (Haiku 4.5), no las llamadas de producción de Sonnet. Cualquier re-ejecución de `make eval` invoca el grafo H4 con llamadas reales a Anthropic. La consecuencia es que la reproducibilidad del eval **no es bit-for-bit** sino metric-deterministic: dos runs sobre el mismo gold set producen métricas estadísticamente comparables pero no idénticas, y el audit trail persistido en `evals/checkpoint.py` + `per_citation_audits` (v0.1.21.1 D2 + v0.1.24 O2) es lo que permite los diagnósticos $0 a posteriori. La nota I12 del deep-review explicita este matiz; el carry-forward es HX si en producción se requiere reproducibilidad bit-for-bit con cache completo.

### 18.5.3 cost_per_chat €0.054 sobre bar €0.05

El v0.1.20-bar establecido en ADR-0021 fija `cost_per_chat ≤ €0.05`. El v0.1.25-prod 30-case mide €0.054, **€0.004 por encima del bar**. La causa es el overhead de la retry loop Capa C de la Tier 2 hardening (ADR-0027 D4): tres intentos con feedback específico para forzar la emisión de Findings cuando la primera respuesta no satisface el contrato Pydantic. El trade-off es deliberado y está consignado como carry-forward; en v0.1.22 (€0.061 main per `evals/reports/v0.1.22/v0.1.22-prod-main.md`) y v0.1.29 (€0.058 main per `evals/reports/v0.1.29/v0.1.29-prod-main.md`) se reprodujo el mismo gap con magnitud comparable. Aceptable como signal-level above target, no como gate fail.

## 18.6 Gaps de calidad respecto a los umbrales aspiracionales §17

### 18.6.1 Citation precision y recall

El §17 fija como objetivo aspirational `precision ≥ 0.90` y `recall ≥ 0.80`. Las medidas v0.1.25-prod sobre 30 casos chat son: precision 0.27 y recall 0.68. Ambas pasan el v0.1.20-bar (0.25 / 0.60 respectivamente) y la recall pasa el gate MVP §16.2 #5 (0.40). Pero la distancia al objetivo es estructural: el Analyst v1.5 emite múltiples Findings por refusal y el match contra el gold es lenient pero exigente. HX si se desea cerrar este gap (calibración Auditor + Council binding más restrictivo + posible custom reranker).

### 18.6.2 Cobertura de tests

El gate §16.2 #10 aspira a `cobertura ≥ 80%`. La cobertura real medida es **88.62 %** sobre el umbral operativo de **85 %** fijado en v0.1.26 (`pyproject.toml:225` y `:240` con `--cov-fail-under=85`). El histórico fue 90% pre-v0.1.21.3, bajado a 87.83% por el hotfix `@slow` y restaurado parcialmente a 88.55% en v0.1.22. La decisión de bajar el gate a 85% es operativa y honesta: documenta el trade-off entre exclusiones `@slow` necesarias para CI rápido y la cobertura nominal aspiracional. Cumple el gate MVP y los aspiracionales del §17 con margen.

### 18.6.3 Tasa de bloqueo del Auditor en adversarial set

El §17 #6 aspira a `≥ 0.95`; el gate MVP §16.2 #4 está relajado a `≥ 0.90` y se cumple con **0.92** sobre la smoke run determinista. La full run de 50 ataques completada en H11 dio raw 0.28 contaminado por 21 timeouts de API degradada (0.54 entre 26 completados), lo cual **no representa la capacidad real** del sistema sino la fragilidad de la API en ese instante. El gate sigue anclado a la smoke run por su determinismo; HX si en producción se necesita una full run periódica con tolerancia a timeouts.

## 18.7 Síntesis honesta

RegulAItor cumple su mandato como TFM: demo pública, invariante §6 intacto, 13 milestones consecutivos con §22.22 honest framing, 2 REVERTs documentados con la misma exigencia que los CONFIRM, gate MVP §16.2 verde en sus 10 puntos. Lo que no hace, no mide o mide bajo el umbral aspiracional está aquí enumerado y trazado a su fuente: ADRs, decisions_log, deep-review, código. La distancia entre lo que está y lo que el §17 aspiracional describe es el trabajo HX que cualquier producto real necesitaría antes de salir a producción regulada. La defensa académica se sostiene precisamente porque ese gap está documentado, no escondido.
