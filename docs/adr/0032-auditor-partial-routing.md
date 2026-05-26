# ADR 0032 — Auditor Strict-Answer partial-Findings routing softening (Design H D2) (v0.1.25)

- **Status:** Accepted — 2026-05-26 — squash `<squash-sha>`, tag `v0.1.25-auditor-partial-routing`
- **Deciders:** controller + project owner (Design H D2 chosen 2026-05-26 from D1/D2/D3 alternatives post-v0.1.24.1 Path B DOMINANT 8/10 diagnostic).
- **Companion ADRs:** 0027 (v0.1.21 Tier 1 RHR quorum — the v0.1.21 STRICT counter that v0.1.23 attempted to loosen + that v0.1.25 leaves UNCHANGED), 0029 (v0.1.22 paid validation — exposed verdict_match drop 0.30 < bar 0.35 that motivated the v0.1.22.1 → v0.1.23 → v0.1.24 → v0.1.24.1 → v0.1.25 lineage), 0030 (v0.1.23 Design B Auditor lenient quorum REVERTED per empirical refutation; the REVERT post-mortem narrowed the candidate intervention layer + supplied the v0.1.23 REVERT precedent invoked by v0.1.25 flip protocol), 0031 (v0.1.24 gold alignment + AuditResult `failed_check` decomposition — O2 confirmed H1.C=10/10 paraphrase-only at the v0.1.22.1 H1 cases + supplied the per-citation instrumentation that v0.1.25's D2 helper reads).

## Context

ADR-0030 closure shipped v0.1.23 as REVERT (0/10 H1 cases flipped RHR → PASS as predicted; 8/10 unchanged RHR; 2/10 flipped RHR → BLOCK unexpectedly). The REVERT post-mortem narrowed the candidate-intervention layer via three hypotheses (A: Check 1/2 conflation; B: Strict-Answer partial-Findings routing upstream of Tier 1 quorum; C: Finding-Lenient strict-text-match upstream of Tier 1 quorum). ADR-0031 v0.1.24 O2 shipped the `failed_check` decomposition that lets cached AuditResults be classified at $0; the decomposition diagnostic (`evals/reports/v0.1.24/decomposition-h-attribution.md`) ruled out Hypothesis A (H1.C = 10/10 = 100% Check 3 paraphrase-only; 0% Check 1/2 fabrication).

The v0.1.24.1 cross-version diagnostic (`evals/reports/v0.1.24.1/finding-path-attribution.md`) then arbitrated between Hypotheses B and C by comparing v0.1.22-prod vs v0.1.23-prod cached actual_verdict for the same 10 H1 cases. The headline: **Path B (Strict-Answer partial-Findings routing) DOMINANT at 8/10 = 80%** (Path A Tier 1 quorum = 0/10 confirmed not the layer per the v0.1.23 REVERT outcome; Path C-ish = 2/10 = chat-016 / chat-017 flipped RHR → BLOCK — all-blocked routing or Sonnet non-determinism, not addressable by a partial-routing change).

v0.1.25 ships Design H D2 with HIGH confidence (empirically diagnosed gatekeeper + ZERO arbitrary tunable parameters): a NEW `_all_blocked_findings_paraphrase_only` helper in `src/regulaitor/agents/auditor.py` + a 1-branch change at the Strict-Answer partial-Findings aggregation policy. The partial branch (previously always RHR) now routes to PASS when every blocked Finding's invalid citations are all `failed_check==3` paraphrase-only; routes to RHR otherwise (any non-Check-3 invalid → fabrication evidence → preserve pre-v0.1.25 routing). Validator + schemas + Finding-Lenient + Tier 1 quorum + Council + Analyst prompts + retrieval + eval pipeline + gold set BYTE-EQUIVALENT.

## Decision

### D1 — Implementation: D2 partial routing softening + helper in `agents/auditor.py`

NEW helper `_all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results) -> bool` above `AuditorAgent`. Returns True iff every blocked Finding has all its invalid citations with `failed_check==3`. Returns False on any non-Check-3 invalid (Check 1 article fabrication; Check 2 apartado fabrication; or `failed_check=None` for pre-v0.1.24 cached data — conservative). Partial-Findings branch (lines ~97-112 post-edit) replaces unconditional RHR with `PASS if helper(...) else RHR`.

### D2 — Tests (TDD red → green): 7 new unit tests in `tests/unit/agents/test_auditor.py`

4 helper-level tests (Check 3 / Check 1 / Check 2 / None) + 3 integration tests (Auditor.audit() with synthetic partial scenarios: all-paraphrase-blocked → PASS; Check 1/2 fabrication-blocked → RHR; failed_check=None → RHR conservative). Pre-existing tests preserved (partial→RHR semantics retained for non-paraphrase cases).

### D3 — Paid validation methodology: 1-arm FRESH vs CACHED v0.1.22-prod baseline ($0 baseline)

**ARM v0.1.25-prod** (FRESH paid): production state post-fix (env-unset = v1.5 chat + Tier 1 STRICT quorum + Tier 2 Capa A+B+C + retrieval defaults + Council binding ON + NEW Strict-Answer partial-routing D2 softening). 1-arm fresh on H10 30-case (chat-001..030).

**Baseline: ARM v0.1.22-prod** (CACHED, $0): extracted from `evals/reports/v0.1.22/v0.1.22-prod-main.md` + probe.md. Same cohort, same prompts, same retrieval, same Sonnet model (4.6), same Haiku judge (4.5), same v0.1.18 hierarchical containment instrument — only difference is Strict-Answer partial-Findings routing semantics. v0.1.22 baseline preferred over v0.1.23 because v0.1.23 was REVERTED → production state pre-v0.1.25 is functionally identical to v0.1.22.1; v0.1.22 cached data is the canonical pre-Tier-1-experiment baseline.

**Probe gate** (per cost-estimation discipline registered v0.1.8): 5-case probe (chat-001..005); if per-case cost > 1.5× v0.1.22-prod anchor (~€0.063), abort. If OK, PROCEED to remaining 25 cases.

Expected total: ~€1.90 expected / €2.85 high (×1.5). Budget remaining ~$9.06 entering v0.1.25; ~$6 headroom post-fix.

### D4 — Flip protocol: hard safety floor + soft per-metric narrative (mirrors ADR-0029 D4 + ADR-0030 D5)

**Hard safety floor** (mechanical gate; failure → REVERT):
- redteam-smoke ≥ 0.90 under post-fix production state (deterministic patterns; partial-routing change does not affect sanitizer/injection patterns; expected 0.92 carry).
- §6 invariant manual content-check on 6 designated content-safety cases (chat-014, chat-015, chat-029, chat-030, nis2-006, dora-006) per H15 C1 backstop pattern: cached outputs UNCHANGED (those cases route via all-blocked → BLOCK or via Lenient-Finding with refusal-Finding → pass; partial-routing change doesn't touch their routing).
- Per-citation `failed_check` trail populated for all v0.1.25-prod cases (v0.1.21.1 D2 + v0.1.24 O2 already shipped).

**Soft per-metric narrative**: 7 v0.1.20-bar metrics A/B v0.1.25-prod vs cached v0.1.22-prod. HEADLINE: verdict_match delta + per-case detail for 10 H1 cases (chat-016..026) — predicted 6-8/10 flip RHR → PASS per v0.1.24.1 Path B 8/10 dominance.

**Decision logic** (v0.1.23 REVERT precedent invoked):
- Hard floor PASS + verdict_match lifts ≥+0.10 + no §6 regression → **CONFIRM** (ship Design H D2 as production).
- Hard floor PASS + verdict_match lifts but mixed → **CONDITIONAL CONFIRM** (ship D2 + carry-forward).
- Hard floor FAIL OR §6 regression OR verdict_match REGRESSES → **REVERT** (1-line cherry-pick revert of partial branch + §REVERT section appended to this ADR, mirroring ADR-0030 §REVERT structure).

### D5 — ADR-0032 single-ADR scope

Single ADR documenting §6 interpretive distinction (centerpiece) + 3 D-variants evaluated (D1/D2/D3) + risk mitigation + paid validation methodology + flip protocol + §22.22 disclosures. Mirrors ADR-0027 / 0029 / 0030 / 0031 single-ADR-multi-decision precedents.

### D6 — Closure docs + ceremony

ADR-0032 + decisions_log §v0.1.25 (~100-130 lines) + evidence_matrix (3 spots: ADR count 31 → 32 + tag-table row + scope paragraph) + CLAUDE.md (3 spots: §16.3 H15.X + §27 Hitos cerrados + §27 Hito siguiente flip). Per v0.1.23 REVERT precedent: CONFIRM → standard closure narrative; CONDITIONAL → document carry-forward; REVERT → mirror v0.1.23 REVERT-aware framing throughout.

### D7 — Memory roll-forward + push

After T-final ceremony: rename memory file (`v0.1.24.1_closed_v0.1.25_or_H16_starting.md` → `v0.1.25_closed_H16_starting.md` OR REVERT-suffix variant). NO push to origin until user authorizes separately.

## §6 interpretive distinction (the centerpiece)

RegulAItor enforces "no citation, no answer" via a **three-layer architecture**. v0.1.25 refines ONLY the third layer:

**Layer (a) — Per-citation validator** (`src/regulaitor/citation/validator.py` + `src/regulaitor/citation/schemas.py`): the §6-invariant guardian. Three STRICT checks per citation: (1) `article_exists`, (2) `apartado_exists`, (3) `text_normalized_match`. v0.1.24 ADR-0031 added the additive `failed_check: Literal[1, 2, 3] | None` observability field (byte-equivalent validation semantics; first-failing-check label populated at the existing fail-fast returns). v0.1.25 does **NOT touch this layer** — `git diff main...HEAD -- src/regulaitor/citation/` MUST be empty at the T8 pre-closure gate.

**Layer (b) — Finding-level Lenient aggregation** (`src/regulaitor/agents/auditor.py` line ~61): a Finding passes iff ≥1 of its citations validates STRICTLY (`any(r.validated for r in this_finding_results)`). Fabricated articles (Check 1 fail) or fabricated apartados (Check 2 fail) STILL cause Finding-Lenient to block when every citation in the Finding strict-fails — the fabrication-detection path is preserved. v0.1.25 does **NOT touch this layer**.

**Layer (c) — Turn-level aggregation policy** (`src/regulaitor/agents/auditor.py` lines ~83-112): combines per-Finding verdicts into a turn-level verdict via three sub-routes. The all-pass-Findings sub-route includes the v0.1.21 Tier 1 RHR quorum (ADR-0027 STRICT counter — v0.1.23 attempted lenient counter REVERTED per ADR-0030; v0.1.25 leaves it UNCHANGED). The all-blocked-Findings sub-route routes to BLOCK (UNCHANGED). The partial-Findings sub-route (some pass, some blocked) is **the empirical gatekeeper that v0.1.25 refines** — pre-v0.1.25 always RHR; post-v0.1.25 PASS iff every blocked Finding's invalid citations are all `failed_check==3` paraphrase-only, else RHR.

D2 operates ONLY at Layer (c) partial-routing — NO change at Layer (a) or Layer (b). The **fabrication-detection chain is UNBROKEN**: a fabricated citation (Check 1 or Check 2 fail) lands at Layer (a) marked invalid + populated with `failed_check ∈ {1, 2}`; Layer (b) Finding-Lenient blocks the containing Finding if the fabricated citation is the only one in that Finding; Layer (c) partial-routing reads `failed_check` via the helper — any non-3 value → False → RHR (preserves pre-v0.1.25 routing). The case Layer (c) unlocks is exactly the H1.C profile: Finding-Lenient blocks because all citations are STRICT-invalid via Check 3 (paraphrase mismatch); article + apartado exist (no §6-relevant fabrication); D2 routes partial → PASS instead of spurious RHR.

The "§6 byte-equivalent" claim from ADR-0031 **EVOLVES** to also cover Layer (c) aggregation policy refinement: validation semantics byte-equivalent (Layer a unchanged) + Finding-Lenient byte-equivalent (Layer b unchanged) + Turn-level aggregation policy gains one ADDITIVE conditional branch (Layer c — pre-v0.1.25 RHR routing preserved on the non-paraphrase code path; the new PASS code path is gated on the binary all-paraphrase-only condition derived from the Layer (a) observability field).

## 3 D-variants evaluated

### D1 — Threshold-based (50% of blocked Findings pass + most invalids `failed_check==3`) — REJECTED

Route partial → PASS when ≥50% of blocked Findings have all-Check-3 citations AND the majority of remaining invalids are Check 3.

- **Rejected for**: (a) the 50% threshold is arbitrary and tunable (no empirical anchor); (b) the helper has a concrete §6 vulnerability — a partial scenario with 1 paraphrase-blocked Finding + 1 fabrication-blocked Finding satisfies "50% of blocked Findings pass-Check-3-only" → routes to PASS even though a fabrication is present in the answer. Threshold-based logic admits "tolerated fabrication noise" by construction; that conflicts with the §6 no-citation-no-answer invariant.

### D2 — All-paraphrase-only binary condition — ACCEPTED

Route partial → PASS iff EVERY blocked Finding has all-invalid-citations `failed_check==3`. ZERO fabrication evidence anywhere in the answer. Single binary condition; no arbitrary parameters to tune; strongest §6 safeguard at the partial-routing layer.

- **Coverage equivalence in our cohort**: v0.1.24 O2 decomposition diagnostic confirmed H1.C = 10/10 = 100% for the v0.1.22.1 H1 cases (0 Check 1/2 fabrications in any of those 10 cases). D2 has EQUIVALENT coverage to D1 and D3 on the actual cohort — the trade-off between "stricter safety floor (D2)" and "broader coverage (D1/D3)" does not exist empirically.
- **Selected for**: ZERO arbitrary parameters + binary §6 condition + empirically-equivalent coverage on the diagnosed bottleneck cohort.

### D3 — Citation-level majority X% — REJECTED

Route partial → PASS when X% of invalid citations across all blocked Findings are `failed_check==3` (e.g. ≥80% Check 3).

- **Rejected for**: arbitrary X% parameter + explicitly accepts "tolerated fabrication noise" (an answer with 4 Check 3 invalids + 1 Check 1 fabrication satisfies 80% Check 3 → PASS despite the Check 1 fabrication). Same conceptual weakness as D1 with an additional tuning knob. Tuning territory closed by D2's binary design.

## Risk mitigation

- **Binary §6 safety condition**: D2's helper returns False on ANY non-Check-3 invalid in any blocked Finding. No thresholds to tune; no parameters that future contributors could relax inadvertently. Fabrication-detection chain through Layer (a) + Layer (b) preserved by construction.
- **Conservative on missing `failed_check`**: pre-v0.1.24 cached AuditResults have `failed_check=None` (Pydantic v2 default for missing optional fields). The helper returns False on None → preserves pre-v0.1.25 partial→RHR routing for legacy data. Fresh v0.1.25-prod runs have the field populated natively per v0.1.24 O2.
- **Validator + Finding-Lenient + Tier 1 quorum + schemas BYTE-EQUIVALENT**: verified at the T8 pre-closure gate via 5 HARD `git diff` invariants (citation/ + analyst.py + council.py + prompts/ + retrieval.py + eval pipeline + gold set MUST be empty).
- **Rollback = 1-line revert**: minimum-surface intervention design. The partial branch's NEW conditional can be cleanly reverted to the original unconditional RHR via `git revert` or cherry-pick. v0.1.23 §REVERT in ADR-0030 is the precedent for the protocol.
- **v0.1.23 REVERT precedent invoked**: if T6 measurement REFUTES the prediction (verdict_match REGRESSES OR §6 regression OR hard floor FAIL), a §REVERT section is appended to this ADR (mirroring ADR-0030 §REVERT structure) and production state is restored to v0.1.22.1 baseline. The experiment is preserved in git history; the tag `v0.1.25-auditor-partial-routing` still applies (semantically: "the experiment that was run; production state restored if T6 REVERT").

## Paid validation methodology summary

- **1-arm FRESH paid** (v0.1.25-prod) **vs CACHED v0.1.22-prod baseline** (extracted $0). 30 cases on H10 cohort (chat-001..030).
- **Probe-then-PROCEED via SKIP/PROCEED gate** (5-case probe + cost extrapolation per cost-estimation discipline registered v0.1.8).
- **Expected cost**: ~€1.90 expected / €2.85 high (×1.5).
- **Budget remaining**: ~$9.06 entering v0.1.25; ~$6 headroom post-fix.
- **Carries**: ADR-0021 v0.1.20-bar thresholds (formal measurement target); ADR-0024 v0.1.18 hierarchical containment (eval-metric instrument); ADR-0027 Tier 1 + Tier 2 (production state under measurement); ADR-0029 1-arm-vs-cached methodology + per-citation audit trail diagnostic infrastructure; ADR-0030 v0.1.23 REVERT precedent (flip protocol third path); ADR-0031 O2 `failed_check` instrumentation (read by D2 helper).

## Flip protocol summary

- **CONFIRM**: hard floor PASS + verdict_match lifts ≥+0.10 + no §6 regression → ship Design H D2 as production. Closes the v0.1.22→v0.1.22.1→v0.1.23→v0.1.24→v0.1.24.1 lineage with an empirically-validated targeted intervention at the diagnosed gatekeeper layer.
- **CONDITIONAL CONFIRM**: hard floor PASS + verdict_match lifts but mixed → ship D2 + carry-forward (e.g. all-blocked path softening, Finding-Lenient softening, or eval-side hierarchical containment propagation if a residual gap to bar persists).
- **REVERT**: §6 regression OR hard floor FAIL OR verdict_match REGRESSES → 1-line cherry-pick revert of partial branch + §REVERT section appended to this ADR (mirroring ADR-0030 §REVERT structure) + decisions_log + CLAUDE.md updated REVERT-aware.

## §22.22 disclosures (the centerpiece of the v0.1.X milestone narrative)

The honest framing of what v0.1.25 ships, predicts, and explicitly does NOT resolve at the time of this ADR write:

1. **Estimated verdict_match lift +0.20-0.30 is PRE-MEASUREMENT prediction** (not a promise). Derived from v0.1.24.1 Path B 8/10 dominance applied to the v0.1.22-prod baseline (predicted 6-8 of 10 H1 cases flip RHR → PASS; if 8/8 do flip + the 2 Path C-ish cases stay BLOCK → verdict_match lifts by 8/30 ≈ +0.27 on the 30-case cohort). The actual delta is measured at T6 and may diverge if (a) Sonnet behavior drifts between the v0.1.22 cached baseline (2026-05-24) and the v0.1.25 fresh run (2026-05-27+), (b) some H1.C cases route via Finding-Lenient (Layer b) instead of partial-routing (Layer c) — the v0.1.24.1 cross-version inference cannot definitively separate the two, (c) the Tier 1 STRICT quorum (still in place) interacts with the partial-routing change in ways the diagnostic cannot pre-compute.

2. **D2 coverage equivalence relies on v0.1.24 O2 attribution correctness** (H1.C = 10/10 = 100% paraphrase-only). The O2 decomposition diagnostic uses reason-text re-derivation on cached data per ADR-0031 Option B — the mapping (`article_not_found` → Check 1, `apartado_not_found` → Check 2, `text_not_in_*` → Check 3) is heuristic. If any of the 10 H1 cases actually has a hidden Check 1/2 failure that the reason-text mapping missed (e.g. a future validator messaging change), D2 would correctly preserve RHR for that case (conservative on non-Check-3) but D1/D3 would not — the empirical coverage equivalence is established on the current validator's error-message strings.

3. **v0.1.22 cached baseline has ~3-day API drift caveat**. v0.1.22-prod cached on 2026-05-24; v0.1.25-prod fresh run targeted for 2026-05-27+; ~3-day gap. Sonnet non-determinism at temperature=0 contributed ~20% noise floor in the v0.1.23 §REVERT measurement (2-day gap between v0.1.22 and v0.1.23 produced 2/10 unexpected RHR → BLOCK flips for chat-016 + chat-017). v0.1.25 inherits the same caveat — the verdict_match delta measured at T6 is the combined effect of (a) the D2 intervention + (b) ~3-day API drift noise. If T6 verdict_match flat or regresses, the §REVERT analysis must distinguish drift from intervention effect.

4. **2 Path C-ish cases (chat-016, chat-017) UNADDRESSED by D2**. Per v0.1.24.1 finding-path-attribution.md these 2 cases went RHR → BLOCK in v0.1.23 — all-blocked Findings routing OR API drift, not the partial-Findings routing layer that D2 refines. D2 leaves the all-blocked → BLOCK sub-route untouched (correct: that sub-route requires every Finding to be blocked, indicating no valid citation in any Finding — true fabrication scenario by Layer (b) construction). If T6 shows chat-016 + chat-017 still route to BLOCK under D2, that is expected behavior, not a D2 failure; the underlying mechanism (all-blocked Findings) would need a separate Design D-style intervention deferred to HX post-TFM.

5. **Pre-v0.1.24 cached AuditResults lack `failed_check`**. The D2 helper returns False on `failed_check=None` (conservative; preserves pre-v0.1.25 partial→RHR routing). Fresh v0.1.25-prod runs have the field populated natively per ADR-0031 O2. The 1-arm-vs-cached methodology of D3 is unaffected — the v0.1.22-prod cached evidence does NOT need the field re-populated because the comparison reads `actual_verdict` outputs only (the D2 intervention runs against the FRESH v0.1.25-prod data which has the field populated). The cached-data conservative default exists for the edge case where the helper is invoked at runtime against an AuditResult that was constructed and serialized before v0.1.24 — not a code path exercised by the v0.1.25 paid validation.

6. **D2 single binary condition; no arbitrary parameters; v0.1.25.1+ tuning territory closed by design**. Unlike D1's 50% threshold or D3's X% threshold, D2 has nothing to tune. The §6 safety floor is established by construction (ANY non-Check-3 invalid → False → RHR); the coverage is established by the v0.1.24 O2 H1.C=10/10 evidence. Future iteration would have to either (a) accept the §6 risk explicitly and document the trade-off (e.g. relax to "all blocked Findings have ≥1 Check 3 invalid + 0 Check 1/2 invalids" — which is structurally D1 with the additional "every Check 1/2 → False" gate; a minor relaxation), or (b) propagate the relaxation to a DIFFERENT layer (Layer b Finding-Lenient softening; Layer a validator fuzzy-match; eval-side hierarchical containment) — those are HX post-TFM territory per the ADR-0030 §REVERT lessons learned.

7. **Post-v0.1.25 residual verdict_match drop (if any) carries forward to HX post-TFM**. v0.1.25 attacks the diagnosed Path B (Strict-Answer partial-routing) layer. If T6 shows verdict_match lifts but does not close the residual gap to bar (0.35) — e.g. CONDITIONAL CONFIRM with verdict_match at 0.50 still below an aspirational target — the remaining drop is attributable to Path C-ish cases (all-blocked routing; chat-016, chat-017), the 6 v0.1.22.1 mixed cases not in the H1 bucket (gold-vs-behavior mismatch territory; partially addressed by v0.1.24 O1), or new mechanisms surfaced by the v0.1.25-prod fresh run. HX post-TFM is the carry-forward home for any such residual.

## Carry-forwards (post-v0.1.25)

- **2 Path C-ish cases (chat-016, chat-017) all-blocked routing softening (Design D territory)** — deferred to HX post-TFM if T6 confirms BLOCK persistence under D2.
- **`failed_check` populated automatically on fresh runs** — no per-Finding instrumentation needed for future $0 diagnostics; v0.1.24 O2 + v0.1.21.1 D2 per_citation_audits trail is the established pipeline.
- **Coverage gate threshold 88.55% < 90%** — carry from v0.1.21.3 @slow hotfix per ADR-0029 §22.22 #8; remains carry to H16 (adjust threshold OR fix offline-SSL test path).
- **truststore in pyproject.toml** for the SSL test path — carry from v0.1.22 SSL discovery per ADR-0029.
- **Doc-mode A/B** — carry from v0.1.20 per ADR-0026 D2 design-coherence catch.
- **Per-capability cost attribution** — still unmeasured; the v0.1.25 measurement is cumulative (D2 layered on top of v0.1.22-cumulative state). Surgical ablation of the D2 effect would require an additional FRESH arm with D2 reverted under the same date; not in v0.1.25 scope.

## References

- **Spec**: `docs/superpowers/specs/2026-05-26-v0.1.25-auditor-partial-routing-design.md` @ commit `20d4fa5`.
- **Plan**: `docs/superpowers/plans/2026-05-26-v0.1.25-auditor-partial-routing.md` @ commit `1752b24`.
- **Motivating diagnostics**: `evals/reports/v0.1.22.1/verdict-drop-analysis.md` (H1 attribution); `evals/reports/v0.1.24/decomposition-h-attribution.md` (H1.C = 10/10 confirmed); `evals/reports/v0.1.24.1/finding-path-attribution.md` (Path B DOMINANT 8/10).
- **Source code touched by v0.1.25**:
  - `src/regulaitor/agents/auditor.py` (D1 + D2 — NEW `_all_blocked_findings_paraphrase_only` helper + partial branch conditional).
- **Source code BYTE-EQUIVALENT** (verified at T8 pre-closure gate):
  - `src/regulaitor/citation/validator.py` + `src/regulaitor/citation/schemas.py` (§6 guardian; ADR-0031 O2 additive field unchanged from v0.1.24).
  - `src/regulaitor/agents/analyst.py` (v0.1.21 Tier 2 Capa A + Capa C — orthogonal).
  - `src/regulaitor/agents/council.py` (v0.1.19 binding ON — orthogonal).
  - `src/regulaitor/agents/prompts/` (v1.0-v1.5 Analyst prompts — orthogonal).
  - `src/regulaitor/rag/retrieval.py` (v0.1.21.2 defaults — orthogonal).
  - `evals/metrics.py` + `evals/schemas.py` + `evals/harness.py` + `evals/report.py` (eval pipeline — orthogonal).
  - `evals/gold_set.jsonl` (gold ground truth; v0.1.24 O1 acceptable_verdicts already shipped — orthogonal).
- **Test coverage**: 7 new $0 unit tests in `tests/unit/agents/test_auditor.py` (4 helper + 3 integration). Baseline 972 + 7 new = 979 expected at the T8 pre-closure gate.
- **Companion ADRs**: 0027 (v0.1.21 Tier 1 STRICT quorum — unchanged), 0029 (v0.1.22 paid validation — exposed verdict_match drop), 0030 (v0.1.23 Design B REVERT — flip protocol precedent + narrowed candidate layer), 0031 (v0.1.24 gold alignment + O2 `failed_check` decomposition — supplied per-citation instrumentation that D2 helper reads + confirmed H1.C = 10/10).
- **Future commits referenced from this ADR**: T1+T2 (`47a8995`), T3 ADR-0032 (this commit), T4+T5 paid (TBD), T6 comparison + per-citation diagnostic + verdict-flip review (TBD), T7 closure docs (TBD), T-final squash (`<squash-sha>`; populated at T-final).
- **Empirical resolution**: T6 outcome documented in `evals/reports/v0.1.25/comparison.md` + `per-citation-mechanism.md` + `verdict-flip-review.md` (predicted 6-8 of 10 H1 flips RHR → PASS; actual count is the headline finding).
- **Future**: if T6 outcome is CONFIRM or CONDITIONAL CONFIRM → **H16** (HF Spaces deploy + foundation production-grade per user pref) → **H17** (TFM closure: memoria + model card + data card + AI Act assessment + runbook + cost analysis + video demo + slide deck + Product Roadmap appendix + tag v1.0.0). If T6 outcome is REVERT → CONDITIONAL CLOSE v0.1.25 with REVERT documented (§REVERT section appended); proceed to H16 with v0.1.22.1 baseline restored (Design H D2 reverted; v0.1.24 O1 + O2 + v0.1.24.1 diagnostic evidence preserved).
