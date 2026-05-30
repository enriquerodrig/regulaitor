# 20. Conclusiones, entregables y matriz de evidencias

## 20.1 Tesis técnica defendida

RegulAItor se cierra como un servicio multi-agente de cumplimiento normativo europeo que cumple su propia regla central: **sin cita verificable, no hay respuesta** (`CLAUDE.md` §6). El invariante no es una aspiración; es una propiedad observable del sistema, sostenida por 35 ADRs, 13 hitos consecutivos con framing §22.22 honesto (v0.1.19 → v0.1.32), 2 REVERTs documentados como evidencia científica (v0.1.23 Auditor lenient quorum + v0.1.30 title-augmented embeddings), y una arquitectura §6 de cuatro capas explícitas (`CLAUDE.md` §6.1) cuyas modificaciones a lo largo del proyecto endurecen la frontera de enforcement en lugar de relajarla.

Las cuatro capas, con su frontera de enforcement preservada:

- **Capa (a)** — validador por cita en `src/regulaitor/citation/validator.py` (3 checks estrictos; tercera evolución interpretativa en v0.1.32-post añade rechazo de whitespace-only `Citation.text` — defense-in-depth en `citation/schemas.py:30-36` validator + recordatorio en `validator.py:96-113` — tras el deep-review C1 que reprodujo empíricamente un bypass §6 con `Citation(text=" ")`).
- **Capa (b)** — agregación Finding-Lenient en `src/regulaitor/agents/auditor.py:65` (`any(r.validated for r in this_finding_results)`, byte-unchanged desde v0.1.21).
- **Capa (c)** — política de agregación turn-level en las ramas del `audit()`, modificada quirúrgicamente en v0.1.21 (Tier 1 quorum, ADR-0027), v0.1.25 (partial-routing softening, ADR-0032) y v0.1.29 (all-blocked routing softening, ADR-0034) mediante el helper compartido `_all_blocked_findings_paraphrase_only` (`auditor.py:20-48`), que por construcción retorna `False` ante cualquier Check 1 o Check 2 (fabricación de artículo o apartado) y por tanto preserva BLOCK/RHR en presencia de fabricación.
- **Capa (d)** — refuerzo prompt-level en `prompts/analyst/system.v1.5.md` y `prompts/document_analyst/system.v1.6.md` (Hard Rule 4 inviolable "Never emit placeholder citation strings (UNKNOWN/N/A/TBD)", v0.1.28 ADR-0033).

Por construcción documentada en `CLAUDE.md` §6.1, **la fabricación nunca es PASS** en ninguna capa.

## 20.2 La metodología como contribución

El proyecto sostiene una afirmación complementaria al producto: el ciclo `diagnose → intervene → measure → refute/confirm → revert/ship → document` aplicado milestone-by-milestone, con divulgación §22.22 honesta de las divergencias plan-vs-realidad, es defendible como contribución académica además del propio software. Las dos REVERTs (v0.1.23 y v0.1.30) son la validación más clara: ambos hitos pagaron evidencia empírica (€1.76 y €0.65 respectivamente), refutaron la hipótesis prospectiva, revirtieron atómicamente al estado anterior (verificado por `git diff main` vacío), y preservaron sus ADRs con sección `§REVERT` apendizada como registro científico. El §6 sobrevivió a ambas iteraciones intacto.

La asimetría empírica descubierta en v0.1.30 — que el title-prepend del lado query ayuda (`document_graph.py:161`, v0.1.28 T4-bis SHIP) pero el title-prepend del lado corpus daña (v0.1.30 REVERT) — es un hallazgo no obvio sobre dinámicas retrieval-vs-emission en `v1.6` doc_analyst, y queda documentado en ADR-0035 §REVERT como input directo para el roadmap HX (HyDE, hybrid BM25+dense, reranker legal).

## 20.3 Entregables H17

Los entregables académicos del cierre TFM, todos presentes en el repositorio:

- `docs/memoria_sections/01..20-*.md` — memoria académica completa (20 secciones), esta sección la cierra.
- `docs/model_card.md` — bilingüe; router multi-LLM, modelos cubiertos, prompts versionados.
- `docs/data_card.md` — corpus AI Act + RGPD + NIS2 + DORA (1569 filas LanceDB; ai_act 687 + gdpr 324 + nis2 244 + dora 314); gold set 64 chat + 10 docs.
- `docs/runbook.md` + `docs/H16_DEPLOY.md` — runbook operativo extendido con el procedimiento de despliegue HF Spaces (12 rondas R1-R12).
- `docs/cost_analysis.md` — análisis de coste con la honestidad documentada (H12 list-price + H15 router accumulator real; per-run measurement carry-forward).
- `docs/evidence_matrix.md` — matriz M1-M5 completa con tabla de tags por hito (H0.1 → v0.1.32) y ADRs cruzados.
- `docs/security_report.md` — informe de seguridad (red team + SSDLC + ataques §18).
- `docs/technical_decisions_log.md` — 5335 líneas; espinazo narrativo del TFM, todas las decisiones desde H0.
- `docs/adr/0001..0035-*.md` — 35 ADRs (ADR-0030 y ADR-0035 incluyen sección `§REVERT` apendizada).
- Demo público vivo: `https://huggingface.co/spaces/enriro00/regulaitor` (v0.1.32-h16-deploy tag).
- Tag `v1.0.0` — cierre académico (pendiente de publicación al firmar este documento).
- `docs/ai_act_assessment.md` — auto-evaluación provisional del propio sistema RegulAItor bajo el AI Act (presente en `docs/` con §1-§6 redactados; clasificación PROVISIONAL como limited-risk pendiente de certificación por notified body cuando esté disponible 2025-2027).

Reproducibilidad: `make setup && make ingest && make eval && make redteam && make serve && make docker` en clone fresco, conforme a `CLAUDE.md` §20 + gate §16.2 #1.

## 20.4 Cumplimiento de módulos M1-M5

Mapeo verificable contra `CLAUDE.md` §24 y desplegado por filas en `docs/evidence_matrix.md`:

- **M1 (Modelos y prompts)** — `src/regulaitor/models/router.py` (3 proveedores, 6 modos), `agents/prompts/` (analyst v1.0-v1.5, doc_analyst v1.0-v1.6, judge v1.0, council v1.0), `docs/cost_analysis.md`, `docs/model_card.md`. ADRs 0013, 0014, 0020, 0023, 0026, 0033.
- **M2 (Agentes y autonomía)** — `agents/{retriever,analyst,auditor,council}.py`, `orchestration/{graph,document_graph}.py` (LangGraph), `mcp_server/` (5 tools), `citation/validator.py` (§6 enforcement). ADRs 0005, 0006, 0007, 0014, 0027, 0030, 0032, 0034.
- **M3 (RAG + Evaluación + Despliegue + Monitorización)** — `rag/{chunking,embeddings,reranker,store,retrieval,build}.py`, `evals/` (64 chat + 10 docs gold, harness, judge Haiku 4.5), `.github/workflows/ci.yml` (5 jobs Lint + Test + Document E2E + Security + Red Team Smoke), `observability/{logging,langfuse_client}.py`, `docs/H16_DEPLOY.md`. ADRs 0003, 0004, 0010, 0012, 0015, 0016, 0017, 0018, 0019, 0021, 0024, 0028, 0029, 0031, 0035.
- **M4 (Seguridad y red team)** — `security/{injection,allowlist,rate_limit}.py`, `document/sanitizer.py` (12 categorías), `redteam/attacks.jsonl` (50 ataques sobre los 10 escenarios §18), `docs/security_report.md`, CI Security job (bandit + semgrep + pip-audit + gitleaks v8.21.2 pinned). ADR 0011.
- **M5 (Proyecto integrador P1-P7)** — estructura completa del repositorio (CLAUDE.md §11), corpus + agents + evals + redteam + workflows + deploy + observability todos presentes; P1-P7 mapeados en `evidence_matrix.md` §"Módulo 5".

## 20.5 Definition of Done por hito

`CLAUDE.md` §25 enumera diez criterios que cada hito debe cumplir antes de cierre. La closure H17 verifica:

1. Código tipado y linteado (`mypy src` Success 71 source files exit 0 — carry baseline desde v0.1.15.1).
2. Tests unitarios + integración (gate baseline post-v0.1.32-post: 1000 passed / 0 failed / 1 skipped esperado; cobertura 88.59% ≥ 85%).
3. Documentación actualizada (memoria + MkDocs + 35 ADRs).
4. CI verde con gates (ver `.github/workflows/ci.yml`; 5 jobs Lint + Test + Document E2E + Security + Red Team Smoke).
5. Evals: gold set 64 chat + 10 docs; reportes en `evals/reports/v0.1.*/`.
6. Seguridad: 50 ataques en `redteam/attacks.jsonl`; smoke `block_rate` 0.92 carry desde v0.1.14.
7. ADRs al día (count 35).
8. Limitaciones documentadas (sección 18 de esta memoria).
9. Matriz de evidencias actualizada (`docs/evidence_matrix.md` revisado en v0.1.32-post).
10. Pendientes explícitos (sección 19 + carry-forwards en `decisions_log §v0.1.32`).

## 20.6 Reconocimientos

Este proyecto se beneficia del corpus normativo público de EUR-Lex (acceso vía Playwright tras CloudFront WAF, documentado en ADR-0003 y ADR-0015), de los modelos Anthropic Claude Sonnet 4.6 (Analyst) y Claude Haiku 4.5 (juez de evaluación y miembro del Council of Judges) — el Auditor es pure-Python determinista, no llama LLM —, de los modelos BGE-M3 y bge-reranker-v2-m3 (BAAI, retrieval), y de la disciplina de revisión por pares facilitada por el subagente Opus en la skill `superpowers`, cuyas catch de Criticals pre-spend (H15 C1, H15.1 T8.1, H15.2 T3, H16 pre-merge 4 Criticals, deep-review C1 §6 whitespace) evitaron varios fallos defendibles ante tribunal. El error final, sin embargo, es del autor.

## 20.7 Cierre

RegulAItor entrega un producto funcional con demo público, una metodología documentada milestone-by-milestone con 13 §22.22 consecutivos y 2 REVERTs honestos, y un invariante §6 que ha sobrevivido a 35 ADRs y a una refutación empírica externa (deep-review C1 whitespace bypass) tightening, nunca relajando, la frontera. **La metodología es la contribución; el producto es la evidencia de que la metodología funciona.** Tag `v1.0.0`.
