# H12 — Router multi-LLM + cost analysis · Design Spec

**Date:** 2026-05-16 (brainstorming closed). **Milestone:** H12 (advanced track; H11 closed `v0.1.1-h11`).

**Goal:** Extend `models/router.py` + `models/config.py` to 3 real providers with mode-based routing and controlled fallback, add an eval-only model override, run a user-gated paid A/B over the gold set, and produce `docs/cost_analysis.md` with **measured** cost-vs-quality numbers — without touching the H1–H5 backend.

---

## 1. Context (current state)

- `models/router.py` is a thin, **already H12-ready** single entry `complete(...) -> CompletionResult` (provider-agnostic: `text`, `tool_use_input`, `usage`, `model_id`, `latency_ms`, `cost_eur`). Today `ModelChoice = Literal["default","quality"]` → both call `_call_anthropic_sonnet` (Sonnet 4.6); `cost`/`evaluation`/`fallback` raise `NotImplementedError` (the docstring already anticipates the H12 mapping). Retry via tenacity on Anthropic transient errors.
- `models/config.py`: `PRICING` dict keyed by model_id (only Sonnet 4.6: $3/$15 per M), `cost_eur()` helper, `USD_TO_EUR=0.93`.
- Only the **Analyst** calls the router (Auditor is mechanical/validator-based). The Analyst calls `complete(model_choice="default")` with a hardwired choice and consumes `tool_use_input` for its structured `Answer`.
- `evals/harness.py` hardwires `_PRODUCTION_MODEL="claude-sonnet-4-6"` and **estimates** cost heuristically (`estimate_cost_eur`, 3000/800 tok) — not measured per-call. Judge = Haiku 4.5 (cached judge layer).
- `docs/cost_analysis.md` does not exist. A **frozen Sonnet baseline** (quality metrics + cost) exists from H10/H11 (`evals/reports/latest.md`, decisions §H10).
- Boundary contract (carried from H6+): H1–H5 backend (agents, prompts, schemas, graph), API, Streamlit are **read-only**; `router.py`/`config.py` are explicitly in H12 scope.

## 2. Decisions (brainstorming, user-approved 2026-05-16)

- **D1 — A/B scope:** Reuse the frozen Sonnet baseline (no re-run). Run only **GPT-4o** and **Llama-Groq** over the **same 40-case gold set** (30 chat + 10 doc) → 3-way table. Comparable because the judge (Haiku) and gold set are identical. Est. cost ~$3–5.
- **D2 — Lineup (4 modes):** `default`/`quality` = Claude Sonnet 4.6 (frozen baseline) · `cost` = Llama-3.x-70B via Groq · `evaluation` = GPT-4o · `fallback` = GPT-4o-mini. **Disambiguation:** the `evaluation` *router mode* is a production-path Analyst model used as an A/B arm — it is **not** the LLM-as-judge. The judge stays Haiku 4.5 (CLAUDE.md §19: judge ≠ production model; unchanged from H8 for cross-arm comparability). Requires `OPENAI_API_KEY` + `GROQ_API_KEY` in the single `.env` (user adds them; never committed; never `.env.example`). Exact Groq 70B model id verified against Groq's live catalog at implementation time (3.1-70B may be renamed to 3.3-70B).
- **D3 — Done + spend gating:** Build router + measured-cost infra + A/B harness, **and execute the real paid A/B within H12 with explicit user OK before the run** (the H11 T7 pattern). `cost_analysis.md` closes with MEASURED numbers; H12 does not close until the real 3-way table exists.
- **D4 — Architecture:** Approach 1 — env-override read by the router + per-provider dispatch + real-cost capture (alternatives rejected: threading `model_choice` through `graph.run()` violates backend-read-only; a unified SDK like litellm adds a heavy dependency and undercuts the Module-1 hand-built-router deliverable).

## 3. Architecture & components

**`models/config.py`** — add model-id constants (`OPENAI_GPT_4O`, `OPENAI_GPT_4O_MINI`, `GROQ_LLAMA_70B`); extend `PRICING` with their real published USD prices; add `PRICING_SNAPSHOT_DATE` constant (reproducibility); keep `USD_TO_EUR` pinned. `cost_eur()` unchanged (keyed by model_id).

**`models/router.py`**
- `ModelChoice = Literal["default","quality","cost","evaluation","fallback"]`.
- A `_MODE_MAP: dict[ModelChoice, tuple[provider, model_id]]`.
- `complete()`: read optional env `REGULAITOR_ROUTER_MODE`; if set to a valid mode, it **overrides** the caller's `model_choice` (invalid value → ignored with WARNING — never break prod on a bad env). Resolve `(provider, model_id)`; dispatch to the provider call function. On the active provider's **terminal** failure (post-retry), fall back **exactly once** to the `fallback` model (GPT-4o-mini), log `fallback_used=true`; never loop. Unset env + `model_choice="default"` ⇒ behavior byte-identical to today (Sonnet) — regression-zero.
- `_call_anthropic` (refactor of current `_call_anthropic_sonnet`, now takes `model_id`), `_call_openai`, `_call_groq`: each does timing, usage extraction, `cost_eur` via config, structured log, and its own tenacity retry on that SDK's transient exception types; each returns the existing `CompletionResult`. Clients constructed via per-provider helpers that **fail-fast** if the key env var is missing (same pattern as `_anthropic_client` today).
- **Cross-provider tool-calling translation:** the Analyst relies on Anthropic `tools`/`tool_choice` → `tool_use` → `CompletionResult.tool_use_input`. `_call_openai`/`_call_groq` translate the same abstraction to/from the OpenAI-style `tools`/`tool_choice`/`tool_calls` schema and populate `tool_use_input` identically. This is the main implementation complexity.

**`scripts/ab_eval.py`** (new, thin) — reuses `evals/harness.py` + the cached Haiku judge. Runs the 40-case gold set with `REGULAITOR_ROUTER_MODE=evaluation`, then `=cost`; captures **measured** per-call `cost_eur` from `CompletionResult` (not the heuristic). Sonnet arm = reuse frozen H10/H11 baseline numbers (no re-run). Emits the aggregated per-model metrics+cost+latency.

**`docs/cost_analysis.md`** (new) — 3-way table (Sonnet [reused frozen] / GPT-4o / Llama-Groq) over 40 cases: quality metrics (faithfulness, citation precision/recall, answer_relevancy, context_precision, verdict_match, severity_match), measured €/chat-query, €/10-page-doc, latency p50/p95; + methodology, `PRICING_SNAPSHOT_DATE`, judge=Haiku note, and honest caveats (Llama structured-output quality; the known H15 calibration gaps apply to all arms; Sonnet column is the frozen baseline reused, not re-measured this run).

## 4. Data flow

- **Prod (unchanged):** Analyst → `complete(model_choice="default")`, env unset → Sonnet 4.6 → `CompletionResult`.
- **A/B arm:** harness sets `REGULAITOR_ROUTER_MODE=evaluation|cost` → router override → provider call → real `cost_eur`/`usage` in `CompletionResult` → harness aggregates → `cost_analysis.md`.
- **Fallback:** active provider terminal-fails post-retry → one retry on GPT-4o-mini → `fallback_used` logged → `CompletionResult` from fallback.

## 5. Error handling

- Missing `OPENAI_API_KEY`/`GROQ_API_KEY` → `RuntimeError` at client construction with a clear, actionable message (mirrors current Anthropic behavior). Only raised when that provider is actually invoked (prod default path never constructs OpenAI/Groq clients).
- Per-provider tenacity retry (3 attempts, exp backoff) on that SDK's transient/rate-limit/timeout exception types.
- Invalid/unknown `REGULAITOR_ROUTER_MODE` → ignored, WARNING logged, caller's `model_choice` used (prod safety).
- Controlled fallback is bounded to one hop; if the fallback model also fails, the original exception propagates (no infinite loop).
- Observability (H11): the LangFuse trace already records cost/latency; `model_id` emission verified against the redaction allowlist (model ids are non-sensitive categorical metadata; add to the allowlist if not already covered — router/observability scope only, no agent change).

## 6. Testing

- **Unit (mocked SDKs, $0):** `_MODE_MAP` resolution for all 5 modes; env-override precedence (set/unset/invalid); each provider's `CompletionResult` extraction incl. tool-calling translation (Anthropic↔OpenAI/Groq schema); fallback-exactly-once on terminal failure; `cost_eur` for each new model id; missing-key fail-fast.
- **Regression-zero:** env unset + `model_choice="default"` ⇒ `complete()` behavior/shape identical to pre-H12 (prod = Sonnet); existing router/Analyst/graph tests stay green untouched.
- **Integration evidence:** the user-gated paid A/B run (explicit OK before spend) → `cost_analysis.md` measured table.
- CI: 5 jobs stay green; coverage gate ≥90% on `models/`.

## 7. Gate / definition of done (operative plan §16.3, §21.7, §24 Módulo 1)

1. Router serves all 5 modes with real provider calls + controlled fallback.
2. env-override + regression-zero proven by unit tests.
3. CI green; coverage ≥90% on changed subsystems.
4. **Gated paid A/B executed (user OK) → `docs/cost_analysis.md` with measured 3-way table, N=40 per arm (≥30 satisfied).**
5. ADR 0013 + decisions log §H12 + evidence_matrix + CLAUDE.md §27 + memory updated.
6. Tag `v0.1.2-h12`.

If a measured metric underperforms (e.g., Llama weak structured output), it is reported honestly as a cost-vs-quality finding (per §22.22 + the H11 precedent of accept+document over re-run-for-prettier-numbers), not hidden.

## 8. Non-goals (YAGNI)

No latency optimization (streaming/`max_tokens`/parallel retriever — remains a deferred H15 follow-up); no LoRA; no judge change (Haiku stays for comparability); no providers beyond the 3; no agent/graph/API/Streamlit changes; no new MCP.

## 9. Risks

- **Cross-provider tool-calling parity (highest):** Analyst structured output must survive on OpenAI/Groq schemas; Llama-70B may produce weaker structured output — a valid, documented finding, not a defect to mask.
- **Groq model-id drift:** exact 70B id verified against Groq's live catalog at implementation time.
- **Budget:** ~$5 Anthropic credit vs A/B ~$3–5 (GPT-4o is the cost driver; Groq is cheap/fast). The Sonnet-reuse decision minimizes spend. H15 will need a separate recharge regardless — flag to the user before the A/B spend.
- **Provider rate limits differ:** OpenAI variable, Groq fast; the harness already tolerates slow runs (H8/H11 machinery).

## 10. Boundary contract H12 inherits

Backend H1–H5 / graph / API / Streamlit read-only (router.py + config.py + new eval script + docs only). `.env.example` PROHIBITED — single `.env`; user adds OpenAI/Groq keys (gated, like LangFuse H11). Decisions log = TFM backbone (every approved decision incl. "ok"/option picks → §H12). Measured numbers in reports/log are authoritative over Makefile/plan estimate comments. gitleaks not local on Windows → CI-enforced; local commits `SKIP=gitleaks` (never `--no-verify`). subagent-driven-development with 2-stage review per task.

## 11. References

- CLAUDE.md §10.4 (router modes), §16.3 H12, §21.7 (`cost_analysis.md`), §24 Módulo 1.
- Decisions log §H4 (thin-router-one-backend decision being extended), §H10 (frozen baseline), §H11 (env-gating idiom precedent; gated-paid-run T7 pattern).
- `evals/reports/latest.md` (frozen Sonnet baseline reused as the A/B Sonnet arm).
