# RegulAItor

> "RegulAItor no responde sin cita verificable: convierte la consulta normativa rutinaria y la revisión documental en un acto auditable, en minutos y por céntimos."

Multi-agent regulatory compliance service with strict citation verification. TFM project for the Master in Generative AI.

## Status

**v0.1.30 closed (2026-05-28) — title-augmented corpus embeddings (ACCEPTED then REVERTED per probe).** Tag `v0.1.30-title-augmented-embeddings`. Advanced track post-MVP wrapped; Stage 4 H16 (public HF Spaces deploy) next.

### Lineage at a glance

| Track | Tag span | Highlight |
|---|---|---|
| **MVP** (H0-H10) | `v0.0.1-h0.1` → `v0.1.0-mvp` | corpus + RAG + 3 agents + Streamlit + FastAPI + eval harness + red team + docs freeze |
| **Advanced** (H11-H15.2) | `v0.1.1-h11` → `v0.1.7-h15.2` | LangFuse + multi-LLM router + Council of Judges + NIS2/DORA corpus + Auditor calibration study |
| **Optimization micro-milestones** (v0.1.8-v0.1.30) | `v0.1.8` → `v0.1.30-title-augmented-embeddings` | 23 micro-milestones; 12 consecutive §22.22-honest closures with **2 documented REVERTs** (v0.1.23 + v0.1.30) — methodology contribution |
| **H16** | (next) | HF Spaces public deploy |
| **H17** | (post-deploy) | TFM cierre académico (memoria + model card + data card + video demo) |

### Recent advanced-track headlines

| Milestone | Tag | Date | Headline |
|---|---|---|---|
| v0.1.18 | `v0.1.18-citation-granularity` | 2026-05-22 | eval-instrument fix: hierarchical containment match → holdout citation_recall 0.00 → 0.64 |
| v0.1.19 | `v0.1.19-council-binding` | 2026-05-22 | Council binding ON (conservative direction; PASS→RHR on unanimous BLOCK) |
| v0.1.20 | `v0.1.20-paid-validation` | 2026-05-24 | A/B v1.0 vs v1.4: v1.4 production default flipped (T7 safety floor PASS) |
| v0.1.21 | `v0.1.21-auditor-quorum-hard-constraints` | 2026-05-24 | Tier 1 Auditor RHR quorum + Tier 2 Analyst format hard constraints (Capa A+B+C) |
| v0.1.22 | `v0.1.22-paid-validation` | 2026-05-25 | Cumulative-impact paid validation: CONDITIONAL CONFIRM; Tier 2 100% effective |
| v0.1.23 | `v0.1.23-auditor-lenient-quorum` | 2026-05-26 | **REVERT** — Auditor lenient quorum Design B prediction REFUTED; §6 invariant held |
| v0.1.24 | `v0.1.24-gold-alignment-decomposition` | 2026-05-26 | $0 gold alignment + AuditResult `failed_check` instrumentation; +0.10 lift via re-aggregation |
| v0.1.25 | `v0.1.25-auditor-partial-routing` | 2026-05-26 | Auditor partial-routing softening (Design H D2): **verdict_match +0.33** (largest single-milestone lift) |
| v0.1.26 | `v0.1.26-h16-deploy-prep` | 2026-05-27 | $0 Docker + CORS + truststore + cov gate + H16 runbook |
| v0.1.27 | `v0.1.27-doc-mode-validation` | 2026-05-27 | Doc-mode baseline measurement (€0.16) + NEW doc_analyst placeholder citation bug found |
| v0.1.28 | `v0.1.28-doc-analyst-v1-6-refusal` | 2026-05-27 | Doc fix: v1.6 Finding-based refusal + title-prepend query-side; citation_recall 0→0.33; FOURTH-layer §6 architecture |
| v0.1.29 | `v0.1.29-chat-016-all-blocked-softening` | 2026-05-27 | Auditor all-blocked routing softening (D Mirror): verdict_match +0.08; chat-016 BLOCK→PASS as predicted |
| v0.1.30 | `v0.1.30-title-augmented-embeddings` | 2026-05-28 | **REVERT** — title-augmented corpus embeddings (corpus-side mirror); over-citation 5x; v0.1.28 query-side prepend stays |

Full milestone log in `CLAUDE.md` §16.3 + `docs/technical_decisions_log.md`.

### Codebase

~8k LOC Python (`src/`), **~21k LOC tests** + ~1000 tests + 88.62% coverage. **35 ADRs** in `docs/adr/`. CI: lint + test + Document E2E + security (bandit + pip-audit + gitleaks) + redteam smoke jobs.

⚠️ This system does not replace legal counsel. It is a first-line analysis tool that returns auditable findings with verified citations against the official regulatory corpus.

## Methodology contribution (§22.22 honest framing)

The TFM defense rests on the **diagnose → intervene → measure → refute → revert → document** science cycle. 12 consecutive milestones (v0.1.19 → v0.1.30) have been closed with §22.22-honest framing — every empirical refutation shipped as REVERT (v0.1.23 Auditor lenient quorum; v0.1.30 title-augmented embeddings) was documented with full §REVERT section in its ADR, atomic restoration to pre-intervention state, and prospective design retained as scientific record. Both REVERTs preserved the §6 "no citation, no answer" invariant throughout. The methodology applies across Auditor-layer interventions (v0.1.23) and retrieval-layer interventions (v0.1.30) — vindicated as cross-cutting discipline, not single-layer luck.

The asymmetric finding of v0.1.30 — query-side title-prepend HELPS (v0.1.28), corpus-side title-augmented HURTS — is the substantive scientific contribution about retrieval-vs-emission dynamics in v1.6 doc_analyst, worth highlighting in H17 memoria.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/), Python 3.11, and Git LFS (for the PDF corpus snapshots).

```bash
make setup        # install dependencies via uv + pre-commit hooks
make lint         # ruff + black --check + mypy
make test         # pytest (excludes slow integration tests; ~30s, ~1000 tests)
make ingest       # parse PDF corpora into manifests + processed/
make rag-build    # chunk + embed + populate LanceDB (downloads ~3 GB on first run)
```

> **Windows note:** `make` is not bundled with Git for Windows. Either install GNU Make (e.g., via `choco install make` or `scoop install make`) or run the underlying `uv` commands directly. The `Makefile` is one short file; each target is one `uv run ...` line. CI runs on Ubuntu (`make` always available there).

The first `make rag-build` downloads BGE-M3 (~2.3 GB) and bge-reranker-v2-m3 (~600 MB) from HuggingFace Hub into `~/.cache/huggingface/`. Re-runs are idempotent (`chunks_added=0` when nothing changed).

### Document analysis mode

Analyze a corporate policy PDF or Markdown against the EU regulatory corpus:

```bash
python -m scripts.analyze \
    --file path/to/policy.pdf \
    --lang es \
    --corpus ai_act,gdpr
```

Output is a JSON `DocumentReport` with per-segment audit verdicts and a global verdict (PASS / BLOCK / REQUIRES_HUMAN_REVIEW). Exit code 0 on PASS, 1 on BLOCK or REQUIRES_HUMAN_REVIEW, 2 on extraction error, 3 on configuration error. **No respuesta sin cita validada — incluso para documentos.**

### UI Streamlit

Lanza el MVP de dos pestañas (Pregunta / Analiza documento):

```bash
make serve
```

Streamlit imprime una URL local (típicamente `http://localhost:8501`). El banner de aviso jurídico es persistente; si `ANTHROPIC_API_KEY` no está en `.env`, la app muestra un error y no expone los tabs. El frontend usa la paleta Legal Navy R3 (Vercel/shadcn-sobrio, sin emojis; v0.1.26 polish).

**No respuesta sin cita validada — incluso en la UI**.

## API Quickstart

Three endpoints (`POST /ask`, `POST /analyze`, `GET /health`) behind a static Bearer token. Same backend pipelines as the Streamlit UI.

### Prerequisites

- Set `REGULAITOR_API_TOKEN` (≥16 chars) and `ANTHROPIC_API_KEY` in `.env`.
- LanceDB index populated via `make rag-build` (≥1 chunk required for `/health` to report `ok`).

### Running

```bash
make serve-api
```

The API listens on `http://localhost:8000`. OpenAPI docs at `/docs`. CORS allowlist configurable per environment (v0.1.26 H16 deploy-prep).

### Examples

```bash
# Health (no auth)
curl http://localhost:8000/health

# Chat
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer ${REGULAITOR_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"¿Qué dice el AI Act sobre sistemas de alto riesgo?","corpus":"ai_act","language":"es"}'

# Document analysis
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer ${REGULAITOR_API_TOKEN}" \
  -F "file=@policy.pdf;type=application/pdf" \
  -F "corpus=ai_act" \
  -F "language=es"
```

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `REGULAITOR_API_TOKEN` | (required) | Bearer token (≥16 chars) |
| `ANTHROPIC_API_KEY` | (required) | Production model + judge model access |
| `REGULAITOR_RATE_LIMIT_ASK` | `30/minute` | per-token quota for `/ask` |
| `REGULAITOR_RATE_LIMIT_ANALYZE` | `5/minute` | per-token quota for `/analyze` |
| `REGULAITOR_MAX_UPLOAD_BYTES` | `10485760` (10 MB) | max upload size for `/analyze` |
| `REGULAITOR_RATE_LIMIT_DISABLED` | (unset) | set to `1` to disable rate limiting (tests) |
| `REGULAITOR_API_CORS_ORIGINS` | (empty) | comma-separated allowlist for CORS (v0.1.26) |
| `LANCEDB_PATH` | `./corpus/indexes/regulaitor.lance` | persistent volume for HF Spaces / Render / Fly.io |
| `REGULAITOR_ANALYST_PROMPT_VERSION` | (unset → role-aware default) | env seam for retrospective Analyst prompt A/B |

## Docker + H16 deploy

Multi-stage Dockerfile + docker-compose for local + HF Spaces deploy (v0.1.26 H16 deploy-prep):

```bash
make docker-build         # multi-stage build (~1.5 GB image)
docker compose up         # api:8000 + streamlit:8501
```

Full deploy runbook in `docs/H16_DEPLOY.md` covering HF Spaces (Streamlit SDK), Render, Fly.io, and local Docker.

## Evaluation

The harness runs the full RegulAItor pipeline against a curated gold set
(**64 chat + 10 docs**), computes Ragas + custom metrics with a Haiku 4.5
LLM judge (ADR-0010 + ADR-0021), and emits `evals/reports/latest.md`.

### Quickstart

```bash
# Full run with live LLM (~$3-5 Anthropic credit; populates judge cache)
make eval

# Subsequent regenerations from judge cache: ~50% of original cost
# (H4/H5 production calls are NOT cached; see v0.1.18 T3 pivot doc)
make eval-from-cache

# Debugging the harness with first 5 chat + 1 doc case (~$0.30)
make eval-subset
```

> **Partial reproducibility caveat:** `make eval-from-cache` replays only the
> judge layer (Haiku 4.5 calls are cached). The H4 chat graph and H5 document
> pipeline make their own live LLM calls on every run (per v0.1.18 controller
> verification at T3 PIVOT).

### Reading the report

`evals/reports/latest.md` has five sections:

1. **Header** — run date, commit SHA, model versions, total cost.
2. **Aggregate table** — each metric with **two columns**: v0.1.20-bar (anchored to H10 + H15 v1.2 baselines per ADR-0021) AND aspirational §17 targets (long-term direction).
3. **Per-case appendix** — 64 chat + 10 doc sections (one per gold case).
4. **Reproducibility block** — literal commands to regenerate the report.
5. **Caveats** — limitations of the eval setup (same-vendor judge, latency contamination, synthetic gold set).

### Current metric state (v0.1.29 H10 25-case main, last paid run 2026-05-27)

| Metric | v0.1.29-prod-main | v0.1.20-bar | Aspirational §17 |
|---|---|---|---|
| faithfulness | **0.72** | ≥0.65 ✅ | ≥0.85 |
| answer_relevancy | **0.70** | ≥0.55 ✅ | ≥0.85 |
| context_precision | 0.59 | ≥0.55 ✅ | ≥0.80 |
| citation_precision | 0.34 | ≥0.25 ✅ | ≥0.90 |
| citation_recall | **0.81** | ≥0.60 ✅ + **≥0.80 ASP ✅** | ≥0.80 |
| verdict_match | **0.76** | ≥0.35 ✅ | ≥0.85 |
| severity_match | 0.43 | ≥0.35 ✅ | ≥0.80 |

**7/7 v0.1.20-bar PASS** preserved across v0.1.25 + v0.1.29. citation_recall hits the aspirational ≥0.80 target (the only aspirational hit so far).

## Red Team

50 adversarial attacks covering the 10 scenarios from `CLAUDE.md` §18 (22 chat-mode + 28 doc-mode). See `redteam/attacks.jsonl`.

```bash
make redteam-smoke    # deterministic subset only ($0, ~30s) — runs in CI
make redteam          # full run with live LLM (~$3)
```

Gate §16.2 #4: `block_rate_final ≥ 0.90`. Current value: **0.92** (frozen since v0.1.14; preserved across all subsequent milestones by construction — agent-layer changes do not touch sanitizer/injection paths).

Defense in depth: sanitizer (12 categories) + injection regex (23+ patterns) + citation validator (3 checks; v0.1.24 instrumented with `failed_check` field; ADR-0031) + Auditor 4-layer architecture (v0.1.29 §6 evolution — see `CLAUDE.md` §6.1).

## §6 invariant — multi-layer architecture

The "no citation, no answer" invariant has evolved across milestones into **four explicit layers** (full statement in `CLAUDE.md` §6.1):

- **Layer (a)** per-citation validator — `src/regulaitor/citation/validator.py`; BYTE-EQUIVALENT since H4 (v0.1.24 ADR-0031 added `failed_check` observability).
- **Layer (b)** Finding-Lenient aggregation — `agents/auditor.py`; BYTE-UNCHANGED since v0.1.21.
- **Layer (c)** Turn-level aggregation policy — `agents/auditor.py` branches; modified at v0.1.21 (Tier 1 quorum) + v0.1.25 (partial-routing softening D2; ADR-0032) + v0.1.29 (all-blocked routing D Mirror; ADR-0034).
- **Layer (d)** prompt-level explicit forbid — `agents/prompts/analyst/system.v1.5.md` + `prompts/document_analyst/system.v1.6.md`; Hard rule "Never emit placeholder citation strings" (v0.1.28 ADR-0033).

**By construction**: fabrication (article or apartado not in corpus) NEVER routes PASS through any layer. The helper `_all_blocked_findings_paraphrase_only` (auditor.py:20-48) only returns True when EVERY invalid citation has `failed_check==3` (paraphrase mismatch where article + apartado DO exist in corpus).

## Stack

Python 3.11 · `uv` · Pydantic v2 · **LanceDB · BGE-M3 · bge-reranker-v2-m3** · FastAPI · LangGraph · Streamlit · Docker · GitHub Actions · LangFuse (H11) · Ragas + DeepEval + custom harness.

Multi-LLM router (ADR-0013) wires Anthropic Sonnet 4.6 (production) + Haiku 4.5 (judge) + OpenAI GPT-4o + Groq Llama-3.3-70b (fallback). Cross-vendor judge migration deferred to HX post-TFM per ADR-0021 D3.

## Roadmap

See `CLAUDE.md` §16 for the full milestone roadmap (H0 → H17 + optional HX).

**Current state**: post-v0.1.30 REVERT; Auditor aggregation layer LOW-MEDIUM §6 risk surface exhausted (v0.1.25 partial + v0.1.29 all-blocked); doc-mode retrieval engineering attempted (v0.1.30 corpus-side title-augmented REVERTED; v0.1.28 query-side title-prepend SHIPPED).

**Active**: **H16 — Public Docker deploy (Hugging Face Spaces)** [Stage 4 per agreed ordering] → **H17 — TFM cierre académico**.

**HX post-deploy / post-TFM** carry-forwards: HyDE retrieval reformulation; hybrid BM25 + dense; custom legal-pair reranker; cross-vendor judge migration (ADR-0021 D3); citation_precision aspirational target (HIGH §6 risk; ADR-0030 §REVERT lessons); LoRA severity classifier (charter §15.3 HX1); Next.js triple-surface frontend (HX2).

## Documentation

- `CLAUDE.md` — project charter, architecture, milestones, security, evaluation gates, §6.1 multi-layer architecture, §16.3 H15.X milestone log, §27 Hitos cerrados.
- `docs/technical_decisions_log.md` — ~4900 lines; every approved technical decision (TFM defense memory spine).
- `docs/adr/` — 35 Architecture Decision Records (0001-0035; 2 with §REVERT sections retained as scientific record).
- `docs/superpowers/specs/` — design specs per milestone.
- `docs/superpowers/plans/` — implementation plans per milestone.
- `docs/H16_DEPLOY.md` — deployment runbook (HF Spaces + Render + Fly.io + local Docker).
- `docs/pre_h16_review.md` — pre-H16 deep review + Stage 3 status update.
- `evals/reports/` — paid run reports across v0.1.20 onwards (TFM evidence trail).

## License

Proprietary. All rights reserved.
