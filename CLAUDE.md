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
- **H15.X** (microhitos optimización, plan maximalista user-confirmed 2026-05-20; renumbered post-v0.1.9 cuando insertamos per-article cap como v0.1.10 + per-norma cap como v0.1.11 + top_k_auto como v0.1.12 + industry-realistic gold extension como v0.1.13 + segmenter overhaul como v0.1.14 + gap-analysis chat mode como v0.1.15 user-approved insertion 2026-05-21): `v0.1.8` ✅ harness checkpoint per-case (cerrado 2026-05-20, squash 91080ec) · `v0.1.9` ✅ xcorpus-002 diagnostic (cerrado 2026-05-21, squash c8e096b) · `v0.1.10` ✅ per-article dedup cap (cerrado 2026-05-21, squash 2ab7a93) · `v0.1.11` ✅ per-NORMA dedup cap — BREAKTHROUGH 1/3→2/3 (cerrado 2026-05-21, squash 107479d) · `v0.1.12` ✅ top_k_auto capability (cerrado 2026-05-21, squash 64c6eac, empirical deferred) · `v0.1.13` ✅ industry-realistic cross-corpus gold extension 44→54 cases (cerrado 2026-05-21, squash 3ee42d9) · `v0.1.14` ✅ segmenter heading regex extension — closes H15 0-segments deferral, 8/8 fixtures within tolerance (cerrado 2026-05-21, squash 1ebe17d + populate c2227c1, ADR-0019) · `v0.1.15` ✅ chat gap-analysis mode — Analyst prompt v1.3 (NL auto-detect, Finding reuse, opt-in via env) + 10 gold cases industry-g/gv (cerrado 2026-05-21, squash `4ea2d9e`, ADR-0020) · `v0.1.16` ✅ dual-layer §17 thresholds + judge family stays Haiku (cerrado 2026-05-21, squash `bc7b349`, ADR-0021) · `v0.1.17` ✅ no-Answer residual diagnostic ($0 cache-mining classifier; verdict other-dominant 10/12; deeper finding = prose-without-findings 5th mechanism; intervention v0.1.17.1) (cerrado 2026-05-22, squash `e5dbedd`, ADR-0022) · `v0.1.17.1` ✅ no-Answer residual fix (TWO-part + 5-bucket extension; 3 REFUSAL_PHRASES additions + Analyst prompt v1.4 force-Finding-emission opt-in via env + classifier prose_without_findings bucket; production default stays v1.0; T6 re-run verdict refusal 0→2 + prose_without_findings 0→8 + other 10→0 clean partition; $0; v1.4 effectiveness measured at v0.1.20) (cerrado 2026-05-22, squash `98f3768`, ADR-0023) · `v0.1.18` ✅ citation granularity confound (eval-instrument fix; hierarchical containment match resolves H15.1 §22.22 design-defect; retrospective re-render of 15 reports at $0; holdout citation_recall 0.00 → 0.64 / precision 0.00 → 0.65; T3 pivot from `make eval-from-cache` to script-only after controller-verification found cache-only mode still calls Analyst API; ADR-0024) (cerrado 2026-05-22, squash `670e35e`) · `v0.1.19` ✅ Auditor RHR + Council binding ON (conservative-only direction; PASS→RHR on unanimous 3/3 BLOCK; H13 ADR-0014 + H15 deferral lineage CLOSED; ADR-0025) (cerrado 2026-05-22, squash `8831bcd`) · `v0.1.20` ✅ paid validation A/B (v1.0 vs v1.4): FLIP approved — v1.4 production default for chat `analyst` role per ADR-0026 (T7 safety floor PASS + T6 H10 bar 6/7 PASS + T6.5 diagnostic +9 real flips / ~2 real regressions); doc_analyst role retains v1.0 (v1.4 chat-only; doc-mode A/B carried forward); v0.1.21 carries forward Auditor RHR quorum + hard constraints findings non-empty (cerrado 2026-05-24, squash `1f838ee`) · `v0.1.21` ✅ Auditor RHR quorum (Tier 1, ≥2 invalid citations → turn RHR) + Analyst format hard constraints (Tier 2 Capa A Anthropic strict mode + minItems + Capa B Pydantic min_length=1 + Capa C aggressive 3-attempt retry with failure-specific feedback); T6 $0 cache-mining diagnostic LOWER bound MARGINAL (0 unambiguous flips of v0.1.20 ARM A RHR cases; UPPER bound 0..36 ambiguous K≥2 — cache schema limitation: aggregate verdict + emitted citations persisted, NOT per-citation AuditResult) → v0.1.22 paid 30-case validation A/B (~€4-6) CONDITIONAL on user authorization (default: defer per interpretation A + go to H16; opt-in for empirical resolution per interpretation B) (cerrado 2026-05-24, squash `f073e74`, ADR-0027) · `v0.1.21.1` ✅ pre-v0.1.22 hardening ($0; 3 contamination vectors: D1 fix `scripts/v0120_compare.py` transition matrix bug + D2 per-citation `AuditResult` persistence in `evals/schemas.py::ChatCaseResult.per_citation_audits` with backward-compat Optional + D3 v1.5 refusal mock e2e tests; NO new ADR; 9 new $0 tests across 3 NEW test files; 0 src/ changes — D1 in scripts/ + D2 in evals/ + D3 in tests/) (cerrado 2026-05-24, squash `911ecae`) · `v0.1.21.2` ✅ Tier 2 retrieval defaults flip + chat refusal mock ($0; D1 max_chunks_per_norma=2 default + D2 top_k_auto=12 default + D3 chat refusal mock e2e closes v0.1.21 I5 caveat; ADR-0028; backward-compat via explicit None opt-out; NO paid pre-flip — v0.1.22 measures cumulative) (cerrado 2026-05-24, squash `6552d1c`) · `v0.1.22` ✅ paid validation (cumulative-impact A/B vs v0.1.20 ARM B baseline): **CONDITIONAL CONFIRM** per spec D4 third path — production state retained (no flip; package already shipped at prior milestones); cumulative v0.1.19→v0.1.21.2 capability arc empirically validated as safe-to-retain with mixed performance + documented carry-forwards for v0.1.23+ iteration. 1-arm fresh vs cached baseline methodology (~50% cost savings vs 2-arm fresh; v0.1.20 ARM B reused authoritatively, chat-001..030 extracted at $0 via `scripts/v0122_extract_armb.py`). H10 30-case chat + 2 ad-hoc safety (nis2-006, dora-006) under env-unset production state (v1.5 chat + Tier 1 Auditor quorum + Tier 2 Capa A+B+C + retrieval defaults + Council binding ON). Total paid €1.91 (~$2.06 USD; probe €0.32 + main €1.30 + safety €0.29; well under €3.78 high-extrapolation / $13 budget = ~16% of forecast high). **§22.22 spec amendment (the headline payload)**: spec said "ZERO backend touch — pure measurement"; reality 1 src/ file modified (`agents/analyst.py` recursive `_set_additional_properties_false_recursive` walker — Capa A schema fix). v0.1.21 Capa A shipped silently broken for ~12h (set `additionalProperties=False` on schema root only; nested `$defs` Finding+Citation untouched → Anthropic strict mode rejects with 400 → Capa C retries 3× fail → empty Answer at Capa B → Auditor RHR → 100% RHR rate on chat post-v0.1.21 merge). Broken-fail-safe per §6 (conservative all-RHR; no fabrication) but production unmeasured-as-actually-shipped. Fixed DURING v0.1.22 + 3 regression-guard tests; this is the §22.22-honest path (vs ship-broken-measurement-and-amend-later). **3 prior probe attempts failed at $0** before first paid call: (1) truststore absent → Windows CryptoAPI CRL revocation block on both HuggingFace + Anthropic SSL (CRYPT_E_NO_REVOCATION_CHECK 0x80092012); (2) HF fix only (HF_HUB_OFFLINE); (3) SSL fixed via `truststore.inject_into_ssl()` in `scripts/v0122_run.py`, Capa A schema bug surfaced. Each $0 but real wall-clock + discovery cost; documented in `evals/reports/v0.1.22/probe-attempt-{1,2,3}*.md`. truststore 0.10.4 in `.venv` only NOT in `pyproject.toml` → carry-forward to v0.1.22.1 OR H16 deploy. **Per-metric outcome (7 v0.1.20-bar)**: 4/7 PASS bar (faithfulness 0.71 / answer_relevancy 0.74 / context_precision 0.78 / severity_match 0.40); 3/7 improve over baseline (answer_relevancy +0.14, context_precision +0.11, severity_match +0.07); 3/7 regress (faithfulness -0.05 still above bar; citation_precision -0.08 below bar; citation_recall -0.09 below bar — mechanism = v1.5 Finding-based refusal emits more citations per refusal, narrower intersection with gold); 1/7 flat (verdict_match 0.30 below bar 0.35). Aggregate verdict counts: pass=10 / RHR=16 / block=4 on 30 cases. **Per-citation mechanism (T5 5-bucket diagnostic via v0.1.21.1 D2 trail $0)**: **NEW v0.1.21 Tier 1 quorum-triggered RHR cases = 11/30 (36.7%)** (Bucket C). Empirically resolves ADR-0027 §22.22 caveat (LOWER bound 0 / UPPER bound 0..36 → REAL = 36.7% within predicted [0%, 100%] interval, clearly nonzero). Bucket A=0 + Bucket D=0 → **Tier 2 Capa A+B+C is 100% effective at preventing empty-findings escape** on this cohort (closes the empty-findings escape route v0.1.17.1 v1.4 prompt-only could only reach ~50% on). Bucket B=4 (deterministic pre-v0.1.21 BLOCK path unchanged). Bucket E=15. **Hard safety floor PASS**: redteam-smoke 0.92 (= v0.1.14-v0.1.21.2 frozen carry; v1.5 prompt-loading does not regress sanitizer/injection path) + 6/6 designated content cases SAFE + 0/6 fabrications + 6/6 explicit rejection + 6/6 real corpus citation + 18/18 judge criteria PASS. §6 invariant ROCK-SOLID across the cohort. H15 C1 prompt-blind-mechanical issue documented (5/6 cases show ❌ verdict_match because gold expected literal `block` but v1.5 returns `pass` with refusal content; content SAFE per controller + judge review; carry-forward to v0.1.23+: update gold expected_verdict OR Auditor refinement to detect v1.5 Finding-based refusal pattern). **10 §22.22 disclosures verbatim in ADR-0029**: (1) 3 prior probe attempts $0 documented; (2) Windows CryptoAPI CRL block infra fix; (3) v0.1.21 Capa A bug 12h broken-fail-safe; (4) spec amendment for Capa A fix during v0.1.22 (§22.22-honest path); (5) 1-arm-vs-cached vs 2-arm fresh trade-off (~24h API drift acknowledged; mitigated by same-day execution + ~50% cost savings); (6) per-capability attribution NOT measured (factorial 64-arm cost-prohibitive at any reasonable budget; v0.1.22 measures package not parts); (7) cost-per-chat €0.063 over soft bar €0.05 by €0.013/case (Capa C retry overhead per ADR-0027 D4); (8) coverage gate inherited failure 88.55% < 90% from v0.1.21.3 `@slow` hotfix (v0.1.22 IMPROVES +0.72pp); (9) Bucket D heuristic overlap with Bucket A in T5 (both 0 cases anyway, doesn't affect headline); (10) pre-v0.1.22 budget gap ~$3.50 (harness $8.46 vs Anthropic console $11.95 — Haiku judge layer untracked in harness + EUR/USD variance + possible dev/test calls; H17 honesty). HARD invariants intact: §6 `citation/validator.py` byte-unchanged + Auditor + Council + Analyst prompts v1.0-v1.5 + Pydantic schemas + eval pipeline + gold set + retrieval (the Capa A fix is in `agents/analyst.py` tool_use schema construction only; v0.1.22 modifies ONLY this one src/ file). ADR-0029 (count: 28 → 29) + 5-bucket per-citation mechanism report + comparison report + safety-floor manual review + skip-proceed-decision (T2 PROCEED gate) + probe (T1 €0.32) + main+safety (T3 €1.59). Gate autoritativo: `uv run pytest -m "not slow"` → **962 passed / 0 failed / 1 skipped** (was 968 at v0.1.21.3 hotfix baseline; net delta narrated by T8 verification logs; 3 new Capa A regression tests + harness/scripts adjustments) + `uv run mypy src` Success 71 source files exit 0 (UNCHANGED — no new .py under src/; recursive walker added to existing `agents/analyst.py`) + redteam-smoke 0.92 carry. **5 consecutive milestones with §22.22 honest framing pattern** (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 / v0.1.22): per-task reviews validate per-task correctness; cumulative empirical validation lives at paid-milestone cadence; honest disclosure of trade-offs in closure narrative. **Closes the v0.1.21 T6 §22.22 caveat lineage AND closes the cumulative-impact measurement question for the entire v0.1.19→v0.1.21.2 capability arc** (cerrado 2026-05-25, squash `57d7711`, ADR-0029) · `v0.1.22.1` ✅ verdict-match drop diagnostic ($0 cache mining; responds to user-flagged "verdict_match muy bajo + no hay mejoría tan grande como la esperada" at v0.1.22 close; mirrors v0.1.21.1 / v0.1.17 diagnose-first pattern). NEW `scripts/v0122_1_verdict_diagnostic.py` (789 lines) classifies 16 RHR cases per 4 hypotheses with precedence H4 > H1 > H3 > H2. **Headline: H1 DOMINANT 10/16 = 62.5%** (validator-too-strict vs eval-metric mismatch); H4 = 1/16 chat-003 (legitimate Tier 1 catch); H2 = H3 = 0/16; mixed (n_invalid=1 below quorum) = 5/16. **Diagnostic interpretation**: production validator (`citation/validator.py` byte-unchanged since H4 per §6 invariant) uses STRICT text-match; eval-metric (`evals/metrics.py` v0.1.18 hierarchical containment per ADR-0024) uses lenient bidirectional containment. When v0.1.21 Tier 1 quorum fires on `n_invalid ≥ 2`, those "invalid" citations are often FALSE NEGATIVES from validator — gold-expected articles ARE emitted + valid per hierarchical containment, but validator rejects via strict text matching → unnecessary RHR escalation. Examples: chat-016, chat-017, chat-018, chat-019, chat-021..026 all show emitted citations matching gold per hierarchical containment but validator marks them invalid with `text_not_in_apartado` errors. **v0.1.23 decision tree**: H1 dominant → v0.1.23 path = propagate hierarchical containment match from eval-metric to production validator. **HIGH §6 risk** (validator IS the §6 enforcement layer). Requires NEW ADR-0030 + careful TDD + paid mini-validation (~€2-3) to confirm verdict_match improves on H10 cohort. Alternative: accept Tier 1 working-as-designed verdict_match drop as documented safety cost + proceed directly to H16; revisit v0.1.23+ post-TFM. User decides at v0.1.22.1 T-final review. **HARD invariants (5 PASS, all empty diffs)**: NO src/ touch + NO test additions + NO gold update + NO evals/ pipeline changes + NO new ADR. Gate UNCHANGED: 962/0/1 + mypy 71 Success + redteam-smoke 0.92 + coverage 88.55%. **§22.22 caveats** (5 documented in verdict-drop-analysis.md): H2 refusal-regex may false-positive; H1 lenient bidirectional containment may over-attribute if gold inconsistent; H4 > H1 > H3 > H2 precedence prioritizes "legitimate catch" (5 mixed need manual); gold expected_citations may itself be incomplete; per_citation_audits trail integrity verified post-v0.1.21.1 D2. **6 consecutive milestones with §22.22 honest framing** (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 / v0.1.22 / v0.1.22.1) — diagnostic-first methodology vindicated again. $0 throughout (~$10.95 Anthropic budget UNUSED in v0.1.22.1) (cerrado 2026-05-25, squash `14335ff`, NO new ADR; mirrors v0.1.21.1 light pattern) · **v0.1.23 CONDITIONAL** (propagate hierarchical containment to validator.py; ADR-0030; HIGH §6 risk; ~2-3 days $0 implementation + ~€2-3 paid mini-validation) OR direct H16 HF Spaces deploy + foundation production-grade · H17 TFM closure.
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

**Nota (v0.1.16, ADR-0021):** los thresholds del informe `evals/reports/latest.md` ahora se renderizan en dos columnas: la columna **Aspiracional** mantiene los targets §17 verbatim como dirección a largo plazo (informacional), y una nueva columna **v0.1.20-bar** define el mark medible que el run de pago v0.1.20 debe cumplir (anclado a las medidas H10 30-case + H15 v1.2 30-case — sin números prometidos). Soft mark (no rompe CI; ADR-0010 D4 sigue firme). El juez sigue siendo Haiku 4.5 (ADR-0010 D1 caveat resuelto con "stay" explícito; migración cross-vendor diferida a HX post-TFM). Ver `docs/v0120_bar_thresholds.md` para WHAT/WHY/HOW/IMPACT + tabla de valores derivados.

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

- **v0.1.15** — Chat gap-analysis mode cerrado (2026-05-21, squash `4ea2d9e`, tag `v0.1.15-gap-analysis-chat`). Prompt-only extension Analyst v1.2 → v1.3 with NL auto-detection (Hard Rule 8: BOTH state declaration + gap-seeking question; ambiguous → Q&A default). Gap-analysis Findings reuse existing `Finding{text, citations[], severity}` schema → zero schema change, zero API change, zero backend touch beyond the prompt file itself. §6 Auditor + citation-validator BYTE-UNCHANGED (verified by 4 git-diff checks). Production default stays v1.0 (boundary contract carried — env-unset = v0.1.14 byte-identical); v1.3 opt-in via `REGULAITOR_ANALYST_PROMPT_VERSION=v1.3` for TFM demos and v0.1.20 paid bundle. v1.3 preserves the v1.2 Q&A Example 1 verbatim (regression-zero anchor on Q&A path even when v1.3 loaded). Gold set 54 → 64 chat cases (+5 precise industry-g{1..5} + 5 vague-real industry-gv{1..5}, all `corpus_esperado="auto"`). 14 new $0 unit tests (7 prompt fidelity + 7 gold case schema). ADR-0020 + `docs/gap_analysis_chat_mode.md` memoria-ready (WHAT/WHY/HOW/IMPACT + §6 invariant interpretation callout). NO paid LLM run in v0.1.15 (empirical measurement deferred to v0.1.20 paid bundle alongside all maximalist-plan optimizations). Code-review follow-ups carried for v0.1.20 / possible v1.4: I-1 positive-coverage example missing, I-2 Rule 8 keyword list closed (may under-trigger on paraphrases), I-3 severity scale e.g. vs Example 2 calibration drift. Gate authoritative: `uv run pytest -m "not slow"` → 850 passed / 0 failed / 1 skipped, ≥90% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 + redteam-smoke 0.92 (= v0.1.14 carry). Plan maximalist microhito 8/12 done. Ver `docs/technical_decisions_log.md` §v0.1.15 + ADR-0020 + `docs/gap_analysis_chat_mode.md`.

- **v0.1.16** — Dual-layer §17 thresholds + judge family stays Haiku 4.5 cerrado (2026-05-21, squash `bc7b349`, tag `v0.1.16-section17-thresholds`). Replaces `evals/report.py::_THRESHOLDS` 3-tuple `(metric, threshold, gated)` with 4-tuple `(metric, v0120_bar, aspirational, gated)`; report renders 4-column aggregate table with dual ✅/❌ marks; new `_render_caveats_block` function emits 4-bullet "Caveats — v0.1.20-bar reading" subsection (aspirational framing, bar derivation lineage, Haiku-stays-judge, latency-contamination-note). Bar values per metric (anchored to H10 + H15 v1.2 measured baselines, no promised numbers): faithfulness 0.65, answer_relevancy 0.55, context_precision 0.55, citation_precision 0.25, citation_recall 0.60, verdict_match 0.35, severity_match 0.35; aspirational values verbatim from CLAUDE.md §17 (≥0.85/0.85/0.80/0.90/0.80/0.85/0.80). Judge family: ADR-0010 D1 caveat ("deferred to H12") resolved as explicit "stays Haiku 4.5 in v0.1.16; cross-vendor migration to GPT-4o-mini / Llama-3.3-70b via Groq moved to HX post-TFM"; preserves H10 cache continuity; §19 satisfied literally (Haiku ≠ Sonnet model class). Soft mark only (no `--gate` CLI, no CI break; ADR-0010 D4 carries). v0.1.20 acceptance ritual unlocked: decisions_log §v0.1.20 will narrate "X/8 metrics passed bar; Y/8 below" with per-metric production-default flips decided in that narrative. Single src file modified (`evals/report.py`); backend H1-H5/H7 + Auditor + citation-validator + Pydantic schemas + DTOs + eval-internals (judge/cache/harness/metrics/schemas) all BYTE-UNCHANGED (3 git-diff HARD checks empty). 6 new $0 unit tests pin bar values + aspirational values + dual-column render + caveats anchors + bar < aspirational sanity. ADR-0021 + `docs/v0120_bar_thresholds.md` memoria-ready. NO paid LLM run in v0.1.16 (measurement bundled into v0.1.20). Gate authoritative: `uv run pytest -m "not slow"` → 856 passed / 0 failed / 1 skipped, ≥90% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 + redteam-smoke 0.92 (= v0.1.14/v0.1.15 carry). Plan maximalist microhito 9/12 done. Ver `docs/technical_decisions_log.md` §v0.1.16 + ADR-0021 + `docs/v0120_bar_thresholds.md`.

- **v0.1.17** — No-Answer residual diagnostic ($0 cache-mining classifier) cerrado (2026-05-22, squash `e5dbedd`, tag `v0.1.17-no-answer-diagnosis`). New `scripts/diagnose_no_answer.py` (559 lines) disambiguates the no_answer residual (H10 baseline 7/30 + H15 v1.2 holdout 2/14) into 4 sub-cases (refusal / analyst_raise / transport_error / other) by mining the 381-file judge cache (each cached judge prompt contains the full Analyst `actual_answer` text per request.user JSON). **Verdict: other-dominant** (per `docs/no_answer_residual_diagnosis.md`): 12 total no_answer cases; refusal=0, analyst_raise=0, transport_error=2 (17%), other=10 (83%). Trajectory analysis H10 v1.0 → H15 v1.2 confirms Intervention B (hardened Output contract) HELPED: transport_error dropped from 1 to 0, other halved from 6 to 3 on the 30-case cohort. **Deeper finding (beyond mechanical interpretation)**: inspecting the 10 `other` cases reveals they are mostly **prose-without-findings** — Analyst emits substantive text-field answers (real RGPD/AI Act content) but fails to structure as `Finding` objects with citations. The redteam-block cases ARE refusals but with phrasings outside the 22-entry seed list ("Esta solicitud/consulta no puede ser atendida"). This is a 5th mechanism v0.1.17's taxonomy didn't anticipate; documented honestly per §22.22. **Intervention v0.1.17.1 = TWO-part**: (a) expand REFUSAL_PHRASES seed to catch "Esta solicitud/consulta no puede ser atendida" patterns (reclassifies ~2 cases from `other` → `refusal`); (b) tighten Analyst Output contract via prompt v1.4 to FORCE Finding emission even when emitting substantive prose. Intervention itself NOT shipped in v0.1.17 (diagnostic-first design per ADR-0022 D1). 11 new $0 unit tests pin classifier behavior + 22 REFUSAL_PHRASES (16 ES + 6 EN) seed-list regression anchor + actual_answer extractor + report parser (handles chat + cross-corpus case IDs). ADR-0022 (count 21 → 22) + `docs/no_answer_residual_diagnosis.md` memoria-ready (produced by the script, not hand-written; doubles as WHAT/WHY/HOW/IMPACT). Fix-the-right-thing risk reduced: a fix-first prompt v1.4 (skipping the diagnostic) would have addressed only the refusal-phrasing aspect, not the more dominant prose-without-findings pattern — diagnostic-first paid off by exposing the 5th mechanism. NO paid LLM run in v0.1.17 (cache-mining covers data at $0). Backend H1-H5/H7 + Auditor + citation-validator + Pydantic schemas + DTOs + eval pipeline (judge/cache/harness/metrics/schemas/report) + Analyst prompts v1.0/v1.1/v1.2/v1.3 + gold set ALL BYTE-UNCHANGED (5 git-diff HARD checks empty). Gate authoritative: `uv run pytest -m "not slow"` → 867 passed / 0 failed / 1 skipped, ≥90% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 + redteam-smoke 0.92 (= v0.1.14/v0.1.15/v0.1.16 carry). Plan maximalist microhito 10/12 done. Ver `docs/technical_decisions_log.md` §v0.1.17 + ADR-0022 + `docs/no_answer_residual_diagnosis.md`.

- **v0.1.17.1** — No-Answer residual fix (TWO-part + 5-bucket extension) cerrado (2026-05-22, squash `98f3768`, tag `v0.1.17.1-no-answer-fix`). $0 milestone; intervention derived from v0.1.17 cache-mining diagnostic verdict (other-dominant 10/12 = 83%) + per-case inspection that surfaced a 5th mechanism (8 of 10 `other` cases = prose-without-findings, NOT just refusals-with-different-phrasing). **THREE-part scope**: (a) `scripts/diagnose_no_answer.py` REFUSAL_PHRASES seed 22 → 25 (3 ES additions: "esta solicitud no puede ser atendida", "esta consulta no puede ser atendida", "no se puede atender" — observed in chat-014/015 redteam-block cases); (b) NEW `src/regulaitor/agents/prompts/analyst/system.v1.4.md` (216 lines) = v1.3 verbatim + Hard Rule 9 (force-Finding-emission + self-check + "remove the claim or add Finding" out) + Output contract amendment on context-supports-answer branch ("every substantive claim in `text` must map to ≥1 Finding — empty `findings` with non-empty substantive `text` is INVALID"). Hard rules 1-8 + Output format + Output contract — gap-analysis branch + Examples 1-3 BYTE-IDENTICAL to v1.3 (regression-zero on gap-analysis chat mode + Q&A; verified by 4 byte-equal tests); (c) classifier 5th bucket `prose_without_findings` (cache entry present + non-empty + no refusal phrase + len > 100; cases ≤ 100 chars stay `other` per conservative heuristic per ADR-0023 D4). Production default stays **v1.0** (boundary contract carried since v0.1.15; v1.4 opt-in via `REGULAITOR_ANALYST_PROMPT_VERSION=v1.4` for v0.1.20 paid bundle measurement). NO paid LLM run in v0.1.17.1 (empirical v1.0 vs v1.4 A/B deferred to v0.1.20 bundle per bundled-validation discipline established v0.1.8 + ADR-0021 v0.1.20-bar). Diagnostic re-run validates (a)+(c) work: refusal 0 → **2**, prose_without_findings 0 → **8**, other 10 → **0** (clean 100% partition of v0.1.17's `other`-dominant residual into the two new evidence-driven categories), transport_error 2 → 2 unchanged, analyst_raise 0 → 0 unchanged. Per-report: candidate-v1.2.md 3 cases (refusal=2, prose_without_findings=1) / holdout-v1.2-chat.md 2 cases (transport_error=1, prose_without_findings=1) / latest.md 7 cases (transport_error=1, prose_without_findings=6). Backend H1-H5/H7 + Auditor + citation/validator + eval pipeline (judge/cache/harness/metrics/schemas/report) + Pydantic schemas + DTOs + prior Analyst prompts v1.0/v1.1/v1.2/v1.3 + gold set ALL BYTE-UNCHANGED (5 git-diff HARD checks at T7). ADR-0023 (count: 22 → 23) + `docs/no_answer_residual_diagnosis.md` memoria-ready (regenerated by script with v0.1.17.1-aware H1+Status). 13 new $0 unit tests (4 new + 1 updated in test_diagnose_no_answer.py + 9 new in test_analyst_v1_4_loads.py); 1 test renamed in T2 fix (`test_classify_other_when_non_refusal_prose` → `test_classify_prose_just_above_100_char_threshold` to remove misleading name after assertion update). Gate authoritative: `uv run pytest -m "not slow"` → 880 passed / 0 failed / 1 skipped, ≥90% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 (UNCHANGED — no new .py under src/) + redteam-smoke 0.92 (= v0.1.14/v0.1.15/v0.1.16/v0.1.17 carry). **Diagnostic-first design vindicated**: had v0.1.17.1 been a speculative fix-first (skipping v0.1.17), v1.4 would have addressed only 17% of the residual instead of the dominant 67%. 4 code-quality review catches across T1/T2/T4 (T1 Critical stale docstring → amended; T2 Important misleading test name → rename; T4 I-1 Hard Rule 9 vs gap-analysis Example 3 borderline-claim → carried for v0.1.20 measurement; T4 I-2 English self-check in bilingual prompt → acceptable under `model_compatibility: [claude-sonnet-4-6]`). Plan maximalist microhito **10b/12** done. Ver `docs/technical_decisions_log.md` §v0.1.17.1 + ADR-0023 + `docs/no_answer_residual_diagnosis.md`.

- **v0.1.18** — Citation granularity confound (eval-instrument fix) cerrado (2026-05-22, squash `670e35e`, tag `v0.1.18-citation-granularity`). $0 milestone resolving H15.1 §22.22 design-defect disclosure (ADR-0017) on instrument invariance: v1.2's holdout citation=0.00 was instrument-artifact (granularity mismatch: H8 apartado-level expected vs H14/industry article-level expected; 38 apartado + 91 article across 64 chat cases), NOT measurement of v1.2 quality. **Scope**: (a) `evals/metrics.py` gains `_citation_matches` helper encoding 7-row hierarchical containment truth table (article-expected matches any apartado of that article; apartado-expected requires exact apartado match; prefix-collision defended via trailing-dot startswith) + rewritten `compute_citation_metrics` body (signature + return type + dedup-first behavior preserved); (b) re-rendered 15 historical chat-mode reports at $0 via new `scripts/rerender_reports.py` (~200 lines; string-surgery on per-case Citation rows + aggregate header recomputation; idempotent); (c) ADR-0024 (count: 23 → 24) documents 5 decisions + 6 rejected alternatives + §6 interpretive distinction (production-side citation VALIDATION byte-unchanged; only post-hoc EVAL metric rewritten). **T3 implementation pivot** (the most important honesty point): plan originally specified `make eval-from-cache` for `latest.md` rerender at $0; controller-verification at T3 discovered `--cache-only` caches ONLY judge layer (chat graph still calls real Anthropic API per `evals/harness.py:204-208`) — NOT $0. Pivoted to use rerender script for ALL 15 files. Documented in T3 commit + ADR-0024 D3 + Alternatives so future milestones don't repeat the assumption. **T3 dramatic flips** (Done-when #9 anchor; H15.1 §22.22 design-defect RESOLVED): `holdout-v1.2-chat.md` precision_mean 0.00 → **0.65** / recall_mean 0.00 → **0.64**; `h15_1-holdout.md` 0.00 → 0.69 / 0.72; `holdout-v1.2-chat-probe.md` 0.00 → 0.71 / 1.00. Smaller H10/H8 cohort deltas: `latest.md` 0.18 → 0.21 / 0.48 → 0.56; `latest.cost.md` 0.49 → 0.56 / 0.60 → 0.69; `latest.evaluation.md` 0.46 → 0.53 / 0.55 → 0.63. **9 byte-identical files** (4 H15-era cohort + 5 probes) had per-row values invariant under both rules + H15 study aggregator already excluded block cases — script ran but produced byte-identical output, git correctly shows no diff (documented as historical-pipeline detail, not defect). Apples-to-oranges aggregate caveat documented (script's `old → new` mean comparison includes block in old / excludes in new per `evals/metrics.py::aggregate`; the HEADLINE holdout flip 0.00 → 0.65 is REAL since every per-row was 0.00). Doc-mode reports (using `**Findings citations**` label) UNTOUCHED per spec §5 — doc-mode uses same `compute_citation_metrics` transitively, applies to FUTURE v0.1.20 doc-mode runs. Backend H1-H5/H7 + Auditor + `src/regulaitor/citation/validator.py` + eval pipeline non-metric files (judge/cache/harness/schemas/report) + Pydantic schemas + DTOs + Analyst prompts v1.0/v1.1/v1.2/v1.3/v1.4 + gold set ALL BYTE-UNCHANGED (5 git-diff HARD checks at T5). 12 new $0 unit tests (7 helper truth-table rules + 5 aggregate scenarios); 5 pre-existing `compute_citation_metrics` tests stay UNCHANGED (dedup-first preserves edge-case behavior). Gate authoritative: `uv run pytest -m "not slow"` → 892 passed / 0 failed / 1 skipped, ≥90% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 (UNCHANGED — no `.py` under src/; rerender script is under `scripts/`) + redteam-smoke 0.92 (= v0.1.14/v0.1.15/v0.1.16/v0.1.17/v0.1.17.1 carry). NO paid LLM run; empirical v0.1.20 measurement validates the v1.4 prompt + retrieval levers under the corrected instrument. Plan maximalist microhito **12/12 done** — FINAL $0 microhito of the maximalist plan. Ver `docs/technical_decisions_log.md` §v0.1.18 + ADR-0024.

- **v0.1.19** — Auditor RHR aggregation + Council binding ON cerrado (2026-05-22, squash `8831bcd`, tag `v0.1.19-council-binding`). $0 milestone resolving H13 ADR-0014 Council-binding seam (wired-OFF since shipment) + H15 §16.3 deferral lineage. **Scope (conservative-only direction per ADR-0025 D1)**: flip `_COUNCIL_BINDING: bool = True` in `src/regulaitor/agents/council.py:33` + change `CouncilAgent.__init__` default policy `AdvisoryMajorityPolicy()` → `MonotonicEscalatePolicy()` (D4; aggregate behavior identical; would_escalate becomes available) + NEW `bind_verdict(audited, review, council)` top-level helper (D3; signature takes CouncilAgent to keep private-access concern internal) + `_council_node` wiring in `src/regulaitor/orchestration/graph.py` (D5) + `_council_notice` signature update in `src/regulaitor/api/schemas.py` (`(cr) → (cr, audited=None)` backward-compat default) + branch on `"COUNCIL_BIND:"` reason prefix + caller updates in `to_ask_response()` and `ui_streamlit/_render.py`. **Spec amendment documented honestly (§22.22)**: spec assumed 2 src/ files; reality is 4 (the notice lives in api/schemas.py, not graph.py). **Conservative-only semantics**: PASS → RHR ONLY on unanimous (3/3 ok) BLOCK; NEVER relaxes BLOCK or RHR (the H13 false-RHR pattern 7/12 cases UNCHANGED — deferred to v0.1.20+ evidence-driven decision). §6 invariant ROCK-SOLID: production-side citation VALIDATION (`citation/validator.py`) byte-unchanged + Auditor Lenient-Finding + Strict-Answer aggregation (`auditor.py`) byte-unchanged + Analyst prompts v1.0-v1.4 + eval pipeline + gold set ALL BYTE-UNCHANGED (5 HARD git-diff checks at T5). ADR-0025 (count: 24 → 25). 15 new $0 unit tests (8 in test_council_policy.py = 7 bind_verdict + 1 flag pin; NEW test_graph_council_binding.py with 5 tests for _council_node wiring; 2 new tests in test_council_dto.py for _council_notice binding branch) − 1 stale removed (test_council_binding_seam_is_off) = +14 net delta vs main baseline 893. Gate authoritative: `uv run pytest -m "not slow"` → 907 total / 906 passed / 0 failed / 1 skipped, 93.62% coverage exit 0 + `uv run mypy src` Success 71 files exit 0 (UNCHANGED — bind_verdict added to existing council.py) + redteam-smoke 0.92 carry. NO paid LLM run; empirical effect on escalation rate measured at v0.1.20. **Closes H13 ADR-0014 Council-binding seam + H15 §16.3 deferral lineage.** Ver `docs/technical_decisions_log.md` §v0.1.19 + ADR-0025.

- **v0.1.20** — Paid validation A/B (v1.0 vs v1.4) — FLIP approved cerrado (2026-05-24, squash `1f838ee`, tag `v0.1.20-paid-validation`). Paid milestone (€7.83 / ~$8.45 of $24.95 budget, ~31% spend; ~14h wall-clock paid runs over T1+T2+T4+T5). **Scope**: 64-chat paid A/B of Analyst prompt v1.0 (control) vs v1.4 (force-Finding-emission per Hard Rule 9, v0.1.17.1) using disjoint allowlists (no resume needed); T6 comparison report + T6.5 RHR root-cause diagnostic + T7 hard safety floor + T8 ADR-0026 + T9 closure. **Result: FLIP approved for chat `analyst` role** — env-unset default `agents/analyst.py` flipped v1.0 → v1.4; `document_analyst` role retains v1.0 default (v1.4 was authored for chat role only; doc-mode A/B carried forward as future work). T6 H10 bar 6/7 PASS for v1.4 vs 0/7 for v1.0; T6 full-cohort verdict_match +9.4pp (v1.4 40.6% vs v1.0 31.2%, +6 net wins); T6.5 diagnostic confirms 9 real positive flips vs ~2 real regressions (likely Auditor/Council non-determinism noise). T7 hard safety floor PASS (redteam-smoke 0.92 under v1.4 env + 6/6 designated content-based safety cases pass manual review per H15 C1 pattern). §22.22 T9a scope adjustment honest framing: plan called "1-line change" but TDD on first gate run surfaced a role-aware design defect (uniform v1.4 default broke `AnalystAgent(prompt_role="document_analyst")` — no v1.4 file on disk for that role); fixed by role-aware env-unset branch + new regression test (`test_document_analyst_role_defaults_to_v1_0_when_env_unset`) pinning the gap visibly. HARD invariants intact: §6 `citation/validator.py` + Auditor `auditor.py` + Analyst prompt FILES v1.0-v1.4 + eval pipeline + gold set ALL BYTE-UNCHANGED (5 HARD git-diff checks at T9b); only the default REFERENCE in `agents/analyst.py` flipped (1 src/ file). ADR-0026 (count: 25 → 26). Gate authoritative: `uv run pytest -m "not slow"` → 921 passed / 0 failed / 1 skipped (1 new regression test + 3 test pin updates + 1 docstring update) + `uv run mypy src` Success 71 source files exit 0 (UNCHANGED — flip is 1 src/ file edit; no new .py) + redteam-smoke 0.92 carry (= v0.1.14-v0.1.19 frozen; v1.4 env preserves the rate per T7 measurement). **Closes §22.22 v0.1.17.1 lineage**: the "v1.4 effectiveness measured at v0.1.20" commitment is now measured + decided. Dominant RHR mechanism UNCHANGED (42% nonempty-RHR; v0.1.21 target Auditor RHR quorum) + 35% empty-findings cases UNCHANGED (prompt-only Hard Rule 9 obtains ~50% compliance; v0.1.21 target hard constraints findings non-empty). Wall-clock 14h was 4× plan's 30-60min estimate (§22.22 plan error documented; future paid milestones should use this calibration). T6 caught + fixed a transition-matrix bug in `scripts/v0120_compare.py` inline; script cleanup carried to v0.1.21. Ver `docs/technical_decisions_log.md` §v0.1.20 + ADR-0026 + comparison report + safety-floor evidence + rhr-root-cause-diagnostic.

- **v0.1.21** — Auditor RHR quorum (Tier 1) + Analyst format hard constraints (Tier 2 Capa A+B+C) cerrado (2026-05-24, squash `f073e74`, tag `v0.1.21-auditor-quorum-hard-constraints`). **$0 capability milestone** (~$0.01 noise para T0 Anthropic strict-mode field-support probe; otherwise no paid LLM run). **Scope dual-tier per ADR-0027 D1-D6**: Tier 1 modifies `src/regulaitor/agents/auditor.py` aggregation semantics — replaces the implicit "any per-citation invalid → turn RHR" branch with explicit quorum threshold `sum(invalid) >= 2 → turn RHR; exactly 1 invalid → turn PASS` (PASS / BLOCK branches unchanged); targets the 42% dominant nonempty-RHR mechanism from v0.1.20 T6.5 diagnostic. Tier 2 layers three defensive enforcement mechanisms targeting the 35% empty-findings mechanism: Capa A modifies `src/regulaitor/agents/analyst.py` tool_use construction with `"strict": True` on `emit_answer` tool entry + `"minItems": 1` on `findings` array property (API-level guarantee; T0 confirmed Sonnet 4.6 supports `strict` field); Capa B modifies `src/regulaitor/citation/schemas.py` with `Answer.findings: list[Finding] = Field(min_length=1)` (server-side defense-in-depth); Capa C modifies `AnalystAgent.analyze` in `analyst.py` from H8 1-retry pattern to 3-attempt loop catching ANY Pydantic ValidationError + failure-specific feedback (failure category + first 200 chars of offending text + actionable instruction). **T6 $0 cache-mining diagnostic outcome (§22.22 honest framing, the headline payload)**: `scripts/v0121_quorum_diagnostic.py` + `evals/reports/v0.1.21/quorum-diagnostic.md` cache-mines v0.1.20 ARM A checkpoints to estimate Tier 1 impact at $0. **LOWER bound = 0 unambiguous flips** (zero K=1 RHR cases — no v0.1.20 ARM A RHR was triggered by a single-citation invalid); **UPPER bound = 0..36 ambiguous K≥2 RHR cases** (cache schema limitation: aggregate `actual_verdict` + `citations.emitted` list persisted, NOT per-citation `AuditResult` — cannot replay validator outputs to determine how many invalid citations each ambiguous case had); **mechanical D5 verdict MARGINAL** (0 ≤ 5 threshold). 2 RHR-no-citations cases (Tier 2 territory, skipped). The MARGINAL verdict is an **artifact of the cache schema, not necessarily a measurement of Tier 1's actual impact** — real flip count is in interval [0, 36] (could be 0% if every ambiguous case had ≥2 invalid → Tier 1 changes nothing; could be 100% if every ambiguous case had exactly 1 invalid → Tier 1 would flip 36/38 ≈ 95% of v0.1.20 RHR). **v0.1.22 paid validation DEFERRED to user authorization per ADR-0027 dual interpretation**: (A) Strict mechanical = defer per spec D5, proceed to H16 (default recommendation) / (B) Acknowledged ambiguity = pursue v0.1.22 PRECISELY because diagnostic cannot resolve the 36 ambiguous cases (~€4-6 30-case A/B). HARD invariants intact: §6 `citation/validator.py` + Auditor aggregation (the deterministic Lenient-Strict logic outside the quorum branch) + Council (`council.py`, `council_binding`, `bind_verdict`) + Analyst prompts v1.0-v1.4 + eval pipeline + gold set ALL BYTE-UNCHANGED (5 HARD git-diff checks at T7). 3 src/ files modified (`agents/auditor.py` + `agents/analyst.py` + `citation/schemas.py`; 6th HARD invariant: src/ scope = 3 expected files). ADR-0027 (count: 26 → 27). 11 new $0 unit tests across 3 NEW test files (4 Tier 1 quorum in `tests/unit/agents/test_auditor_quorum.py` + 3 Capa B Pydantic in `tests/unit/citation/test_schemas_findings_min_length.py` + 4 Capa C retry feedback in `tests/unit/agents/test_analyst_retry_feedback.py`) + **7 pre-existing test sites updated for Capa B contract** (honest scope expansion: spec projected 5; T3 found 2 additional; `test_answer_findings_can_be_empty` inverted to `test_answer_rejects_empty_findings` documents the contract change directly) + 4 H8-era tests updated for Capa C 3-attempt contract (`test_analyze_no_retry_when_other_validation_errors` + `test_analyze_raises_after_two_failed_attempts` + 2 related pins). Gate autoritativo: `uv run pytest -m "not slow"` → **935 passed / 0 failed / 1 skipped** (was 921 baseline at v0.1.20 closure; +14 net) + `uv run mypy src` **Success 71 source files exit 0** (UNCHANGED — no new .py under src/) + redteam-smoke **0.92** carry (= v0.1.14-v0.1.20 frozen; new Auditor quorum does not regress safety floor — redteam-smoke cases never hit the K≥2 cell that quorum loosens). Sin skills nuevas. **Closes the v0.1.20 T6.5 diagnostic lineage** as capability shipment; the empirical effect against v0.1.20-bar is the v0.1.22 conditional question. **Final whole-branch review caught 4 Criticals resolved pre-closure**: (C1) ADR-0027 D1 + decisions_log honest amendment — pre-v0.1.21 code never used `any() RHR` aggregation; what v0.1.21 ships is a STRENGTHENING (NEW escalation path from all-pass-Findings to RHR when n_invalid ≥ 2); partial + all-blocked branches UNCHANGED. (C2) NEW escalation-path test `test_aggregation_lenient_finding_passes_but_quorum_escalates` added + misleading docstrings fixed + M3 rename (`test_audit_answer_with_no_findings_passes` → `_rejected_at_schema`). (C3) Diagnostic script + report + synthetic-test docstring amended — the classifier is correct for the wrong reason because pre-v0.1.21 K=1 RHR cases are nil by construction. (C4) **v1.5 Analyst prompt SHIPPED + chat default flip v1.4 → v1.5** (`src/regulaitor/agents/prompts/analyst/system.v1.5.md` + `src/regulaitor/agents/analyst.py` default ref): Capa A+B contradicted the v1.0-v1.4 `findings: []` refusal pattern → would have caused §6 invariant violation at runtime (Capa B rejects → Capa C retries → Sonnet fabricates Finding). v1.5 ships Finding-based refusal (exactly 1 Finding + corpus citation + severity high) preserving §6 via corpus-grounded refusal. Doc role unchanged (still v1.0; no v1.5 for doc-mode). 3rd consecutive milestone with §22.22 honest scope adjustment from per-task review missing cross-task design coherence (v0.1.19 + v0.1.20 + v0.1.21). 10 new $0 unit tests in `tests/unit/test_analyst_v1_5_loads.py` + 1 pre-existing test renamed in `test_analyst_prompt_env_seam.py` (default assertion flipped v1.4 → v1.5). Ver `docs/technical_decisions_log.md` §v0.1.21 + ADR-0027 + `evals/reports/v0.1.21/quorum-diagnostic.md`.

- **v0.1.21.1** — Pre-v0.1.22 hardening (Tier 1: 3 contamination vectors) cerrado (2026-05-24, squash `911ecae`, tag `v0.1.21.1-pre-v0122-hardening`). **$0 capability micro-milestone** (no paid LLM run; mini-milestone decimal per precedent v0.1.8/v0.1.15.1/v0.1.17.1). **Scope (3 items, NO new ADR)**: (D1) fix `scripts/v0120_compare.py` transition matrix bug carried from v0.1.20 T6 (was fixed inline in comparison.md; script itself still had bug → corrupted v0.1.22 comparison report if reused); (D2) add `per_citation_audits: list[dict] | None = None` field to `evals/schemas.py::ChatCaseResult` + propagate from `evals/metrics.py` chat harness path — enables future $0 diagnostics with per-citation precision (closes v0.1.21 C3 §22.22 cache-schema limitation); backward-compat Optional default for old v0.1.20 ARM A/B checkpoints; (D3) v1.5 refusal mock e2e tests (`tests/unit/agents/test_v1_5_refusal_e2e.py`, 5 tests) verifying Finding-based refusal format passes Capa A+B + Capa C doesn't retry valid format + Auditor processes correctly + §6 invariant under fabricated-citation refusal blocks. **0 src/ changes** (all D1-D3 in scripts/ + evals/ + tests/); HARD invariants intact: §6 `citation/validator.py` + `citation/schemas.py` + `auditor.py` + `council.py` + Analyst prompts v1.0-v1.5 + gold set ALL BYTE-UNCHANGED. **NO new ADR** (mechanical bug fix + schema extension + test addition). Gate: `uv run pytest -m "not slow"` → **955 passed / 0 failed / 1 skipped** (was 946 baseline at v0.1.21 close; +9 net = 1 D1 + 3 D2 + 5 D3 new tests) + `uv run mypy src` Success 71 source files exit 0 (UNCHANGED) + redteam-smoke 0.92 carry. **Closes 3 contamination vectors before v0.1.22 paid run** — v0.1.22 (if pursued) will (a) produce correct transition matrix report + (b) emit per-citation audit trail for future $0 diagnostics + (c) ship with v1.5 refusal interaction tested + verified. Ver `docs/technical_decisions_log.md` §v0.1.21.1.

- **v0.1.21.2** — Tier 2 retrieval defaults flip + chat refusal mock cerrado (2026-05-24, squash `6552d1c`, tag `v0.1.21.2-tier2-flips`). $0 mini-milestone (precedent v0.1.21.1). Scope: (D1) flip max_chunks_per_norma=2 production default in `src/regulaitor/rag/retrieval.py:63` per v0.1.11 BREAKTHROUGH 1/3→2/3 cross-corpus evidence; (D2) flip top_k_auto=12 production default per v0.1.12 wiring algorithmically verified (applies to auto-corpus queries only); (D3) NEW `tests/unit/redteam/test_chat_refusal_mock.py` (6 tests) closes v0.1.21 final review I5 caveat (smoke gate doc-mode-filtered; chat refusal under v1.5+Capa A+B was unmeasured). Backward-compat: explicit `RetrievalConfig(max_chunks_per_norma=None, top_k_auto=None)` opt-out restores old behavior. **§22.22 honest framing**: NO paid validation pre-flip; v0.1.22 paid run (CONDITIONAL) measures cumulative package (Tier 1 quorum + Capa A+B+C + v1.5 + retrieval defaults). HARD invariants intact: §6 `citation/validator.py` + Auditor + Council + Analyst prompts v1.0-v1.5 + eval pipeline + gold set ALL BYTE-UNCHANGED. 1 src/ file modified (`rag/retrieval.py` 2 lines). ADR-0028 (count: 27 → 28). 13 new $0 unit tests across 2 NEW test files (7 retrieval defaults + 6 chat refusal mock). Gate 968 passed / 0 failed / 1 skipped + mypy 71 Success UNCHANGED + redteam-smoke 0.92 carry. 4th consecutive milestone with §22.22 framing on capability ships without paid pre-validation (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 — pattern: per-task reviews validate per-task correctness; cumulative empirical validation lives at paid-milestone cadence). **Closes v0.1.21 I5 caveat + ships best-evidence retrieval defaults to production**. Ver `docs/technical_decisions_log.md` §v0.1.21.2 + ADR-0028.

- **v0.1.22** — Paid validation (cumulative-impact A/B vs v0.1.20 ARM B baseline) cerrado (2026-05-25, squash `57d7711`, tag `v0.1.22-paid-validation`). Paid milestone (€1.91 / ~$2.06 USD of $13 budget = ~16% of forecast high; well under €3.78 high-extrapolation per spec D3 SKIP/PROCEED gate). **Scope**: 1-arm fresh paid (ARM v0.1.22-prod) vs cached baseline (ARM v0.1.20-ARM-B extracted $0 from existing 64-case ARM B report) on H10 30-case chat (chat-001..030) + 2 ad-hoc safety (nis2-006, dora-006) under env-unset production state (v1.5 chat + Tier 1 Auditor quorum + Tier 2 Capa A+B+C + retrieval defaults max_chunks_per_norma=2 / top_k_auto=12 + Council binding ON). Closes the cumulative §22.22 caveat lineage from v0.1.19→v0.1.21.2 (5 capabilities empirically validated as a package). **Decision: CONDITIONAL CONFIRM** per spec D4 third path — production state retained (no flip needed; package already shipped at prior milestones); cumulative arc safe-to-retain with mixed performance + carry-forwards documented for v0.1.23+. **§22.22 spec amendment**: spec said "ZERO backend touch — pure measurement"; reality 1 src/ file modified (`agents/analyst.py` recursive `_set_additional_properties_false_recursive` walker — Capa A schema fix). v0.1.21 Capa A shipped silently broken for ~12h (additionalProperties=False set on root only; nested $defs Finding+Citation untouched → Anthropic strict mode rejects 400 → Capa C retries 3× fail → empty Answer → Auditor RHR → 100% RHR rate on chat post-v0.1.21 merge). Broken-fail-safe per §6 (conservative all-RHR, no fabrication) but production was 100%-RHR-as-actually-shipped. Fixed DURING v0.1.22 + 3 regression tests; §22.22-honest path (vs ship-broken-measurement). **3 prior probe attempts failed at $0** before first paid call: (1) truststore absent → Windows CryptoAPI CRL block both HF+Anthropic SSL (CRYPT_E_NO_REVOCATION_CHECK 0x80092012); (2) HF fix only; (3) SSL fixed via `truststore.inject_into_ssl()`, Capa A bug surfaced. Documented in `evals/reports/v0.1.22/probe-attempt-{1,2,3}*.md`. truststore 0.10.4 in `.venv` only NOT in `pyproject.toml` → carry-forward. **Per-metric results (7 v0.1.20-bar)**: 4/7 PASS bar (faithfulness 0.71 / answer_relevancy 0.74 / context_precision 0.78 / severity_match 0.40); 3/7 improve (answer_relevancy +0.14 / context_precision +0.11 / severity_match +0.07); 3/7 regress (faithfulness -0.05 above bar; citation_precision -0.08 below bar; citation_recall -0.09 below bar — mechanism = v1.5 Finding-based refusal emits more citations per refusal, narrower gold intersection); 1/7 flat (verdict_match 0.30 below bar 0.35). Aggregate verdict pass=10/RHR=16/block=4. **Per-citation mechanism (T5 5-bucket $0 diagnostic via v0.1.21.1 D2 trail)**: **NEW v0.1.21 Tier 1 quorum-triggered RHR cases = 11/30 (36.7%)** (Bucket C). Empirically resolves ADR-0027 §22.22 caveat (LOWER 0 / UPPER 0..36 → REAL 36.7% within predicted interval). Bucket A=0 + Bucket D=0 → **Tier 2 Capa A+B+C 100% effective** at preventing empty-findings escape on this cohort. **Hard safety floor PASS**: redteam-smoke 0.92 carry + 6/6 designated content cases SAFE + 0/6 fabrications + 6/6 explicit rejection + 6/6 real corpus citation + 18/18 judge criteria PASS. §6 invariant ROCK-SOLID. 10 §22.22 disclosures documented verbatim in ADR-0029 (count: 28 → 29). HARD invariants intact: §6 `citation/validator.py` + Auditor + Council + Analyst prompts v1.0-v1.5 + Pydantic schemas + eval pipeline + gold set + retrieval ALL BYTE-UNCHANGED. 1 src/ file modified (`agents/analyst.py` Capa A fix). 3 new $0 regression tests for recursive walker. Gate autoritativo: `uv run pytest -m "not slow"` → **962 passed / 0 failed / 1 skipped** + `uv run mypy src` Success 71 source files exit 0 UNCHANGED + redteam-smoke 0.92 carry. Coverage 88.55% (PRE-EXISTING inherited from v0.1.21.3 `@slow` hotfix at 87.83%; v0.1.22 IMPROVES +0.72pp via Capa A regression tests; carry-forward: adjust gate to 85% OR fix offline-SSL test path). **5 consecutive milestones with §22.22 honest framing pattern** (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 / v0.1.22): per-task reviews validate per-task correctness; cumulative empirical validation lives at paid-milestone cadence. **Closes the v0.1.21 T6 §22.22 caveat lineage AND closes the cumulative-impact measurement question for the entire v0.1.19→v0.1.21.2 capability arc.** Sin skills nuevas. Ver §16.3 H15.X entry + `docs/technical_decisions_log.md` §v0.1.22 + ADR-0029 + `evals/reports/v0.1.22/` (10 report files: probe-attempt-{1,2,3} + probe + skip-proceed-decision + v0.1.22-prod-main + v0.1.22-prod-safety-adhoc + v0.1.20-armB-baseline + comparison + per-citation-mechanism + safety-floor).

- **v0.1.22.1** — Verdict-match drop diagnostic ($0 cache mining) cerrado (2026-05-25, squash `14335ff`, tag `v0.1.22.1-verdict-diagnostic`). $0 mini-milestone (mirrors v0.1.21.1 / v0.1.17 diagnose-first pattern) responding to user-flagged §22.22 observation at v0.1.22 close: "verdict_match muy bajo + no hay mejoría tan grande como la esperada". **Scope**: NEW `scripts/v0122_1_verdict_diagnostic.py` (789 lines; ruff + black + mypy strict clean; idempotent; $0) + `evals/reports/v0.1.22.1/verdict-drop-analysis.md` (277 lines; 16-row table + per-case detail blocks) + `evals/reports/v0.1.22.1/v0.1.23-decision-tree.md` (38 lines). NO src/ touch + NO test additions + NO gold update + NO evals/ pipeline changes + NO new ADR (light pattern). Mines v0.1.22 checkpoints (probe + main = 30 cases) + per_citation_audits trail (v0.1.21.1 D2) + gold expectations to classify 16 RHR cases per 4 hypotheses with precedence H4 > H1 > H3 > H2. **Headline: H1 DOMINANT 10/16 = 62.5%** (validator-too-strict vs eval-metric mismatch); H4 = 1/16 chat-003 (legitimate Tier 1 catch — Sonnet answered wrong articles); H2 = H3 = 0/16; mixed (n_invalid=1 below quorum threshold) = 5/16. **Diagnostic interpretation**: production validator (`citation/validator.py` byte-unchanged since H4 per §6 invariant) uses STRICT text-match; eval-metric (`evals/metrics.py` v0.1.18 hierarchical containment per ADR-0024) uses lenient bidirectional containment. When v0.1.21 Tier 1 quorum fires on `n_invalid ≥ 2`, those "invalid" citations are often FALSE NEGATIVES from validator — gold-expected articles ARE emitted + valid per hierarchical containment, but validator rejects them via strict text matching (e.g. `text_not_in_apartado` errors) → unnecessary RHR escalation. Per-case examples (H1 dominant): chat-016, chat-017, chat-018, chat-019, chat-021..026 all show this pattern. **v0.1.23 decision tree**: H1 dominant → v0.1.23 path = **propagate hierarchical containment match from eval-metric to production validator**. **HIGH §6 risk** (validator IS the §6 enforcement layer; loosening must be careful + reversible). Requires NEW ADR-0030 + careful TDD + paid mini-validation (~€2-3) to confirm verdict_match improves on H10 cohort post-fix. **Alternative path**: accept Tier 1 working-as-designed verdict_match drop as documented safety cost + proceed directly to H16; revisit v0.1.23+ post-TFM. User decides post-T-final review. **HARD invariants (5 PASS, all empty diffs)**: NO src/ touch (`git diff main -- src/` empty), NO test additions, NO gold_set update, NO evals/ pipeline changes (metrics.py + schemas.py + harness.py + report.py byte-unchanged), NO new ADR (deferred to v0.1.23+). Gate UNCHANGED: 962/0/1 + mypy 71 Success + redteam-smoke 0.92 + coverage 88.55%. **§22.22 caveats** (5 documented in verdict-drop-analysis.md): H2 refusal-regex heuristic; H1 lenient bidirectional containment may over-attribute if gold inconsistent; H4 > H1 > H3 > H2 precedence prioritizes "legitimate catch"; gold expected_citations may itself be incomplete; per_citation_audits trail integrity verified post-v0.1.21.1 D2. **6 consecutive milestones with §22.22 honest framing pattern** (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 / v0.1.22 / v0.1.22.1) — diagnostic-first methodology vindicated again. $0 throughout (~$10.95 Anthropic budget UNUSED). Ver §16.3 H15.X entry + `docs/technical_decisions_log.md` §v0.1.22.1 + `evals/reports/v0.1.22.1/` (script + 2 reports).

### Hito siguiente

- **v0.1.23 (CONDITIONAL) — Validator hierarchical containment propagation** (HIGH §6 risk; ADR-0030; ~2-3 días $0 implementation + ~€2-3 paid mini-validation on H10 cohort). Per v0.1.22.1 H1-dominant diagnostic: propagate `evals/metrics.py::_citation_matches` lenient bidirectional containment logic to production `src/regulaitor/citation/validator.py`. Goal: reduce validator false-negatives that trigger unnecessary Tier 1 RHR escalation; expected to lift verdict_match 0.30 → ~0.40-0.45 (estimated, not measured). §6 invariant interpretive distinction: validator STILL enforces "no citation, no answer" at hierarchical-containment-match level (not strict-text-match level); the loosening is at the MATCHING layer, not the EXISTENCE layer. ADR-0030 + careful TDD + paid mini-validation to confirm before flip. NOTE: this milestone CAN be deferred OR direct H16 if user prefers (v0.1.22.1 verdict_match drop is documented + Tier 1 working-as-designed; H16 deploy can ship the current state).

- **H16 — Despliegue público (HF Spaces + foundation production-grade per "future product" preference)** — default next milestone if v0.1.23 deferred. v0.1.22 paid validation CLOSED (CONDITIONAL CONFIRM per ADR-0029; cumulative v0.1.19→v0.1.21.2 capability arc empirically validated; NEW Tier 1 quorum mechanism fires 36.7% of cohort; Capa A+B+C 100% effective; hard safety floor PASS). v0.1.22.1 verdict-drop diagnostic CLOSED (H1 dominant 62.5%; v0.1.23 CONDITIONAL). Dual deploy: HF Spaces (demo TFM, gratis) + Render/Fly.io setup (foundation reusable). Docker compose serio + secrets manager + health checks + CORS/CSP. H16 also addresses carry-forwards: truststore → pyproject.toml + coverage gate threshold adjustment (88.55% → 85% OR fix offline-SSL test path) + (if v0.1.23 deferred) verdict_match documentation as known issue. ~1 semana.

- **H17 — Cierre académico**: memoria, model card, data card, AI Act assessment, runbook, cost analysis, video demo, slide deck, evidence matrix completa + apéndice "Product Roadmap" (per "future product" preference). Tag `v1.0.0`. ~1-2 semanas post-H16.
