# v0.1.20 SKIP/PROCEED gate decision

**Date:** 2026-05-23
**Branch:** `feat/v0.1.20-paid-validation` @ `9babf8d`
**Spec:** §3 D3 step 3 (https://...specs/2026-05-23-v0.1.20-paid-validation-design.md)
**Predecessors:** T1 PROBE-A (commit `d3e40ca`), T2 PROBE-B (commit `9babf8d`)

## Probe measurements (from T1 + T2)

| metric | ARM A (v1.0) | ARM B (v1.4) | combined |
|---|---|---|---|
| n_cases | 5 | 5 | 10 |
| cost_sum_eur | 0.3082 | 0.2950 | 0.6032 |
| cost_mean_per_case_eur | 0.0616 | 0.0590 | **0.1206 (A+B per case)** |
| cost_max_per_case_eur | 0.0901 | 0.0717 | — |
| latency_max_s (wall-clock) | 433.4 | 416.0 | — |
| crashes | 0 | 0 | 0 |
| cost-drift (v1.4 vs v1.0 2× threshold) | n/a | PASS (0.0717 ≤ 0.1233) | — |

## Extrapolation

Per spec §3 D3 step 3: `total_high = (probe_A_mean + probe_B_mean) × 64 × 1.5`

```
total_expected = 0.1206 EUR × 64 cases = 7.72 EUR
total_high     = 7.72 EUR × 1.5         = 11.58 EUR
```

## Budget

- **User budget recharged 2026-05-23: $24.95 USD**
- USD→EUR conversion at ~$1.08/€: $24.95 ≈ **€23.10** (working approximation per plan T3 note)
- Equivalent in USD: total_high €11.58 ≈ **$12.50 USD**

## Decision

**PROCEED** ✅

| comparison | value |
|---|---|
| total_high (EUR) | 11.58 |
| total_high (USD ~) | 12.50 |
| budget (USD) | 24.95 |
| budget (EUR ~) | 23.10 |
| headroom (USD) | $12.45 (~50%) |
| headroom (EUR) | €11.52 (~50%) |
| gate | total_high ≤ budget — **PASS** |

## Rationale

- Per-case cost on Sonnet 4.6 + Haiku judge in v0.1.20 epoch is ~€0.060 / case for either arm, marginally below the H10 historical anchor of ~€0.077.
- v1.4 cost is slightly lower than v1.0 (~4% lower), within sample noise on n=5; not a basis for any flip-decision input but does suggest v1.4 doesn't materially increase per-case cost.
- 50% budget headroom is comfortable; even if main-run per-case cost drifts 50% above probe-mean (unlikely), the run still fits in budget.
- Per-case wall-clock ~7 min unchanged from H10 / H11 / H15 era — main-run T4+T5 will take ~14h total wall-clock split across both arms.

## Carry-forward notes

- The 3/5 v1.0 vs v1.4 divergence in probe outputs (chat-005 verdict flip is the headline) is a directional signal that v1.4's Hard Rule 9 force-Finding-emission may reduce false-RHR. **NOT input to the flip decision at probe size** — the per-metric narrative in T9 closure uses the H10 30-case subset from the main runs.
- Wall-clock budget: user authorized full path in prior checkpoint. T4+T5 to be run in this session OR scheduled across multiple sessions (each arm independent + per-case checkpointed; can resume on crash per v0.1.8 discipline).

## Next: T4 (main ARM A, 59 cases, v1.0)
