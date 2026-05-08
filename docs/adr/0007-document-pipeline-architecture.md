# ADR 0007 — Document pipeline architecture (H5)

- **Status:** Accepted
- **Date:** 2026-05-07 (H5 closure)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0005 (MCP server architecture), 0006 (chat E2E architecture).

## Context

H5 ships the document analysis pipeline (extractor + sanitizer + segmenter +
E2E flow) closing the second of three product surfaces (chat done in H4;
document is H5; API is H7). The defining requirement is "no citation, no
answer" extended to documents, plus four-layer defense in depth against
prompt injection embedded in user-supplied PDFs.

## Decision

Eight design decisions taken at brainstorming (2026-05-06) and preserved
through implementation, organized as follows:

| Tier | Modules introduced |
|---|---|
| Public surface | `scripts/analyze.py` (CLI smoke) |
| Orchestration | `orchestration/document_graph.py` (sequential per-segment loop) |
| Document layer | `document/extractor.py`, `document/sanitizer.py`, `document/segmenter.py` |
| Agents | `agents/analyst.py` extended (`prompt_role` parameter) |
| Helpers | `security/injection.py` extended (`mode` parameter), `security/allowlist.py` (new) |
| Schemas | `citation/schemas.py` extended (10 BaseModels + 1 exception) |
| MCP | `mcp_server/tools.py` + `server.py` (extract_document + segment_document) |
| Prompt | `agents/prompts/document_analyst/system.v1.0.md` |

### D1 — No OCR in H5

Scanned PDFs are rejected with `likely_scanned=True` flagged on each page;
the orchestration treats this as an extraction failure path rather than
performing OCR. Reasoning: deterministic pipeline > stochastic OCR layer;
SSDLC narrower; revisitable in HX optional post-H17.

### D2 — Only `pypdfium2` + `markdown-it-py` + `pikepdf` (deviation from CLAUDE.md §10.2)

CLAUDE.md §10.2 listed `pypdfium2 + unstructured + pdfplumber`. We narrowed
to `pypdfium2` (PDF text + outline) plus `pikepdf` (deep-scan for JS/URI/
forms/attachments) plus `markdown-it-py` (Markdown). `unstructured` and
`pdfplumber` deferred to H15 calibration if H8 evals show table-bound gaps.

### D3 — Sanitizer policy: strip & log + critical-block

JavaScript, attachments, form actions, URI actions targeting non-allowlisted
domains, and password-encrypted PDFs trigger an immediate `DocumentBlockedError`
→ `document_verdict=REQUIRES_HUMAN_REVIEW`. Metadata, annotations, invisible
text, hidden layers, and unicode tricks are stripped from the payload but
logged with SHA256[:12] hashes (warning). Outline + large-doc go log-only
(info).

### D4 — Segmenter: structural-by-outline + token-cap fallback

Outline ≥1 entry → split structurally (relaxed from ≥2 in plan during
implementation; see decisions log amendment). No outline + heading-like
lines detected → heuristic split. Otherwise → token-windowed fallback
(warning logged). Cap defaults to 1500 BGE-M3 tokens; oversized sections
split by paragraph with `is_continuation=True` on tail pieces.

### D5 — Document Analyst = same `AnalystAgent` class + separate prompt directory

`AnalystAgent` gains a `prompt_role: Literal["analyst", "document_analyst"]`
parameter. New prompt at `agents/prompts/document_analyst/system.v1.0.md`.
Same router, same `Answer` schema, same Auditor downstream.

### D6 — Separate `orchestration/document_graph.py` + sequential per-segment loop

Document E2E orchestration is a plain Python loop, NOT a LangGraph compiled
graph. Reasoning: linear control flow, fewer failure modes, easier to audit
in TFM defense. Chat graph in `graph.py` (LangGraph-based) is untouched.

### D7 — `is_injection(text, mode)` extension

Backwards-compatible: `mode="chat"` (default) keeps the 10 H4 patterns.
`mode="document"` adds ~13 document-specific patterns covering
instruction-to-evaluator, self-validating, citation poisoning,
authorize-exception, meta-inject, role override, data exfiltration,
jailbreak chains.

### D8 — Synthesized policy + adversarial twin for the integration test

Two PDF fixtures committed (regenerable from `.source.md` via
`make regenerate-fixtures`). Clean fixture exercises the happy path;
adversarial fixture exercises sanitizer + anti-injection layers in one slow
E2E test. ReportLab used as the PDF backend (pure Python, no system deps;
WeasyPrint deferred due to Windows host limitations).

## Alternatives considered

- **OCR with PaddleOCR / Tesseract** (D1): heavy dependencies, stochastic
  outputs, opens a path where the Analyst sees corrupted text and the
  Auditor cannot detect because the citation still validates against the
  corpus. Hybrid (text-extract first, OCR fallback) has the same SSDLC
  concern with more complexity.
- **Full CLAUDE.md §10.2 stack** (D2): `unstructured` adds ~200-300 MB of
  transitive dependencies (`nltk`, `lxml`, model downloads) and broadens
  SSDLC surface. `pdfplumber`-only is weaker for outline + metadata
  extraction.
- **Pass-through with `[METADATA: ...]` markers** (D3): LLMs are weak to
  marker-based meta-instructions; erodes "no citation, no answer". Silent
  strip without log breaks the evidence matrix narrative.
- **Naive token-windowed segmentation** (D4): rips clauses mid-thought;
  degrades Analyst quality. LLM-based semantic segmentation is stochastic
  and breaks H8 evals reproducibility.
- **Multi-mode Analyst prompt v2.0** (D5): prompt bloat; harder to evolve
  modes independently. Separate `DocumentAnalystAgent` class duplicates
  router/tool-use/path-traversal-defense logic.
- **Same `graph.py` with mode branch** (D6): bloats `ChatState` with optional
  fields, breaks `extra='forbid'`. Per-segment parallel fan-out
  (`asyncio.gather`) is non-deterministic ordering breaking H8 evals;
  rate-limit risk; deferred to H12.
- **Two separate functions** `is_injection_chat` / `is_injection_document`
  (D7): forces all callers to update; benefit dubious. LLM-based classifier
  is stochastic; non-determinism kills H8 evals; cost overhead per segment.
- **Real public policy** as fixture (D8): licensing maintenance, IP risk,
  source-disappearance fragility. Defer to H8/H9 violates the H5 deliverable
  list, sets bad precedent. WeasyPrint requires cairo/pango/gdk-pixbuf
  system libs unavailable on the user's Windows development host.

## Consequences

### Positive

- New package `src/regulaitor/document/` (3 modules: extractor, sanitizer,
  segmenter; orchestration in `orchestration/document_graph.py`).
- New orchestration entrypoint `run_document(...)` distinct from H4 `run(...)`.
- New schemas (10 BaseModels + 1 exception) in `citation/schemas.py`.
- New Spanish-language Document Analyst prompt versioned at
  `agents/prompts/document_analyst/system.v1.0.md`.
- `security/injection.py` API extended (backcompat preserved via default
  `mode="chat"`).
- `agents/analyst.py` API extended (backcompat preserved via default
  `prompt_role="analyst"`).
- New CLI `scripts/analyze.py` mirroring the `scripts/chat.py` shape.
- New skill `document-analysis` activated.
- Property + integration + unit tests added; full suite green (390 fast).
- Coverage gate raised: `document/sanitizer.py` and `document/extractor.py`
  ≥95%; ≥90% global.
- New runtime dependencies: `pypdfium2>=4.30,<5.0`, `pikepdf>=9.0,<10.0`,
  `markdown-it-py>=3.0,<4.0`. Dev deps: `reportlab>=4.0,<5.0`.
- Two PDF fixtures (clean + adversarial) regenerable from Markdown source
  via `make regenerate-fixtures`.

### Negative

- ReportLab limitations (no automatic page break tuning, byte non-determinism
  across reruns) leak through to fixtures; mitigated by regenerating before
  test runs in CI.
- WeasyPrint deferred — fidelity for HTML/CSS-driven adversarial fixtures
  is lower in ReportLab; D8 revision conditions track this.
- The sanitizer policy is conservative — false-positive critical-blocks on
  legitimate forms or URI actions targeting unfamiliar but legitimate
  domains. Mitigated by H7 allowlist expansion + REQUIRES_HUMAN_REVIEW
  verdict (not silent BLOCK).
- The segmenter token-cap fallback rate is unknown until H8 evals; some
  documents may produce many small chunks via paragraph-splitting on
  oversized sections.

## Revision conditions

- **D1** reopened if H17 academic scope requires OCR demo, or if a target
  user provides a test corpus dominated by scans.
- **D2** reopened if H8 evals reveal table-bound or layout-bound findings
  missed by the current extractor.
- **D6** reopened in H12 router milestone (parallelism becomes useful when
  multi-LLM router enables modes coste/calidad).
- **D8** PDF backend reopened if ReportLab limitations (no automatic page
  break tuning, byte non-determinism) become problematic for evals
  reproducibility — at that point WeasyPrint via Linux CI host or a
  deterministic alternative (e.g., Typst).

## References

- `docs/superpowers/specs/2026-05-06-h5-document-pipeline-design.md` — H5 spec.
- `docs/superpowers/plans/2026-05-06-h5-document-pipeline.md` — H5 plan.
- `docs/technical_decisions_log.md` H5 section.
- `docs/adr/0006-chat-e2e-architecture.md` — predecessor; H4 chat E2E.
- `.claude/skills/document-analysis/SKILL.md` — activated by H5.
- `src/regulaitor/{document,orchestration,agents,security,citation,mcp_server}/`
  — concrete output.
