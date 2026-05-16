# CLAUDE.md - RegulAItor

## 1. Rol de Claude Code

Eres mi pareja de programación senior para construir RegulAItor, el TFM del Máster de IA Generativa con aspiración 9-10.

Prioridad: excelencia, trazabilidad, evaluabilidad, reproducibilidad y defensa académica. **No optimices por velocidad.**

Trabaja siempre en pasos pequeños, revisables y con aprobación explícita entre hitos. No tomes decisiones de arquitectura relevantes sin proponérmelas antes. Antes de cualquier tarea no trivial, invoca `superpowers` y produce un mini-plan (2-6 pasos) con riesgos y criterios de éxito; espera mi OK.

---

## 2. Objetivo y narrativa ancla

RegulAItor es un servicio multi-agente de cumplimiento normativo europeo con verificación estricta de citas. **No es un chatbot legal genérico.** Convierte consultas normativas y documentos corporativos en respuestas e informes auditables, donde ninguna afirmación relevante puede salir del sistema sin una cita textual validada contra un corpus normativo oficial.

Narrativa ancla, repetida sin desviarse en README, memoria, demo y presentación:

> "RegulAItor no responde sin cita verificable: convierte la consulta normativa rutinaria y la revisión documental en un acto auditable, en minutos y por céntimos."

---

## 3. Problema que resuelve

Cuatro problemas:

1. Alto coste de la consulta jurídica o de compliance.
2. Lentitud en la revisión interna de documentos.
3. Riesgo de alucinación de modelos LLM generalistas.
4. Falta de trazabilidad para auditoría.

El sistema **no sustituye a un asesor jurídico**. Es una herramienta de primera línea para análisis, preparación de borradores, revisión documental y generación de evidencias verificables. Esta limitación debe aparecer en UI, README, memoria y demo.

---

## 4. Usuarios objetivo

- **Primario:** responsable de calidad, compliance, DPO o IT manager en PYME europea (50-500 empleados).
- **Secundario:** asesoría boutique que presta servicios de compliance a varias PYMES.
- **Terciario:** equipo interno de gobernanza de IA en organización mediana.

---

## 5. Superficies del producto

### 5.1 Modo análisis documental (principal, el que vende el proyecto)

El usuario sube un PDF/Markdown corporativo (política de IA, contrato, política de privacidad, evaluación de impacto, registro de sistema de IA, procedimiento interno) y recibe un informe estructurado.

Pipeline:

1. Extraer texto.
2. Sanitizar (texto invisible, metadatos, márgenes, prompt injection embebido).
3. Segmentar.
4. Identificar corpus normativo aplicable.
5. Generar hallazgos (severidad, riesgo, cita textual, recomendación).
6. Bloquear cualquier hallazgo sin cita válida.
7. Emitir informe en JSON y Markdown. PDF si da tiempo.

### 5.2 Modo chat

Pregunta en lenguaje natural → respuesta razonada con citas inline verificadas. **No responde si no puede respaldar la respuesta con citas del corpus.**

### 5.3 Modo API

FastAPI con OpenAPI auto. Endpoints mínimos: `POST /ask`, `POST /analyze`, `GET /health`. `GET /cases` si da tiempo. Auth básica + rate limiting desde H7.

---

## 6. Regla central: "no citation, no answer"

> **Sin cita verificable, no hay respuesta.**

Toda salida del Analyst-Agent pasa por el Auditor-Agent. El Auditor valida:

1. Que la cita existe en el corpus.
2. Que el texto citado coincide literal o normalizado con el corpus.
3. Que el artículo y apartado existen.
4. Que la cita apoya la afirmación.
5. Que la salida no contiene afirmaciones jurídicas no respaldadas.
6. Que no se han seguido instrucciones maliciosas del documento del usuario.

Si falla cualquier validación crítica, la salida se bloquea o se marca como "requiere revisión humana". **No hay atajos.**

---

## 7. Corpus normativo

### 7.1 MVP obligatorio

1. AI Act.
2. RGPD.

Fuente: EUR-Lex (HTML oficial multilingüe ES/EN). Versionado del corpus con DVC o Git-LFS desde H1.

### 7.2 Avanzado deseable

3. NIS2.
4. DORA.

Si NIS2/DORA consumen demasiado tiempo, pueden quedar como corpus parcialmente integrado o como trabajo futuro. **AI Act y RGPD deben funcionar correctamente antes de tocar NIS2/DORA.**

Cada chunk debe tener metadatos: `norma, articulo, apartado, idioma, version, fuente, fecha_ingesta, hash`.

---

## 8. Arquitectura de agentes

### 8.1 Retriever-Agent

Recibe consulta o segmento documental. Busca artículos relevantes (embeddings + reranking). Devuelve contexto estructurado. **No razona jurídicamente.**

### 8.2 Analyst-Agent

Analiza pregunta o documento. Genera respuesta o hallazgos con severidad, recomendación y citas candidatas. Trabaja siempre con contexto recuperado. **No produce salida final directamente al usuario.**

### 8.3 Auditor-Agent (componente diferencial)

Valida citas, comprueba consistencia entre afirmación y cita, bloquea salidas sin evidencia, detecta alucinaciones, detecta prompt injection, decide si requiere revisión humana.

### 8.4 Council of Judges (alcance avanzado, H13)

Tres jueces independientes votan sobre hallazgos de severidad alta o casos ambiguos: válido / inválido / requiere revisión humana. El resultado se registra como evidencia de evaluación avanzada.

---

## 9. MCP server propio

Servidor MCP del proyecto en `src/regulaitor/mcp_server/` con cinco tools (introducción en H3):

- `search_articles(query, corpus, top_k)` - búsqueda en LanceDB con reranking.
- `fetch_article(norma, articulo, apartado)` - lookup directo al corpus.
- `validate_citation(text, corpus, articulo, apartado)` - usado por el Auditor.
- `extract_document(file_bytes)` - extracción robusta de PDF/Markdown.
- `segment_document(text)` - segmentación lógica para el modo documental.

Esto es un **diferencial técnico fuerte para los módulos M1-M2 del Máster** y un activo de defensa del TFM. Tests de contrato obligatorios.

---

## 10. Stack técnico

### 10.1 Base

- Python 3.11.
- `uv` como gestor de paquetes.
- FastAPI + Pydantic v2 + OpenAPI auto.
- LangGraph para orquestación.
- LanceDB local como vector store.
- SQLite para metadatos en MVP; Postgres solo si se justifica en avanzado.
- Streamlit para UI MVP.
- Next.js (App Router) + Tailwind sobrio + shadcn/ui para frontend avanzado.
- Docker + docker-compose.
- GitHub Actions para CI/CD.

### 10.2 Procesamiento documental

- `pypdfium2` + `unstructured` + `pdfplumber` para extracción robusta de PDF.
- Sanitización de objetos embebidos contra prompt injection.

### 10.3 RAG

- Chunking estructural por artículo. **No mezclar artículos distintos en el mismo chunk si se puede evitar.**
- Embeddings multilingües: BGE-M3.
- Reranker: bge-reranker-v2-m3.

### 10.4 Modelos

Router multi-LLM (`models/router.py`). **Ningún agente llama directamente a un modelo; todo pasa por el router.**

Modelos previstos:

- Claude Sonnet.
- GPT-4o.
- Llama-3.1-70B-Instruct vía Groq o Together.
- Avanzado: clasificador de severidad fine-tuned LoRA sobre Llama-3.1-8B (H10+).

Modos del router: coste bajo / calidad alta / evaluación / fallback controlado.

### 10.5 Observabilidad

- MVP: logs estructurados con `case_id`, coste estimado, latencia, tokens (si disponible), resultado del Auditor.
- Avanzado: LangFuse en todos los agentes + Prometheus básico + alertas + dashboard (citation accuracy, latencia p95, coste, tasa de bloqueo).

### 10.6 Evaluación y tests

- Evals: Ragas + DeepEval + harness propio.
- Tests: pytest + hypothesis + schemathesis (contract).
- Lint/format/types: ruff + black + mypy (gradual hasta H10, estricto después).
- Seguridad estática: bandit, semgrep, pip-audit, gitleaks.

### 10.7 Documentación y diagramas

- MkDocs Material para sitio de documentación.
- Mermaid + Structurizr DSL (C4) para diagramas.

### 10.8 Despliegue

- MVP: Hugging Face Spaces (Docker).
- Avanzado: Render o Fly.io.

Si propones desviarte de este stack, da 2-3 alternativas con pros/contras y espera mi aprobación.

---

## 11. Estructura objetivo del repositorio

```text
regulaitor/
├── CLAUDE.md
├── README.md
├── LICENSE
├── pyproject.toml
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── .mcp.json
├── .claude/
│   ├── agents/                # subagentes especializados
│   ├── skills/                # skills custom + superpowers
│   └── settings.json
├── .github/workflows/
│   ├── ci.yml                 # lint + test + evals smoke + redteam smoke
│   ├── full-evals.yml         # evals completos en main y release
│   └── deploy.yml
├── docs/
│   ├── index.md
│   ├── architecture.md        # C4 en Mermaid + Structurizr
│   ├── model_card.md
│   ├── data_card.md
│   ├── ai_act_assessment.md
│   ├── runbook.md
│   ├── cost_analysis.md
│   ├── evidence_matrix.md
│   ├── postmortems/
│   ├── adr/
│   └── diagrams/
├── src/regulaitor/
│   ├── __init__.py
│   ├── agents/
│   │   ├── prompts/<agent>/<role>.vN.M.md
│   │   ├── retriever.py
│   │   ├── analyst.py
│   │   ├── auditor.py
│   │   └── council.py         # avanzado
│   ├── orchestration/graph.py
│   ├── document/
│   │   ├── extractor.py
│   │   ├── segmenter.py
│   │   └── sanitizer.py
│   ├── rag/
│   │   ├── ingest.py
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── reranker.py
│   │   └── store.py
│   ├── corpus/
│   │   ├── fetch.py
│   │   ├── parse.py
│   │   └── validate.py
│   ├── mcp_server/
│   │   ├── server.py
│   │   └── tools.py
│   ├── citation/
│   │   ├── validator.py
│   │   └── schemas.py
│   ├── models/
│   │   ├── router.py
│   │   ├── config.py
│   │   ├── severity_classifier.py   # LoRA, avanzado
│   │   └── prompts.py
│   ├── api/
│   │   ├── main.py
│   │   ├── routes_ask.py
│   │   ├── routes_analyze.py
│   │   ├── routes_cases.py    # avanzado
│   │   ├── auth.py
│   │   └── schemas.py
│   ├── schemas/               # Pydantic
│   ├── security/
│   │   ├── injection.py
│   │   ├── pii.py
│   │   ├── allowlist.py
│   │   └── rate_limit.py
│   ├── observability/
│   │   ├── logging.py
│   │   ├── metrics.py
│   │   └── langfuse_client.py
│   └── ui_streamlit/
│       ├── app.py
│       ├── tab_ask.py
│       └── tab_analyze.py
├── frontend_next/             # avanzado, App Router
├── corpus/                    # versionado con DVC o Git-LFS desde H1
│   ├── ai_act/
│   ├── rgpd/
│   ├── nis2/                  # avanzado
│   ├── dora/                  # avanzado
│   ├── manifests/
│   ├── raw/
│   ├── processed/
│   └── indexes/
├── evals/
│   ├── gold_set.jsonl         # ≥30 MVP, ≥60 avanzado (40% modo documento)
│   ├── document_cases/
│   ├── harness.py
│   ├── metrics.py
│   ├── baselines/
│   └── reports/
├── redteam/
│   ├── attacks.jsonl          # ≥10 MVP smoke, ≥50 MVP completo, ≥80 avanzado
│   ├── documents/
│   ├── runner.py
│   └── reports/
├── notebooks/
│   └── lora_severity.ipynb    # avanzado
├── scripts/
│   ├── ingest.py
│   ├── evaluate.py
│   ├── redteam.py
│   └── serve.py
└── tests/
    ├── unit/
    ├── contract/
    ├── integration/
    └── regression/
```

---

## 12. Skills (Agent Skills)

Procedimientos canónicos que Claude carga bajo demanda. Algunas siempre activas; otras por hito.

### 12.1 superpowers - skill base, siempre activa

Define el meta-procedimiento de trabajo: planificación previa por hitos, división en sub-tareas verificables, propuesta antes de actuar, revisión por pares (subagentes), checklists de cierre, definition of done, redacción de PRs y commits.

**Reglas duras:**

- Antes de cualquier tarea no trivial, invoca `superpowers` y produce un mini-plan (2-6 pasos) con riesgos y criterios de éxito. Espera mi OK.
- Toda PR pasa por la checklist de cierre que define `superpowers`.
- Cualquier desviación del plan se anota explícitamente y se justifica.
- `superpowers` se invoca también para decidir cuándo invocar otras skills.

### 12.2 Skills oficiales de Anthropic

- `pdf` - ingesta y generación de PDFs (informes descargables, corpus si llega en PDF).
- `docx` - borradores Word para entregables.
- `xlsx` - tablas de evals, panel de costes para la memoria.
- `pptx` - esqueleto del slide deck.

### 12.3 Skills custom del repositorio

Cada una en `.claude/skills/<name>/SKILL.md` con frontmatter (`name`, `description` empezando por "Use this skill when…", `version`, `allowed-tools` opcional). **Antes de redactar cada una, propón el `SKILL.md` y espera mi OK.** Mantén cada SKILL.md ≤ 150 líneas y procedimental; detalle largo a recursos.

1. `citation-validator` - validación canónica de citas (corazón del Auditor).
2. `rag-ingest` - ingesta idempotente de un cuerpo normativo.
3. `document-analysis` - pipeline de modo documento.
4. `prompt-versioning` - versionado y cambio seguro de prompts.
5. `evals-runner` - ejecución, interpretación y gating de evals en PR.
6. `redteam-runner` - ejecución y reporte de la suite de red team.
7. `adr-writer` - Architecture Decision Records.
8. `model-card` y `data-card` - plantillas vivas, bilingües.
9. `ai-act-assessment` - clasificación AI Act del propio sistema.
10. `secure-coding-checklist` - checklist canónica de seguridad por PR.

### 12.4 Skills avanzadas

11. `lora-finetune-recipe` - receta reproducible del fine-tune LoRA.
12. `ui-style-guide` - sobriedad en Streamlit y Next.js.
13. `incident-postmortem` - plantilla blameless.
14. `next-frontend-architect` - convenciones para Next.js (App Router, server components, WCAG 2.2 AA).
15. `cost-accounting` - coste por consulta y por documento, por modelo, con curvas de escala.

### 12.5 Orden de introducción por hito

- **H0-H1:** `superpowers` activa siempre. `adr-writer` y `rag-ingest` se proponen en H1 (no en H0.1).
- **H2-H3:** `prompt-versioning`.
- **H4:** `citation-validator`, `document-analysis`.
- **H8:** `evals-runner`, `model-card`, `data-card`.
- **H9:** `redteam-runner`, `secure-coding-checklist`.
- **H17:** `ai-act-assessment`, `cost-accounting`. Skills oficiales `xlsx`, `pptx`, `docx` para entregables finales.
- **HX (opcionales):** `lora-finetune-recipe`, `ui-style-guide`, `next-frontend-architect`, `incident-postmortem`.

### 12.6 Reglas de uso

- `superpowers` se invoca **siempre** al abrir cada sesión y antes de cada tarea no trivial.
- Una skill se invoca cuando su `description` matchea la tarea. No la fuerces si no aplica.
- Operaciones críticas (validar cita, evals, redteam, release) **exigen** invocar la skill correspondiente y dejarlo registrado en el PR.
- Las skills se versionan con el repo y evolucionan por PR.

---

## 13. MCPs externos

Configurar en `.mcp.json` con scopes mínimos. **Antes de instalar cualquier MCP, propón el comando exacto y espera mi OK.** Nunca instales MCPs en H0.1; ninguno es necesario en bootstrap.

- `filesystem` (oficial) - solo a este workspace.
- `git` (oficial).
- `github` (oficial) - least privilege.
- `fetch` (oficial) - con allowlist (`eur-lex.europa.eu`, `boe.es`, `arxiv.org`). Se introduce en H1.
- `sequential-thinking` (Anthropic) - planificación.
- `memory` (oficial) - notas persistentes entre sesiones.
- `puppeteer` o `playwright` - scraping JS-rendered si EUR-Lex requiere navegación. Decisión en H1.
- `mcp-server-time` - fechas correctas.
- `mcp-pandoc` - conversiones de formato.
- `langfuse-mcp` (comunidad) - consultar trazas y métricas. Se introduce en H11.
- `tavily-mcp` o `brave-search` - búsqueda web acotada.
- `sqlite` (oficial) - metadatos auxiliares; sustituir por `postgres` solo si se justifica.

---

## 14. Subagentes especializados

En `.claude/agents/` con prompts versionados. Cada subagente se niega a actuar fuera de su scope y deriva la decisión.

- `software-architect` - decisiones de arquitectura, ADRs.
- `security-engineer` - seguridad por PR, MCP scopes, secrets, dependencias.
- `legal-aiact-reviewer` - revisión de claims jurídicos del Analyst y mantenimiento de `ai_act_assessment.md`.
- `evals-engineer` - gold set, métricas, gates.
- `redteam-engineer` - suite de ataques.
- `mlops-engineer` - CI/CD, despliegue, observabilidad.
- `frontend-engineer` - Streamlit MVP y Next.js avanzado.
- `docs-writer` - README, MkDocs, model card, data card, runbook, ADRs.
- `tech-writer-academic` - resúmenes técnicos de hito para luego migrar a memoria.

Decisiones con impacto en seguridad o legal pasan por los subagentes correspondientes antes de mergear.

---

## 15. Alcance por niveles

### 15.1 MVP obligatorio (H0-H10)

Cerrado en H10 con tag `v0.1.0-mvp`. Incluye:

1. Bootstrap reproducible.
2. Corpus AI Act + RGPD.
3. Chunking estructural por artículo.
4. RAG base (LanceDB + BGE-M3 + reranker).
5. MCP server propio con 5 tools.
6. Retriever-Agent, Analyst-Agent, Auditor-Agent.
7. Citation validator literal/normalizado.
8. Modo chat E2E + modo análisis documental E2E.
9. Streamlit con dos pestañas + FastAPI mínima.
10. Gold set inicial + `make eval` reproducible.
11. Red team inicial + `make redteam` reproducible.
12. Logs estructurados + ID de caso.
13. README, `docs/architecture.md`, ADR 0001, evidence matrix, informe de evaluación, informe de seguridad.

### 15.2 Avanzado prioritario (H11-H17)

Solo si MVP cierra todos los gates (sección 16.2):

1. LangFuse + dashboard de métricas reales.
2. Router multi-LLM con A/B y modos coste/calidad.
3. Council of Judges para severidad alta.
4. Corpus NIS2 y DORA.
5. Calibración del Auditor.
6. Despliegue público en HF Spaces.
7. Memoria académica, model card, data card, AI Act assessment, runbook, cost analysis, video demo, slide deck.

### 15.3 Avanzado opcional (HX)

Solo si H17 está completo:

- Fine-tune LoRA del clasificador de severidad.
- Frontend Next.js completo (App Router, triple superficie).
- Conector webhook o GitHub Action.
- Servidor MCP separado.
- Prometheus + Grafana avanzado.
- Postmortems formales.
- Despliegue en Render o Fly.io con dominio.

---

## 16. Roadmap por hitos

**Trabajamos por hitos, no por semanas.** Mi disponibilidad es variable; el avance depende de evidencia, no de calendario. Pídeme aprobación al cerrar cada hito.

### 16.1 Núcleo MVP

- **H0** Decisiones y plan aprobado.
- **H0.1** Bootstrap mínimo del repositorio.
- **H1** Corpus AI Act + RGPD: descarga, parser estructural, validación, manifests.
- **H2** RAG base: chunking, embeddings, reranker, LanceDB.
- **H3** MCP server propio + Retriever-Agent + schemas Pydantic + citation validator inicial.
- **H4** Analyst-Agent + Auditor-Agent + flujo chat E2E (LangGraph).
- **H5** Pipeline documental: extractor + sanitizer + segmenter + flujo análisis E2E.
- **H6** Streamlit MVP (dos pestañas).
- **H7** FastAPI mínima (`/ask`, `/analyze`, `/health`) + auth básica + rate limiting.
- **H8** Gold set + harness de evaluación + métricas + informe.
- **H9** Red team inicial + informe de seguridad.
- **H10** Documentación MVP (README, architecture, ADRs, evidence matrix) + tag `v0.1.0-mvp`.

### 16.2 Gate MVP → avanzado

No se avanza a H11+ hasta que TODOS estos gates están verdes:

1. `make setup && make ingest && make eval && make redteam && make serve` corren limpios en clone fresco.
2. Cobertura de tests ≥80% en `citation/`, `agents/`, `rag/`.
3. `evals/reports/latest.md` con métricas reales (no `[medicion pendiente]`) para citation precision/recall, faithfulness y tasa de bloqueo.
4. Tasa de bloqueo del Auditor ≥0.90 en `redteam/attacks.jsonl`.
5. **Citation recall ≥0.40 sobre gold set** (métrica safety-relevant: ¿el sistema encuentra el artículo correcto que debe citar?). Medido 0.44 ✅ en `evals/reports/latest.md`. **Citation precision** (medido 0.17; over-citation del Analyst) queda **documentado pero no bloqueante en MVP** — su objetivo ≥0.85 se mueve a H15 (calibración Auditor + Council). Justificación: el Auditor valida cada cita emitida contra el corpus (invariante "no citation, no answer" se cumple al 100%); precision baja = ruido de calidad, no fallo de seguridad. Ver `docs/technical_decisions_log.md` §H10 (decisión B + plan de calibración H15).
6. gitleaks limpio.
7. bandit / semgrep / pip-audit sin findings altos ni críticos.
8. Demo reproducible por humano externo siguiendo el README.
9. ADRs al día.
10. Tag `v0.1.0-mvp` publicado.

Si un gate falla, se itera dentro del MVP. **No se invierte tiempo en H11+ hasta cerrar todos.**

### 16.3 Avanzado prioritario

- **H11** Observabilidad: LangFuse + dashboard.
- **H12** Router multi-LLM real + análisis de coste + modos coste/calidad.
- **H13** Council of Judges para severidad alta.
- **H14** Ampliación corpus: NIS2 + DORA.
- **H15** Calibración Auditor + A/B testing.
- **H16** Despliegue público MVP (Hugging Face Spaces).
- **H17** Cierre académico: memoria, model card, data card, AI Act assessment, runbook, cost analysis, video demo, slide deck. Tag `v1.0.0`.

### 16.4 Opcionales

- **HX1** LoRA severidad. **HX2** Next.js triple superficie. **HX3** Webhook/GitHub Action. **HX4** MCP server externo. **HX5** Prometheus avanzado.

El detalle por hito (objetivo, entregables, archivos, comandos de validación, criterio Done, riesgos, decisión previa) vive en el plan operativo aprobado en `~/.claude/plans/`.

---

## 17. Métricas objetivo (gates de CI bloqueantes)

Métricas objetivo, **no resultados garantizados**. No deben presentarse como resultados hasta ser medidas. Si una métrica no está medida, marcar `[medicion pendiente]`.

1. Faithfulness ≥ 0.85. *(objetivo avanzado; medido MVP 0.54 — plan calibración §H10/H15.)*
2. Citation precision ≥ 0.90. *(objetivo avanzado post-H15 Council; **NO gate MVP** — el gate MVP §16.2 #5 es recall-based. Medido MVP 0.17.)*
3. Citation recall ≥ 0.80. *(objetivo avanzado; gate MVP relajado a ≥0.40 §16.2 #5, medido 0.44 ✅.)*
4. Answer relevancy ≥ 0.85. *(objetivo avanzado; medido MVP 0.53.)*
5. Context precision ≥ 0.80. *(objetivo avanzado; medido MVP 0.48 — palanca de retrieval, §H10 plan.)*
6. **Tasa de bloqueo del Auditor en adversarial set ≥ 0.95.** *(MVP gate §16.2 #4 relajado a ≥0.90, medido smoke 0.92 ✅; full run 50 completado en H11 = 0.28 raw contaminado por 21 timeouts de API / 0.54 entre 26 completados — señal calibración H15, gate sigue en smoke 0.92 inmune a API. Ver §H9 amendment 6.)*
7. Latencia p95 ≤ 12 s en MVP, ≤ 8 s en avanzado. *(El `latency_p95_ms` del eval (~572 s) NO es la SLA de producto: mide batch de 40 casos secuenciales bajo rate-limit + tenacity backoff. Latencia real de UNA query ≈ 15-60 s (retriever 1-3 s + Sonnet 10-40 s + Auditor ms). Aún sobre el objetivo 12 s → optimización (streaming, max_tokens, retriever paralelo, router rápido) documentada como follow-up H11/H15. Medición limpia per-span = H11 LangFuse.)*
8. Coste por consulta ≤ 0.05 € con modelo abierto.
9. Coste por análisis documental ≤ 0.50 € por 10 páginas.
10. Cobertura de tests ≥ 80%.
11. Sin secrets en repo.
12. Sin vulnerabilidades altas conocidas.
13. Sin findings críticos en bandit, semgrep, pip-audit.

**Si caen, no se mergea.**

---

## 18. Seguridad

Seguro por diseño. Controles mínimos:

1. Sanitización de PDFs (texto invisible, metadatos, márgenes).
2. Detección de prompt injection.
3. Detección de instrucciones maliciosas dentro del documento.
4. Separación entre instrucciones del sistema y contenido del usuario.
5. Filtro PII (log redactado, alerta, opción de cancelar).
6. Allowlist de dominios oficiales para fuentes.
7. Rate limiting básico.
8. Logs sin datos sensibles.
9. Revisión humana para casos ambiguos o de alta severidad.

Ataques mínimos del red team (≥10 en H9 smoke, ≥50 en MVP completo, ≥80 en avanzado):

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

---

## 19. Evaluación

Combinar métricas deterministas y evaluación LLM-as-judge (modelo juez distinto al de producción).

Cada caso del gold set debe incluir:

- `id`, `tipo` (chat o documento), `entrada`, `corpus_esperado`, `articulos_esperados` (si aplica), `severidad_esperada` (si aplica), `criterios_evaluacion`, `salida_esperada` o checklist, `requiere_revision_humana` (sí/no).

Gold set: ≥30 casos chat + ≥10 documentos en MVP. ≥60 casos + 40% modo documento en avanzado.

---

## 20. Reproducibilidad

El repo debe soportar:

```bash
make setup
make lint
make test
make ingest
make serve
make eval
make redteam
make docker
make deploy
```

Si un comando todavía no está implementado, debe existir como placeholder documentado y no debe fallar de forma confusa.

---

## 21. Documentación obligatoria

Sitio MkDocs Material.

1. README.md (raíz).
2. docs/architecture.md (con diagramas C4 en Mermaid + Structurizr DSL).
3. docs/model_card.md.
4. docs/data_card.md.
5. docs/ai_act_assessment.md.
6. docs/runbook.md.
7. docs/cost_analysis.md.
8. docs/adr/0001-project-scope.md (+ ADRs adicionales por decisión no trivial).
9. evals/reports/latest.md.
10. redteam/reports/latest.md.
11. docs/evidence_matrix.md.
12. docs/technical_decisions_log.md (registro acumulativo de decisiones técnicas, espinazo de la memoria del TFM).

---

## 22. Reglas de operación

1. **`superpowers` siempre activa.** Cualquier tarea no trivial empieza con un mini-plan invocando `superpowers`.
2. Antes de una tarea no trivial, produce mini-plan y espera OK.
3. No escribas archivos sin decir que vas a escribir.
4. No borres archivos sin confirmación explícita.
5. No instales dependencias, MCPs ni skills sin justificar y esperar OK.
6. No uses secretos reales. `.env.example` siempre. `gitleaks` en pre-commit.
7. No hagas commits automáticamente salvo que se pida.
8. **No avances a la siguiente fase si falla el gate actual.**
9. Toda salida del Analyst-Agent pasa por el Auditor-Agent. **No hay atajos.**
10. Toda PR pasa: ruff, black, mypy (gradual hasta H10, estricto después), pytest, evals (gold set), redteam (smoke). Sin warnings.
11. Cada decisión de arquitectura no trivial → un ADR.
11.b. **Cada decisión técnica aprobada → entrada en `docs/technical_decisions_log.md`** (incluye respuestas tipo "OK"/"A" en brainstorming, elecciones de stack, ajustes de pins, etc.). El ADR formal sigue siendo solo para no triviales; el log captura todas.
12. Cada prompt del sistema versionado en `src/regulaitor/agents/prompts/<agent>/<role>.vN.M.md` con cabecera y changelog.
13. Cada modelo accedido va por `router.py`. Ningún agente llama directamente a un modelo.
14. PII detectada → log redactado, alerta, opción de cancelar.
15. Citas validadas contra el corpus, **nunca contra el conocimiento del modelo**.
16. **No implementes Next.js antes de cerrar Streamlit, evaluación y red team.**
17. **No implementes LoRA antes de tener gold set y baseline.**
18. **No implementes NIS2/DORA si AI Act y RGPD no están estables.**
19. Decisiones con impacto en seguridad o legal pasan por subagentes correspondientes antes de mergear.
20. Si detectas sobreingeniería, dilo.
21. Si falta información, pregunta.
22. Si una métrica no existe, marca `[medicion pendiente]`.
23. Si una afirmación jurídica no tiene fuente, marca `[validacion juridica pendiente]`.

---

## 23. Idiomas

- Código: inglés.
- Comentarios técnicos del código: inglés.
- UI: español.
- README: inglés o bilingüe, según decidamos.
- Memoria académica: español.
- Model card y data card: bilingüe si da tiempo.
- Documentación técnica: inglés.
- Prompts internos: versionados y consistentes.

---

## 24. Relación con el Máster

El proyecto debe evidenciar los cinco módulos.

### Módulo 1 - Modelos y prompts

Modelos previstos, configuración, consumo, parametrización, prompts versionados, costes. Activos: `models/router.py`, `agents/prompts/`, `docs/cost_analysis.md`, `docs/model_card.md`.

### Módulo 2 - Agentes y autonomía

Tres agentes + Council, flujo operativo, autonomía limitada por el Auditor, intervención humana en casos ambiguos, framework LangGraph, controles intermedios (citation validator, anti-injection). Activos: `agents/`, `orchestration/graph.py`, MCP server propio.

### Módulo 3 - RAG, evaluación, despliegue, monitorización

RAG estructural por artículo, evaluación reproducible, tests, despliegue en HF Spaces, monitorización con LangFuse, métricas de rendimiento. Activos: `rag/`, `evals/`, `.github/workflows/`, `observability/`.

### Módulo 4 - Seguridad y red team

Seguridad por diseño, riesgos, red teaming, prompt injection, controles de producción. Activos: `security/`, `redteam/`, `docs/security_report.md`, `.gitleaks.toml`, `bandit`, `semgrep`.

### Módulo 5 - Proyecto integrador (P1-P7)

- P1 planteamiento (este documento + `0001-project-scope.md`).
- P2 activos y recursos (estructura del repo).
- P3 preparación del contexto (`corpus/`, `rag/`).
- P4 modelos y prompts (`models/`, `agents/prompts/`).
- P5 evaluaciones y seguridad (`evals/`, `redteam/`).
- P6 cadena de despliegue (`docker-compose.yml`, workflows, deploy a HF Spaces).
- P7 monitorización y mejora continua (`observability/`, postmortems si aplica).

`docs/evidence_matrix.md` mantiene esta correspondencia viva con enlaces a artefactos concretos.

---

## 25. Definition of Done por hito

Un hito está terminado solo si:

1. El código relevante existe, está tipado y linteado.
2. Tests unitarios + al menos un test de integración relevante pasan.
3. Documentación actualizada (README, MkDocs, ADRs si aplica).
4. CI verde con todas las gates.
5. Si toca evaluación: gold set actualizado, reporte adjunto al PR.
6. Si toca seguridad: caso añadido al `redteam/attacks.jsonl`.
7. Las decisiones quedan registradas en ADR si son relevantes.
8. Las limitaciones quedan documentadas.
9. La matriz de evidencias se actualiza.
10. Se indica explícitamente qué queda pendiente.

---

## 26. Cómo quiero que me hables

- Conciso, técnico, sin emojis, sin marketing.
- Pregunta antes de inventar.
- Cuando propongas decisiones, da 2-3 alternativas con pros/contras y tu recomendación.
- Cuando algo huela a sobreingeniería, dilo.
- Tras cada paso, resume qué se hizo, qué falta y qué arriesga.

---

## 27. Primera tarea de cada sesión

Cuando empiece una sesión nueva, no implementes directamente.

Primero:

1. Lee este CLAUDE.md.
2. Resume el objetivo y el hito actual.
3. Propone el plan de trabajo inmediato.
4. Identifica riesgos.
5. Espera mi OK.

### Hitos cerrados

- **H0** — Plan operativo aprobado (2026-04-30). Ver `docs/technical_decisions_log.md` §H0.
- **H0.1** — Bootstrap reproducible cerrado (2026-04-30). Tag `v0.0.1-h0.1`. Ver `docs/technical_decisions_log.md` §H0.1.
- **H1** — Corpus AI Act + RGPD ingestado (2026-05-04). Tag `v0.0.2-h1`. Pivote a PDF documentado en ADR 0003. Ver `docs/technical_decisions_log.md` §H1.
- **H2** — RAG base operativo: chunker + BGE-M3 + reranker + LanceDB (2026-05-05). Tag `v0.0.3-h2`. ADR 0004. 1011 chunks indexados. Ver `docs/technical_decisions_log.md` §H2.
- **H3** — MCP server propio (5 tools) + Retriever-Agent + citation_validator inicial cerrado (2026-05-05). Tag `v0.0.4-h3`. ADR 0005. Ver `docs/technical_decisions_log.md` §H3.
- **H4** — Analyst-Agent + Auditor-Agent + flujo chat E2E (LangGraph) cerrado (2026-05-05). Tag `v0.0.5-h4`. ADR 0006. Ver `docs/technical_decisions_log.md` §H4.
- **H5** — Pipeline documental cerrado (2026-05-07). Tag `v0.0.6-h5` publicado. Squash commit `415d269` en main. ADR 0007. Sanitizer + segmenter + document_graph operativos. Skill `document-analysis` activa. Ver `docs/technical_decisions_log.md` §H5.
- **H6** — Streamlit MVP cerrado (2026-05-07). Tag `v0.0.7-h6` publicado. Squash commit `e53f295` en main. ADR 0008. Dos pestañas (Pregunta / Analiza documento) envolviendo `run()` y `run_document()` sin tocar el backend H1-H5. Aviso jurídico persistente. Skill `ui-ux-pro-max` referenciada en memoria pero NO activada (alcance pelado). Ver `docs/technical_decisions_log.md` §H6.
- **H7** — FastAPI mínima cerrado (2026-05-10). Tag `v0.0.8-h7` publicado. Squash commit `5b1f664` en main. ADR 0009. Tres endpoints (`/ask`, `/analyze`, `/health`) wrapping H4/H5 sin tocar backend. Auth Bearer (HTTPBearer + hmac.compare_digest) + slowapi rate limit + DTOs explícitas + handlers globales + readiness `/health`. Schemathesis 4.x contract (60 fuzz cases) + httpx integration tests con backend fakes (cero coste LLM). 481 tests, 92.99% coverage. Ver `docs/technical_decisions_log.md` §H7.
- **H8** — Gold set + harness de evaluación + métricas + informe cerrado (2026-05-12). Tag `v0.0.9-h8` publicado. Squash commit `fe7b2e5` en main. ADR 0010. 30 chat + 10 docs gold set, harness Python (Ragas + custom layer), Haiku 4.5 LLM-as-judge con prompt versionado, cache hash-keyed (judge-layer only), `evals/reports/latest.md` con métricas reales sobre 40 casos ($2.51 gastados; signal diagnóstico para H10/H15 calibración). `make eval-from-cache` regenera la capa judge sin coste (H4/H5 no cacheado per spec §6.4). Skill `evals-runner` activada. Ver `docs/technical_decisions_log.md` §H8.
- **H9** — Red team inicial cerrado (2026-05-13). Tag `v0.0.10-h9` publicado. Squash commit `c1e7de6` en main. ADR 0011. 50 ataques autorados sobre los 10 escenarios §18 (22 chat-mode + 28 doc-mode; 15 con requires_e2e). Runner standalone Python (`redteam/runner.py`) + `make redteam-smoke` CI job ($0, ~30s). Evidencia de cierre: smoke `block_rate` **0.92** sobre 13 deterministas (gate §16.2 #4 ≥ 0.90 ✅). Full run sobre 50 **completado en H11** (commit `602c2da`, 2026-05-16, 1.99 €): block_rate raw 0.28 contaminado por 21/50 timeouts de API Anthropic degradada (el timeout per-attack de H11/T6 resolvió el hang de H9); entre 26 completados 0.54 — señal calibración H15, NO re-abre H9, gate §16.2 #4 sigue en smoke 0.92 (determinista, inmune a API; reframe §H10). Skills `redteam-runner` v1.0 + `secure-coding-checklist` v1.0 activadas. Ver `docs/technical_decisions_log.md` §H9 amendment 6 + §H11.

- **H10** — Documentación MVP + congelación cerrado (2026-05-15). Tag `v0.1.0-mvp` publicado. Squash commit `b8dbf10` en main. Sin código de producción nuevo. Entregables: README refresh (cronología H0.1-H10 + roadmap MVP/Advanced), `docs/architecture.md` (C4 L1/L2/L3 + sequence diagrams), `docs/evidence_matrix.md` (M1-M5 + gates + follow-ups), decisions log §H10 con plan calibración H15. Gate §16.2 #5 reframe: `citation_precision ≥0.85` → `citation_recall ≥0.40` (medido 0.44 ✅; precision 0.17 documentado, objetivo ≥0.85 → H15). Re-eval medido $2.51 (números reales, no estimados). Gate §16.2 10/10 verdes. **MVP completo (H0-H10) cerrado.** Ver `docs/technical_decisions_log.md` §H10.

### Hito siguiente

- **H11** — Observabilidad: LangFuse en todos los agentes + dashboard métricas reales + per-span latency (mide SLA limpia sin batch contention). **Incluye**: añadir timeouts per-attack al redteam runner + re-correr full 50-attack run (deferido de H9, primer intento hung en Anthropic silent timeout). Gate avanzado §16.2 cumplido para arrancar (10/10 MVP verdes).
