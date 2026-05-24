# v0.1.20 PROBE-B summary (ARM B candidate, v1.4)

**Date:** 2026-05-23 (checkpoint `20260523T084207Z-d3e40ca.jsonl`)
**Cases:** chat-001..005 (5 cases — same as PROBE-A by spec §4 design)
**Env:** `REGULAITOR_ANALYST_PROMPT_VERSION=v1.4`
**Branch:** `feat/v0.1.20-paid-validation` @ `d3e40ca`
**Output report:** `evals/reports/v0.1.20/armB-probe.md`

## Aggregate (measured)

- n_cases: **5**
- cost_sum_eur: **€0.2950**
- cost_mean_per_case_eur: **€0.0590** (slightly UNDER v1.0's €0.0616)
- cost_max_per_case_eur: **€0.0717** (chat-005)
- latency_max_s (wall-clock): **416.0** (chat-001)
- per-case latencies (s): 416 / 391 / 390 / 389 / 394
- per-case costs (€): 0.0549 / 0.0522 / 0.0612 / 0.055 / 0.0717

## Abort triggers evaluation (per spec §3 D3 step 2)

- [x] **No case crashed the harness** — all 5 cases completed cleanly. PASS.
- [x] **v1.4 cost-drift ≤ 2× v1.0 mean** — max €0.0717 ≤ €0.1233 threshold. PASS with €0.0516 headroom.
- [x] **No unrecovered 429s** — tenacity backoff handled all transient errors; no aborts. PASS.
- [⚠ §22.22 spec amendment carried from T1] **latency wall-clock 416s** — same harness-mode pattern as PROBE-A (not API degradation per H11 sense). Trigger PASS under spirit.

## v1.4 env routing — LIVE-FIRE CONFIRMED

3 of 5 cases show different outputs between ARM A v1.0 and ARM B v1.4 (citation or verdict diverged):

| case_id | v1.0 verdict | v1.4 verdict | divergence |
|---|---|---|---|
| chat-001 | pass | pass | same |
| chat-002 | pass | pass | **citations changed** (v1.4 cites 6.3+6.4 vs v1.0 6.2+6.3) |
| chat-003 | requires_human_review | requires_human_review | **v1.4 emitted citations (16, 17.1, ...) vs v1.0 empty** — Auditor still RHR |
| chat-004 | pass | pass | same |
| chat-005 | requires_human_review | **pass** | **VERDICT FLIP** — v1.4's Hard Rule 9 force-Finding-emission appears to reduce a false-RHR case |

3/5 divergence on n=5 is too small to draw conclusions but confirms v1.4 is reaching the Analyst (the env seam at `src/regulaitor/agents/analyst.py:63-77` is live).

## Verdict

**PROCEED-TO-T3** ✅ (then SKIP/PROCEED gate decision then T4+T5 main runs)

## Combined extrapolation (for T3 SKIP/PROCEED gate)

- v1.0 mean: €0.0616 / case
- v1.4 mean: €0.0590 / case
- Combined per-case cost (A+B per case): **€0.1206**
- Total expected for 64 cases × 2 arms: **€7.72**
- Total high (×1.5): **€11.58** ≈ **$12.50** at $1.08/€

User budget $24.95 vs $12.50 high → **$12.45 headroom (~50%)** — PROCEED.

## Notes

- v1.4 per-case cost is ~4% LOWER than v1.0 — surprising. Likely just sample variance on n=5; could also reflect v1.4 emitting more structured Findings (more tool_use efficiency) vs v1.0 longer prose responses. To be confirmed at n=64 in the main runs.
- chat-005 verdict flip is an early directional signal but inconclusive at n=5; the H10 30-case subset in the main runs will provide statistically meaningful evidence for the flip decision.
- Wall-clock per case ~7 min unchanged from PROBE-A → ~7h per main arm → ~14h total wall-clock for T4+T5 (matches T1 extrapolation).
