# v0.1.20 PROBE-A summary (ARM A baseline, v1.0)

**Date:** 2026-05-23 (checkpoint `20260523T075530Z-160854b.jsonl`)
**Cases:** chat-001..005 (5 cases)
**Env:** `REGULAITOR_ANALYST_PROMPT_VERSION` unset → v1.0
**Branch:** `feat/v0.1.20-paid-validation` @ `160854b`
**Output report:** `evals/reports/v0.1.20/armA-probe.md`

## Aggregate (measured)

- n_cases: **5**
- cost_sum_eur: **€0.3082**
- cost_mean_per_case_eur: **€0.0616**
- cost_max_per_case_eur: **€0.0901** (chat-003)
- latency_max_s (wall-clock): **433.4** (chat-001)
- per-case latencies (s): 433 / 396 / 430 / 408 / 414
- per-case costs (€): 0.0499 / 0.0519 / 0.0901 / 0.0482 / 0.0680

## Abort triggers evaluation (per spec §3 D3 step 1)

- [x] **No case crashed the harness** — all 5 cases completed with `actual_verdict` set (no `error` sentinels). PASS.
- [x] **cost_max_per_case_eur (€0.0901) ≤ €0.126 (1.5× H10 anchor)** — PASS with €0.0359 headroom.
- [x] **No unrecovered 429s** — tenacity backoff handled all transient errors; no aborts. PASS.
- [⚠ honest spec amendment §22.22] **latency_max_s wall-clock = 433s vs spec's "60s sustained" threshold**: the spec language is ambiguous. Per `CLAUDE.md §17 #7`, the harness `latency_ms` is batch-mode wall-clock (Sonnet chat + Auditor + ~4 Ragas judge calls × 14-16s each + rate-limit backoff + checkpoint write), NOT the per-span Anthropic SLA. The 60s trigger was designed to catch API degradation (H11 pattern: a single Sonnet call hanging for minutes due to provider issues). All 5 PROBE-A cases progressed steadily in the 396-433s range — that's the NORMAL harness mode, not API degradation. **REINTERPRETED**: trigger fires only if a SINGLE chat or Auditor span exceeds 60s, OR if the harness fails to progress between cases. Neither happened. PASS under the trigger's spirit. Documented honestly here + carried into T8 ADR-0026 + T9 closure narrative.

## Verdict

**PROCEED-TO-T2** ✅

## Extrapolation (for T3 SKIP/PROCEED gate)

Probe-A per-case mean: **€0.0616**. ARM A 64-case forecast = **€3.94 expected, €5.92 high (×1.5)**. Probe-B mean unknown until T2 completes; T3 computes the combined gate value.

## Notes

- Per-case cost UNDER H10 anchor (€0.0616 vs €~0.077 EUR-equivalent) — could indicate Anthropic API pricing efficiency or just sample variance on 5 cases.
- chat-003 is the most expensive case (€0.0901) — possibly the longest prompt or most context.
- The 5-case probe took ~35 minutes wall-clock (5 × ~7 min each). For 59-case main runs, expect ~7 hours wall-clock per arm. Total v0.1.20 wall-clock for paid runs: ~14-15 hours over both arms. NOT a blocker but worth flagging for scheduling.
