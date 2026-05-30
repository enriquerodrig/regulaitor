# 07. Sistema multi-agente (Retriever + Analyst + Auditor + Council)

RegulAItor se organiza como un pipeline de agentes especializados con responsabilidades estrictamente delimitadas, conforme a CLAUDE.md §8. La cadena canónica del modo chat es Retriever → Analyst → Auditor → (opcional) Council, orquestada con LangGraph (ADR-0006). El principio rector "no citation, no answer" (§6) no es una propiedad emergente del conjunto sino una garantía mecánica codificada en el Auditor y reforzada en capas adicionales por encima (esquema Pydantic, prompts, Council de jueces). Cada agente tiene un único motivo para cambiar, una superficie de E/S Pydantic v2 frozen, y un contrato verificable con tests unitarios.

Esta sección describe los cuatro agentes en el orden en que intervienen, documenta el versionado de prompts del Analyst (v1.0 → v1.6), detalla la arquitectura multicapa del Auditor que evolucionó entre v0.1.19 y v0.1.29, y explica la promoción del Council de "advisory" (H13) a "binding conservador" (v0.1.19).

## 1. Retriever-Agent — adaptador fino y sin razonamiento jurídico

El `RetrieverAgent` (src/regulaitor/agents/retriever.py:18) es un adaptador stateless entre el estado LangGraph y el helper canónico `rag.retrieval.run` (o `run_auto` cuando el cliente pide selección automática de corpus). Su contrato:

- Entrada: `query: str`, `corpus: CorpusSelector` (`"ai_act" | "gdpr" | "nis2" | "dora" | "auto"`), `language: Language` (`"es" | "en"`), `top_k: int | None` opcional.
- Salida: `Context` Pydantic frozen (src/regulaitor/citation/schemas.py:71) que envuelve `chunks: list[RetrievedChunk]`, `embedding_model: str`, `resolved_normas: list[Norma]` y `retrieved_at: datetime`.

El agente **no llama a ningún LLM y no razona**. Esta disciplina es deliberada (CLAUDE.md §8.1): permite que la capa de retrieval (BGE-M3 + bge-reranker-v2-m3 + LanceDB) sea reemplazable sin tocar el grafo y, sobre todo, hace que cualquier hallazgo emitido posteriormente por el Analyst pueda trazarse a un conjunto cerrado y reproducible de chunks. El campo `resolved_normas` documenta qué corpus se materializaron tras el modo `auto` (relevante para preguntas cross-corpus tipo "¿qué obligaciones aplican a una fintech con IA y datos personales?"). Las decisiones de retrieval (purity gate, dedup per-article, dedup per-norma, top_k_auto) viven en `RetrievalConfig` (ADR-0017, ADR-0028) y son ortogonales al agente: éste sólo expone el seam `top_k` para casos especiales.

## 2. Analyst-Agent — generación estructurada vía tool use

El `AnalystAgent` (src/regulaitor/agents/analyst.py:96) produce un `Answer` Pydantic frozen mediante el patrón Anthropic tool use, garantizando salida estructurada SDK-validated (ADR-0006 — alternativa "JSON mode" rechazada por fragilidad del parser de prosa). Carga un prompt versionado desde `src/regulaitor/agents/prompts/<role>/system.vN.M.md` y delega la llamada al LLM al `router` (src/regulaitor/models/router.py). Ningún agente llama directamente a un proveedor (CLAUDE.md §13).

### 2.1 Selección de prompt por rol y versión

El constructor acepta `prompt_role: Literal["analyst", "document_analyst"]` y `prompt_version: str | None`. Cuando la versión es `None`, el seam de entorno `REGULAITOR_ANALYST_PROMPT_VERSION` decide; si está unset, se aplica el default por rol (src/regulaitor/agents/analyst.py:125):

- `analyst` → **v1.5** (default desde v0.1.21 closure C4, ADR-0027; v0.1.20 flipó previamente v1.0 → v1.4 per ADR-0026 y la C4 final-review encadenó el segundo flip v1.4 → v1.5 para compatibilidad con las hard constraints Capa A+B).
- `document_analyst` → **v1.6** (default desde v0.1.28, ADR-0033).

Una versión inválida en el env cae a v1.0 con un warning (nunca crashea por mala configuración).

### 2.2 Linaje de prompts del rol chat (v1.0 → v1.5)

El versionado sigue la skill `prompt-versioning` (CLAUDE.md §12.3.4). Cada versión vive como archivo separado, con frontmatter YAML que enumera cambios y `model_compatibility`.

- **v1.0** (H4, 2026-05-05): prompt inicial con reglas duras 1-5 (cita literal, idioma del usuario, sin alucinar artículos, sin asesoramiento jurídico definitivo).
- **v1.1 / v1.2** (H15, 2026-05-18): intervenciones quirúrgicas (A) regla minimum-citation y (B) hardened output contract / structured refusal. v1.2 sustituye a v1.1 tras un probe direccional que detectó "teaching-to-the-grader".
- **v1.3** (v0.1.15, ADR-0020): añade Hard Rule 8 (detección NL del gap-analysis chat-mode: declaración + pregunta gap-seeking → modo "qué me falta"; ambiguo → Q&A por seguridad).
- **v1.4** (v0.1.17.1, ADR-0023): añade Hard Rule 9 (force-Finding-emission cuando `text` contiene afirmaciones sustantivas; self-check explícito); responde al hallazgo "prose-without-findings" del diagnóstico cache-mining `scripts/diagnose_no_answer.py`.
- **v1.5** (v0.1.21 closure C4, ADR-0027; v0.1.20 ADR-0026 había flipado v1.0 → v1.4 primero, y la C4 final-review encadenó v1.4 → v1.5): convierte el patrón de refusal `findings: []` (incompatible con las hard constraints Capa A+B de v0.1.21) en un Finding-based refusal con exactamente 1 `Finding`, citación a un chunk real del contexto recuperado y `severity="high"`. Preserva §6 por construcción ("no citation, no answer" se cumple mediante refusal anclado al corpus, no mediante respuesta vacía). El Example 4 del prompt (src/regulaitor/agents/prompts/analyst/system.v1.5.md:264) ilustra el patrón frente a un intento de prompt-injection.

### 2.3 Linaje de prompts del rol documental (v1.0 → v1.6)

- **v1.0** (H5, 2026-05-07): prompt inicial doc-mode. Reglas inviolables data-not-instructions + no-citation-no-answer. Permitía `findings: []` cuando el segmento no era analizable.
- **v1.6** (v0.1.28, ADR-0033): adapta v1.0 a las hard constraints de v0.1.21. El probe v0.1.27 reveló que v1.0 + Capa B (`min_length=1` en `findings`) generaba el **placeholder citation bug** — el LLM emitía `articulo="<UNKNOWN>"`, `"N/A"` o `"TBD"` para satisfacer el esquema cuando no podía analizar el segmento; el validator rechazaba (Check 1 fabrication) y los 3/3 documentos del probe terminaron en BLOCK. v1.6 ataca el problema en **dos planos**: añade Rule 2 Finding-based refusal (mirror del v1.5 chat) que cita el artículo de ámbito del corpus (AI Act art. 2, GDPR art. 2, etc.), y añade Hard Rule 4 inviolable que **prohíbe explícitamente** strings placeholder. Esta regla constituye la "Capa (d) prompt-level explicit forbid" de la arquitectura §6 multicapa (CLAUDE.md §6.1).

### 2.4 Capa A + Capa B + Capa C — hard constraints sobre `findings`

ADR-0027 introdujo en v0.1.21 tres defensas concéntricas contra la salida `findings: []`:

- **Capa A** (Anthropic strict mode + `minItems: 1`): el helper `_strip_unsupported_schema_fields` (src/regulaitor/agents/analyst.py:57) marca el tool `emit_answer` con `"strict": True` e inyecta `"minItems": 1` en la propiedad `findings`. La función `_set_additional_properties_false_recursive` recorre el JSON Schema y fija `additionalProperties: False` en cada subschema de tipo `object` (root, nested y `$defs`). Este recursor se shipped en v0.1.22 (ADR-0029): la versión inicial sólo fijaba la propiedad en la raíz, dejando que `$defs` Finding+Citation fueran rechazados por la API con 400 → 100% RHR durante ~12 horas (broken-fail-safe per §6; documentado §22.22 verbatim).
- **Capa B** (Pydantic): `Answer.findings: list[Finding] = Field(min_length=1)` (src/regulaitor/citation/schemas.py:128). Defense-in-depth server-side: si Capa A está degradada, Pydantic atrapa el vacío y lanza `ValidationError`.
- **Capa C** (retry con feedback específico): bucle de hasta 3 intentos en `AnalystAgent.analyze` (src/regulaitor/agents/analyst.py:156). En cada `ValidationError` se construye un `tool_result` con `is_error=True` y un texto de feedback derivado del tipo concreto de error. La función `_build_retry_feedback` (src/regulaitor/agents/analyst.py:265) clasifica el fallo en cuatro buckets — findings missing/empty; citations malformadas dentro de un Finding; `text` vacío; fallback genérico — y devuelve instrucciones accionables citando el primer error. El refinamiento I2 de deep-review (post-v0.1.32) reemplazó un mensaje hardcodeado por la rama por-bucket actual, honrando el mandato ADR-0027 D4 "failure-specific feedback".

Si las tres capas fallan tras 3 intentos, se levanta `RuntimeError` preservando el comportamiento hard-fail H8. El Auditor sólo actúa sobre la salida válida si los intentos 1 ó 2 tuvieron éxito.

## 3. Auditor-Agent — el componente diferencial

El `AuditorAgent` (src/regulaitor/agents/auditor.py:51) es pure-Python determinista. Recibe un `Answer` y devuelve un `AuditedAnswer` con `verdict ∈ {PASS, BLOCK, REQUIRES_HUMAN_REVIEW}`, la lista completa de `AuditResult` por citación, y un `reason` legible para humanos. El método central `audit` (src/regulaitor/agents/auditor.py:54) valida cada `Citation` invocando el validator §6 y agrega según una política multicapa que ha evolucionado en cuatro hitos consecutivos (v0.1.21 → v0.1.24 → v0.1.25 → v0.1.29).

### 3.1 Arquitectura §6 multicapa

La sección 6.1 de CLAUDE.md formaliza la arquitectura en cuatro capas (a/b/c/d) y obliga a documentar cada modificación en su ADR + decisions_log:

- **Capa (a) — Per-citation validator** (`src/regulaitor/citation/validator.py`). Los tres checks estrictos canónicos (article_exists / apartado_exists / text_normalized_match) con fail-fast en el primer fallo. **Byte-equivalent semantics desde H4** (ADR-0006); v0.1.24 ADR-0031 añadió el campo aditivo `failed_check: Literal[1, 2, 3] | None` como instrumentación (no participa en la decisión, sólo etiqueta qué check disparó el fallo). La skill `citation-validator` (CLAUDE.md §12.3.1) documenta el procedimiento canónico.
- **Capa (b) — Finding-Lenient aggregation** (src/regulaitor/agents/auditor.py:65). Un `Finding` pasa si **≥1 de sus citas** valida estrictamente. Esta semántica permite que un Finding bien fundado sobreviva a una citación accesoria mal pegada, sin que la respuesta entera se hunda. **Byte-unchanged desde v0.1.21**.
- **Capa (c) — Turn-level aggregation policy** (src/regulaitor/agents/auditor.py:87-135). Combina los veredictos por Finding en un veredicto de turno. Modificada en (1) v0.1.21 ADR-0027 D1 — quorum Tier 1 `n_invalid_citations >= 2` escala al all-pass-Findings a RHR; (2) v0.1.25 ADR-0032 D2 — partial-Findings sub-route puede pasar a PASS si todas las citas inválidas de los Findings bloqueados son `failed_check==3` (paráfrasis); (3) v0.1.29 ADR-0034 — mirror del anterior en la sub-route all-blocked-Findings.
- **Capa (d) — Prompt-level explicit forbid** (prompts/document_analyst/system.v1.6.md Hard Rule 4 + prompts/analyst/system.v1.5.md Rule 2). Defensa model-side complementaria a la Capa (a) validator-side.

El helper compartido `_all_blocked_findings_paraphrase_only` (src/regulaitor/agents/auditor.py:20) es el centro de las modificaciones v0.1.25 y v0.1.29. Sólo retorna `True` cuando **toda** citación inválida de **todo** Finding bloqueado tiene `failed_check == 3`; cualquier Check 1 (article fabrication) o Check 2 (apartado fabrication) retorna `False`, preservando el routing original. Por construcción la fabricación nunca puede ser PASS.

### 3.2 Las tres ramas del agregador de turno

El método `audit` materializa una decisión en tres ramas mutuamente exclusivas (src/regulaitor/agents/auditor.py:87-135):

1. **All-pass-Findings** (todos los Findings pasan a nivel Lenient): si `n_invalid_citations >= 2` → RHR vía quorum Tier 1 (ADR-0027 D1); en caso contrario PASS. El razonamiento: cuando Lenient swallow ≥2 citas inválidas dentro de Findings que aún pasan, la respuesta sigue siendo sospechosa.
2. **All-blocked-Findings** (ningún Finding pasa): si el helper retorna `True` → PASS (v0.1.29 ADR-0034 D Mirror); en caso contrario → BLOCK. Esta rama materializa el caso chat-016 medido en v0.1.25 (3/3 citas con paráfrasis Check 3; gold esperaba PASS).
3. **Partial-Findings** (algunos pasan, otros no): si el helper retorna `True` → PASS (v0.1.25 ADR-0032 D2); en caso contrario → RHR. Ataca el patrón Path B "Strict-Answer partial routing" identificado en el diagnóstico v0.1.24.1 como gatekeeper dominante de 8/10 casos H1.C.

El método `_aggregate_reason` (src/regulaitor/agents/auditor.py:145) construye una explicación trazable, separando con ` | ` los motivos por citación (el validator nunca emite ese separador, garantizando split unambiguo aguas abajo).

### 3.3 Inmutabilidad del Answer

El Auditor **nunca muta el `Answer` del Analyst**. `AuditedAnswer` (src/regulaitor/citation/schemas.py:139) lo envuelve sin tocarlo, añadiendo `verdict`, `audit_results` y `reason`. Esta disciplina hace que la salida del Analyst sea evidencia auditable independiente del veredicto, y permite que el Council reciba el par `(audited, context)` con el `Answer` original íntegro para revisión.

## 4. Council of Judges — promoción de advisory a binding conservador

El `CouncilAgent` (src/regulaitor/agents/council.py:149) materializa la decisión §8.4: un panel de **3 jueces LLM independientes** vota `valid | invalid | requires_human_review` sobre los Findings de severidad alta o casos ambiguos. ADR-0014 lo introdujo en H13 como capa puramente advisory (D1: nunca muta el veredicto del Auditor mecánico); ADR-0025 lo promovió en v0.1.19 a binding conservador.

### 4.1 Tres proveedores distintos

El módulo selecciona tres modos del router para garantizar independencia paramétrica (ADR-0014 D3, src/regulaitor/agents/council.py:118):

- `judge` → Claude Haiku 4.5 (Anthropic).
- `evaluation` → GPT-4o (OpenAI).
- `cost` → Llama-3.3-70b vía Groq.

Cada juez se ejecuta secuencialmente con tool use sobre `cast_vote` (src/regulaitor/agents/council.py:124). El prompt `prompts/council/judge.v1.0.md` instruye al juez a votar exclusivamente sobre si las citas **soportan** la afirmación, usando exclusivamente el `retrieved_context` que se le entrega. Cualquier excepción en `_one_judge` se traga (src/regulaitor/agents/council.py:231) — invariante advisory: un fallo del Council nunca puede romper el turno; el juez degrada con `ok=False` y `error_category=type(e).__name__`.

### 4.2 Trigger híbrido y selección de Findings

El Council se dispara automáticamente cuando `audited.verdict == REQUIRES_HUMAN_REVIEW` o cualquier `finding.severity == "high"` (D2). El cliente API puede forzarlo con `council: bool` en el cuerpo de `POST /ask`. Se omite si la query fue bloqueada por anti-injection o si no hay `audited_answer`. `_findings_under_review` (src/regulaitor/agents/council.py:160) filtra a Findings high-severity más los que tienen ≥1 citación inválida cuando el Auditor no pasó; si el filtro queda vacío, devuelve todos los Findings (degrade-safe).

### 4.3 Políticas de agregación: Advisory vs Monotonic

Dos políticas implementan el `Protocol` `AggregationPolicy` (src/regulaitor/agents/council.py:58):

- **`AdvisoryMajorityPolicy`** (H13 default original): el veredicto es la moda de los votos `ok` si ≥2 jueces coinciden, si no RHR. Label: `unanimous` / `majority` / `split` / `degraded`.
- **`MonotonicEscalatePolicy`** (default desde v0.1.19): `aggregate` idéntico a la anterior; `would_escalate` (src/regulaitor/agents/council.py:102) implementa la regla binding **conservative-only**: PASS → RHR sólo si los 3 jueces están `ok` y todos votan BLOCK unánime; **nunca** relaja BLOCK ni RHR.

### 4.4 La promoción v0.1.19 — binding ON

ADR-0025 cerró la deferida del H15 §16.3 ("Council binding") flipando dos cosas (src/regulaitor/agents/council.py:55):

- `_COUNCIL_BINDING: bool = True`.
- Default policy del `CouncilAgent.__init__` cambia a `MonotonicEscalatePolicy()`.

El helper `bind_verdict(audited, review, council)` (src/regulaitor/agents/council.py:278) consume `would_escalate` y, cuando dispara, devuelve un nuevo `AuditedAnswer` con `reason` prefijado por `"COUNCIL_BIND:"` que incluye el conteo `n_block/n_ok` y la razón original del Auditor para trazabilidad. La firma toma `council: CouncilAgent` (no la policy directamente) para mantener el acceso a `council._policy` interno al módulo (D3).

El estudio empírico H13 (12/21 ≈ 57% de divergencia entre Council y Auditor) había identificado un caso canónico — **chat-11** Auditor=PASS → Council=RHR — que el binding ahora captura por construcción. La dirección opuesta (7/12 Auditor=RHR → Council=valid; panel más leniente en ambiguos) **no** se aborda en v0.1.19: relajar RHR a PASS por mayoría de jueces debilitaría §6. ADR-0025 D1 documenta esta asimetría explícita.

### 4.5 Ortogonalidad con las modificaciones del Auditor (v0.1.25 + v0.1.29)

El comentario al inicio de council.py (src/regulaitor/agents/council.py:19-27) hace explícito que las softenings del Auditor en Layer (c) **no anulan** el binding del Council. Las dos capas son ortogonales: la agregación Auditor ataca falsos RHR/BLOCK por paráfrasis; el Council binding ataca PASS que el panel rechaza unánimemente. Un turno puede pasar por ambos refinamientos en cascada — el Auditor entrega su veredicto mecánico, el Council se dispara si el trigger aplica, y `bind_verdict` decide si promover.

## 5. Disciplina §22.22 y trazabilidad

Las modificaciones sobre el Auditor (v0.1.21 / v0.1.23 / v0.1.24 / v0.1.25 / v0.1.29) y sobre el Council (v0.1.19) están todas documentadas en ADRs individuales con sección §22.22 (honest framing), referencias verbatim a los reports de evaluación pagados y, cuando procede, sección §REVERT (v0.1.23 ADR-0030: Design B aceptado y revertido tras refutación empírica). El conjunto constituye, en palabras del propio CLAUDE.md §27 cierre v0.1.25, "the methodology is the contribution": diagnose → intervene → measure → refute-or-confirm → revert-or-keep → document. El §6 invariant ha sobrevivido a las evoluciones interpretativas documentadas en CLAUDE.md §6.1 (v0.1.24 → v0.1.29: v0.1.24 añadió la observabilidad `failed_check`; v0.1.25 introdujo la arquitectura multi-capa explícita en a/b/c; v0.1.28 añadió la Capa (d) prompt-level forbid; v0.1.29 reusó el helper de v0.1.25 en la sub-rama all-blocked) sin que ningún cambio haya tocado el byte-level del validator de Capa (a) ni del Finding-Lenient de Capa (b); todas las modificaciones han ocurrido en Capa (c) routing o Capa (d) prompts, con la fabricación atrapada por construcción en las dos primeras capas.
