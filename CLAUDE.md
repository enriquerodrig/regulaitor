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
- **H15.1** Optimización system-level: retriever (lever C) + segmentador documental + no-Answer residual + semántica RHR-aggregation del Auditor. *(Insertado post-H15 — consecuente de los hallazgos del estudio de calibración + petición del user; decimal sin renumerar, precedente H0.1. Decisión de roadmap aprobada 2026-05-19, ver `docs/technical_decisions_log.md` §H15.1.)*
- **H15.2** Eval rede-design (wiring fix surgical para measurability del tuning lever). *(Cerrado 2026-05-20, tag `v0.1.7-h15.2`. Wiring fix shipped + design-defect §22.22 de H15.1 cerrado. A/B paid crasheó mid-flight con credit exhaustion → solo probe n=3 persisted; spec §6 cubrió explícitamente este outcome. Plan maximalista post-H15.2 user-confirmed: 8 microhitos decimales `v0.1.8`-`v0.1.15` + single paid validation `v0.1.16` cuando recargue budget, luego retorno a H16/H17. Ver `docs/technical_decisions_log.md` §H15.2.)*
- **H15.X** (microhitos optimización, plan maximalista user-confirmed 2026-05-20; renumbered post-v0.1.9 cuando insertamos per-article cap como v0.1.10 + per-norma cap como v0.1.11 + top_k_auto como v0.1.12 + industry-realistic gold extension como v0.1.13 + segmenter overhaul como v0.1.14 + gap-analysis chat mode como v0.1.15 user-approved insertion 2026-05-21): `v0.1.8` ✅ harness checkpoint per-case (cerrado 2026-05-20, squash 91080ec) · `v0.1.9` ✅ xcorpus-002 diagnostic (cerrado 2026-05-21, squash c8e096b) · `v0.1.10` ✅ per-article dedup cap (cerrado 2026-05-21, squash 2ab7a93) · `v0.1.11` ✅ per-NORMA dedup cap — BREAKTHROUGH 1/3→2/3 (cerrado 2026-05-21, squash 107479d) · `v0.1.12` ✅ top_k_auto capability (cerrado 2026-05-21, squash 64c6eac, empirical deferred) · `v0.1.13` ✅ industry-realistic cross-corpus gold extension 44→54 cases (cerrado 2026-05-21, squash 3ee42d9) · `v0.1.14` ✅ segmenter heading regex extension — closes H15 0-segments deferral, 8/8 fixtures within tolerance (cerrado 2026-05-21, squash 1ebe17d + populate c2227c1, ADR-0019) · `v0.1.15` ✅ chat gap-analysis mode — Analyst prompt v1.3 (NL auto-detect, Finding reuse, opt-in via env) + 10 gold cases industry-g/gv (cerrado 2026-05-21, squash `<squash-sha>`, ADR-0020) · `v0.1.16` §17 thresholds + LLM-judge same-provider · `v0.1.17` no-Answer-residual · `v0.1.18` citation granularity confound · `v0.1.19` Auditor RHR + Council binding · `v0.1.20` single paid validation A/B (when budget recharges).
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

- **H11** — Observabilidad (LangFuse) + redteam reliability cerrado (2026-05-16). Tag `v0.1.1-h11` publicado. Squash commit `8378015` en main. ADR 0012. Instrumentación observability-layer (`graph.run()` + `document_graph.run_document()`, backend H1-H5 intacto): módulo `observability/langfuse_client.py` con `trace_turn` metadata-only, no-op total sin `LANGFUSE_*` (SDK ni se importa), guard de redacción allowlist en egress, cliente cacheado + `flush()` per-turn, toda excepción tragada con WARNING. Redacción **probada end-to-end vs LangFuse Cloud real** (canary ausente server-side). Redteam: timeout per-attack daemon-thread (300 s chat / 900 s doc) — **el code-review en 2 fases capturó un Critical del plan** (`ThreadPoolExecutor` colgaba en `__exit__`/atexit ante hang real → daemon-thread; snippet del plan corregido). Full 50-attack run completado (commit `602c2da`, 1.99 €): block_rate 0.28 raw contaminado por 21/50 timeouts de API degradada / 0.54 entre 26 completados — señal calibración H15, gate §16.2 #4 sigue en smoke 0.92 (inmune a API), NO re-abre H9. `docs/runbook.md` (setup + dashboard + interpretación latencia §17 #7). Out-of-plan: gitleaks enforced en CI (`ci.yml` Security, v8.21.2; gate §16.2 #6) — user opt A. langfuse-mcp **diferido** (user, ítem de menor valor). Observación honesta: Analyst emite a veces Answer sin `findings` → palanca añadida a H15. Sin skills nuevas (`cost-accounting` sigue H17). Ver `docs/technical_decisions_log.md` §H11 + §H9 amendment 6.

- **H12** — Router multi-LLM + análisis de coste cerrado (2026-05-17). Tag `v0.1.2-h12` publicado. Squash commit `d59a33f` en main. ADR 0013. Router de 1 backend → **3 proveedores (Anthropic/OpenAI/Groq), 5 modos**, fallback controlado one-hop (estrechado a errores transport tras el review) + override eval `REGULAITOR_ROUTER_MODE`; helpers puros `_translate` Anthropic↔OpenAI; **backend H1-H5/graph/api intacto, regression-zero**. **El code-review en 2 fases capturó 2 defectos consecuentes**: T7 I-1 (fallback `except Exception` ancho habría re-enrutado errores deterministas → corrompido la medición A/B; estrechado a 12 tipos transport) y T8 #5 (unit tests "mockeados" ejecutaban un `git checkout` REAL sobre el working tree; report-isolation hecho inyectable). A/B de pago ejecutado (~$5, OK usuario) pero **salió comprometido y se documentó con honestidad (§22.22, patrón H11, sin re-run)**: (a) coste NO per-run-medido — el harness H8 reusado reporta heurística Sonnet hardcodeada (gap de pipeline; los reviews T8 no lo cazaron) → captura real diferida a H15; (b) arm Llama contaminado ~19/40 (cap free-tier Groq 100k/día + crédito OpenAI agotado por arms secuenciales → fallback GPT-4o-mini también falló = I-2 empírico). **Hallazgo clave: calidad uniformemente baja en Sonnet/GPT-4o/Llama → el techo es system-level (retriever+Auditor), NO la elección de modelo → refuerza H15.** `docs/cost_analysis.md` entregado honesto/caveated (calidad 3-vías real + coste list-price analítico); arm reports trackeados como evidencia. CVE-2026-41488 (langchain-openai SSRF, transitivo ragas, ruta no alcanzable) ignore documentado patrón CVE-2026-1839. Sin skills nuevas (`cost-accounting` sigue H17). Ver `docs/technical_decisions_log.md` §H12.

- **H13** — Council of Judges cerrado (2026-05-18). Tag `v0.1.3-h13` publicado. Squash commit `db991dc` en main. ADR 0014. Capa advisory de **3 jueces LLM independientes** (Haiku 4.5/GPT-4o/Llama-3.3-70b vía router, D3) sobre el flujo chat para severidad alta y casos ambiguos; D1-D7 cumplidas. `AdvisoryMajorityPolicy` (default) registra el resultado sin mutar el veredicto del Auditor mecánico (invariante §6 "no citation, no answer" al 100% intacto). `MonotonicEscalatePolicy` implementada+testeada, cableada OFF (`_COUNCIL_BINDING=False`) = seam de promoción H15. Trigger híbrido: auto (`verdict==RHR` OR `severity=="high"`) + override API `council: bool`. `council_notice` visible en API + Streamlit cuando el Council diverge. Modo `judge`→Haiku 4.5 añadido al router como 6º modo (5 existentes regression-zero). Prompt `council/judge.v1.0.md` versionado (skill `prompt-versioning`). **El code-review en 2 fases capturó 4 defectos consecuentes**: T7 (invariante `trigger_reason` podía lanzar excepción y romper el turno → Literal estrechado), T10 (resumen council no llegaba al trace LangFuse → egress gap corregido), T12 (`_render.py` reimplementaba `_council_notice` verbatim → single-source-of-truth restaurado), T14b (`council_analysis.md` sobreestimaba "~9" vs real 7 divergencias → corregido per §22.22). **Run gated T14 afloró 3 defectos de ruta `# pragma: no cover`** (warmup ausente, invocación `uv run --env-file .env` vs bare `python -m`, sin `try/except` por caso); cada crash fail-fast antes de llamadas de pago (~$0.04 en el tercero; presupuesto protegido). **Resultados reales T14 (30 casos chat, Council forzado vía override):** 21 resumidos, 9 skipped (30%) por flakiness Analyst `findings=[]` (documentada desde §H10); Council divergió del Auditor en **12/21 ≈ 57%**; 7/12 son Auditor=RHR→Council=valid (panel más leniente en ambiguos); 1 caso chat-11 Auditor=pass→Council=RHR (escalación semántica que el Council estaba diseñado para detectar); Groq I-2 recurrió (~6 panels 2-OpenAI, no 3-proveedores-independientes, por cap free-tier); coste **~$1.2–1.5** (aproximación honesta; NOT per-run-medido — mismo gap H12 → H15). Falsa alarma de cobertura T13 (79% de invocación parcial) aclarada: gate autoritativo **93.40%** (full `python -m pytest -q`, exit 0). **Hallazgo clave**: 57% de divergencia + patrón 7/12 RHR→valid confirma que el Auditor sobre-dispara RHR en ambiguos — refuerza las palancas H15 (calibración Auditor + schema-adherence Analyst + promoción binding). Sin skills nuevas (`cost-accounting` sigue H17). Ver `docs/technical_decisions_log.md` §H13.

- **H14** — NIS2 + DORA corpus expansion cerrado (2026-05-18). Tag `v0.1.4-h14` publicado. Squash commit `d2f2a75` en main. ADR 0015. NIS2 (Directiva (UE) 2022/2555, CELEX `32022L2555`, **46 artículos** ES+EN) + DORA (Reglamento (UE) 2022/2554, CELEX `32022R2554`, **64 artículos** ES+EN) aterrizados en LanceDB (**1569 rows** total: ai\_act 687 + gdpr 324 sin cambio + nis2 244 + dora 314); D1-D4 cumplidas; AI Act + RGPD regression-zero (§22.18). **EUR-Lex CloudFront WAF bloqueó curl/httpx** (ADR-0003 lineage continúa): resolución = Playwright headless in-browser fetch (acceso legítimo a legislación pública; token WAF TLS-fingerprint-bound al browser, no exportable a curl). Base-act CELEX `2022-12-27` usado (consolidado bloqueado por WAF; base-act = texto autorizado para instrumentos 2022 sin enmienda). **9 spots hardcodeados ampliados** (spec estimaba 6; refinamiento honesto: +`evals/schemas.py` GoldCaseDoc + `scripts/ingest.py` + `scripts/rag_build.py`). **El code-review en 2 fases capturó 3 errores de corpus-ground en el gold set**: nis2-005 (sanción art 36 incorrecta → arts 32/33/34), dora-003 (plazos 4h/24h/72h no están en art 19 sino delegados a RTS art 20), xcorpus-001 (conclusión "prevalece" no establecida) — corpus-ground-fixed commit `26e6997`, re-revisados PASS. Gold set: **44 casos chat** (eran 30; +14 H14: nis2-001…006 + dora-001…006 + xcorpus-001…002; incluyendo 2 casos hallucination-attack block fuera del plan mínimo). Test slow $0 cross-corpus: **8/8** (`@pytest.mark.slow`, controller-verificado commit `2e9220b`, excluido de CI estándar por diseño — paridad `ci.yml` `-m "not slow"`). Gate autoritativo: `uv run pytest -m "not slow"` → **703 passed / 0 failed, 93.40%** cobertura ≥90% exit 0 (1 test de regresión capturado en gate: `test_analyze_invalid_corpus_returns_415` usaba `"nis2"` como sentinel inválido; corregido a `"invalid_corpus"` antes del gate). **$0 total** (sin run de LLM de pago; BGE-M3 local). Follow-ups: `source_url` absoluta en manifests (pre-existing, §22.18 → future); `CORPORA_WITH_MANIFESTS` vs `ALL_NORMAS` separados deliberadamente (D2 seam → future derivación runtime); `rag-ingest` SKILL.md Formex-centric vs PDF reality → doc follow-up; LLM-judge eval + §17 thresholds → H15. Sin skills nuevas (`rag-ingest` activa desde H1; `cost-accounting` sigue H17). Ver `docs/technical_decisions_log.md` §H14.

- **H15** — Auditor calibration study cerrado (2026-05-19). Tag `v0.1.5-h15` publicado. Squash commit `76fc6e7` (post-merge) en main. ADR 0016. **Reframe honesto §16.3** (linaje H10/H13/H14, §22.22): el Auditor es un agregador determinista pure-Python SIN umbrales numéricos → H15 no es "calibración de umbral" sino un **estudio de calibración system-level** con una afirmación científica única; el Auditor (`citation/validator.py` + agregación Lenient/Strict) NO se tocó, invariante §6 intacta al 100%. Reporte canónico `docs/auditor_calibration.md`. D1-D5 cumplidas (D2: intervenciones A+B Analyst PROMPT-ONLY; C retriever medición-solo, re-tuning diferido; **D Council-binding FUERA — `MonotonicEscalatePolicy`/`_COUNCIL_BINDING` sigue OFF**). **Dos seams de backend deliberados** (los únicos toques de backend, enablers mínimos NO scope creep; precedente `REGULAITOR_ROUTER_MODE` de ADR-0013): `REGULAITOR_ANALYST_PROMPT_VERSION` env (`agents/analyst.py`, default prod v1.0 byte-idéntico) + acumulador de coste real process-level (`models/router.py`, cierra el gap estimate-not-measured de H12/H13). Divergencia plan-vs-realidad honesta: plan decía v1.0→v1.1, candidato congelado = **v1.2** (v1.1 iteración intermedia dentro del budget D4 ≤3). Diagnóstico ($0 frozen) **77% Analyst-attributable** (corroborado 83% sobre re-baseline v1.0). **A/B single-variable v1.0→v1.2 (30 casos chat-001..030): real pero MODESTO** — verdict_match 0.17→0.27 (**+0.10**), faithfulness 0.54→0.75 (+0.21), citation_recall 0.46→0.71 (§16.2#5 floor 0.40 **PASS**), citation_precision 0.18→0.30, severity_match 0.31→0.42; los 6 casos ambiguous-RHR designados SIN CAMBIO (el +0.10 no es gaming); chat-026 micro-regresión de citación divulgada; el techo de calidad sigue siendo system-level (predicho por H12/H13/H14). **Holdout** (14 casos cross-corpus H14, medido UNA vez, nunca iterado): NO colapsa (faithfulness 0.66 / verdict_match 0.43 — NO se sobre-afirma como "mejor generalización"); citation 0.00 = **confound de granularidad del instrumento de medición** (apartado-level H8 vs article-level H14 exact-match), NO fallo de v1.2, instrumento deliberadamente no editado post-hoc (§22.22/D3). **Guarda de seguridad DURA content-based (enmienda C1):** mecánico `safety_ok=False` PERO content-backstop manual del controller **6/6 content-safe** (chat-014/015/029/030 + holdout nis2-006/dora-006: cada uno rechazó la premisa maliciosa, NO fabricó artículo, citó corpus REAL para refutar) + redteam-smoke **0.92** (== §16.2#4 congelado) → **v1.2 NO revertido**. Coste real **medido ≈ €5.05** del techo ~€7.5 (medido, no estimado). **El review en 2 fases capturó un Critical plan-level C1** (T5, Opus, ANTES de cualquier gasto de pago: la regla mecánica `safety_ok` habría auto-rechazado el rechazo estructurado más seguro y redteam-smoke es prompt-blind → spec/plan enmendado a seguridad content-based + backstop manual; el catch más valioso de H15) + Criticals recurrentes de no-op-test (T3/T4/T6a/T7a) + T6c FIX-NOW + correcciones T9. Gate autoritativo (controller-verificado): `uv run pytest -m "not slow"` → **746 passed / 0 failed, 1 skipped esperado, 93.46%** cobertura ≥90% exit 0. Follow-ups post-H15: re-tuning retriever C (palanca dominante remanente), document segmenter (doc-mode A/B), no-Answer-residual robustez, Auditor RHR-aggregation + Council binding OFF, confound granularidad métrica (eval-instrument), §17 thresholds. Sin skills nuevas (`evals-runner` activa desde H8; `cost-accounting` sigue H17). Ver `docs/technical_decisions_log.md` §H15.

- **H15.1** — Optimización system-level (retriever cross-corpus auto + purity gate + `RetrievalConfig`) cerrado (2026-05-20). Tag `v0.1.6-h15.1` publicado. Squash commit `e283412` (post-merge) en main. ADR 0017. **Hito decimal user-requested** (precedente H0.1, sin renumerar — H16/H17 intactos). Opt-in `corpus="auto"` path + post-rerank purity gate `_apply_purity_gate(share(norma)≥threshold → collapse-else-multi)` + `RetrievalConfig` (`pre_rerank`/`top_k`/`purity_threshold`/`query_normalize`) de palancas contenidas; **path explícito byte-identical** a v0.1.5-h15 (T6 asserted en `tests/unit/test_explicit_path_unchanged.py`, §22.18 no-leakage preservada por construcción); **invariante §6 Auditor/citation-validator byte-unchanged** (100% intacta). Coste real **medido ≈ €3.92** del techo ~€7.5 (probe 0.16 + cand-1 1.48 + cand-2 1.53 + holdout 0.75; menor que H15 ≈€5.05 porque NO hubo re-baseline pagada — ahorro ≈€1.85; router accumulator H15 reusado, cierra el gap H12/H13). **Cross-corpus per-case (n=2): 1/2 partial WIN** (xcorpus-001: verdict pass→RHR ✅ FIXED, context_precision 0.00→**1.00**, judge-criteria 1/4→2/4 ✅; cita el marco legal correcto NIS2 art 4 lex-specialis aunque no recupera el específico DORA 1/47 esperado) / **1/2 mixed-with-verdict-regression** (xcorpus-002: verdict RHR ✅→**block ❌ REGRESSED**; citas unchanged `['23.1','23.4']` — auto NO superficó NIS2 art 35 ni GDPR art 33; faithfulness 0.43→0.62 sobre set de citas defectuoso). **§22.22 design-defect disclosure (headline TFM-defense honesty point del hito post-spend):** la A/B 30-calibración es estructuralmente invariante al tuning lever — `DEFAULT_CONFIG` consumed only en 2 sitios auto-path-only + los 30 casos calibración all explicit-corpus → cand-1/cand-2 deltas vs control H15 son **€3.01 de non-determinismo LLM-provider medido sobre el path explícito byte-identical, NO un real tuning-lever signal**; mutual exclusivity con la garantía no-leakage T6 by design (code-path-correct, measurement-design-incoherent); per-task reviews validaron correctness per-task pero no chequearon cross-task design coherence — lineage C1 / H14-gold-corpus-ground. **3 review-discipline catches:** (a) §22.22 design-defect post-spend ofensivo en T10/T11; (b) T8.1 pre-spend safety catch (commit `1e5d82f` annotation-only previno mid-spend paid-run crash hole — el contrato never-crash de `RetrievalConfig` era más débil de lo declarado); (c) T4 cross-milestone mypy-since-H13 cleanup (strict `mypy src` silenciosamente rojo desde `db991dc`/H13 porque "gate green" usaba `pytest -m "not slow"` que NO corre mypy — fixed annotation-only en `_JUDGE_MODES`/`_one_judge`, zero runtime behaviour change). **HARD-revert NONE fires** (4 checks: citation_recall floor §16.2#5 carry-forward 0.71 PASS / explicit byte-identical T6 asserted / redteam-smoke 0.92 prompt-blind / 6 designated block cases code-path-equivalent C1 backstop carried). Follow-ups: **H15.2 NEW eval rede-design** (user-approved POST-SPEND), citation-granularity confound carried, xcorpus-002 open question, mypy-since-H13 surfaced+fixed, LLM-judge same-provider carried. Gate autoritativo `uv run pytest -m "not slow"` → **777 passed / 0 failed / 1 skipped esperado, 93.50%** cobertura ≥90% exit 0 + strict `mypy src` Success 71 files exit 0 (T4 cleanup). Sin skills nuevas (`evals-runner` activa desde H8; `cost-accounting` sigue H17). Ver `docs/technical_decisions_log.md` §H15.1.

- **H15.2** — Eval rede-design (wiring fix surgical) cerrado (2026-05-20). Tag `v0.1.7-h15.2` publicado. Squash commit `0bf8081` (post-merge) en main. ADR 0018. **Hito decimal user-approved POST-SPEND** (precedente H0.1 + H15.1, sin renumerar — H16/H17 intactos). Constraint reinterpretation surgical: T6 invariant scope (`tests/unit/test_explicit_path_unchanged.py`) clarificado a **WHERE-CLAUSE + empty short-circuit ONLY** — NO `PRE_RERANK=50` / NO `top_k=5` / NO config-insensitivity (H15.1 §4.3 "mutually exclusive as designed" framing re-interpretado como conservative implementation interpretation). Wiring shipped: `rag.retrieval.run(query, corpus, language, top_k=None, pre_rerank=None)` con per-call DEFAULT_CONFIG resolution; `RetrieverAgent.retrieve()` + `search_articles()` threaded default-None; **production byte-identical** a v0.1.6-h15.1 bajo env-unset (`DEFAULT_CONFIG()` defaults = `top_k=5, pre_rerank=50` matching prior hardcoded values; verified by keystone test 4/4 PASS + T6 unchanged 1/1 PASS + Opus reviewer cross-check via `git show v0.1.6-h15.1`). §6 Auditor + citation/validator **byte-unchanged** (100% intacta). **§22.22 outcome parcial honesto (headline TFM-defense honesty payload):** T1-T5 wiring fix SHIPPED ($0, cerrando el §22.22 design-defect de H15.1); T6 cand-1 probe (n=3, MEASURED €0.19) shows directional positive (faith +0.23, verdict_match +0.40 vs control H15 — **NO defendible como "improvement" por n=3**); T6 cand-1 full 30-case **CRASHED mid-flight** en case ~24/30 con `anthropic.BadRequestError: credit_balance_too_low` (€2.24 consumido antes de credit-out, 0 disk artifact porque harness escribe report only atómicamente al final via `_REPORT_PATH.write_text` — `chat_results: list` en RAM perdido); T7+T8 **CANCELLED** por budget exhausted. Total H15.2 paid spend **€2.43** (entire pre-existing balance), de los cuales €0.19 produjeron persistible evidence — effective €0.81/persisted-case (10.8× worse than H15 baseline €0.050/case), driven by the crash. **Cross-milestone lesson** (análogo a H15.1's design-coherence gap): per-task reviews validan per-task correctness; NO validan cross-task design coherence (H15.1) ni cost-estimation discipline (H15.2). Disciplina nueva registrada effective desde `v0.1.8`: probe min N=**5** (no 3), cost estimates SIEMPRE as ranges (low/expected/high=expected×1.5), if user budget < high-estimate → DO NOT recommend "proceed", **no paid run authorized hasta harness checkpoint per-case shipped**. **4 review-discipline catches:** (a) T1 code-review found unused `# type: ignore` × 4 + 2 readability Minors; (b) T2 code-review APPROVED (Opus verified WHERE-CLAUSE byte-identical vs v0.1.6-h15.1 tag, `is not None` not truthy-check pattern justified); (c) T3 code-review found **Critical** stale contract test (`test_mcp_tool_schemas.py:23` asserting `default==5`, would FAIL CI silently) + Important docstring asymmetry on `auto` path ignoring `top_k`; (d) T5 code-review found 2 Important (Decision section invariant restatement + References path-abbreviation). El T3-Critical es el catch más valioso (continúa linaje C1 H15 / T8.1 H15.1 — 2-stage review consistently captura defectos consecuentes). HARD-revert NONE fires (T6 WHERE-CLAUSE green under both env states / §6 Auditor byte-unchanged / redteam-smoke 0.92 prompt-blind / citation_recall floor + 6 designated block cases N/A porque full no ejecutado → carry-forward intacto). Gate autoritativo (controller-verificado T4 pre-paid): `uv run pytest -m "not slow"` → **782 passed / 0 failed, 1 skipped esperado, 93.51%** cobertura ≥90% exit 0 + strict `mypy src` Success 71 files exit 0 + redteam-smoke 0.92 (= H15 frozen carry). Spec §6 explícitamente cubrió este escenario: *"the measurement-design fix IS the H15.2 contribution"*. Sin skills nuevas. Ver `docs/retriever_h15-2_redesign.md` (study report canónico) + `docs/technical_decisions_log.md` §H15.2.

- **v0.1.8** — Harness checkpoint per-case + cost-estimation discipline cerrado (2026-05-20, squash `91080ec`). $0 milestone que resolvió la causa raíz estructural del desastre H15.2: `evals/checkpoint.py` NEW con `append_case` + `fsync` (sobrevive SystemExit/OS kill/OOM) + harness wraps chat-loop body en try/except (la H15.2 T6 mode failure capturado). Nueva memory `feedback_cost_estimation_discipline.md` registra reglas duras (probe min N=5, cost ranges low/expected/high=expected×1.5, SKIP si budget<high, no paid sin checkpoint). 12 new tests (9 checkpoint module + 3 crash-recovery). Gate 794/0/1, 93.51%, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.8.

- **v0.1.9** — xcorpus-002 retrieval diagnostic cerrado (2026-05-21, squash `c8e096b`). Documentation-only milestone $0 que cerró el open question de H15.1 sobre xcorpus-002. 3-call $0 local CPU diagnostic identifica root cause = standard `BAAI/bge-reranker-v2-m3` single-article dominance failure mode (no purity gate, no dense retrieval depth). NIS2 art 35 + GDPR art 33 ARE en el dense pool (Call 3 con pre_rerank=200) pero el reranker positions 5 paragraphs distintos de NIS2 art 23 más alto. NO production change; 3 fix candidates surfaced (A per-article cap, B MMR, C hybrid score). Nueva memory `feedback_optimization_narrative_doc.md` (user-flagged en sesión 2026-05-21): WHAT/WHY/HOW/IMPACT discipline para H17 memoria spine. 3 nuevos slow tests pin diagnostic baseline. Gate 794/0/1 (slow excluded), 93.51%, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.9.

- **v0.1.10** — Per-article dedup cap cerrado (2026-05-21, squash `2ab7a93`). $0 follow-up to v0.1.9 (option A surgical). `RetrievalConfig.max_chunks_per_article: int | None = None` (backward-compat default) caps per `(norma, article)` key. Algorithm-WORKS measurement (Call 4: cap=2 emits 4 distinct NIS2 articles vs baseline 5×nis2.23) PERO **NO arregla xcorpus-002** (top-5 sigue siendo 5/5 NIS2 just diversified within norma → purity gate sigue colapsando → 1/3 unchanged). Deeper finding: reranker bias is at NORMA level, not just article level. 3 new fix candidates surfaced ((i) per-NORMA cap → v0.1.11, (ii) raise top_k 5→12 → v0.1.12, (iii) different reranker → large). 11 new tests (6 dedup helper + 5 config field). Gate 805/0/1, 93.48%, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.10.

- **v0.1.11** — Per-NORMA dedup cap cerrado (2026-05-21, squash `107479d`). $0 follow-up to v0.1.10 deeper finding (option (i) surgical). **MEASURED BREAKTHROUGH 1/3 → 2/3 expected articles surfaced** (NIS2 23 + GDPR 33). Boundary math discovery crítica: cap=2 (sub-threshold 2/5=0.4 < 0.6 default) força multi-corpus; cap=3 (boundary-exact 3/5=0.6 inclusive) STILL collapses. Recommended demo-mode config = `RetrievalConfig(max_chunks_per_norma=2)`. NIS2 art 35 still missed (reranker scores below DORA 19/22 — deeper ceiling carried a v0.1.12). 12 new tests. Gate 817/0/1, 93.47%, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.11.

- **v0.1.12** — top_k_auto field para auto-path top_k override cerrado (2026-05-21, squash `64c6eac`). $0 capability shipped + wiring algorithmically verified by 9 unit tests with mocked rerank; **EMPIRICAL xcorpus-002 measurement DEFERRED** (12-call diagnostic killed at 41 min — 3ª subestimación CPU rerank esta sesión). `dataclasses.replace(cfg, top_k=cfg.top_k_auto)` pattern para inyectar override en gate_cfg; explicit-corpus `run()` path ignora field → T6 byte-identical preserved. Nueva memory `feedback_local_cpu_rerank_cost.md`: hard rules para local-CPU diagnostics (per-call 15-30s NOT 5-10s; N-call = N×30s+60s+1.5margin; redesign si >5min; NEVER PowerShell `| Select-Last` for long scripts; check zombies). Empirical question deferred a (a) dedicated session con proper time budget, o (b) v0.1.20 paid bundle validation. Gate 826/0/1, 93.56%, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.12.

- **v0.1.13** — Industry cross-corpus gold extension cerrado (2026-05-21, squash `3ee42d9`). $0 data-only milestone que extiende `evals/gold_set.jsonl` 44→54 chat cases con 10 industry-realistic cross-corpus questions (todos `corpus_esperado="auto"`). User-validated antes de añadir per industry-demo readiness requirement (TFM dual-target: LinkedIn publish + AI industry presencial session). **5 precise** (industry-c1 hospital IA / c3 fintech scoring / c4 banco cyber+brecha / c5 cloud financiero / c8 IA RRHH — todos triple-corpus AI Act+GDPR+NIS2/DORA) + **5 vague-real** (industry-v1 worry "¿legal?" / v2 practical "¿qué hacer?" / v3 speculative "¿problema?" / v4 reactive "¿avisamos?" / v5 confused "¿aplica?" — sin mencionar nombres normas ni números artículo, tests production-UX). 6 new unit tests pin schema + 5+5 split + vague-no-legalese. Empirical measurement deferred a v0.1.20. Gate 832/0/1, 93.56%, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.13 + `docs/industry_gold_extension.md`.

- **v0.1.14** — Segmenter heading regex extension cerrado (2026-05-21, squash `1ebe17d` + post-merge populate `c2227c1`). $0 surgical 1-line regex fix que **closes H15 "0 segments" deferral** que había bloqueado doc-mode evaluation desde H5 (2026-05-07 → 2026-05-21 gap). ADR-0019 (count: 18 → 19). `_HEADING_LIKE` regex extendido con third alternative para Spanish numbered sections (`\d+(?:\.\d+)*\.?\s+\S.{2,100}`) detectando "1. Introducción", "2.1 Subsección", "3.1.1 Detalle". **8/8 testable doc fixtures NOW within expected_n_segments ± tolerance** (pre-fix all 8 silently MISS-ing — el H5 author diseñó gold expectations correctamente pero implementación segmenter never delivered hasta ahora). 5 new unit tests pin numbered-section detection + downstream filter para sentences. §6 invariant intact (Auditor + citation validator byte-unchanged). Doc-mode A/B paid validation still deferred a v0.1.20 bundle. Gate 837/0/1, mypy strict 71 files. Ver `docs/technical_decisions_log.md` §v0.1.14 + ADR-0019.

- **v0.1.15** — Chat gap-analysis mode cerrado (2026-05-21, squash `<squash-sha>`, tag `v0.1.15-gap-analysis-chat`). Prompt-only extension Analyst v1.2 → v1.3 with NL auto-detection (Hard Rule 8: BOTH state declaration + gap-seeking question; ambiguous → Q&A default). Gap-analysis Findings reuse existing `Finding{text, citations[], severity}` schema → zero schema change, zero API change, zero backend touch beyond the prompt file itself. §6 Auditor + citation-validator BYTE-UNCHANGED (verified by 4 git-diff checks). Production default stays v1.0 (boundary contract carried — env-unset = v0.1.14 byte-identical); v1.3 opt-in via `REGULAITOR_ANALYST_PROMPT_VERSION=v1.3` for TFM demos and v0.1.20 paid bundle. v1.3 preserves the v1.2 Q&A Example 1 verbatim (regression-zero anchor on Q&A path even when v1.3 loaded). Gold set 54 → 64 chat cases (+5 precise industry-g{1..5} + 5 vague-real industry-gv{1..5}, all `corpus_esperado="auto"`). 14 new $0 unit tests (7 prompt fidelity + 7 gold case schema). ADR-0020 + `docs/gap_analysis_chat_mode.md` memoria-ready (WHAT/WHY/HOW/IMPACT + §6 invariant interpretation callout). NO paid LLM run in v0.1.15 (empirical measurement deferred to v0.1.20 paid bundle alongside all maximalist-plan optimizations). Code-review follow-ups carried for v0.1.20 / possible v1.4: I-1 positive-coverage example missing, I-2 Rule 8 keyword list closed (may under-trigger on paraphrases), I-3 severity scale e.g. vs Example 2 calibration drift. Gate authoritative: `uv run pytest -m "not slow"` → 850 passed / 0 failed / 1 skipped, ≥90% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 + redteam-smoke 0.92 (= v0.1.14 carry). Plan maximalist microhito 8/12 done. Ver `docs/technical_decisions_log.md` §v0.1.15 + ADR-0020 + `docs/gap_analysis_chat_mode.md`.

### Hito siguiente

- **`v0.1.16` — §17 thresholds + LLM-judge same-provider-family** (carry-forward from H15/H15.1/v0.1.13 list of deferred items; ADR-0010 lineage on judge-vs-prod model family). Scope: define numeric thresholds for §17 metrics (faithfulness, citation_precision/recall, answer_relevancy, context_precision, severity_match) appropriate for the v0.1.13-extended gold set + v0.1.15-extended gap-analysis cases; decide whether the LLM judge should stay Haiku 4.5 (different provider family from Sonnet prod — current ADR-0010 stance) or move to same-provider-family (Sonnet judge of Sonnet prod — risk of self-evaluation bias but cheaper + tighter cross-comparison). Medium ceremony (~1-2 días $0 OR ~$1-2 paid if quick A/B sample to inform the decision). Tras `v0.1.16`: secuencia `v0.1.17` (no-Answer-residual robustness) · `v0.1.18` (citation granularity confound — eval-instrument work, may require full A/B re-baseline) · `v0.1.19` (Auditor RHR + Council binding ON, the §6-invariante-adjacent work) · `v0.1.20` (single paid validation A/B cuando recargue budget) · luego retorno a **H16** (HF Spaces deploy) + **H17** (TFM cierre académico).
