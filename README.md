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
