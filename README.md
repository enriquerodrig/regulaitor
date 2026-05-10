# RegulAItor

> "RegulAItor no responde sin cita verificable: convierte la consulta normativa rutinaria y la revisión documental en un acto auditable, en minutos y por céntimos."

Multi-agent regulatory compliance service with strict citation verification. TFM project for the Master in Generative AI.

## Status

**H2 closed (2026-05-05) — RAG base operational.** Tag `v0.0.3-h2`.

- H0 / H0.1 / H1 / H2 closed. See [`docs/technical_decisions_log.md`](docs/technical_decisions_log.md).
- Corpus AI Act + GDPR ingested (PDF snapshot, 113 + 99 articles, ES + EN).
- LanceDB index `corpus/indexes/regulaitor.lance/` populated with 1011 chunks (BGE-M3 1024-dim dense + bge-reranker-v2-m3).
- 111 tests, 92.55% coverage. CI green.
- Next: H3 (MCP server + Retriever-Agent + citation validator).

⚠️ This system does not replace legal counsel. It is a first-line analysis tool that returns auditable findings with verified citations against an official regulatory corpus.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/), Python 3.11, and Git LFS (for the PDF corpus snapshots).

```bash
make setup        # install dependencies via uv + pre-commit hooks
make lint         # ruff + black --check + mypy
make test         # pytest (excludes slow integration tests)
make ingest       # parse PDF corpora into manifests + processed/
make rag-build    # chunk + embed + populate LanceDB (downloads ~3 GB on first run)
```

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

## Stack (current + planned)

Python 3.11 · `uv` · Pydantic v2 · **LanceDB · BGE-M3 · bge-reranker-v2-m3** (active) · FastAPI · LangGraph · Streamlit (MVP) · Next.js (advanced) · Docker · GitHub Actions · LangFuse · Ragas + DeepEval (planned).

## Roadmap

See `CLAUDE.md` §16 for the full milestone roadmap (H0 → H17 + optional HX). Active milestone: **H3 (MCP server + Retriever-Agent + citation validator)**.

## Documentation

- `CLAUDE.md` — project charter, architecture, milestones, security, evaluation gates.
- `docs/technical_decisions_log.md` — every approved technical decision (TFM defense memory).
- `docs/adr/` — Architecture Decision Records.
- `docs/superpowers/specs/` — design specs per milestone.
- `docs/superpowers/plans/` — implementation plans per milestone.

## License

Proprietary. All rights reserved.
