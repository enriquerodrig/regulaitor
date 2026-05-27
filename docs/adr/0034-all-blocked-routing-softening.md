# ADR-0034 — All-blocked Findings routing softening (Design D Mirror)

- **Status:** Accepted — 2026-05-27 — squash `<squash-sha>`, tag `v0.1.29-chat-016-all-blocked-softening`
- **Milestone:** v0.1.29 (chat-016 all-blocked routing softening; mirror of v0.1.25 D2 at the second Turn-level aggregation sub-route)
- **Spec/plan:** inline (light pattern; fully derived from ADR-0032 precedent)
- **Companion ADRs:** [0027](0027-v0121-auditor-quorum-hard-constraints.md) (Tier 1 quorum + Capa A+B+C); [0030](0030-auditor-lenient-quorum.md) (Design B REVERTED — different lever, same goal); [0031](0031-gold-alignment-audit-decomposition.md) (failed_check field this design consumes); [0032](0032-auditor-partial-routing.md) (Design H D2 — the partial-routing twin this design mirrors at all-blocked branch)

## Context

**The chat-016 pattern from v0.1.25 paid validation.** v0.1.25 ADR-0032 Design H D2 softened the PARTIAL-Findings routing (mix of pass + blocked Findings). It explicitly LEFT the all-blocked routing branch UNCHANGED — i.e., when EVERY Finding in the Answer has all citations failing strict validator, the Auditor still emits BLOCK verdict unconditionally.

The v0.1.25 paid measurement surfaced 1 case where this hurt:
- **chat-016** (gold=`pass`, v0.1.25 actual=`BLOCK`): all 3 emitted citations failed strict validator with `failed_check=3` (paraphrase-only mismatch; article + apartado exist in corpus, only text-match differs). All-blocked routing → BLOCK. Gold expected PASS.

The v0.1.25 carry-forward in CLAUDE.md §27 framed this as:
> v0.1.26 (CONDITIONAL — only if needed post-deploy) — All-blocked-Findings routing softening (Design D territory; targets chat-016-like cases)

User authorized v0.1.29 to address this per the "Plan C" pre-H16 lineage (see v0.1.27 + v0.1.28 work).

## Decision

### D1 — Mirror v0.1.25 D2 at the all-blocked sub-route

REUSE the existing `_all_blocked_findings_paraphrase_only` helper (added in v0.1.25 ADR-0032) at the all-blocked branch in `AuditorAgent.audit`. Single 1-branch edit:

```python
elif all(v == "blocked" for v in finding_verdicts):
    if _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results):
        verdict = AuditVerdict.PASS
        reason = None
    else:
        verdict = AuditVerdict.BLOCK
        reason = _aggregate_reason(...)
```

Helper semantics unchanged from v0.1.25:
- Returns `True` iff EVERY blocked Finding has EVERY failed citation with `failed_check == 3` (paraphrase mismatch only).
- Returns `False` if ANY blocked Finding has ANY invalid citation with `failed_check == 1` (article fabrication) OR `failed_check == 2` (apartado fabrication) OR `failed_check == None` (pre-v0.1.24 legacy data; conservative).

Routing maps:
- v0.1.25 partial route: helper True → PASS; helper False → RHR
- v0.1.29 all-blocked route: helper True → PASS; helper False → BLOCK

### D2 — §6 invariant interpretive evolution: Turn-level routing now softened at BOTH sub-routes

v0.1.25 ADR-0032 established THREE-layer Auditor architecture:
- Layer (a) per-citation validator — BYTE-UNCHANGED
- Layer (b) Finding-Lenient aggregation — BYTE-UNCHANGED
- Layer (c) Turn-level aggregation policy — modified at v0.1.25 (partial sub-route only)

v0.1.28 ADR-0033 added FOURTH layer (d) prompt-level explicit forbid (orthogonal dimension).

v0.1.29 ADR-0034 EXTENDS Layer (c) to the all-blocked sub-route:
- **Layer (c) Turn-level aggregation policy** — partial sub-route softened at v0.1.25; all-blocked sub-route softened at v0.1.29
- Both sub-routes use the same `_all_blocked_findings_paraphrase_only` helper
- Both preserve fabrication blocking (Check 1/2 failures still route to original BLOCK/RHR)
- §6 enforcement boundary preserved at Layer (a) + (b); only Layer (c) routing policy evolves

### D3 — §6 risk: MEDIUM-HIGH (higher than v0.1.25 D2)

- v0.1.25 D2 softened the PARTIAL route: at-least-one Finding had ≥1 valid citation (Lenient-Finding PASS). The blocked Findings whose citations all failed Check 3 were treated as supportive scope rather than blocking evidence. **§6 risk: MEDIUM** (Lenient-Finding still passed; at-least-one-valid-citation still guarantees §6 per-citation invariant).
- v0.1.29 D Mirror softens the ALL-BLOCKED route: EVERY Finding has EVERY citation failed strict validator. Routing PASS means ZERO citations in the answer passed strict validation. **§6 risk: MEDIUM-HIGH** (closer to "loose validator" territory).

**Mitigation**: Check 1 (article fabrication) + Check 2 (apartado fabrication) failures STILL route BLOCK by construction. Fabrication caught. Only Check 3 (paraphrase mismatch where article + apartado DO exist) routes PASS.

§6 invariant statement at v0.1.29: "validator + Finding-Lenient byte-unchanged; Turn-level aggregation policy modified at BOTH partial AND all-blocked sub-routes; fabrication detection chain through Layer (a) Check 1 + Check 2 UNBROKEN by construction; only Check 3 paraphrase-only failures (where article + apartado exist in corpus) route PASS."

### D4 — Expected outcome (paid validation will measure)

Predictions (cohort-specific):
- **chat-016**: should flip BLOCK → PASS at v0.1.29 (mirror condition matches exactly).
- **Bucket B all-blocked cases from v0.1.25** (chat-015 / 016 / 020 / 027 / 028; 5 cases): need per-case Check decomposition to predict; some may flip if all Check 3, some stay BLOCK if any Check 1/2.
- **Overall verdict_match lift**: marginal (+0.033 = 1/30 if only chat-016 flips; up to +0.10-0.15 if 3-5 Bucket B cases flip).

Honest estimate: +1 to +3 chat verdict_match wins on H10 30-case cohort. Modest by design — chat-016 is 1/30; Bucket B contains 5 cases but some may have Check 1/2 fabrication that correctly stays BLOCK.

### D5 — Light ceremony (no separate spec/plan document)

Per established mini-milestone pattern (v0.1.21.1, v0.1.21.2, v0.1.24, v0.1.24.1, v0.1.26, v0.1.27, v0.1.28-light closure): when the design is fully derived from precedent (here: ADR-0032), no separate spec/plan document. ADR-0034 IS the formal documentation.

## Alternatives considered

### Alternative A: D-Threshold (route PASS if ≥X% of failures are Check 3, e.g., 80%)

**Rejected** — same reason ADR-0032 rejected D1 threshold: arbitrary parameter introduces tolerated-fabrication-noise concern. v0.1.25 D2 chose binary (100% Check 3) as the conservative §6-safe choice. v0.1.29 D Mirror inherits this binary semantics.

### Alternative B: D-Schema-field (add bypass field on AuditedAnswer)

**Rejected** — same reason ADR-0032 rejected D3 schema field: adds new bypass mechanism vs the surgical 1-branch routing change. Higher §6 risk (bypass field could be misused upstream). v0.1.29 D Mirror keeps the §6 enforcement inside the routing logic.

### Alternative C: Defer D entirely (ship v0.1.28 + skip chat-016 fix)

**Rejected** — User explicitly chose to pursue Plan C item #2 (chat-016 Design D) after Plan C item #1 (doc-mode validation + fix) completed. CLAUDE.md §27 v0.1.25 carry framed v0.1.26-CONDITIONAL specifically for this fix; v0.1.29 closes that conditional.

### Alternative D: Higher §6 risk lever (loosen Layer (a) validator itself)

**Rejected** — explicitly per v0.1.23 ADR-0030 §REVERT precedent. Validator-direct intervention REJECTED then; remains HX post-TFM territory if v0.1.29 D Mirror proves insufficient.

## §22.22 honest disclosures (5)

1. **Marginal expected lift**: 1-3 chat verdict_match wins on H10 30-case = +0.033 to +0.10 lift. Modest by design. The v0.1.25 D2 measured +0.33 (much higher) because partial routing affected MORE cases (8-9/10 H1 cases flipped). All-blocked is rarer per-cohort.

2. **§6 risk higher than v0.1.25 D2**: ALL citations in answer failed strict. Routing PASS is closer to "loose validator" semantically. Mitigation: Check 1/2 fabrication still BLOCKs. Acceptable trade-off per design analysis.

3. **chat-016 paid measurement at v0.1.25 used cached data**: the failed_check field was populated post-v0.1.24 (ADR-0031), so chat-016's per_citation_audits trail at v0.1.25 should have failed_check decomposition. The v0.1.29 paid validation will confirm whether chat-016's 3 citations indeed all have failed_check=3.

4. **Cumulative v0.1.25 + v0.1.29 effect not factorial-isolated**: v0.1.29 paid run measures combined v0.1.25 D2 + v0.1.29 D Mirror state, not D Mirror in isolation. Per project precedent (v0.1.22 cumulative-impact measurement), this is acceptable for milestone-level decision but disclosed for completeness.

5. **No measurement of doc-mode impact**: v0.1.29 paid validation is CHAT cohort (chat-001..030 H10). Doc-mode may also benefit if doc segments produce all-blocked Findings with paraphrase-only failures, but no separate doc paid run planned for v0.1.29 (out of scope; ~€0.50 marginal would inform but not change decision).

## Consequences

### Positive

- chat-016 (and potentially 1-2 other Bucket B cases) flip BLOCK → PASS.
- Auditor aggregation policy now symmetric across partial + all-blocked sub-routes for the paraphrase-only-failure case.
- §6 enforcement preserved at Layer (a) + (b); Layer (c) consistent.
- Closes the v0.1.26 CONDITIONAL carry from CLAUDE.md §27.

### Negative / risks

- HIGHER §6 risk than v0.1.25 D2 (PASS routes when ALL citations failed strict, vs PASS when at-least-one passed).
- Marginal lift may not justify the §6 risk (paid measurement informs).
- Potential REVERT outcome if paid validation shows verdict_match regresses or fabrication slips through (mirror v0.1.23 REVERT discipline).

### Neutral

- Cost: ~€1.60 expected / €3 high. Budget ~$9.97 USD pre-v0.1.29 → ~$7-9 USD post.
- src/ scope: EXACTLY 1 file modified (`agents/auditor.py` 1-branch wire + helper docstring update).
- Tests: +3 new integration tests (999 baseline → 999 total = +3 net delta vs main after v0.1.28 was 998).
- No new infrastructure; no breaking change.

## References

- ADR-0027 (v0.1.21): Tier 1 quorum + Capa A+B+C.
- ADR-0030 (v0.1.23): Design B REVERTED — different lever (validator-direct lenient), refuted empirically.
- ADR-0031 (v0.1.24): failed_check field on AuditResult (this design consumes it).
- ADR-0032 (v0.1.25): Design H D2 — partial-routing softening (this design mirrors at all-blocked sub-route).
- v0.1.25 paid measurement: chat-016 case at `evals/reports/v0.1.25/v0.1.25-prod-main.md`.
- Future commits referenced from this ADR: T1+T2 (helper docstring + 1-branch edit + 3 tests; same commit), T3 ADR-0034 (this commit), T4 pre-paid gate, T5 paid probe, T6 paid main, T7 verdict-flip review, T8 closure docs, T-final squash (`<squash-sha>`; populated at T-final).
