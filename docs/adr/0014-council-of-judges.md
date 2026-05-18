# ADR 0014 — Council of Judges (H13)

- **Status:** Accepted
- **Date:** 2026-05-17 (decision); 2026-05-18 (implemented; squash `<squash-sha>`, tag `v0.1.3-h13`)
- **Deciders:** Project owner.
- **Companion ADRs:** 0006 (chat graph — sole orchestration modified), 0012 (observability
  — LangFuse egress pattern followed), 0013 (router — `judge` mode added here).

## Context

CLAUDE.md §16.3 lists H13 as: a Council of 3 independent LLM judges for high-severity
findings and ambiguous cases, voting `valid | invalid | requires_human_review`; result
recorded as auditable evidence. §8.4 defines the Council as the differentiating advanced
component. §6 ("no citation, no answer") requires the deterministic mechanical Auditor
verdict to remain 100% reproducible — the Council is explicitly advisory.

Entering H13 (main post-H12 `v0.1.2-h12`) the chat graph had: retriever → analyst →
auditor → response. The router had 5 modes (default/quality/cost/evaluation/fallback).
Hard constraints: H1–H5 backend / document pipeline / API / Streamlit / `evals/harness.py`
read-only; the mechanical Auditor verdict is never mutated. The H12 A/B finding reinforced
that the quality ceiling is system-level (retriever + Auditor calibration), not model choice.

## Decision

Seven design decisions (brainstorming closed 2026-05-17; full rationale + amendments in
`docs/technical_decisions_log.md §H13`):

### D1 — Authority: advisory + visible notice + promotion-ready

The Council verdict **never mutates** the mechanical Auditor verdict (deterministic,
reproducible; §6 "no citation, no answer" stays 100% intact). `council_review` is
explicitly non-deterministic advisory evidence. A visible `council_notice` is surfaced
via the API response and Streamlit UI when the Council diverges from the Auditor. The
`AggregationPolicy` is swappable; `AdvisoryMajorityPolicy` (default) records the
advisory outcome without touching the verdict. `MonotonicEscalatePolicy` is implemented
and unit-tested but wired OFF via `_COUNCIL_BINDING = False` — the H15 promotion seam.

### D2 — Trigger: hybrid (auto + API override)

Auto-trigger: `audited.verdict == REQUIRES_HUMAN_REVIEW` OR any `finding.severity ==
"high"`. API override: `council: bool | None` in the request body. Skip if
injection-blocked or no `audited_answer`. Explicit reviewer-documented intent: `AuditVerdict.BLOCK`
is intentionally NOT an auto-trigger — it is the strictest deterministic verdict; the
advisory Council never relaxes a BLOCK.

### D3 — Judges: 3 distinct providers via the router

`judge` mode → Haiku 4.5 (new router mode added in H13 T1); `evaluation` mode → GPT-4o;
`cost` mode → Llama-3.3-70b-Groq. Per-judge failure degrades gracefully to `ok=False`
(the run continues); all exceptions are swallowed at the Council layer (advisory
invariant: a Council failure must never break the chat turn).

### D4 — Scope: chat graph only

The document pipeline is untouched (read-only). Document-mode Council is explicitly a
future follow-up. This keeps the H5 document graph at regression-zero.

### D5 — Success: honest divergence study (not an improvement claim)

By construction, an advisory layer that never mutates the Auditor verdict cannot
"improve faithfulness" or "block rate" in aggregate. The deliverable is a divergence
study on the triggered subset (the gated paid run). This is an explicit honest reframe
of the CLAUDE.md §16.3 "Done when" language, mirroring the H10 gate-reframe pattern.

### D6 — Architecture: new `council` LangGraph node + conditional edge

A new `council` node is added after the `auditor` node in the chat graph, connected via
a `_route_after_audit` conditional edge. `CouncilAgent.review()` is the entry point;
`GraphState` gains `council_review: CouncilReview | None`. Backend H1–H3/Analyst/mechanical-Auditor
read-only/regression-zero. `api/routes_ask.py`, `api/schemas.py`, and
`ui_streamlit/_render.py` receive the `council_review` field.

### D7 — Router `judge`-mode extension

A new `judge` mode mapping to Haiku 4.5 (Anthropic) is added to `models/router.py` and
`models/config.py`. This is the sixth router mode; all existing 5 modes are
regression-zero. The "all LLM via the router" invariant (CLAUDE.md §13) is preserved.
Justified as ADR-worthy: it is the only new production-constant addition to the router
in H13.

> **Two-stage review caught four milestone-consequential defects** (recorded per
> CLAUDE.md §22.1 — see §H13):
> **T7** — `CouncilAgent.review` could raise via the `CouncilReview`
> `triggered/trigger_reason` invariant when passed `"not_triggered"`, violating the
> paramount advisory "never break the turn" invariant; fixed by narrowing the `Literal`
> (the controller also caught a related mypy `Context|None` defect).
> **T10** — the council summary reached the JSON log but was NOT forwarded to the
> LangFuse trace (`tt.set_root` not extended) — the allowlist was inert; egress gap
> fixed (spec §3/§5 required BOTH log AND LangFuse).
> **T12** — `_render.py` re-implemented `_council_notice` verbatim instead of reusing
> the canonical `api.schemas._council_notice` (single-source-of-truth violation); fixed
> by cross-layer reuse.
> **T14b** — `council_analysis.md` initially overstated one divergence sub-pattern as
> "~9" vs the real 7 — caught by the honesty review, corrected (§22.22 exact-number
> discipline).

## Consequences

**Positive:**
- Advisory Council layer is live on the chat path with 3 independent LLM providers —
  the §8.4 advanced academic deliverable for Módulo 2.
- Prompt versioned: `prompts/council/judge.v1.0.md` (skill `prompt-versioning` applied).
- `MonotonicEscalatePolicy` + `_COUNCIL_BINDING = False` implement the H15 promotion
  seam with zero production impact today (all unit-tested).
- Real divergence study: **12/21 ≈ 57%** of triggered cases diverged between the Council
  and the mechanical Auditor; **chat-11** (Auditor=pass → Council=requires\_human\_review)
  demonstrates the semantic-support escalation the advisory Council was built to surface.
- `evals/reports/latest.council.md` + `docs/council_analysis.md` are reproducible
  auditable evidence for the TFM defense.
- Backend H1–H5 / document pipeline / mechanical Auditor untouched; regression-zero.
- Coverage gate: **93.40%** (full `python -m pytest -q` run, authoritative; a partial
  invocation during T13 quality review reported 79% — false alarm from incomplete scope,
  not the gate run; real gate green).

**Negative / accepted (documented honestly, not re-run — §22.22, H11/H12 precedent):**
- **30% skip rate in the paid run.** 9/30 gold cases were skipped because the Analyst
  emitted no `findings` (the documented schema-adherence flakiness from §H10/§H11
  Amendment 4). The raw skip label in `evals/reports/latest.council.md` reads
  "(injection-blocked or council-unavailable)"; `docs/council_analysis.md` is the
  authoritative accurate attribution. Not re-run for a cosmetic label.
- **Groq I-2 contamination recurred (H12 precedent).** The Groq free-tier 100k-TPD
  cap 429'd approximately 6 times; the H12 controlled fallback substituted GPT-4o-mini
  in the Llama slot for those panels → approximately 6 of the 21 panels were
  Haiku+GPT-4o+GPT-4o-mini (2 OpenAI models, not 3 independent providers). Documented,
  not re-run.
- **Cost not per-run-measured.** The same pipeline gap as H12: nothing aggregates
  `CompletionResult.cost_eur` across judges. Honest approximation: **~$1.2–1.5**
  (not a measured figure). Follow-up → H15.
- **3 paid-path defects surfaced by the gated run** (T13 `# pragma: no cover` path
  structurally unexecutable by the two-stage review): (1) missing `corpus_loader.warmup()`,
  (2) correct invocation requires `uv run --env-file .env python -m scripts.council_eval`
  (bare `python -m` does not load `.env`), (3) no per-case `try/except` (one flaky
  Analyst case aborted the full run). Each crashed fail-fast before paid calls (~$0.04
  on the third); a `--limit 3` probe validated the thrice-fixed harness before the full
  spend. Budget protected.
- **`_council_notice` Spanish string lives in the API schema layer** (`api/schemas.py`)
  — spec-approved (spec §4 verbatim); sole consumer is the Spanish Streamlit UI. Revisit
  if a non-UI API consumer is added.
- **Cross-layer private import:** `ui_streamlit/_render.py` imports from `api.schemas`
  (single-source-of-truth tradeoff, plan-endorsed); promote to a shared notices module
  if a second non-UI consumer appears.
- No new skills activated; `cost-accounting` stays H17.

## Alternatives considered

- **Binding Council (immediately replace Auditor verdict)** — rejected (D1). Breaks the
  "no citation, no answer" deterministic/reproducible invariant; non-deterministic LLM
  votes cannot be the authoritative security gate.
- **Single-provider Council (3 Haiku calls)** — rejected (D3). Provides no independence;
  all calls share the same paramétric biases. Three distinct providers are the academic
  and operational differentiator.
- **Synchronous parallel judge calls** — considered; rejected for MVP (adds threading
  complexity, harder to debug). Sequential calls are simpler and the advisory result is
  non-blocking.
- **Document-mode Council** — deferred (D4). Requires `document_graph.py` changes and
  multi-segment aggregation logic; out of H13 scope (H1–H5 read-only constraint).
- **Re-run the contaminated paid run with paid Groq tier** — rejected by project owner
  (§22.22, H11/H12 honesty precedent; the Groq I-2 and the 30% skip are themselves
  honest, valuable findings).

## References

- Spec: `docs/superpowers/specs/2026-05-17-h13-council-of-judges-design.md`
- Decisions log `§H13` (D1–D7, all amendments, paid-path defects, real T14 results,
  follow-ups); `§H12` (H12 A/B finding: quality ceiling is system-level).
- `evals/reports/latest.council.md` (raw 30-case run output).
- `docs/council_analysis.md` (authoritative attribution of skip cause + divergence
  analysis; 7-of-12 RHR→pass pattern; chat-11 escalation).
- `src/regulaitor/agents/council.py`, `src/regulaitor/orchestration/graph.py`,
  `src/regulaitor/agents/prompts/council/judge.v1.0.md`.
