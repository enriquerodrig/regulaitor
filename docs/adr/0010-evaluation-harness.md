# ADR 0010 — Evaluation harness for H8

- **Status:** Accepted
- **Date:** 2026-05-10 (decision); 2026-05-12 (H8 merged, squash `<sha>` TBD post-merge, tag `v0.0.9-h8` TBD)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0006 (chat E2E), 0007 (document pipeline), 0009 (FastAPI architecture).

## Context

CLAUDE.md §16.1 lists H8 as the milestone where `make eval` becomes reproducible with
real metrics, gating the move from MVP to advanced (§16.2 #3 + #5: report with real
metrics + citation precision ≥ 0.85). H8 must produce: (a) a 30 chat + 10 doc gold
set, (b) a Python harness, (c) a markdown report committed to main, all within a
constrained $10 Anthropic budget.

The harness closes the reproducible eval loop without touching the H1-H5 backends —
the same constraint applied in H6 (Streamlit) and H7 (FastAPI). It imports
`orchestration.graph.run` and `orchestration.document_graph.run_document` directly
(no HTTP, no auth overhead) and wraps calls in a SHA256 hash-keyed cache so the
budget is consumed exactly once.

## Decision

Eight design decisions:

### D1 — Judge = Anthropic Haiku 4.5

Single API key simplicity. `claude-haiku-4-5-20251001` is a distinct model class
from the production `claude-sonnet-4-6`, reducing within-Anthropic echo-chamber
risk while staying within a single billing account. Known limitation: same vendor
weakens the "independent judge" claim per CLAUDE.md §19; promoted to deferral when
H12 router multi-LLM introduces an external vendor (GPT-4o-mini or similar). The
caveat is baked into the report's `Caveats` block — not hidden.

### D2 — Framework = Ragas + custom layer

Ragas provides standard RAG metrics (faithfulness, answer_relevancy,
context_precision, context_recall) that are directly cite-able in TFM defense. A
custom layer adds RegulAItor-specific metrics (citation_precision, citation_recall,
verdict_match_rate, severity_match_rate) not covered by Ragas. DeepEval is deferred
to H15 calibration where pytest-driven thresholds add value without redundancy.

### D3 — Scope = 30 chat + 10 docs, stratified

Minimum per CLAUDE.md §19. Stratification: 15/15 by corpus (ai_act/gdpr), 10/3/2
verdict split per chat (pass/requires_human_review/block), 4/4/2 docs by corpus
(ai_act/gdpr/mixed). Cache is mandatory — without it a debugging iteration consumes
the entire $10 budget.

### D4 — Execution = local + manual commit

CI runs only unit tests on harness logic; no LLM calls in CI (decision firm: $7/PR
is unsustainable on $10 budget). `--subset N` and `--cache-only` flags for debugging
without spend. `make eval` is human-initiated.

### D5 — Authoring = hybrid (human skeleton + subagent draft + PR review)

Human authors the stratification skeleton (~3-4h); subagent drafts `gold_set.jsonl`,
10 ReportLab PDFs, and manifests (~1-2h background); human reviews in PR (~1-2h).
Manual full authoring (10-15h) rejected for opportunity cost. Subagent-only (0h
human) rejected because gold set quality gates TFM credibility.

### D6 — Report = aggregate + per-case appendix

~5-7 pages markdown. Aggregate table with pass/fail marks per CLAUDE.md §17
threshold. Per-case appendix (40 sections) for audit by examiner. Stratified
breakdown deferred to H10/H17 polish. Bake-ins: `temperature=0`, `Caveats` block
(same-vendor judge + heuristic cost + synthetic gold set), reproducibility block.

### D7 — Cache = SHA256 hash-keyed JSON in `evals/cache/` (gitignored)

Key = `SHA256(model + temperature_str + prompt_text)`. Cache miss → live Anthropic
call + write JSON. Cache hit → read JSON, skip API. `evals/cache/` is gitignored;
operator regenerates with `make eval`. Cache covers the judge layer only — H4/H5
production LLM calls are NOT intercepted (accepted limitation, documented in §6.4
of the spec and in the harness comments).

### D8 — No backend modification

Harness consumes H4/H5 as black boxes. No instrumentation, no token-surfacing hooks,
no internal changes. If H4 returns an unexpected schema, the harness catches
`pydantic.ValidationError` and emits a sentinel result rather than crashing.

## Alternatives considered

- **OpenAI GPT-4o-mini as judge** — rejected: requires second vendor billing now;
  defer to H12.
- **Groq Llama-3.1-70B as judge** — rejected: free tier rate limits cause flaky
  runs that invalidate reproducibility.
- **DeepEval pytest integration** — rejected: redundant with custom layer + Ragas
  for H8 metrics; bring in H15 calibration where its threshold enforcement adds
  genuine value.
- **Pure custom harness without Ragas** — rejected: weakens TFM defense (Ragas is
  the RAG benchmark standard).
- **Below-minimum gold set (20 chat + 5 docs)** — rejected: violates CLAUDE.md §19
  gate and weakens the H10 coverage argument.
- **Full-CI gating per-PR** — rejected: $7/PR is unsustainable on $10 budget;
  decision is firm — documented in Q4.
- **Manual full gold set authoring (10-15h)** — rejected: opportunity cost vs
  hybrid (5-6h total).
- **Aggregate-only report (no per-case appendix)** — rejected: examiner cannot
  audit individual cases; TFM evidence matrix requires per-case traceability.

## Consequences

### Positive

- Harness reproducible: `make eval-from-cache` regenerates identical report for
  free once cache is populated.
- Cost-bounded: $10 budget covers exactly one full live run + unlimited cache
  replays.
- Backend H1-H5 untouched; regression risk is zero by construction (same guarantee
  as H6 and H7).
- Ragas standard metrics are directly citable in TFM Módulo 3 (RAG, evaluación,
  despliegue).
- Same-vendor judge caveat is documented as a known limitation, not concealed.

### Negative / accepted

- Judge same vendor as production (Haiku vs Sonnet, both Anthropic) weakens
  independence claim. Documented in report Caveats; deferred to H12.
- Cost estimation is heuristic-based (fixed token approximation: ~3000 in + 800
  out per chat, ~30k in + 8k out per doc) since H4/H5 do not surface usage tokens
  to the harness. Real cost may diverge ±30%; report shows the estimate.
- `evals/cache/` files are large (~5-50 KB each × 40+ entries). Gitignored;
  operator regenerates with `make eval` on a fresh clone.

### Deferred to future-work doc in H17

- Adversarial set + Auditor block rate (H9 redteam).
- DeepEval pytest integration (H15).
- LangFuse trace integration (H11).
- A/B comparison multi-model (H12).
- Stratified breakdown by corpus + verdict in report (H10/H17 polish).
- Migration of judge to non-Anthropic vendor (H12).
- Per-page-normalized `cost_per_doc_eur` (H17).
- CI gating per-PR (never, by design).

## Implementation amendments

Deviations from the spec discovered during implementation. Captured here per the
H1 PDF-pivot pattern (decisions log §H1).

1. **Task 2 — `schemas.py` lint fixes.** Minor import sort and removal of an
   unused `DocCaseResult` import. Functionally identical to spec.

2. **Task 3 — `cache.py` resilience hardening.** `try/except JSONDecodeError`
   added to treat corrupt cache files as misses rather than crashing. `_PROMPT_SEP`
   constant extracted. File schema assertions added to tests. Cost test covers
   both-tokens-nonzero case. Regression test added for corrupt-cache scenario.

3. **Task 4 — `metrics.py` critical fixes.** NaN guard added to
   `_ragas_metrics_chat` (Ragas can produce `nan` → Pydantic `ValidationError` →
   harness crash). Doc faithfulness uses segment text as context (was `contexts=[]`
   which produced zero-faithfulness spuriously). `audited=None` maps to
   `requires_human_review` (not `block`). Latency p95 split into `chat`, `doc`,
   `combined` sub-fields in `AggregateMetrics`. Additional unit tests added for
   these paths.

4. **Task 5 — `judge.py` strip-markdown-fence helper.** `_strip_markdown_fence`
   added to `score_criteria` — Haiku 4.5 occasionally wraps JSON in ` ```json `
   fences despite the prompt; resilient parsing strips the fence and recovers the
   inner JSON.

5. **Task 7 — `harness.py` sentinel wrapping.** `run_chat_case` and `run_doc_case`
   wrapped in `try/except` with sentinel result on failure. H4 Analyst occasionally
   produces a tool-use response missing the `findings` field → Pydantic
   `ValidationError` → without this guard the harness would crash mid-run. Sentinel
   preserves the error in the report. Backend is NOT modified (D8).

6. **Task 7 — `corpus_loader.warmup()` call at harness start.** The warmup was
   only called by `mcp_server` at process start; `harness.main()` lacked it, causing
   the first retrieval call to fail on a fresh Python process. Added at top of
   `main()`.

7. **Task 7 — `langchain-anthropic>=0.3,<1.0` added to dev.** Ragas LLM backend
   requires this package; not a transitive install of `ragas` itself.

8. **Task 7 — `langchain-huggingface>=1.0,<2.0` + `HuggingFaceEmbeddings`.**
   Ragas embedding backend defaults to OpenAI if no embeddings adapter is passed.
   Passing `HuggingFaceEmbeddings("BAAI/bge-m3")` avoids a second API key (rejected
   per Q1). Added to dev dependencies.

9. **Task 7 — `ChatAnthropic(max_tokens=4096)`.** Default `max_tokens=1024`
   caused `LLMDidNotFinishException` in Ragas faithfulness for longer passages.

10. **Task 10 — Gold set block-case sentinel fix.** Block cases initially used
    `articulos_esperados=["N/A"]` (schema required `min_length=1`). Fix-pass: schema
    relaxed to allow empty list `[]`; aggregate excludes empty-expected cases from
    citation metrics; 4 block-case records updated to `[]`. New generation script
    `scripts/generate_h8_gold_set.py` (not extending H5's
    `regenerate_document_fixtures.py` to avoid coupling).

11. **Task 11 — Two transitive CVEs ignored.** CVE-2025-69872 (diskcache pickle
    RCE, no upstream fix; only exploitable with write access to `evals/cache/` which
    is operator-local) and CVE-2026-6587 (ragas SSRF in `multi_modal_faithfulness`
    module, not exercised by our text-only metric set). Both use `--ignore-vuln` in
    CI workflow with rationale comment.

12. **Task 11 — `.env.example` removal.** Per user instruction superseding
    CLAUDE.md §22.6: single `.env` only. Captured in memory.

## Revision conditions

- When H12 router multi-LLM lands: migrate judge to GPT-4o-mini or similar, re-run
  gold set, update ADR.
- When H10 gate fails despite system improvements: expand gold set to 60 cases per
  CLAUDE.md §19 advanced stratification.
- When cost estimation diverges >50% from actual Anthropic billing: replace
  heuristic with `response.usage` extraction (requires H4 internal change —
  deferred to avoid violating D8).

## References

- Spec: `docs/superpowers/specs/2026-05-10-h8-evaluation-harness-design.md`
- Plan: `docs/superpowers/plans/2026-05-10-h8-evaluation-harness.md`
- Brainstorming: 6 Qs cerradas (judge, framework, scope, execution, authoring,
  report). Ver §H8 en `docs/technical_decisions_log.md`.
- Predecessors: ADR 0006 (H4 chat), ADR 0007 (H5 document pipeline), ADR 0009
  (H7 FastAPI).
