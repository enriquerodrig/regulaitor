# ADR 0001 — Project scope and core invariants

- **Status:** Accepted
- **Date:** 2026-04-30
- **Deciders:** Project owner (TFM author).

## Context

RegulAItor is the TFM (Master in Generative AI) capstone project. The aspiration is a defensible academic deliverable graded 9-10, evaluated against five master modules (M1-M5) and seven integrator phases (P1-P7).

Before writing implementation code, we need a record of the scope ceiling, the non-negotiable invariants, and the milestone discipline that will govern the project. This ADR pins those decisions so subsequent ADRs can refine sub-areas without re-litigating the foundation.

## Decision

### Product scope

RegulAItor is a **multi-agent regulatory compliance service with strict citation verification**, not a chatbot. It exposes three surfaces:

1. **Document analysis mode** (primary) — ingest a corporate document (PDF/Markdown) and emit a structured findings report with severity, literal citations, risk and recommendation.
2. **Chat mode** — natural language questions answered with verified inline citations.
3. **API mode** — FastAPI endpoints (`POST /ask`, `POST /analyze`, `GET /health`).

### Core invariant: "no citation, no answer"

Every Analyst output passes through the Auditor. Without a literal citation validated against the official corpus, no output is emitted. This is the project's differentiator and the academic anchor.

### Scope levels

- **MVP (H0-H10):** AI Act + RGPD corpus; three agents (Retriever, Analyst, Auditor); chat + document modes; Streamlit UI; minimal FastAPI; gold set evaluation; red team smoke; reproducibility via `make`. Closed with tag `v0.1.0-mvp`.
- **Advanced priority (H11-H17):** LangFuse observability; multi-LLM router with A/B; Council of Judges; NIS2 + DORA corpus; Auditor calibration; public deployment; full academic deliverables (model card, data card, AI Act assessment, runbook, video, slides). Closed with tag `v1.0.0`.
- **Optional (HX1-HX5):** LoRA severity classifier; Next.js advanced frontend; webhook/GitHub Action connector; standalone MCP server; Prometheus advanced.

Advanced is **conditional on MVP gate**. Optional is conditional on H17 closure.

### Milestone discipline

- Work proceeds **by milestones (H0 → H17 + HX), not by weeks**. Author availability is variable.
- No milestone advances without:
  1. The previous milestone's "Done" criteria verified.
  2. Explicit owner approval ("OK, implementa Hx.y").
  3. Pending blocking decisions answered.
- The MVP → Advanced gate (CLAUDE.md §16.2) has 10 mandatory checks.

### Stack ceiling (frozen unless renegotiated)

Python 3.11 · `uv` · FastAPI · Pydantic v2 · LangGraph · LanceDB · BGE-M3 + bge-reranker-v2-m3 · Streamlit (MVP) · Next.js (advanced) · `pypdfium2 + unstructured + pdfplumber` for PDF · MkDocs Material + Mermaid + Structurizr DSL for docs · Ragas + DeepEval for evals · Hugging Face Spaces for MVP deployment.

### Operating decisions ratified for H0.1

1. Package manager: **`uv`**.
2. `pre-commit` enabled from H0.1 (ruff, black, gitleaks, end-of-file, trailing-whitespace).
3. `mypy` permissive at start; tightened to `--strict` at H10.
4. Python 3.11 confirmed.
5. Zero MCPs and zero custom skills installed in H0.1; both governed by propose-and-wait per CLAUDE.md §13 and §12.3.

## Consequences

### Positive

- Clear contract between owner and implementer; reduces renegotiation cost.
- Milestone-based progress aligns with variable author availability.
- "No citation, no answer" rule is the most defensible academic claim and is anchored from day one.
- Stack is frozen enough to avoid analysis paralysis but open at the boundaries we expect to hit (NIS2/DORA structure, embeddings local vs API).

### Negative / Trade-offs

- Stack freezing without prototyping risks hitting unexpected limitations later (e.g., LanceDB scale, BGE-M3 license issues). Mitigation: ADRs to reopen specific decisions when evidence demands it.
- Advanced as "conditional" may mean some H11-H17 items are not delivered. Mitigation: deliverables marked `[medicion pendiente]` where evidence is missing — honest reporting is preferred over inflated claims.
- Milestone discipline can slow perceived velocity. Mitigation: small, finely-divided milestones (H0.1, H1, H2…) keep cadence visible.

### Decisions deferred

Listed in `CLAUDE.md` §27 deferrable decisions and re-stated in `0002-skills-mcps-roadmap.md`:

- Corpus version pinning and source CELEX identifiers (decided in H1).
- Corpus languages: ES only / EN only / both (decided in H1).
- Embeddings local vs API (decided in H2).
- First LLM provider (decided in H4).
- Citation matching tolerance policy (decided in H3).
- API auth strategy (decided in H7).
- OCR support for documents (decided in H5).
- Public deployment platform (decided in H16).
- LLM-as-judge model (decided in H8).
- Memoria language: ES only or bilingual (decided in H17).
- Corpus versioning strategy: branch / manifest / tag (decided in H1, options narrowed to DVC vs Git-LFS).

## References

- `CLAUDE.md` — full project constitution.
- `~/.claude/plans/lee-el-archivo-claude-md-sparkling-fairy.md` — operational milestone plan with per-hito gates, files, commands and risks.
- ADR `0002-skills-mcps-roadmap.md` — schedule for skill, MCP and subagent introduction.
