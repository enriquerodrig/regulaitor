# Evidence Matrix — RegulAItor MVP

Mapping of RegulAItor artefacts to the five Máster IA Generativa modules
(per `CLAUDE.md` §24). Each row points at concrete files / commits / reports
so the TFM defense can trace any claim to its underlying evidence.

State: MVP closure (`v0.1.0-mvp` pending H10 tag). H0-H9 complete; H10 in
progress. Cells marked **deferred** are out of MVP scope; planned for the
labelled advanced milestone.

---

## Módulo 1 — Modelos y prompts

> Modelos previstos, configuración, consumo, parametrización, prompts versionados, costes.

| Requirement | Artefact | Status |
|---|---|---|
| Router multi-LLM | [`src/regulaitor/models/router.py`](../src/regulaitor/models/router.py) | ✅ active (Sonnet 4.6 default; H12 expands to GPT-4o + Llama + fallback) |
| Model config (temperature, max_tokens, pricing) | [`src/regulaitor/models/config.py`](../src/regulaitor/models/config.py) | ✅ active |
| Prompts versionados (Analyst) | [`src/regulaitor/agents/prompts/analyst/system.v1.0.md`](../src/regulaitor/agents/prompts/analyst/system.v1.0.md) | ✅ v1.0 |
| Prompts versionados (Auditor) | [`src/regulaitor/agents/prompts/auditor/`](../src/regulaitor/agents/prompts/auditor/) | ✅ Lenient-strict in code; no system prompt (deterministic) |
| Prompts versionados (Judge eval) | [`src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md`](../src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md) | ✅ v1.0 (H8) |
| Prompts versionados (Document Analyst) | [`src/regulaitor/agents/prompts/document_analyst/`](../src/regulaitor/agents/prompts/document_analyst/) | ✅ active (H5) |
| Prompt versioning skill | [`.claude/skills/prompt-versioning/SKILL.md`](../.claude/skills/prompt-versioning/SKILL.md) | ✅ active from H4 |
| LLM cost tracking | per-case `cost_eur` in `evals/reports/latest.md` + redteam reports | ✅ active |
| Cost analysis document | `docs/cost_analysis.md` | **deferred H17** |
| Model card | `docs/model_card.md` | **deferred H17** |
| Tool-use call structure | `analyst.py:analyze` (forced tool_use with `emit_answer` schema) | ✅ active (with retry-once on findings-missing) |
| Sonnet 4.6 reliability decision | ADR 0006 + decisions log §H4 + amendment H8 commit `0d0409a` | ✅ documented |

---

## Módulo 2 — Agentes y autonomía

> Tres agentes + Council, flujo operativo, autonomía limitada por el Auditor, intervención humana en casos ambiguos, framework LangGraph, controles intermedios (citation validator, anti-injection).

| Requirement | Artefact | Status |
|---|---|---|
| RetrieverAgent | [`src/regulaitor/agents/retriever.py`](../src/regulaitor/agents/retriever.py) | ✅ H3 |
| AnalystAgent | [`src/regulaitor/agents/analyst.py`](../src/regulaitor/agents/analyst.py) | ✅ H4 |
| AuditorAgent (Lenient-strict) | [`src/regulaitor/agents/auditor.py`](../src/regulaitor/agents/auditor.py) | ✅ H4 |
| Council of Judges | [`src/regulaitor/agents/council.py`](../src/regulaitor/agents/council.py) | **deferred H13** |
| Chat orchestration | [`src/regulaitor/orchestration/graph.py`](../src/regulaitor/orchestration/graph.py) (LangGraph) | ✅ H4 |
| Document orchestration | [`src/regulaitor/orchestration/document_graph.py`](../src/regulaitor/orchestration/document_graph.py) | ✅ H5 |
| Citation validator (3 checks) | [`src/regulaitor/citation/validator.py`](../src/regulaitor/citation/validator.py) | ✅ H3 |
| Anti-injection regex | [`src/regulaitor/security/injection.py`](../src/regulaitor/security/injection.py) (25+ patterns, expanded H9) | ✅ H4 + H5 + H9 |
| MCP server | [`src/regulaitor/mcp_server/`](../src/regulaitor/mcp_server/) | ✅ H3 (5 tools) |
| Architecture diagrams (L1+L2+L3) | [`docs/architecture.md`](architecture.md) | ✅ H10 |
| ADR per agent decision | [`docs/adr/0006-chat-e2e-architecture.md`](adr/0006-chat-e2e-architecture.md), [`0007-document-pipeline-architecture.md`](adr/0007-document-pipeline-architecture.md) | ✅ committed |

**Decisions log evidence**: §H3, §H4, §H5 in [`docs/technical_decisions_log.md`](technical_decisions_log.md).

---

## Módulo 3 — RAG, evaluación, despliegue, monitorización

> RAG estructural por artículo, evaluación reproducible, tests, despliegue en HF Spaces, monitorización con LangFuse, métricas de rendimiento.

| Requirement | Artefact | Status |
|---|---|---|
| Chunking estructural por artículo | [`src/regulaitor/rag/chunking.py`](../src/regulaitor/rag/chunking.py) | ✅ H2 |
| Embeddings BGE-M3 (multilingual) | [`src/regulaitor/rag/embeddings.py`](../src/regulaitor/rag/embeddings.py) | ✅ H2 |
| Reranker bge-reranker-v2-m3 | [`src/regulaitor/rag/reranker.py`](../src/regulaitor/rag/reranker.py) | ✅ H2 |
| LanceDB store | [`src/regulaitor/rag/store.py`](../src/regulaitor/rag/store.py) + `corpus/indexes/regulaitor.lance/` | ✅ H2 (1011 chunks) |
| Corpus parser | [`src/regulaitor/corpus/parse.py`](../src/regulaitor/corpus/parse.py) | ✅ H1 |
| Corpus AI Act | `corpus/raw/ai_act/` + `corpus/processed/ai_act_es.json` + `_en.json` | ✅ H1 (113 articles ES + EN) |
| Corpus GDPR | `corpus/raw/rgpd/` + `corpus/processed/rgpd_es.json` + `_en.json` | ✅ H1 (99 articles ES + EN) |
| Corpus NIS2 + DORA | `corpus/raw/nis2/`, `corpus/raw/dora/` | **deferred H14** |
| Gold set | [`evals/gold_set.jsonl`](../evals/gold_set.jsonl) (30 chat) + [`evals/document_cases/*.expected.json`](../evals/document_cases/) (10 docs) | ✅ H8 |
| Eval harness | [`evals/harness.py`](../evals/harness.py) + `evals/metrics.py` + `evals/judge.py` + `evals/report.py` | ✅ H8 |
| Eval report | [`evals/reports/latest.md`](../evals/reports/latest.md) | ✅ H8 (re-run H10 in progress) |
| LLM-as-judge | Haiku 4.5 with versioned prompt (faithfulness.v1.0) | ✅ H8 |
| Metric thresholds | `CLAUDE.md` §17 (objectives) + §16.2 (gates) | ✅ documented |
| Ragas integration | `evals/metrics.py` Ragas adapter (faithfulness + answer_relevancy + context_precision + context_recall) | ✅ H8 |
| Tests suite | `tests/` (538+ unit + integration + contract) | ✅ active |
| Coverage on gated subsystems | 92.61% on citation/agents/rag (per `pyproject.toml` cov config) | ✅ gate §16.2 #2 |
| CI/CD pipeline | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (5 jobs: Lint, Test, Document E2E, Security, Red Team Smoke) | ✅ H7 + H8 + H9 cleanup |
| Reproducibility commands | `Makefile` (`setup`, `lint`, `test`, `ingest`, `rag-build`, `eval`, `eval-from-cache`, `redteam`, `redteam-smoke`, `serve`, `serve-api`) | ✅ H0.1 + extended |
| Observability (structured logging) | [`src/regulaitor/observability/logging.py`](../src/regulaitor/observability/logging.py) | ✅ H4 (case_id, cost, latency, token_hash) |
| LangFuse traces | [`src/regulaitor/observability/langfuse_client.py`](../src/regulaitor/observability/langfuse_client.py); [ADR 0012](adr/0012-observability-architecture.md) | ✅ H11 (metadata-only, no-op without keys; redaction proven end-to-end vs live backend) |
| Public deploy (Docker / HF Spaces) | `docker-compose.yml` + `.github/workflows/deploy.yml` | **deferred H16** |
| ADRs | [`docs/adr/0003-corpus-pipeline.md`](adr/0003-corpus-pipeline.md), [`0004-rag-architecture.md`](adr/0004-rag-architecture.md), [`0010-evaluation-harness.md`](adr/0010-evaluation-harness.md) | ✅ committed |

**Skills active in this module**: [`rag-ingest`](../.claude/skills/rag-ingest/SKILL.md), [`document-analysis`](../.claude/skills/document-analysis/SKILL.md), [`evals-runner`](../.claude/skills/evals-runner/SKILL.md), [`citation-validator`](../.claude/skills/citation-validator/SKILL.md).

---

## Módulo 4 — Seguridad y red team

> Seguridad por diseño, riesgos, red teaming, prompt injection, controles de producción.

| Requirement | Artefact | Status |
|---|---|---|
| Sanitizer (12 categorías) | [`src/regulaitor/document/sanitizer.py`](../src/regulaitor/document/sanitizer.py) | ✅ H5 + H9 expansion (metadata injection scan + URL allowlist) |
| Injection regex (25+ patterns) | [`src/regulaitor/security/injection.py`](../src/regulaitor/security/injection.py) | ✅ H4 (10 chat) + H5 (13 doc) + H9 (3 additive) |
| URI allowlist | [`src/regulaitor/security/allowlist.py`](../src/regulaitor/security/allowlist.py) (5 EU official domains) | ✅ H4 |
| Citation validator | [`src/regulaitor/citation/validator.py`](../src/regulaitor/citation/validator.py) (3 checks) | ✅ H3 |
| Auditor (verdict aggregation) | [`src/regulaitor/agents/auditor.py`](../src/regulaitor/agents/auditor.py) | ✅ H4 |
| Rate limiting | [`src/regulaitor/security/rate_limit.py`](../src/regulaitor/security/rate_limit.py) (slowapi, per-token) | ✅ H7 |
| Auth (Bearer + hmac.compare_digest) | [`src/regulaitor/api/auth.py`](../src/regulaitor/api/auth.py) | ✅ H7 |
| Red team attack catalog | [`redteam/attacks.jsonl`](../redteam/attacks.jsonl) (50 attacks, 10 scenarios §18) | ✅ H9 |
| Red team runner | [`redteam/runner.py`](../redteam/runner.py) + `scripts/redteam.py` | ✅ H9 |
| Red team report | [`redteam/reports/latest.md`](../redteam/reports/latest.md) (block_rate_smoke 0.92) | ✅ H9 |
| Security report (formal MVP) | [`docs/security_report.md`](security_report.md) | ✅ H9 |
| Bandit static analysis | CI `Security` job — 0 high / 0 medium / 0 low | ✅ |
| Pip-audit | CI `Security` job (3 CVEs ignored with documented rationale) | ✅ |
| Gitleaks secret scan | `.gitleaks.toml`; pre-commit hook (Linux/CI) + [`ci.yml`](../.github/workflows/ci.yml) Security job (pinned v8.21.2) | ✅ H0.1 + **CI-enforced H11** (local Windows hook is golang/no-Go → CI is authoritative; §16.2 #6) |
| Semgrep | (not adopted; bandit + manual review sufficient for MVP) | n/a |
| Red team gate | §16.2 #4 (block_rate ≥ 0.90) — smoke 0.92 ✅ (gate basis, API-immune); full 0.28 raw / 0.54 completed (H11, timeout-contaminated → H15 signal, not gate) | ✅ smoke |
| Full red team run | 50 attacks E2E ([`redteam/reports/latest.md`](../redteam/reports/latest.md), commit `602c2da`, 1.99 €) | ✅ H11 (21/50 API timeouts — see §H9 amendment 6 / §H11; T6 timeout prevented H9-style hang) |
| Skills active | [`redteam-runner`](../.claude/skills/redteam-runner/SKILL.md), [`secure-coding-checklist`](../.claude/skills/secure-coding-checklist/SKILL.md) | ✅ H9 |
| ADRs | [`docs/adr/0011-redteam-runner.md`](adr/0011-redteam-runner.md) | ✅ committed |

---

## Módulo 5 — Proyecto integrador (P1-P7)

> P1-P7 entregables del proyecto integrador.

| Entregable | Artefact (RegulAItor MVP) | Status |
|---|---|---|
| **P1 — Planteamiento** | [`CLAUDE.md`](../CLAUDE.md) (charter completo) + [`docs/adr/0001-project-scope.md`](adr/0001-project-scope.md) | ✅ H0 + H0.1 |
| **P2 — Activos y recursos** | Repository structure (este documento §"Repository layout" en [`docs/architecture.md`](architecture.md)) | ✅ continuous |
| **P3 — Preparación del contexto** | [`src/regulaitor/corpus/`](../src/regulaitor/corpus/), [`src/regulaitor/rag/`](../src/regulaitor/rag/), [`corpus/processed/`](../corpus/processed/) + ADRs 0003/0004 | ✅ H1 + H2 |
| **P4 — Modelos y prompts** | [`src/regulaitor/models/`](../src/regulaitor/models/), [`src/regulaitor/agents/prompts/`](../src/regulaitor/agents/prompts/) | ✅ H4 + H5 + H8 |
| **P5 — Evaluaciones y seguridad** | [`evals/`](../evals/), [`redteam/`](../redteam/), [`docs/security_report.md`](security_report.md) | ✅ H8 + H9 |
| **P6 — Cadena de despliegue** | `docker-compose.yml`, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), deployment to HF Spaces | partial: CI ✅; Docker + deploy **deferred H16** |
| **P7 — Monitorización y mejora continua** | [`src/regulaitor/observability/logging.py`](../src/regulaitor/observability/logging.py); [`langfuse_client.py`](../src/regulaitor/observability/langfuse_client.py); [`docs/runbook.md`](runbook.md); postmortems | logs ✅ H4; LangFuse ✅ H11 (metadata-only, verified live); runbook ✅ H11; postmortems opt HX6 |

**TFM defense memoria backbone**: [`docs/technical_decisions_log.md`](technical_decisions_log.md) (1798+ lines as of MVP closure; every approved technical decision from H0 to H9 plus H10 in progress).

---

## Closed milestones (full traceability)

Each closed milestone has its own §HX section in
[`docs/technical_decisions_log.md`](technical_decisions_log.md) with:
- brainstorming Qs + answers (decision rationale)
- amendments during implementation (what diverged from the spec)
- closure metrics (concrete numbers + threshold pass/fail)
- skills activated
- artefacts delivered

| Hito | Tag | Spec | Plan | ADR | Squash SHA |
|---|---|---|---|---|---|
| H0.1 | `v0.0.1-h0.1` | — (charter only) | — | [0001](adr/0001-project-scope.md) | initial |
| H1 | `v0.0.2-h1` | [spec](superpowers/specs/2026-04-30-h1-corpus-ingest-design.md) | [plan](superpowers/plans/2026-04-30-h1-corpus-ingest.md) | [0003](adr/0003-corpus-pipeline.md) | `79b6c0d` |
| H2 | `v0.0.3-h2` | [spec](superpowers/specs/2026-05-04-h2-rag-base-design.md) | [plan](superpowers/plans/2026-05-04-h2-rag-base.md) | [0004](adr/0004-rag-architecture.md) | `1f5147c` |
| H3 | `v0.0.4-h3` | [spec](superpowers/specs/2026-05-05-h3-mcp-server-design.md) | [plan](superpowers/plans/2026-05-05-h3-mcp-server.md) | [0005](adr/0005-mcp-server-architecture.md) | `44549bb` |
| H4 | `v0.0.5-h4` | [spec](superpowers/specs/2026-05-05-h4-chat-e2e-design.md) | [plan](superpowers/plans/2026-05-05-h4-chat-e2e.md) | [0006](adr/0006-chat-e2e-architecture.md) | `a3611bd` |
| H5 | `v0.0.6-h5` | [spec](superpowers/specs/2026-05-06-h5-document-pipeline-design.md) | [plan](superpowers/plans/2026-05-06-h5-document-pipeline.md) | [0007](adr/0007-document-pipeline-architecture.md) | `415d269` |
| H6 | `v0.0.7-h6` | [spec](superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md) | [plan](superpowers/plans/2026-05-07-h6-streamlit-mvp.md) | [0008](adr/0008-streamlit-ui-architecture.md) | `e53f295` |
| H7 | `v0.0.8-h7` | [spec](superpowers/specs/2026-05-08-h7-fastapi-design.md) | [plan](superpowers/plans/2026-05-08-h7-fastapi-mvp.md) | [0009](adr/0009-fastapi-architecture.md) | `5b1f664` |
| H8 | `v0.0.9-h8` | [spec](superpowers/specs/2026-05-10-h8-evaluation-harness-design.md) | [plan](superpowers/plans/2026-05-10-h8-evaluation-harness.md) | [0010](adr/0010-evaluation-harness.md) | `fe7b2e5` |
| H9 | `v0.0.10-h9` | [spec](superpowers/specs/2026-05-12-h9-redteam-design.md) | [plan](superpowers/plans/2026-05-12-h9-redteam.md) | [0011](adr/0011-redteam-runner.md) | `c1e7de6` |
| **H10** | `v0.1.0-mvp` | — (consolidation only) | — | (this matrix is the consolidation) | `<sha>` (pending) |

---

## Gate §16.2 — MVP → Advanced

| # | Gate | Evidence | Status |
|---|---|---|---|
| 1 | `make setup && make ingest && make eval && make redteam && make serve` clean clone | H10 reproducibility verification (pending) | ⏳ |
| 2 | Coverage ≥80% citation/agents/rag | `pyproject.toml` cov gate + 92.61% measured | ✅ |
| 3 | `evals/reports/latest.md` with real metrics | H8 report + H10 re-eval | ✅ |
| 4 | Auditor block_rate ≥0.90 on adversarial set | smoke 0.92 ✅ (gate basis, deterministic/API-immune); full H11 0.28 raw / 0.54 completed — timeout-contaminated, H15 signal not gate (§H9 amend. 6) | ✅ smoke |
| 5 | citation_recall ≥0.40 (reframed from precision ≥0.85) | measured 0.44 ✅; precision 0.17 documented, ≥0.85 → H15 | ✅ |
| 6 | gitleaks clean | pre-commit (Linux) + **CI Security job v8.21.2 (H11, authoritative)** | ✅ |
| 7 | bandit/pip-audit no high/critical | 0/0/0 (post `cb75d48`) | ✅ |
| 8 | Demo reproducible by external human via README | H10 README + reproducibility check | ⏳ |
| 9 | ADRs current | 0001-0011 (11 ADRs) | ✅ |
| 10 | Tag `v0.1.0-mvp` published | H10 closure | ⏳ |

---

## Open follow-ups (deferred from MVP)

Tracked here for H17 consolidation into the final TFM memoria future-work
section.

| Item | Originally surfaced | Target hito | Notes |
|---|---|---|---|
| Full red team run on 50 attacks | H9 (silent API hang) | ✅ **done H11** | Daemon-thread per-attack timeout added; full run 1.99 € (commit `602c2da`); block_rate 0.28 raw / 0.54 completed — 21/50 API timeouts, gate stays on smoke 0.92 (§H9 amend. 6). |
| Citation precision to 0.85 | H8 (measured 0.16) → H10 (revised threshold) | H15 | Auditor calibration + Council voting reduces over-citation. |
| Severity match rate to 0.80 | H8 (measured 0.19) | H15 | Auditor severity assignment drift; A/B threshold tuning. |
| LangFuse observability | from H4 design | ✅ **done H11** | Orchestration-layer traces (chat + doc), metadata-only, no-op without keys; verified live (trace in LangFuse Cloud + redaction proven end-to-end). [ADR 0012](adr/0012-observability-architecture.md). |
| langfuse-mcp (assistant trace querying) | H11 Q6 | **deferred (user, 2026-05-16)** | Lowest-value H11 item; no product/TFM impact; can add any session (needs new `.mcp.json` + community MCP). |
| Latency optimization (per-query SLA ≤12 s) | H11 runbook §3 (real ~15–60 s > target) | H12/H15 | Streaming, max_tokens, parallel retriever, fast-model router. Measured cleanly via LangFuse per-span (H11). |
| Analyst schema-adherence (`findings` sometimes missing) | H11 (live-trace demo) | H15 | Analyst occasionally emits prose without structured `findings` even after retry; add to H15 Auditor/Analyst calibration levers. |
| Multi-LLM router (GPT-4o + Llama) | from H4 router decision | H12 | Real comparison run for `cost_analysis.md`. |
| Council of Judges | H4 + H13 | H13 | High-severity case voting. |
| NIS2 + DORA corpus | H1 deferred | H14 | Parser per norma; reuse pipeline. |
| Public deploy (HF Spaces) | from charter | H16 | Docker + deploy workflow. |
| Model card + data card | H8 deferred | H17 | Activate skills + populate. |
| AI Act self-assessment | charter §24 | H17 | Activate skill + populate. |
| Cost analysis (per-query, per-doc, scale curves) | H8 | H17 | Concrete numbers after H12 router live. |
| LoRA severity classifier | charter §15.3 | HX1 | Optional; only if H15 needs more discrimination than threshold tuning. |
| Next.js frontend | charter §10 + §15.3 | HX2 | Optional. |
| MCP server external (separate process) | charter §9 | HX4 | Optional; current in-process MCP is sufficient. |

---

## How to use this matrix

- **TFM defense reviewer**: each row links to the concrete file/commit. Click
  through to verify the claim.
- **TFM tutor**: use the §HX sections in `docs/technical_decisions_log.md`
  for the rationale chain (why decisions were made + what alternatives were
  considered).
- **Continuity (future contributors)**: open follow-ups table tells what is
  intentionally deferred. Each entry has a target hito + the originating
  decision.
