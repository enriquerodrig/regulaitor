# RegulAItor — Cost vs Quality Analysis (H12)

**Date:** 2026-05-17 · **Pricing snapshot:** 2026-05-16 (`config.PRICING_SNAPSHOT_DATE`) · **USD→EUR:** 0.93
**Gold set:** 30 chat + 10 doc (40 cases) · **Judge:** Claude Haiku 4.5 (unchanged from H8 — cross-arm comparable, CLAUDE.md §19 judge≠production)
**Router:** H12 multi-LLM (`models/router.py`), arms selected via `REGULAITOR_ROUTER_MODE` env override (Analyst untouched).

> ⚠️ **Read this before citing any number.** This A/B was run once (gated, ~$5 spent) and came out **partially compromised**. It is reported here transparently, not re-run for prettier numbers (CLAUDE.md §22.22; H11 redteam-contamination precedent). Two material limitations — read §Caveats:
> 1. **Cost is NOT per-run-measured.** The reused H8 harness hard-codes the production model + a fixed token estimate for its own report; nothing in the implemented pipeline aggregates the real per-call `CompletionResult.cost_eur`. The cost table below is therefore an **analytical list-price estimate at a fixed representative token profile**, NOT measured per-run spend. Per-call measured-cost capture is a documented follow-up (→ H15).
> 2. **The Llama-Groq arm is contaminated.** Groq's free tier caps at 100k tokens/day; it was exhausted ~halfway → 19/40 cases hit a 429, triggered the controlled fallback, and the GPT-4o-mini fallback *also* failed (the GPT-4o arm ran first and exhausted the ~$5 OpenAI credit). Those 19 Llama cases errored. The Llama column is a degraded/partial measurement.

## Method

- **Sonnet 4.6** column = the **frozen H10/H11 baseline** (`evals/reports/latest.md`, decisions log §H10) — reused, **not re-run** this milestone.
- **GPT-4o** and **Llama-3.3-70b (Groq)** = run this milestone via `scripts/ab_eval.py` (`evals/reports/latest.evaluation.md`, `latest.cost.md`; commit `b293f62`), same gold set, same Haiku judge → quality metrics are real per-model (Ragas + judge on each model's actual Analyst output).
- **Cost** = analytical: `config.cost_eur(model, in, out)` (verified `config.PRICING`, snapshot 2026-05-16) at a fixed representative token profile **chat = 3000 in / 800 out**, **doc(10p) = 30000 in / 8000 out** (the H8 harness's profile). This normalizes the workload and varies only model price — a legitimate list-price comparison, explicitly **not** per-run-measured token counts.

## Quality (real, per-model; uncalibrated system)

| Metric | Sonnet 4.6 (frozen H10) | GPT-4o (clean) | Llama-3.3-70b Groq (⚠️ 19/40 errored) | H15 target |
|---|---|---|---|---|
| faithfulness | 0.54 | 0.73 | 0.67 | ≥0.85 |
| answer_relevancy | 0.53 | 0.76 | 0.71 | ≥0.85 |
| context_precision | 0.48 | 0.62 | 0.62 | ≥0.80 |
| citation_precision | 0.17 | 0.42 | 0.43 | ≥0.90 |
| citation_recall | 0.44 | 0.50 | 0.53 | ≥0.80 |
| verdict_match_rate | 0.28 | 0.17 | 0.20 | ≥0.85 |
| severity_match_rate | 0.23 | 0.04 | 0.04 | ≥0.80 |

## Cost — analytical list-price (NOT per-run-measured; see ⚠️ above)

| Model | €/chat query | €/doc (10p) | vs Sonnet |
|---|---|---|---|
| Claude Sonnet 4.6 | 0.0195 | 0.1953 | 1.0× (baseline) |
| GPT-4o | 0.0144 | 0.1442 | ~0.74× |
| GPT-4o-mini (fallback model) | 0.0009 | 0.0086 | ~0.05× |
| Llama-3.3-70b (Groq) | 0.0022 | 0.0223 | ~0.11× |

(Fixed profile chat 3000/800, doc 30000/8000 tokens × verified per-model `config.PRICING` × 0.93. GPT-4o-mini shown as it is the controlled-fallback model.)

## Reading

At a fixed workload, the open model via Groq (Llama-3.3-70b) is **~9× cheaper per query than Sonnet** and GPT-4o is **~26% cheaper than Sonnet** — large, real list-price deltas. But the decisive finding is on the quality side: **all three models score similarly low** (verdict_match 0.17–0.28, severity_match 0.04–0.23, citation_precision 0.17–0.43), all far below the H15 targets. GPT-4o/Llama do *not* rescue verdict/severity (they are *worse* on verdict_match than the frozen Sonnet baseline). **The quality ceiling is system-level — retrieval + Auditor calibration — not model choice.** Swapping the Analyst model changes faithfulness/answer_relevancy modestly but cannot fix the auditing/severity gap. This directly reinforces the H15 calibration plan (decisions §H10): the leverage is the retriever + Auditor/Analyst calibration, not a bigger/cheaper LLM. For a cost-conscious deployment, the open Groq model is the rational choice **once H15 calibration lands** — paying Sonnet prices buys no quality advantage in the current uncalibrated state.

## Caveats (honest accounting)

1. **No per-run-measured cost (pipeline gap).** The H8 harness (read-only, reused) computes its report cost from a hardcoded `_PRODUCTION_MODEL=claude-sonnet-4-6` + fixed 3000/800-token heuristic — all three arm reports literally print the identical `Total cost: 2.51 €`. `scripts/ab_eval.py` (Task 8) is a thin wrapper over that harness and nothing aggregates the real `CompletionResult.cost_eur` (the router emits it per call but it is not collected; INFO logs were not even captured to the run output). The spec §3's "measured cost" intent is therefore unmet by the implemented pipeline. The cost table above is the honest, defensible alternative (list-price at a fixed profile, fully reproducible from `config.PRICING`). **Follow-up → H15:** add a per-call cost-aggregation hook (or parse the router structured logs) so a future calibrated re-eval reports true measured spend.
2. **Llama-Groq arm contamination (the I-2 risk, now empirical).** Groq free tier = 100k tokens/day. ~19/40 Llama cases hit a 429 → controlled fallback fired (`fallback_triggered=true primary_mode=cost` ×19) → GPT-4o-mini fallback *also* failed (`fallback_used=true` ×0) because the GPT-4o arm ran first (23:13) and exhausted the ~$5 OpenAI credit before the Llama arm (02:43). Those 19 cases errored. The Llama quality column is over a degraded/partial set. This empirically demonstrates the exact fallback-contamination risk the Task-7 code review flagged (I-2): under a free-tier/credit-exhausted provider, the controlled fallback both rescued the run from crashing *and* contaminated the arm — a real operational finding, not a defect to hide.
3. **All metrics low + latency is a batch artifact.** Consistent with the documented H10/H15 calibration gap (retrieval/Analyst over-citation/Auditor). `latency_p95 ~333–400 s` in the arm reports is the batch-under-rate-limit artifact (CLAUDE.md §17 #7, same as H10), **not** the product SLA — do not cite it as such.
4. **Sonnet column is the frozen H10 baseline reused** (not re-measured this run); its own report cost line was always the same heuristic.

## Operational lessons (for any future clean re-run, e.g. post-H15)

- A 40-case eval needs a **paid Groq tier** (free 100k-TPD is ~half a run) or the `cost` arm self-contaminates via fallback.
- Run arms with **independent/sufficient per-provider budget**, or run the cheaper-fallback arm first; sequential arms sharing one OpenAI credit pool caused the Llama fallback to also fail.
- Capture **real per-call cost** (CompletionResult.cost_eur aggregation) instead of relying on the Sonnet-heuristic harness report.

## References

- Spec: `docs/superpowers/specs/2026-05-16-h12-router-cost-design.md` (§3 measured-cost intent, §9 Llama-output risk).
- Decisions log §H12 (this run + the contamination + the cost-gap follow-up) and §H10 (frozen baseline + H15 calibration plan).
- Arm reports: `evals/reports/latest.evaluation.md` (GPT-4o), `evals/reports/latest.cost.md` (Llama-Groq, contaminated). Frozen baseline: decisions §H10 / `evals/reports/latest.md`.
