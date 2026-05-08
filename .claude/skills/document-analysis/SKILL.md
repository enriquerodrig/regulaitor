---
name: document-analysis
description: Use this skill when extracting, sanitizing, segmenting, or analyzing a document end-to-end through the RegulAItor pipeline (PDF or Markdown). Activates the full extract→sanitize→segment→loop[gate→retriever→analyst→auditor]→aggregate flow with SSDLC-aligned defaults.
version: 1.0
allowed-tools: [Read, Bash]
---

# Document Analysis (H5)

## When to use

- Analyzing a corporate document (policy, contract, impact assessment) against an EU regulatory corpus (AI Act, GDPR, NIS2, DORA).
- Extending or debugging the document pipeline modules (`document/extractor.py`, `document/sanitizer.py`, `document/segmenter.py`, `orchestration/document_graph.py`).
- Adding new anti-injection patterns for document mode.

## When NOT to use

- Chat queries → use `orchestration.graph.run` (H4) instead.
- Corpus ingestion (regulatory text) → that is `corpus/fetch.py` + `corpus/parse.py` (H1), not this pipeline.
- One-off PDF inspection → use the MCP tool `extract_document` directly; do not wrap it in custom orchestration.

## Canonical procedure

The single supported entrypoint is:

```python
from regulaitor.orchestration.document_graph import run_document

report = run_document(
    file_bytes=open("policy.pdf", "rb").read(),
    mime_type="application/pdf",
    language="es",
    corpus=["ai_act", "gdpr"],
)
```

CLI equivalent:

```bash
python -m scripts.analyze --file policy.pdf --lang es --corpus ai_act,gdpr
```

## What the pipeline guarantees

1. **No bypass of the sanitizer.** MCP tools `extract_document` and `segment_document` are inspection helpers; the only way to run the full E2E flow is `run_document(...)` (in-process).
2. **No citation, no answer.** Every Finding returned has at least one literal citation validated against the corpus.
3. **Deterministic verdict aggregation.** Per-Finding lenient (≥1 valid citation passes); per-Segment strict (PASS/BLOCK/REQUIRES_HUMAN_REVIEW); per-Document strict (any BLOCK or skipped-by-injection segment ⇒ document BLOCK; mix without BLOCK ⇒ REQUIRES_HUMAN_REVIEW).
4. **Audit trail without PII.** `sanitizer_log` records SHA256[:12] hashes of stripped/blocked content, never plain text (CLAUDE.md §18.8).

## Anti-patterns to avoid

- **Mocking the Auditor** — never. The Auditor is the central control of the project.
- **Mocking the sanitizer in integration tests** — never. The sanitizer is the first SSDLC layer.
- **Exposing the E2E flow as an MCP tool** — never. Defense in depth.
- **Parallelizing the per-segment loop in H5** — deferred to H12.
- **Adding `extra='ignore'` to any document schema** — must be `extra='forbid'`.
- **Logging plain text from sanitized content** — use `content_hash` only.
- **Bypassing `is_injection(seg.text, mode="document")`** in the loop — even for tests.

## References

- Spec: `docs/superpowers/specs/2026-05-06-h5-document-pipeline-design.md`
- ADR: `docs/adr/0007-document-pipeline-architecture.md` (created in Task 18)
- Decisions log: `docs/technical_decisions_log.md` §H5 (populated in Task 18)
