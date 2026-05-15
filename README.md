# RegulAItor

> "RegulAItor no responde sin cita verificable: convierte la consulta normativa rutinaria y la revisión documental en un acto auditable, en minutos y por céntimos."

Multi-agent regulatory compliance service with strict citation verification. TFM project for the Master in Generative AI.

## Status

**H9 closed (2026-05-13) — red team initial.** Tag `v0.0.10-h9`. MVP feature-complete; H10 closes documentation + freezes tag `v0.1.0-mvp`.

| Milestone | Tag | Closure date | Highlight |
|---|---|---|---|
| H0.1 bootstrap | `v0.0.1-h0.1` | 2026-04-30 | repo + CI + lint |
| H1 corpus | `v0.0.2-h1` | 2026-05-04 | AI Act + GDPR PDF snapshot (113 + 99 articles, ES + EN) |
| H2 RAG base | `v0.0.3-h2` | 2026-05-05 | LanceDB + BGE-M3 + reranker; 1011 chunks |
| H3 MCP server | `v0.0.4-h3` | 2026-05-05 | 5 tools + Retriever-Agent + citation validator |
| H4 chat E2E | `v0.0.5-h4` | 2026-05-05 | Analyst + Auditor + LangGraph |
| H5 document pipeline | `v0.0.6-h5` | 2026-05-07 | Extractor + sanitizer + segmenter |
| H6 Streamlit MVP | `v0.0.7-h6` | 2026-05-07 | Two-tab UI (Pregunta / Analiza documento) |
| H7 FastAPI MVP | `v0.0.8-h7` | 2026-05-10 | `/ask`, `/analyze`, `/health` + Bearer auth + rate limit |
| H8 eval harness | `v0.0.9-h8` | 2026-05-12 | Gold set 30 + 10; Ragas + custom + Haiku judge |
| H9 red team | `v0.0.10-h9` | 2026-05-13 | 50 attacks + smoke gate 0.92 |
| **H10 docs MVP freeze** | `v0.1.0-mvp` | in progress | Documentation + reproducibility verification |

Codebase: ~13k LOC Python (src/), 538+ tests, 92.61% coverage on gated subsystems (citation/agents/rag/security all > 90%). CI: lint + test + Document E2E + security + redteam smoke jobs all green.

⚠️ This system does not replace legal counsel. It is a first-line analysis tool that returns auditable findings with verified citations against the official regulatory corpus.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/), Python 3.11, and Git LFS (for the PDF corpus snapshots).

```bash
make setup        # install dependencies via uv + pre-commit hooks
make lint         # ruff + black --check + mypy
make test         # pytest (excludes slow integration tests)
make ingest       # parse PDF corpora into manifests + processed/
make rag-build    # chunk + embed + populate LanceDB (downloads ~3 GB on first run)
```

> **Windows note:** `make` is not bundled with Git for Windows. Either install GNU Make (e.g., via `choco install make` or `scoop install make`) or run the underlying `uv` commands directly. The `Makefile` is one short file; each target is one `uv run ...` line. CI runs on Ubuntu (`make` always available there), so the gate §16.2 #1 reproducibility is verified on Linux per push.

The first `make rag-build` downloads BGE-M3 (~2.3 GB) and bge-reranker-v2-m3 (~600 MB) from HuggingFace Hub into `~/.cache/huggingface/`. Re-runs are idempotent (`chunks_added=0` when nothing changed).

### Document analysis mode (H5)

Analyze a corporate policy PDF or Markdown against the EU regulatory corpus:

```bash
python -m scripts.analyze \
    --file path/to/policy.pdf \
    --lang es \
    --corpus ai_act,gdpr
```

Output is a JSON `DocumentReport` with per-segment audit verdicts and a global verdict (PASS / BLOCK / REQUIRES_HUMAN_REVIEW). Exit code 0 on PASS, 1 on BLOCK or REQUIRES_HUMAN_REVIEW, 2 on extraction error, 3 on configuration error. **No respuesta sin cita validada — incluso para documentos.**

### UI Streamlit (H6)

Lanza el MVP de dos pestañas (Pregunta / Analiza documento):

```bash
make serve
```

Streamlit imprime una URL local (típicamente `http://localhost:8501`). El banner amarillo de aviso jurídico es persistente; si `ANTHROPIC_API_KEY` no está en `.env`, la app muestra un error rojo y no expone los tabs. Usa el flujo Pregunta para queries de chat o el flujo Analiza documento para subir un PDF/Markdown corporativo y ver el `DocumentReport` con verdict por segmento + sanitizer log + audit trail por cita.

**No respuesta sin cita validada — incluso en la UI**.

## API Quickstart (H7)

The API exposes three endpoints (`POST /ask`, `POST /analyze`, `GET /health`)
behind a static Bearer token. Same backend pipelines as the Streamlit UI.

### Prerequisites

- Set `REGULAITOR_API_TOKEN` (≥16 chars) and `ANTHROPIC_API_KEY` in `.env`.
- LanceDB index populated via `make rag-build` (≥1 chunk required for `/health` to report `ok`).

### Running

```bash
make serve-api
```

The API listens on `http://localhost:8000`. OpenAPI docs at `/docs`.

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
| `REGULAITOR_RATE_LIMIT_ASK` | `30/minute` | per-token quota for `/ask` |
| `REGULAITOR_RATE_LIMIT_ANALYZE` | `5/minute` | per-token quota for `/analyze` |
| `REGULAITOR_MAX_UPLOAD_BYTES` | `10485760` (10 MB) | max upload size for `/analyze` |
| `REGULAITOR_RATE_LIMIT_DISABLED` | (unset) | set to `1` to disable rate limiting (tests) |

## Evaluation (H8)

The harness runs the full RegulAItor pipeline against a curated gold set
(30 chat + 10 docs), computes Ragas + custom metrics with a Haiku 4.5
LLM judge, and emits `evals/reports/latest.md`.

### Quickstart

```bash
# Full run with live LLM (~$2.50-$3.50 Anthropic credit; populates judge cache)
make eval

# Subsequent regenerations from judge cache: free (H4/H5 calls are not cached, so
# this only refreshes the judge-layer outputs — see ADR 0010 §6.4)
make eval-from-cache

# Debugging the harness with first 5 chat + 1 doc case (~$0.30)
make eval-subset
```

> **Partial reproducibility caveat:** `make eval-from-cache` replays only the
> judge layer (Haiku 4.5 calls are cached). The H4 chat graph and H5 document
> pipeline make their own live LLM calls on every run. To fully re-run production
> calls use `make eval` (~$3-5 Anthropic credit per full run).

### Reading the report

`evals/reports/latest.md` has five sections:

1. **Header** — run date, commit SHA, model versions, total cost.
2. **Aggregate table** — each metric with its threshold from CLAUDE.md §17 and
   a pass/fail mark.
3. **Per-case appendix** — 40 sections (one per gold case) showing actual vs
   expected verdict, citations emitted vs expected, RAG metrics, criteria scores.
4. **Reproducibility block** — literal commands to regenerate the report.
5. **Caveats** — limitations of the eval setup (same-vendor judge, heuristic cost
   estimation, synthetic gold set).

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | Production model + judge model access |

The judge model (`claude-haiku-4-5-20251001`) and production model
(`claude-sonnet-4-6`) are hardcoded in `evals/harness.py`; change there
if migrating to a different vendor (deferred to H12 per ADR 0010).

## Red Team (H9)

50 adversarial attacks covering the 10 scenarios from CLAUDE.md §18 (22 chat-mode + 28
doc-mode). See `redteam/attacks.jsonl` for the full attack set.

```bash
make redteam-smoke    # deterministic subset only ($0, ~30s) — runs in CI
make redteam          # full run with live LLM (~$3.31)
```

Gate §16.2 #4: `block_rate_final ≥ 0.90`. Current value: see `redteam/reports/latest.md`.

Defense in depth: sanitizer (12 categories) + injection regex (23+ patterns) + citation
validator (3 checks) + Auditor lenient-strict aggregator. Details in
`docs/security_report.md`.

> `make redteam-smoke` runs only the `requires_e2e: false` doc-mode attacks (deterministic,
> no LLM calls). Full run adds chat-mode E2E and the doc-mode E2E subset. Results are
> committed to `redteam/reports/latest.md` after each manual full run.

## Stack (current + planned)

Python 3.11 · `uv` · Pydantic v2 · **LanceDB · BGE-M3 · bge-reranker-v2-m3** (active) · FastAPI · LangGraph · Streamlit (MVP) · Next.js (advanced) · Docker · GitHub Actions · LangFuse · Ragas + DeepEval (planned).

## Roadmap

See `CLAUDE.md` §16 for the full milestone roadmap (H0 → H17 + optional HX).

**MVP track (H0-H10)** — feature freeze at `v0.1.0-mvp`:
- H0-H9 closed (see Status table). H10 in progress.

**Advanced track (H11-H17)** — gated on §16.2 (all 10 MVP gates green):
- H11 LangFuse observability + per-attack timeouts in red team runner.
- H12 Multi-LLM router (Sonnet + GPT-4o + Llama via Groq) + cost analysis.
- H13 Council of Judges for high-severity findings.
- H14 NIS2 + DORA corpus expansion.
- H15 Auditor calibration + A/B testing (target: citation_precision ≥ 0.85).
- H16 Public Docker deploy (Hugging Face Spaces).
- H17 Academic closure (memoria + model card + data card + AI Act assessment + runbook + demo video).

Active milestone: **H10 — Documentation MVP + freeze (`v0.1.0-mvp`)**.

## Documentation

- `CLAUDE.md` — project charter, architecture, milestones, security, evaluation gates.
- `docs/technical_decisions_log.md` — every approved technical decision (TFM defense memory).
- `docs/adr/` — Architecture Decision Records.
- `docs/superpowers/specs/` — design specs per milestone.
- `docs/superpowers/plans/` — implementation plans per milestone.

## License

Proprietary. All rights reserved.
