# ADR 0025 — Auditor RHR aggregation + Council binding ON (v0.1.19)

- **Status:** Accepted — 2026-05-22 — squash `<squash-sha>`, tag `v0.1.19-council-binding`
- **Deciders:** Project owner.
- **Companion ADRs:** 0006 (H4 chat E2E architecture — Auditor Lenient-Finding + Strict-Answer aggregation that v0.1.19 leaves byte-unchanged), 0014 (H13 Council of Judges — the wired-OFF binding seam this milestone closes; D7 `_COUNCIL_BINDING=False` is the literal flag flipped here), 0016 (H15 Auditor calibration — §16.3 deferral list explicitly carried "Council binding" as post-H15.X work; this is that work), 0021 (v0.1.16 v0.1.20-bar measurement venue — Council binding effect on escalation/false-RHR rate measured in the v0.1.20 paid bundle), 0024 (v0.1.18 citation granularity confound — most recent preceding milestone; established the §6 interpretive distinction this milestone reinforces).

## Context

The H13 Council of Judges (ADR-0014) shipped as an advisory layer: 3-judge panel records evidence per chat turn but NEVER mutates the deterministic Auditor verdict in H13. The H15 promotion seam (per `src/regulaitor/agents/council.py:36` post-flip) is the module constant `_COUNCIL_BINDING: bool = False` (now True) together with `MonotonicEscalatePolicy` (added in H13 T7, fully implemented + tested but wired-OFF). The H15 §16.3 deferral list explicitly carried this as post-H15.X work; v0.1.19 closes it.

**Empirical context (from H13 paid run, 21 chat cases with Council forced)**:

- Council DIVERGED from Auditor on 12/21 cases (57%).
- Of those 12 divergences:
  - 7/12 Auditor=RHR → Council=valid (the panel is MORE leniente than the deterministic Auditor on ambiguous cases — the false-RHR pattern). NOT addressed by v0.1.19's conservative-only binding (per spec Q1 Option A).
  - 1/12 chat-11 Auditor=PASS → Council=RHR (escalation case the Council was designed to detect). Addressed by v0.1.19's binding IF Council was unanimous BLOCK.
  - 4/12 other divergences (BLOCK/RHR mixes). Mostly preserved by conservative-only semantics.

**The §6 invariant interpretive distinction (carried from ADR-0024 D5)**:

Two citation layers in RegulAItor:

- **Production-side citation VALIDATION** (`src/regulaitor/citation/validator.py`, the §6-invariant guardian): "Does the citation exist + literally match the corpus?" → byte-unchanged in v0.1.19.
- **Aggregation/escalation layer** (`auditor.py` Lenient-Finding+Strict-Answer + `council.py` advisory/binding): "Given per-citation validations, what's the turn-level verdict?" → v0.1.19 modifies ONLY the Council binding seam; Auditor aggregation byte-unchanged.

The "no citation, no answer" guarantee operates entirely on the first layer. v0.1.19 only changes what happens when the deterministic Auditor returns PASS AND the Council unanimously disagrees with BLOCK votes — promote to RHR (human review). NEVER relaxes BLOCK or RHR to PASS (that direction would weaken §6).

## Decision

### D1 — Conservative-only Council binding (no Auditor aggregation change)

Flip `_COUNCIL_BINDING: bool = True` in `src/regulaitor/agents/council.py`. Wire `MonotonicEscalatePolicy.would_escalate()` into orchestration via new `bind_verdict()` helper. The escalation rule is conservative-only:

- PASS → RHR when Council votes are 3/3 ok AND all 3 votes are BLOCK (unanimous BLOCK).
- NEVER relaxes BLOCK or RHR. The 7/12 H13 false-RHR pattern (Auditor=RHR → Council=valid) is NOT addressed by v0.1.19. Deferred to v0.1.20+ evidence-driven decision.
- NEVER escalates from a non-unanimous Council (2/3 BLOCK keeps PASS).

§6 invariant ROCK-SOLID: only adds conservatism; monotonic in the safe direction.

### D2 — Hardcode `_COUNCIL_BINDING=True` (production ship)

Flip the module constant; no env override. Production runs with binding ON for all chat traffic. Safe under monotonic-conservative semantics.

### D3 — `bind_verdict()` helper + `"COUNCIL_BIND:"` reason prefix

NEW top-level function in `src/regulaitor/agents/council.py`:

```
bind_verdict(audited: AuditedAnswer, review: CouncilReview, council: CouncilAgent) -> AuditedAnswer | None
```

Returns a new AuditedAnswer with the escalated verdict + a `"COUNCIL_BIND:"`-prefixed reason iff the flag is on AND the policy exposes `would_escalate()` AND the verdict differs.

Signature design: takes `council: CouncilAgent` (NOT the policy directly). Keeps the private-access concern (`council._policy`) INTERNAL to council.py. Orchestration's call site is fully public-API.

### D4 — `CouncilAgent.__init__` default changes to `MonotonicEscalatePolicy`

Single-line change. `MonotonicEscalatePolicy.aggregate()` is IDENTICAL to `AdvisoryMajorityPolicy.aggregate()` (verified by pre-existing test `test_monotonic_aggregate_matches_advisory`). The ONLY behavioral difference: `would_escalate()` becomes available for `bind_verdict()` to consume.

`AdvisoryMajorityPolicy` is NOT deleted — stays available for opt-in testing scenarios.

### D5 — `_council_node` + `_council_notice` wiring

Modify `src/regulaitor/orchestration/graph.py::_council_node` to consume `bind_verdict()` after `council.review()`. When binding fires, the node returns `{"council_review": review, "audited_answer": new_audited}` so downstream state pickup the new RHR verdict.

**Spec amendment (§22.22 honest)**: the spec assumed `_council_notice` lived in `graph.py`; it actually lives in `src/regulaitor/api/schemas.py:308` and is also imported by `src/regulaitor/ui_streamlit/_render.py:16`. The plan honestly expanded the implementation scope from "2 src/ files" (the spec's claim) to 4 src/ files (the reality). The §6 invariant interpretive distinction remains intact — `citation/validator.py` + `auditor.py` byte-unchanged.

`_council_notice` signature changes from `(cr) -> (cr, audited=None)`. Backward-compat default keeps v0.1.18 single-arg callers working. New branch: when `audited.reason` starts with `"COUNCIL_BIND:"`, emit the binding-fired notice ("promovieron el veredicto a requires_human_review por unanimidad"). Else the legacy advisory notice ("el veredicto no cambia") unchanged.

`to_ask_response()` + `ui_streamlit/_render.py` callers updated to pass `state.audited_answer`.

## Consequences

**Positive:**

- **H13 ADR-0014 Council-binding seam closed**: the wired-OFF flag flipped + helper wired through. The H15 §16.3 deferral lineage on Council binding is resolved.
- **§6 invariant ROCK-SOLID**: monotonic-conservative escalation only. Validator layer byte-unchanged. Auditor aggregation layer byte-unchanged. Only the Council escalation seam (which was already designed-in via H13 ADR-0014 D7) gets activated.
- **chat-11-style escalation cases caught**: Auditor=PASS + Council=3/3 BLOCK now promotes to RHR.
- **TFM defense narrative gains another clean layer separation**: validator (§6) vs Auditor aggregation vs Council escalation. Three distinct concerns; v0.1.19 touches only the third.
- **$0 milestone**: no paid LLM; clean test coverage; production-safe deployment.
- **Reusable `bind_verdict()` helper**: future policies (e.g. bidirectional, severity-weighted) can extend without modifying orchestration.
- **Spec-amendment transparency**: the "4 src/ files vs spec's 2 src/ files" honest disclosure prevents future readers from misunderstanding the actual implementation surface area.

**Negative / accepted (per §22.22):**

- **H13's 7/12 Auditor=RHR → Council=valid pattern UNCHANGED**: the conservative-only direction doesn't address the false-RHR over-fire. Deferred to v0.1.20+ evidence.
- **Empirical effect on escalation rate UNMEASURED in v0.1.19**: $0 milestone; no paid run. v0.1.20 paid bundle measures real production behavior.
- **Pre-v0.1.19 reports stay frozen**: not $0-derivable from cache. Direct comparison with v0.1.20 numbers needs the "binding-on" caveat documented.
- **Council unanimity requirement is strict (3/3)**: a 2/3 BLOCK + 1 valid council does NOT escalate. If empirical data later shows 2/3 BLOCK is sufficient signal, a future milestone could loosen.
- **No partial-binding signal**: the `_council_notice` says "binding fired" or "advisory divergence"; doesn't distinguish "would have escalated but only 2/3 BLOCK so kept PASS". Minor cosmetic gap.
- **Cross-vendor judge dependency**: Council uses 3 different LLM vendors (Haiku/GPT-4o/Llama via router). If one vendor consistently degrades, the unanimity requirement may rarely be met. Acceptable risk under conservative-only semantics (failure mode is "no binding fires" — not a §6 violation).
- **Implementation surface area larger than spec assumed**: spec said 2 src/ files; reality is 4. Caught + documented in this ADR + the T3 commit body.

## Alternatives considered

- **Bidirectional binding (RHR → PASS on unanimous valid)** — rejected. §6-invariant risk; deferred to v0.1.20+ evidence-driven decision.
- **Auditor aggregation change (e.g. ≥2/3 Findings pass → PASS)** — rejected. Too broad; speculative; affects every chat case; deferred.
- **Env-overridable via `REGULAITOR_COUNCIL_BINDING`** — rejected as YAGNI under monotonic-conservative semantics.
- **Existing `_aggregate_reason` format with appended Council note** — rejected. Less distinguishable than the new `"COUNCIL_BIND:"` prefix.
- **Add `would_escalate` to AdvisoryMajorityPolicy** — rejected. Duplicates logic across two policy classes.
- **Leave CouncilAgent default unchanged; require explicit MonotonicEscalatePolicy construction** — rejected. Defeats v0.1.19 purpose (ships seam but never fires).

## References

- Spec: `docs/superpowers/specs/2026-05-22-v0.1.19-council-binding-design.md` (commit `abf93cd`).
- Plan: `docs/superpowers/plans/2026-05-22-v0.1.19-council-binding.md` (commit `e6e63da`; populated by T6 closure docs).
- ADR-0006 (H4 chat E2E architecture).
- ADR-0014 (H13 Council of Judges — the seam this closes).
- ADR-0016 (H15 Auditor calibration — §16.3 deferral lineage).
- ADR-0021 (v0.1.16 dual-layer thresholds — v0.1.20-bar venue).
- ADR-0024 (v0.1.18 citation granularity — preceding eval-side milestone).
- Source code:
  - `src/regulaitor/agents/council.py` (flag flip + default policy + new `bind_verdict()` helper).
  - `src/regulaitor/orchestration/graph.py` (`_council_node` consumes `bind_verdict()`).
  - `src/regulaitor/api/schemas.py` (`_council_notice` signature update + binding-fired branch + caller update).
  - `src/regulaitor/ui_streamlit/_render.py` (caller updated to pass `state.audited_answer`).
- Empirical data:
  - H13 paid run results (decisions_log §H13: 12/21 divergences; 7/12 Auditor=RHR → Council=valid; 1/12 chat-11 escalation case).
- Future paid validation: v0.1.20 paid bundle (when budget recharges).
