# RegulAItor

> "RegulAItor no responde sin cita verificable: convierte la consulta normativa rutinaria y la revisión documental en un acto auditable, en minutos y por céntimos."

Multi-agent regulatory compliance service with strict citation verification. TFM project for the Master in Generative AI.

## Status

**H0.1 — Bootstrap.** Repository scaffolding only. Not functional yet.

⚠️ This system does not replace legal counsel. It is a first-line analysis tool that returns auditable findings with verified citations against an official regulatory corpus.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.11.

```bash
make setup        # install dependencies via uv
make lint         # ruff + black --check + mypy
make test         # pytest
make precommit    # run pre-commit hooks on all files
```

## Stack (planned)

Python 3.11 · `uv` · FastAPI · Pydantic v2 · LangGraph · LanceDB · BGE-M3 + bge-reranker-v2-m3 · Streamlit (MVP) · Next.js (advanced) · Docker · GitHub Actions · LangFuse · Ragas + DeepEval.

## Roadmap

See `CLAUDE.md` §16 for the milestone roadmap (H0 → H17 + optional HX). Current milestone: **H0.1 (Bootstrap)**. Next: H1 (Corpus AI Act + RGPD).

## License

Proprietary. All rights reserved.
