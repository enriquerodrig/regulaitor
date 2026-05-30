# 17. Gestión del proyecto

Esta sección documenta cómo se gestionó RegulAItor: la disciplina de hitos en lugar de calendarios semanales (CLAUDE.md §16), la gestión de presupuesto para runs de pago (memoria `feedback_cost_estimation_discipline`), y la orquestación del entorno Claude Code (skills, MCPs, subagentes, memoria persistente) que sostuvo 13 milestones consecutivos con framing honesto §22.22 — incluyendo dos REVERTs documentados.

## 17.1 Fases por hito, no por semanas

La regla fundacional del proyecto, fijada en ADR-0001 §"Milestone discipline" (`docs/adr/0001-project-scope.md`, sección "Milestone discipline" alrededor de la línea 35) y reiterada en CLAUDE.md §16, es que **el avance se mide por evidencia cerrada de cada hito, no por calendario**. La disponibilidad del autor del TFM es variable; comprometer fechas semanales habría producido o bien deadlines fallidos o bien recortes silenciosos en los gates.

La línea temporal real fue:

| Bloque | Hitos | Estado |
|---|---|---|
| Bootstrap + corpus + RAG | H0, H0.1, H1, H2 | Cerrados 2026-04-30 → 2026-05-05 |
| Agentes + pipeline + UI + API | H3, H4, H5, H6, H7 | Cerrados 2026-05-05 → 2026-05-10 |
| Evals + redteam + documentación MVP | H8, H9, H10 | Cerrados 2026-05-12 → 2026-05-15 (tag `v0.1.0-mvp`) |
| Observabilidad + router + Council + corpus | H11, H12, H13, H14 | Cerrados 2026-05-16 → 2026-05-18 |
| Calibración + estudio retriever + microhitos | H15, H15.1, H15.2, v0.1.8 → v0.1.30 | Cerrados 2026-05-19 → 2026-05-28 |
| Despliegue público | H16 (tag `v0.1.32-h16-deploy`) | Cerrado 2026-05-28 |
| Cierre académico | H17 (tag `v1.0.0`) | En curso |

Dos patrones merecen ser nombrados explícitamente:

- **Hitos decimales** (H0.1, H15.1, H15.2). Cuando un hito grande se desbordaba o cuando aparecía una palanca system-level no prevista en el roadmap inicial, se insertaba un hito decimal en lugar de renumerar todo el roadmap. Esto preservó la integridad de los identificadores publicados y permitió que H16/H17 siguieran intactos mientras se cubrían deferrals.
- **Microhitos `v0.1.X`**. Tras H15 emergieron numerosos microhitos optimización (la cadena v0.1.8 → v0.1.30), incluyendo subincrementales como v0.1.21.1, v0.1.21.2, v0.1.21.3, v0.1.22.1, v0.1.24.1, además de v0.1.26 (H16 deploy-prep), v0.1.27, v0.1.28, v0.1.29, v0.1.31 y v0.1.32 (H16 deploy). Cada microhito comprendía un objetivo medible, un cierre con tag git y una entrada en `docs/technical_decisions_log.md`. Esta granularidad permitió que los REVERTs (v0.1.23 lenient quorum del Auditor; v0.1.30 title-augmented embeddings) fueran transacciones atómicas: una intervención cerrada con prueba empírica y, si la prueba refutaba la hipótesis, una restauración byte-equivalente del estado anterior.

El gate entre MVP (H10) y avanzado (H11+) se documentó en CLAUDE.md §16.2 como 10 checks bloqueantes (cobertura ≥80%, citation recall ≥0.40, redteam smoke ≥0.90, gitleaks limpio, etc.). Ningún hito avanzado se abrió hasta verificar los 10 verdes; cuando una métrica caía por debajo del objetivo aspiracional pero estaba sobre el gate MVP (caso citation precision 0.17, gate recall-based) se documentó honestamente como follow-up para H15 en lugar de marcarse como éxito o esconderse.

## 17.2 Gestión de presupuesto: la disciplina post-H15.2

El proyecto operó con un presupuesto limitado de APIs Anthropic (~$25 USD totales para todo H15-H17). La disciplina actual de estimación de coste fue **una respuesta directa al desastre H15.2 T6** (2026-05-20), documentado en `docs/technical_decisions_log.md` §H15.2 y en la memoria persistente `feedback_cost_estimation_discipline.md`.

El fallo concreto: en H15.2 se extrapoló linealmente desde una probe de N=3 cases (€0.19) a un full run de N=30 cases (estimación €1.86), con un balance de usuario de €2.43. El run real consumió ~€2.43 y se rompió mid-flight con `anthropic.BadRequestError: credit_balance_too_low` en el caso ~24/30, perdiendo el 100% de los resultados parciales porque el harness escribía el reporte sólo atómicamente al final.

De ahí salieron las cuatro reglas duras que rigieron todos los runs de pago posteriores (v0.1.20, v0.1.22, v0.1.23, v0.1.25, v0.1.27, v0.1.28, v0.1.29, v0.1.30):

1. **Probe mínimo N = 5** (no N = 3). La varianza per-case en latencia y tokens emitidos hace que probes pequeños no sean estadísticamente significativos.
2. **Estimaciones de coste siempre como rango**, no como punto: `low / expected / high = expected × 1.5`. El margen captura varianza + fallback de jueces + retries.
3. **Si el budget del usuario < high-estimate → no se recomienda "proceder"**. Se ofrece SKIP, scope menor, o esperar recarga.
4. **Ningún run de pago sin checkpoint per-case** (v0.1.8 cerró este gate estructuralmente con `evals/checkpoint.py` + `append_case` + `fsync`).

La cuarta regla fue resuelta de forma definitiva por el microhito `v0.1.8` (cerrado 2026-05-20, squash `91080ec`): el harness ahora envuelve el chat-loop body en try/except y persiste cada resultado vía `evals/checkpoint.py::append_case` con `os.fsync()`. Un crash a mitad del run preserva todos los resultados completados hasta ese punto.

El resultado empírico de la disciplina: los ocho runs de pago posteriores a H15.2 (v0.1.20 €7.83, v0.1.22 €1.91, v0.1.23 €1.76, v0.1.25 €1.66, v0.1.27 €0.16, v0.1.28 €1.55, v0.1.29 €1.89, v0.1.30 €0.65) totalizaron ≈€17.41 — todos cerraron sin pérdidas catastróficas y todos produjeron evidencia persistible. El gasto acumulado del proyecto se mantuvo bajo el techo presupuestado.

## 17.3 Orquestación Claude Code: cómo se gestionó el contexto

El proyecto se desarrolló con Claude Code como pareja de programación (CLAUDE.md §1). El entorno se configuró deliberadamente con cuatro mecanismos de gestión de contexto, todos versionados con el repo o con políticas explícitas.

### 17.3.1 Skills

Las skills custom del proyecto viven en `.claude/skills/` con frontmatter (`name`, `description` empezando por "Use this skill when…", `version`, `allowed-tools` opcional). El calendario de introducción se fijó en ADR-0002 (`docs/adr/0002-skills-mcps-roadmap.md`, tabla "Skills introduction calendar") y se siguió con deferrals honestamente documentados (por ejemplo `adr-writer` planificado para H1 nunca llegó a materializarse como skill custom porque la fricción real no lo justificó; los ADRs se escribieron directamente sin procedimiento canónico empaquetado).

Las ocho skills presentes en `.claude/skills/` a la fecha de cierre H16 (siete custom del proyecto + una third-party de Vercel reutilizada para UI/UX):

| Skill | Hito de introducción | Propósito |
|---|---|---|
| `citation-validator` | H4 | Procedimiento canónico de validación 3-checks; documenta reglas para evolucionar la política. |
| `rag-ingest` | H1 | Ingesta idempotente de un cuerpo normativo siguiendo el patrón H1. |
| `document-analysis` | H5 | Pipeline extract→sanitize→segment→loop end-to-end. |
| `prompt-versioning` | H4 | Versionado y rollback seguro de prompts. |
| `evals-runner` | H8 | Ejecución, interpretación y gating de evals. |
| `redteam-runner` | H9 | Ejecución y reporte de la suite de red team. |
| `secure-coding-checklist` | H9 | Checklist canónica de seguridad por PR. |
| `web-design-guidelines` | H16 (skill third-party de Vercel reusada durante deploy) | Compliance UI/UX para el deploy. |

Además, se invocaron skills de orquestación de la suite `superpowers` (siempre activa por CLAUDE.md §22.1): `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:executing-plans`, `superpowers:subagent-driven-development`, `superpowers:requesting-code-review`, `superpowers:receiving-code-review`, `superpowers:verification-before-completion`, `superpowers:systematic-debugging`, `superpowers:finishing-a-development-branch`. La regla operativa fue: cualquier tarea no trivial empieza con un mini-plan vía `superpowers:brainstorming` o `superpowers:writing-plans`, y termina con `superpowers:verification-before-completion` antes de cualquier claim de éxito.

### 17.3.2 MCPs

Los MCPs (Model Context Protocol servers) se introdujeron con la misma regla propose-and-wait (ADR-0002). Cero MCPs en H0.1. El conjunto efectivamente empleado a lo largo del proyecto incluyó: `filesystem` (acceso al workspace), `git` y `github-mcp-server` (operaciones VCS y PRs/issues), `fetch` (descargas con allowlist `eur-lex.europa.eu`, `boe.es`, `arxiv.org`), `sequential-thinking` (planificación compleja), `memory` (notas persistentes), `playwright` (única opción que rompió el WAF CloudFront de EUR-Lex para NIS2/DORA, ver ADR-0015), `sqlite` (metadatos auxiliares), `mcp-server-time`, `mcp-pandoc` (conversiones para entregables) y `tavily-mcp` (búsqueda web acotada para referencias bibliográficas H17).

Algunos MCPs planificados nunca se introdujeron honestamente porque su valor no se materializó: `puppeteer` (cubierto por `playwright`), variantes redundantes de búsqueda, y `langfuse-mcp` (originalmente planeado para H11 pero **diferido por el usuario** como ítem de menor valor en el cierre H11; ver CLAUDE.md §27 H11). Este descarte se documentó en cada cierre de hito en lugar de instalarlos especulativamente.

### 17.3.3 Subagentes especializados

CLAUDE.md §14 define nueve subagentes especializados (`software-architect`, `security-engineer`, `legal-aiact-reviewer`, `evals-engineer`, `redteam-engineer`, `mlops-engineer`, `frontend-engineer`, `docs-writer`, `tech-writer-academic`). Estos no se materializaron como archivos en `.claude/agents/` (el directorio no existe en el repo); se invocaron en su lugar a través de subagentes built-in del harness (Task tool, agentes `general-purpose`, y las skills `superpowers:requesting-code-review` / `superpowers:receiving-code-review` para los reviews de 2 fases) con prompts ad-hoc que codificaban el scope por sesión.

La razón pragmática: el patrón `subagent-driven-development` con subagentes built-in funcionó suficientemente bien para los reviews de 2 fases (un Haiku para detectar Criticals + un Opus para code-review profundo) que detectaron 4 Criticals consecuentes en H15.2, 4 en H13, varios en v0.1.21 (el más notable: la flip de prompt v1.4→v1.5 que evitó una violación silenciosa de §6) y varios en v0.1.30 (la decisión de SKIP el main run tras el probe refutador). Los subagentes especializados con archivos dedicados quedan como ítem opcional H17 si la memoria académica los requiere para la defensa M2.

### 17.3.4 Memoria persistente

Claude Code persiste contexto entre sesiones en `~/.claude/projects/<project-hash>/memory/`. El proyecto adoptó dos patrones complementarios:

- **MEMORY.md como índice**: punto de entrada con bullets enlazando cada memoria por nombre + tagline. 14 entradas al cierre H16, incluyendo 10 feedbacks operativos (`feedback_cost_estimation_discipline`, `feedback_milestone_discipline`, `feedback_ssdlc`, `feedback_decisions_log_living`, `feedback_inspect_real_inputs`, `feedback_optimization_narrative_doc`, `feedback_local_cpu_rerank_cost`, `feedback_no_env_example`, `feedback_resume_verify_state`, `feedback_future_work_doc`).
- **Roll-forward per-milestone**: al cerrar un milestone se escribe un breve archivo de transición (tipo `v0.1.X_<estado>_<siguiente>.md`) con (a) qué se cerró, (b) qué arranca a continuación, (c) gates a recordar, (d) riesgos abiertos. La entrada vigente al cierre H16 es `v0.1.32_h16_deployed_H17_ready.md`. Esto resuelve el problema clásico de pérdida de contexto entre sesiones, especialmente importante con disponibilidad variable del autor.

Los feedbacks operativos son particularmente relevantes para la metodología: `feedback_no_env_example` documenta una regla dura del usuario que overridea CLAUDE.md §22.6 (nunca crear `.env.example`; un solo `.env` en local). `feedback_resume_verify_state` documenta el aprendizaje del incidente H8 (duplicate-eval $1.50 lesson): los snapshots de sistema reminder son point-in-time y los metadatos NTFS de Windows pueden mentir; siempre re-Read antes de acciones costosas.

## 17.4 Workflow orchestration y disciplina §22.22

La metodología trabajo se cristalizó en un ciclo `brainstorm → plan → spec → execute → review → verify → close` aplicado a cada hito. Cada hito produjo (a) un `docs/superpowers/specs/<fecha>-<hito>-design.md`, (b) un `docs/superpowers/plans/<fecha>-<hito>.md` con sub-tareas T0..Tn y criterios Done, (c) un cierre con tag git + entrada en `docs/technical_decisions_log.md` + ADR si la decisión era no trivial.

La disciplina §22.22 (CLAUDE.md §22.22 honest framing) emergió formalmente en H15 y se aplicó verbatim en 13 milestones consecutivos: v0.1.19, v0.1.20, v0.1.21, v0.1.21.2, v0.1.22, v0.1.22.1, v0.1.23 (REVERT), v0.1.24, v0.1.24.1, v0.1.25, v0.1.29, v0.1.30 (REVERT), v0.1.32. El contrato: cada cierre incluye una lista verbatim de disclosures honestas — qué se midió y qué no, qué se prometió y qué se entregó, qué bugs latentes aparecieron mid-milestone, qué scope creció vs el plan. Los dos REVERTs documentados (v0.1.23 lenient quorum del Auditor con 0/10 flip rate sobre los 6-7/10 predichos; v0.1.30 title-augmented embeddings con regresión de citation_precision 0.50→0.00 en doc-001) son la validación empírica de que la disciplina funciona: hipótesis → diagnóstico → intervención → medición → refutación → revert atómico → documentación. El invariante §6 "no citation, no answer" se mantuvo intacto a través de las dos REVERTs precisamente porque los layers Auditor (a) per-citation validator (`citation/validator.py`, byte-equivalent desde H4 con la adición aditiva de `failed_check` en v0.1.24 que NO está en el decision path — ver CLAUDE.md §6.1) y (b) Finding-Lenient aggregation (`auditor.py`, byte-unchanged desde v0.1.21) permanecieron preservados como límite duro de enforcement; ambos REVERTs operaban exclusivamente fuera de esas dos capas.

El cierre del proyecto en H17 hereda esta disciplina: la memoria que el lector tiene en sus manos es ella misma producto de un workflow multi-agente con fact-check adversarial, escrita en sesión H17 sin nuevo código de producción y sin claims que no estén respaldados por evidencia citable en `docs/`, `evals/reports/`, ADRs, o el código del repositorio.
