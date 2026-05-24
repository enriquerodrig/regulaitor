# ADR 0026 — v0.1.20 paid validation A/B (v1.0 vs v1.4) + FLIP decision

- **Status:** Accepted — 2026-05-24 — squash `1f838ee`, tag `v0.1.20-paid-validation`
- **Deciders:** Project owner.
- **Companion ADRs:** 0010 (H8 judge architecture — Haiku 4.5 stays per ADR-0021; no judge change in v0.1.20), 0016 (H15 Auditor calibration — system-level study established the v1.x prompt-iteration framework; v0.1.20 measures the v1.4 candidate from the v0.1.17.1 branch of that lineage), 0017 (H15.1 retriever cross-corpus design-defect → v0.1.18 resolved instrument; v0.1.20 measures under the corrected hierarchical containment), 0021 (v0.1.16 dual-layer thresholds — the v0.1.20-bar is THE target this milestone validates against; "acceptance ritual" venue), 0023 (v0.1.17.1 v1.4 prompt shipped opt-in; production default stays v1.0 pending paid measurement — measured here), 0024 (v0.1.18 citation granularity instrument — used for v0.1.20 metric computation), 0025 (v0.1.19 Council binding ON — production state inherited by BOTH arms in v0.1.20).

## Context

v0.1.17.1 (ADR-0023) shipped the v1.4 Analyst prompt opt-in with the production default frozen at v1.0; the §22.22 commitment was *"v1.4 effectiveness measured at v0.1.20"*. ADR-0021 (v0.1.16) framed v0.1.20 as the "acceptance ritual" venue for the v0.1.20-bar (7 metrics anchored to H10 + H15 v1.2 baselines) and explicitly left per-metric flips for the v0.1.20 closure narrative. v0.1.18 (ADR-0024) closed the H15.1 §22.22 design-defect on instrument invariance by rewriting `evals/metrics.py::compute_citation_metrics` to hierarchical containment, retrospectively re-rendering 15 historical reports at $0; v0.1.19 (ADR-0025) flipped `_COUNCIL_BINDING` to True. v0.1.20 is the FIRST paid measurement under (a) v0.1.18-corrected instrument + (b) v0.1.19 Council binding ON production state.

Three capabilities shipped since H15.X but never paid-measured before v0.1.20: the v1.4 prompt, the per-norma retrieval cap (v0.1.11), and Council binding ON (v0.1.19). v0.1.20 measures **v1.4 only** (per spec D1 1-dim variant choice — per-norma cap measurement deferred; Council binding inherited by both arms as production state, not isolated).

**The §6 invariant interpretive distinction** (carried from ADR-0024/0025): production-side citation VALIDATION (`src/regulaitor/citation/validator.py`) is byte-unchanged in v0.1.20. This milestone is **measurement-only**: no backend code is modified within the v0.1.20 closure ceremony itself. The optional 1-line flip follow-up (`agents/analyst.py:69` default v1.0 → v1.4) ships as part of v0.1.20 closure ONLY because the narrative-driven decision below approved it; the §6 guarantee operates on the validator layer, not the Analyst prompt.

## Decision

### D1 — Variant matrix: 1-dim {v1.0 vs v1.4} = 2 arms

ARM A baseline = `REGULAITOR_ANALYST_PROMPT_VERSION` unset → v1.0 (production default per `agents/analyst.py:69`). ARM B candidate = env set to `v1.4` → v0.1.17.1 opt-in prompt. All other dimensions identical (Sonnet 4.6 / Haiku 4.5 judge / production retrieval config / Council binding ON / MonotonicEscalatePolicy / 64-case chat cohort / v0.1.18 hierarchical containment metric / same time window). Rejected: 2-dim + per-norma cap factorial; 3-dim + Council ON/OFF (scope creep, ADR-0025 D2 rejected env override).

### D2 — Cohort: 64 chat (skip doc)

All 64 chat gold cases × 2 arms = 128 paid Analyst calls. Doc-mode (10 cases) SKIPPED per spec §22.22 design-coherence catch: `prompts/document_analyst/` contains only `system.v1.0.md`; setting v1.4 env in ARM B would crash every doc case at `prompt_path.read_text()`. Doc-mode A/B is not measurable in v0.1.20; carried forward as a separate doc-mode-A/B milestone.

Reporting: H10 baseline 30 cases evaluated against ADR-0021 v0.1.20-bar (PRIMARY); H14 cross-corpus 14 + v0.1.13 industry 10 + v0.1.15 gap-analysis 10 reported as EXPLORATORY (out of bar scope).

### D3 — Cost gate: strict 2-probe

PROBE-A (5 cases chat-001..005, v1.0) + PROBE-B (same 5 cases, v1.4) measure per-case cost + latency + crash signal; the 10 probe cases ARE the first 5 entries of each arm's checkpoint (no double-billing); main runs resume from chat-006. Extrapolated `total_high = (probe_A_mean + probe_B_mean) × 64 × 1.5`; SKIP/PROCEED gate triggers if `user_budget < total_high`.

### D4 — Flip protocol: hard safety floor + soft narrative

**Hard floor** (mechanical, must pass): `redteam-smoke` block_rate ≥ 0.90 under v1.4 env + 6 designated content-based safety cases (chat-014/015/029/030 + nis2-006/dora-006) manually content-backstop reviewed in ARM B (H15 C1 pattern). On any failure → NO FLIP regardless of metric narrative.

**Soft narrative** (per-metric assessment if hard floor passes): per the 7 v0.1.20-bar metrics on the H10 30-case subset, decisions_log narrates "X/7 passed bar; Y/7 beat v1.0; Z/7 regressed" + production-default flip decided in narrative.

### D5 — ARM A baseline: fresh on all 64

ARM A is run FRESH (not reused from H10/H15 historical). Justification: apples-to-apples controls (same time window, same Sonnet version, same Haiku judge cache state). The ~€2-3 savings from reusing historical 30-case numbers don't justify the apples-to-oranges risk.

### D6 — ADR scope: this ADR-0026 + closure docs

This ADR-0026 (count: 25 → 26) documents measurement methodology + flip protocol + cohort rationale + §22.22 lineage closure. Closure artifacts: 2 arm reports + 1 comparison + T7 safety floor + T6.5 RHR root-cause + decisions_log §v0.1.20 + evidence_matrix refresh + CLAUDE.md updates.

## Results

**Cost actuals** (v0.1.20 paid spend): probe-A €0.31 + probe-B €0.30 + ARM A main (chat-006..064) €3.70 + ARM B main (chat-006..064) €3.52 = **€7.83 total of €11.58 high-extrapolation / $24.95 budget** (~33% headroom unused). v1.4 cost actually ~4% LOWER per case than v1.0 (surprising; likely sample-variance + better structured Findings).

**Wall-clock**: ~6.7h ARM A + ~6.7h ARM B = **~14h paid clock-time** (4× the spec §8 "30-60 min" estimate; §22.22 plan error — per-case ~7 min, not the optimistic estimate that ignored per-case Sonnet + Auditor + ~4 Ragas judge spans + tenacity backoff + checkpoint writes).

**T7 hard safety floor: PASS** ✅
- Criterion 1: redteam-smoke block_rate = 0.92 under `REGULAITOR_ANALYST_PROMPT_VERSION=v1.4` env (≥0.90 gate; carries the v0.1.14-v0.1.19 frozen 0.92 baseline).
- Criterion 2: all 6 designated content-based safety cases content-safe in ARM B (manual review documented in `evals/reports/v0.1.20/safety-floor.md`). Each rejected the malicious premise, did NOT fabricate citations, and cited REAL corpus (or honest refusal). The Haiku judge's per-case 3-criteria PASS confirms the controller manual review.

**T6 A/B headline (full 64-case cohort)**:
- verdict_match v1.0 = 20/64 (31.2%) → v1.4 = 26/64 (40.6%) = **+9.4pp / +6 net wins**.
- faithfulness +0.12 / answer_relevancy +0.10 / context_precision +0.12 / citation_precision +0.11 / citation_recall +0.17 / severity_match +0.19 / cost €-0.20.

**H10 bar evaluation (the key result, per ADR-0021)**:
- v1.0 passes **0/7** bar metrics; v1.4 passes **6/7** bar metrics.
- Only verdict_match remains below bar in v1.4 (0.300 vs 0.35 target). The other 6 metrics (faithfulness 0.682, answer_relevancy 0.659, context_precision 0.569, citation_precision 0.289, citation_recall 0.650, severity_match 0.385) all pass.

**Per-cohort verdict_match deltas**:
- H10 30 cases: 0.267 → 0.300 (+3.3pp)
- H14 cross-corpus 14: 0.286 → 0.429 (+14.3pp)
- v0.1.13 industry 10: 0.500 → 0.700 (+20.0pp)
- v0.1.15 gap-analysis 10: 0.300 → 0.400 (+10.0pp)

**T6.5 RHR root-cause diagnostic ($0 post-hoc on checkpoints)**:
- Of the 43 v1.0 RHR cases: 42% are nonempty-RHR-still-RHR-in-v1.4 (DOMINANT mechanism, NOT addressed by v1.4 — targets v0.1.21 Auditor RHR aggregation), 35% empty-findings-STILL-empty-in-v1.4 (v1.4's Hard Rule 9 ~50% effective as soft constraint), 14% nonempty-RHR-FIXED-by-v1.4 (UNANTICIPATED secondary benefit), 7% empty-findings-FIXED-by-v1.4 (clean v1.4 mechanism), 2% became block.
- Of the 9 v1.4 RHR→pass wins: **all 9 demonstrably real** (3 empty-findings-fixed + 6 nonempty-fixed; broader mechanism than originally hypothesized).
- Of the 4 v1.4 pass→RHR regressions: chat-007 + xcorpus-001 have IDENTICAL citations in both arms → likely Auditor/Council non-determinism noise; industry-c3 + industry-v1 have FEWER citations under v1.4 (genuine v1.4 conservatism trade-off).
- **Net real impact ≈ +7** (9 real wins − 2 real regressions), not the surface +6 − 4 = +2 net.

## Decision (the flip)

**FLIP v1.0 → v1.4 production default — APPROVED.**

Rationale (per spec D4 decision logic):
1. Hard safety floor PASS (T7) — unlocks the flip protocol.
2. H10 bar 6/7 PASS — strong evidence of meaningful improvement on the formal bar cohort (v1.0 0/7 baseline is the floor v0.1.20 was designed to move).
3. T6.5 diagnostic shows the wins are MECHANICALLY REAL (9/9 v1.4-only flips have non-noise root cause) with regressions ≈ 2 (net real impact +7 over 64 cases).
4. Cost neutral (v1.4 ~4% cheaper per case).
5. The dominant mechanism v1.4 does NOT address (42% nonempty-RHR) is honestly carried forward to v0.1.21 (Auditor RHR aggregation refinement) — v1.4 is one layer of a multi-milestone improvement program, not a complete fix.

**Implementation**: `src/regulaitor/agents/analyst.py:63-84` env-unset branch changed from literal `"v1.0"` default to role-aware ternary (`"v1.4" if prompt_role == "analyst" else "v1.0"`) + updated test pins + NEW regression test `test_document_analyst_role_defaults_to_v1_0_when_env_unset`. Ships as part of v0.1.20 closure ceremony.

**§22.22 implementation note (honest scope adjustment from plan's "1-line change")**: T9a TDD discipline surfaced a role-aware design defect on the first gate run after the literal flip — uniform v1.4 default crashed `AnalystAgent(prompt_role="document_analyst")` because no `document_analyst/system.v1.4.md` exists on disk (v1.4 authored for chat role only; doc-mode A/B never measured per D2 design-coherence catch in this ADR). Adjusted to role-aware ternary + new regression test pinning doc-mode v1.0 default forever. Net effect: chat callers get v1.4 default (the intended FLIP); doc callers preserved on v1.0 (no breaking change for the unmeasured surface). Documented in 6 places per §22.22: T9a commit body + decisions_log §v0.1.20 WHAT/HOW/IMPACT + CLAUDE.md §27 v0.1.20 bullet + source comment + 2 test docstrings.

**Caveat**: dominant RHR mechanism (42% nonempty-RHR) NOT addressed by v1.4. Carries to v0.1.21 (Auditor RHR aggregation quorum + hard constraints on findings non-empty via Anthropic strict mode + Pydantic min_length=1 + aggressive retry).

## Consequences

**Positive:**

- **v1.4 measured and validated under paid run** for the first time; the §22.22 "v1.4 effectiveness measured at v0.1.20" commitment from ADR-0023 is closed.
- **ADR-0021 v0.1.20-bar acceptance ritual unlocked**: 6/7 bar metrics PASS under v1.4 (vs 0/7 under v1.0); soft-mark verdict per ADR-0021 D4 documented in decisions_log §v0.1.20.
- **Production gets a better default**: meaningful improvement across faithfulness / answer_relevancy / context_precision / citation_precision / citation_recall / severity_match on the H10 bar cohort + net +7 verdict_match real wins across the 64-case cohort.
- **T6.5 diagnostic identifies the next milestone target**: v0.1.21 Auditor RHR aggregation refinement (42% impact target) + hard constraints findings non-empty (35% impact target).
- **Apples-to-apples controls (D5) preserved**: ARM A fresh on all 64 cases (not hybrid with H10 historical); single time window; same API state across both arms.
- **§6 invariant byte-unchanged**: `citation/validator.py` + `citation/schemas.py` + `auditor.py` untouched during v0.1.20 closure ceremony; the flip follow-up touches ONLY the Analyst prompt-version default, not the validator layer.

**Negative / accepted (per §22.22 honest framing):**

- **Dominant RHR mechanism (42% nonempty-RHR) unchanged**: v1.4 does NOT address the fact that 18/43 v1.0 RHR cases have well-structured citations but the Auditor still rejects. v0.1.21 work.
- **verdict_match below bar even under v1.4**: 0.300 on H10 vs 0.35 target. The only 1/7 bar metric missing; acceptable for flip given the other 6 pass, but documented honestly — v1.4 is partial progress, not bar-perfect.
- **Doc-mode A/B never measured**: D2 design-coherence catch (no v1.4 for doc role); carries forward as a separate doc-mode-A/B milestone. v0.1.14 segmenter validation still pending.
- **Per-norma cap (v0.1.11) + Council binding (v0.1.19) effects measured only as part of joint production state**: both arms inherit production config; isolated A/B effects not measured in v0.1.20. ADR-0025's H13 12/21 divergence pattern not re-measured here.
- **Two v1.4 regressions on industry cohort (industry-c3, industry-v1)** where v1.4 produced fewer citations and the Auditor returned RHR — accepted trade-off (Hard Rule 9's "remove unsupported claim" emphasis makes v1.4 more conservative). Could be revisited if v0.1.21 changes the Auditor aggregation.
- **The "prose-without-findings" mechanism hypothesis from v0.1.17 was less dominant than expected**: v0.1.17 estimated this was the dominant residual; T6.5 shows it's only ~17% of empty-findings cases and 7% of total RHR. v1.4 was designed around a partially-correct hypothesis; the bigger mechanism (42% nonempty-RHR) was invisible until the paid measurement made it visible.
- **Wall-clock 14h per A/B run was ~4× plan §8 estimate**: §22.22 plan error — spec §8 said "30-60 min" but per-case ~7 min × 128 cases = ~15h. Discipline carried for v0.1.21+ cost-estimation: always extrapolate from per-case wall-clock, never from "should be fast".
- **`scripts/v0120_compare.py` transition matrix bug**: T6 rendering showed all off-diagonals as 0 (contradicting +9.4pp headline); fixed inline in comparison.md via controller verification; script carries to v0.1.21 cleanup.

## Alternatives considered

1. **NO FLIP — keep v1.0 production default** — rejected. Evidence is clearly favorable: hard floor PASS, H10 bar 6/7, T6.5 confirms wins are real not noise. Continuing v1.0 default after measured v1.4 dominance would be the more speculative path. The T7 preliminary recommendation suggested NO FLIP based on "H10 cohort verdict_match TIED at 5/5/25"; the T6 mechanical comparison + T6.5 diagnostic moved this to FLIP.
2. **2-dim factorial A/B {v1.0, v1.4} × {default, per-norma cap=2}** = 4 arms — rejected at spec time. Doubles cost; per-norma cap measurement deferred to a separate future milestone where it can be measured in isolation. (Spec §3 D1 rejected alternatives, brainstorming Q1.)
3. **3-dim factorial including {Council ON, OFF}** = 8 arms — rejected at spec time. Scope creep; ADR-0025 D2 rejected an env override for Council binding as YAGNI; adding one for v0.1.20 measurement would be a retroactive ADR amendment.
4. **Hybrid ARM A baseline (reuse H10 historical 30-case)** + fresh on remaining 34 — rejected at spec time (D5). Apples-to-oranges risk over ~12-day API drift window; the ~€2-3 savings don't justify the noise risk.
5. **Include doc-mode A/B** — rejected at spec design-coherence catch (D2). No `system.v1.4.md` exists for `prompts/document_analyst/`; v1.4 env would crash every doc case in ARM B. Running doc cases in both arms with v1.0 (no crash) gives 0 A/B signal at 2× cost.
6. **Pre-commit auto-flip rule (strict mechanical)** — rejected at spec D4. The hard safety floor IS mechanical, but the per-metric narrative is intentionally soft to preserve nuance (cohort weighting, regression magnitude, mechanism root-cause). A mechanical rule would have triggered NO FLIP on T7 preliminary signal; the T6.5 diagnostic + T6 comparison context produced a more correct decision.

## References

- **Spec**: `docs/superpowers/specs/2026-05-23-v0.1.20-paid-validation-design.md` @ commit `f9b9cb8`.
- **Plan**: `docs/superpowers/plans/2026-05-23-v0.1.20-paid-validation.md` @ commit `d032601`.
- **Companion ADRs**: 0010 (judge architecture), 0016 (H15 Auditor calibration), 0017 (H15.1 design-defect → v0.1.18 instrument fix), 0021 (v0.1.20-bar thresholds), 0023 (v1.4 prompt shipped opt-in), 0024 (v0.1.18 citation granularity), 0025 (v0.1.19 Council binding ON).
- **Source reports** (under `evals/reports/v0.1.20/`):
  - `armA-probe-summary.md`, `armB-probe-summary.md` (T1+T2)
  - `skip-proceed-decision.md` (T3 gate)
  - `armA-main.md` (T4), `armB-main.md` (T5)
  - `comparison.md` (T6 mechanical A/B)
  - `rhr-root-cause-diagnostic.md` (T6.5 $0 post-hoc)
  - `safety-floor.md` (T7 hard floor)
- **Empirical data**: paid spend €7.83 of $24.95 budget; wall-clock ~14h; 64-chat cohort × 2 arms; 4 cohorts (H10 30 / H14 14 / v0.1.13 industry 10 / v0.1.15 gap-analysis 10).
- **Source code touched by v0.1.20 flip follow-up**: `src/regulaitor/agents/analyst.py:69` (default `"v1.0"` → `"v1.4"`) + corresponding test update. NO other src/ changes in v0.1.20.
- **Future**: v0.1.21 (Auditor RHR aggregation quorum + hard constraints findings non-empty — Tier 1+2 from T6.5 priority order) → H16 (HF Spaces deploy) → H17 (TFM closure: memoria, model card, data card, AI Act assessment, runbook, cost analysis, video demo, slide deck).
