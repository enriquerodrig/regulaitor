# ADR 0013 — Router multi-LLM + cost analysis (H12)

- **Status:** Accepted
- **Date:** 2026-05-16 (decision); 2026-05-17 (implemented; squash `d59a33f`, tag `v0.1.2-h12`)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0006 (chat graph — sole router caller),
  0010 (evaluation harness — reused read-only), 0012 (observability — env-gating idiom precedent).

## Context

CLAUDE.md §16.3 lists H12 as: a real multi-LLM router (`models/router.py`) +
cost/quality analysis + cost/quality/evaluation modes. §10.4 defines the router
modes; §24 Módulo 1 makes the hand-built router an academic deliverable. Entering
H12 (main post-H11 `v0.1.1-h11`) the router was a thin single-backend
(`default`/`quality` → Anthropic Sonnet 4.6; `cost`/`evaluation`/`fallback` →
`NotImplementedError`) with a provider-agnostic `CompletionResult`. Only the
Analyst calls the router (Auditor is mechanical). The H8 harness (read-only)
hard-wires its production-model + a fixed token estimate for its own cost line.
Hard constraint: H1–H5 backend / graph / API / Streamlit / `evals/harness.py`
are read-only — only `models/router.py`, `models/config.py`, a new eval
wrapper, and docs may change.

## Decision

Four design decisions (brainstorming closed 2026-05-16; full rationale +
amendments in `docs/technical_decisions_log.md §H12`):

### D1 — A/B scope: reuse the frozen Sonnet baseline; run only GPT-4o + Llama

The Sonnet 4.6 column reuses the frozen H10/H11 baseline (not re-run). Only
GPT-4o and Llama-3.3-70b (Groq) are run over the same 40-case gold set with the
same Haiku judge → a comparable 3-way table.

### D2 — Lineup (5 modes): default/quality=Sonnet 4.6 · cost=Llama-3.3-70b (Groq) · evaluation=GPT-4o · fallback=GPT-4o-mini

Requires `OPENAI_API_KEY` + `GROQ_API_KEY` in the single `.env` (user-provided;
never `.env.example`). Groq model id verified live in Task 10 pre-flight
(`llama-3.3-70b-versatile`, unchanged).

### D3 — Build + execute the gated paid A/B within H12 (T7 pattern)

H12 builds the router + the A/B wrapper and runs the real paid A/B with explicit
user OK; `docs/cost_analysis.md` ships with that run's results.

### D4 — Architecture: env-override in the router (Approach 1)

`complete()` resolves an optional `REGULAITOR_ROUTER_MODE` env override →
`(provider, model_id)` via `_MODE_MAP` → per-provider dispatch
(`_call_anthropic` bespoke; `_call_openai`/`_call_groq` share
`_call_openai_compatible`, each with its own SDK-specific tenacity retry); pure
Anthropic↔OpenAI `_translate` helpers convert the Analyst's Anthropic-shaped
tools/messages (incl. the H8-retry `tool_use`/`tool_result` blocks). Controlled
one-hop fallback to GPT-4o-mini **only on transport/availability errors** (the
12 SDK transient types) — deterministic app errors propagate loudly. Rejected:
threading `model_choice` through `graph.run()` (breaks backend-read-only); a
unified SDK like litellm (adds a dependency, undercuts the Módulo-1 hand-built
router).

> **Two-stage review caught two milestone-consequential defects** (recorded
> per CLAUDE.md §22.1 — see §H12): **T7 I-1** — the originally-broad
> `except Exception` fallback would have silently re-routed deterministic
> errors to GPT-4o-mini and *corrupted the A/B measurement*; narrowed to a
> transport-only exception set. **T8 Concern #5** — the A/B wrapper's unit
> tests executed a real destructive `git checkout HEAD -- evals/reports/latest.md`
> on the working tree (proven to discard uncommitted work); the report-isolation
> was made injectable so tests cannot mutate the repo.

## Consequences

**Positive:**
- Real multi-provider router (3 providers, 5 modes, controlled fallback) — the
  Módulo-1 academic artifact, hand-built, fully unit-tested ($0, SDKs mocked).
- Backend H1–H5 untouched; prod default path regression-zero (env unset →
  Sonnet, behaviour byte-identical; 42 agents/orchestration tests green).
- `docs/cost_analysis.md` delivers an honest 3-way quality comparison + a
  reproducible list-price cost model from verified `config.PRICING`.
- Genuine finding: quality is uniformly low across Sonnet/GPT-4o/Llama
  (verdict_match 0.17–0.28, severity 0.04–0.23) → the ceiling is **system-level
  (retriever + Auditor calibration), not model choice** → directly reinforces
  the H15 plan (model swaps don't rescue auditing).

**Negative / accepted (documented honestly, not re-run — §22.22, H11 precedent):**
- **Cost is not per-run-measured.** The reused read-only harness reports a
  hardcoded Sonnet heuristic (identical 2.51 € across all arms); nothing
  aggregates the real `CompletionResult.cost_eur`. cost_analysis.md uses an
  analytical list-price model instead. Per-call measured-cost capture is a
  follow-up → H15. (Spec §3 intent partially unmet by the implemented pipeline;
  the T8 reviews did not catch this — they focused on env-handling + the
  destructive-test defect.)
- **Llama-Groq arm contaminated** (~19/40 errored): Groq free tier caps at
  100k tokens/day; sequential arms exhausted the ~$5 OpenAI credit so the
  GPT-4o-mini fallback also failed. This empirically demonstrates the T7
  review's I-2 risk (a free-tier/credit-exhausted provider makes the controlled
  fallback both rescue the run and contaminate the arm).
- LangFuse trace records only the successful call's cost on a fallback hop
  (failed-primary cost untracked — I-2, deferred to H15).

## Alternatives considered

- **Thread `model_choice` through `graph.run()`** — rejected (breaks the
  H1–H5/graph/api read-only boundary).
- **Unified SDK (litellm/langchain router)** — rejected (heavy dependency +
  supply-chain surface; undercuts the Módulo-1 hand-built-router deliverable).
- **Broad `except Exception` fallback** — rejected at review (T7 I-1: masks
  deterministic bugs, corrupts the A/B).
- **Re-run the contaminated A/B with paid Groq tier + topped-up OpenAI** —
  rejected by the project owner (cost-conscious; the contaminated run + the
  cost-gap are themselves honest, valuable findings — H11 precedent).

## References

- Spec: `docs/superpowers/specs/2026-05-16-h12-router-cost-design.md`
- Plan: `docs/superpowers/plans/2026-05-16-h12-router-multi-llm.md`
- Decisions log `§H12` (4 decisions + all amendments + the compromised-A/B
  honest record + deferred follow-ups); `§H10` (frozen baseline + H15 plan).
- `docs/cost_analysis.md`; arm reports `evals/reports/latest.evaluation.md`,
  `latest.cost.md` (tracked as evidence).
