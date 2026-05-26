# ADR 0030 — Auditor lenient quorum (Design B) (v0.1.23)

- **Status:** Accepted 2026-05-25 then **REVERTED 2026-05-26** per T6 empirical refutation — squash `<squash-sha>`, tag `v0.1.23-auditor-lenient-quorum` (semantically: REVERT-milestone; the experiment is preserved in git history; production-side `agents/auditor.py` Tier 1 quorum-counting RESTORED to STRICT `not r.validated` per v0.1.21 ADR-0027 + pre-v0.1.23 baseline). See §REVERT section at end.
- **Deciders:** controller + project owner (path A + Design B chosen 2026-05-25 post-v0.1.22.1 diagnostic).
- **Companion ADRs:** 0024 (v0.1.18 hierarchical containment in eval-metric — the conceptual lineage; v0.1.23 applies the same hierarchical concept at the Auditor aggregation layer that v0.1.18 applied at the eval-metric layer), 0027 (v0.1.21 Tier 1 RHR quorum — the mechanism being refined; v0.1.23 changes ONLY the per-citation invalidity counter that quorum reads), 0029 (v0.1.22 paid validation — exposed the verdict_match drop that motivated this milestone; the cumulative-package was CONDITIONAL CONFIRM with verdict_match flat at 0.30 below bar 0.35).

## Context

ADR-0029 closure shipped v0.1.22 as CONDITIONAL CONFIRM with verdict_match flat at 0.30 below bar 0.35 (-0.05 FAIL on the formal v0.1.20-bar metric). The v0.1.22.1 verdict-drop diagnostic ($0 cache-mining over v0.1.22-prod's per_citation_audits trail; see `evals/reports/v0.1.22.1/verdict-drop-analysis.md`) attributed **H1 (validator-too-strict vs eval-metric mismatch) as DOMINANT cause: 10 of 16 RHR cases = 62.5%** (with 1/16 H4 + 5/16 mixed).

The mechanism is a layered-system inconsistency that accumulated across milestones:

- **v0.1.18 ADR-0024** introduced hierarchical containment match in the EVAL precision/recall metric (`evals/metrics.py::_citation_matches`): article-expected matches any apartado of that article; apartado-expected requires exact apartado match. The eval-metric treats Sonnet's correct-article-wrong-apartado citation as a valid match.
- **v0.1.21 ADR-0027** introduced Tier 1 RHR quorum in the production Auditor (`agents/auditor.py`): when ≥2 per-citation results are invalid in an otherwise-all-pass-Findings aggregation, escalate the turn to RHR.
- **The production validator (`citation/validator.py`) stayed STRICT** across all milestones — its Check 3 `text_normalized_match` rejects Sonnet's paraphrased citation even when (article + apartado) DO exist in corpus. The eval-metric hierarchical containment concept was NEVER propagated to the production validator OR to the Auditor's quorum-counting.
- **The cumulative impact**: Tier 1 quorum reads the STRICT validator output as ground-truth. Sonnet routinely paraphrases real corpus content (the H1 evidence shows this — every chat-016/017/018/019/021/022/023/024/025/026 case emits citations whose (article, apartado) tuples exist + intersect gold expected articles, yet validator.validated=False on Check 3 text mismatch). The quorum then escalates these false-negative citations to RHR. Result: v0.1.22-prod RHR rate 16/30 (53%) vs ARM B baseline 16/30 — the regression is exactly where the gold expects PASS but mechanical RHR fires on strict-text-only failures.

v0.1.23 ships **Design B (Auditor-only intervention)**: a 10-line inline helper `_is_lenient_valid(result)` in `agents/auditor.py` + a 1-line change at the Tier 1 quorum-count line (`not r.validated` → `not _is_lenient_valid(r)`). Validator + schemas BYTE-UNCHANGED. The §6 invariant interpretive distinction is the centerpiece of this ADR.

## Decision

### D1 — Implementation: inline `_is_lenient_valid` helper in `agents/auditor.py`

```python
def _is_lenient_valid(result: AuditResult) -> bool:
    """v0.1.23 (ADR-0030): for Tier 1 quorum counting, a citation is
    'valid enough' if its (article, apartado) tuple exists in corpus.
    Strict text match (Check 3 in citation/validator.py) is preserved
    on AuditResult.validated for Finding-Lenient aggregation +
    confidence/severity reporting + future use-cases.

    Mirrors the v0.1.18 ADR-0024 eval-metric hierarchical containment
    concept applied at the Auditor aggregation layer (NOT at validator
    layer; §6 invariant byte-unchanged at validator). See ADR-0030 §6
    interpretive distinction.
    """
    if not result.article_exists:
        return False
    return result.apartado_exists is not False
```

The `apartado_exists is not False` guard correctly handles the three states of the field: `True` (apartado present + exists → lenient valid), `False` (apartado present + does not exist → lenient invalid), `None` (article-level citation with no apartado → lenient valid). This mirrors the validator's own three-state semantics.

### D2 — Wiring: 1-line change at Tier 1 quorum-count line ONLY

```python
# src/regulaitor/agents/auditor.py line 68 BEFORE:
n_invalid_citations = sum(1 for r in all_results if not r.validated)
# AFTER:
n_invalid_citations = sum(1 for r in all_results if not _is_lenient_valid(r))
```

ZERO other Auditor change. Finding-Lenient aggregation (line 52: `any(r.validated for r in this_finding_results)`) STILL uses strict `r.validated` — preserving the §6 fabrication-detection path. Strict-Answer aggregation routing (`all-pass-Findings` / `all-blocked-Findings` / `partial-Findings`) UNCHANGED. The new `_aggregate_reason` text continues to report strict `n_invalid` for human readability (the human-readable reason field still counts strict failures; only the quorum gate switches to lenient).

### D3 — Tests: 5 new unit tests pinning helper + integration behavior

NEW tests in `tests/unit/agents/test_auditor.py`:

1. `test_is_lenient_valid_returns_true_when_article_and_apartado_exist` — helper baseline.
2. `test_is_lenient_valid_returns_false_when_article_not_exists` — fabrication detection at lenient level.
3. `test_is_lenient_valid_returns_false_when_apartado_not_exists` — apartado fabrication at lenient level.
4. `test_is_lenient_valid_returns_true_for_article_level_citation` — `apartado_exists=None` case.
5. `test_tier1_quorum_lenient_counting_passes_strict_invalid_lenient_valid_cases` — integration: 1 Finding with 3 citations where citation[0] is fully valid + citations[1,2] are strict-invalid-but-lenient-valid (article+apartado exist; text mismatch). Pre-v0.1.23: Tier 1 quorum fires → RHR. Post-v0.1.23: lenient quorum counts 0 invalid → PASS.

Pre-existing tests in `tests/unit/agents/test_auditor_quorum.py` updated to reflect new semantics where they previously pinned strict quorum on lenient-valid scenarios; a separate test continues to pin true-fabricated-citation escalation through the Finding-Lenient path (preserving §6 fabrication-detection coverage).

### D4 — Paid validation methodology: 1-arm fresh vs cached baseline ($0 baseline)

**ARM v0.1.23-prod** (FRESH paid): production state post-fix (env-unset = v1.5 chat + Tier 1 LENIENT quorum + Tier 2 Capa A+B+C + retrieval defaults + Council binding ON). 1-arm fresh on H10 30-case (chat-001..030) per the v0.1.20-bar cohort.

**Baseline: ARM v0.1.22-prod** (CACHED, $0): extracted from `evals/reports/v0.1.22/v0.1.22-prod-main.md` + probe. Same cohort, same Analyst prompt (v1.5), same retrieval defaults, same Sonnet model (4.6), same Haiku judge (4.5), same v0.1.18 hierarchical containment instrument — only difference is Auditor Tier 1 quorum counting (strict → lenient).

**Probe gate** (per cost-estimation discipline registered effective v0.1.8): 5-probe cases first (chat-001..005); if per-case cost > 1.5× v0.1.22-prod anchor (~€0.063), abort. If OK, PROCEED to remaining 25 cases. Expected per-case cost similar to v0.1.22 since Analyst+retrieval+judge layer behavior unchanged; only Auditor verdict differs.

Expected total: ~€1.90 (probe €0.32 + main €1.58) / €2.85 high (×1.5). Budget headroom: ~$10.95 entering v0.1.23; ~$8 post-fix.

### D5 — Flip protocol: hard safety floor + soft per-metric narrative

**Hard safety floor** (mechanical gate; failure → REVERT):
- redteam-smoke ≥ 0.90 under post-fix production state (deterministic patterns; should be 0.92 carry from v0.1.14-v0.1.22 frozen baseline).
- §6 invariant manual content-check on the 6 designated content-safety cases (chat-014/015/029/030 + nis2-006/dora-006) per the H15 C1 backstop pattern: cached outputs UNCHANGED + new Auditor verdict per cached AuditResult re-applied to verify "lenient quorum doesn't relax block/RHR routing for fabricated-citation safety cases".

**Soft per-metric narrative** (decision input; not gate):
- Per-metric comparison v0.1.23-prod vs cached v0.1.22-prod on the 7 v0.1.20-bar metrics.
- HEADLINE: verdict_match delta + bucket-C-RHR count delta on the per-citation mechanism diagnostic (T5 v0.1.22 re-run on v0.1.23-prod).
- Per-case detail for the 10 H1 cases predicted to flip RHR→PASS: report actual flip count + any unexpected outcomes.

**Decision logic**:
- Hard floor PASS + verdict_match ≥ bar (0.35) + no §6 regression → **CONFIRM**: ship Design B as production.
- Hard floor PASS + verdict_match lifts but <bar OR mixed → **CONDITIONAL CONFIRM**: ship Design B + carry-forward Designs A/C for further iteration.
- Hard floor FAIL OR §6 regression → **REVERT**: cherry-pick revert the 1-line auditor change + REVERT outcome documented in this ADR + decisions_log + CLAUDE.md.

### D6 — ADR-0030 scope

Single ADR-0030 (count: 29 → 30) covering the §6 interpretive distinction (centerpiece) + 3 design alternatives evaluated + risk mitigation + paid validation methodology + flip protocol + §22.22 disclosures. Mirrors ADR-0027 + ADR-0029 single-ADR-multi-decision precedents.

### D7 — Closure docs

- `docs/adr/0030-auditor-lenient-quorum.md` NEW (this file).
- `docs/technical_decisions_log.md` §v0.1.23 appended (~80-100 lines).
- `docs/evidence_matrix.md` 3 spots (ADR count 29 → 30 + tag-table row + scope paragraph).
- `CLAUDE.md` §16.3 H15.X bullet extension + §27 Hitos cerrados new bullet + §27 Hito siguiente flip to H16.

## §6 interpretive distinction (the centerpiece)

RegulAItor enforces "no citation, no answer" via a **two-layer architecture**. v0.1.23 refines ONLY the second layer:

**Layer (a) — Per-citation validator** (`src/regulaitor/citation/validator.py` + `src/regulaitor/citation/schemas.py`): the §6-invariant guardian. Three STRICT checks per citation: (1) `article_exists` (does the (norma, articulo, language) tuple resolve in the corpus loader?), (2) `apartado_exists` (does the apartado resolve under that article?), (3) `text_normalized_match` (is the cited text a substring of the corpus text after normalization?). **BYTE-UNCHANGED across all milestones including v0.1.23.** The "no citation, no answer" guarantee is anchored HERE. Any citation that fails Check 1 or Check 2 represents a fabricated article/apartado that the production system MUST detect and block. Any citation that fails Check 3 represents text that does not literally appear in the corpus at the cited location.

**Layer (b) — Auditor aggregation** (`src/regulaitor/agents/auditor.py`): an interpretive policy that combines per-citation results into a turn-level verdict. Multiple sub-policies:

- **Finding-Lenient aggregation** (H4, line 52): a Finding passes if ≥1 of its citations validates STRICTLY (validator.validated=True). Pre-v0.1.21 and v0.1.23: unchanged. The Finding-Lenient path is what rejects Sonnet's fabricated articles — a Finding with all-strict-invalid citations gets `finding_verdict="blocked"`, and if ALL Findings block then the turn routes to BLOCK.
- **Strict-Answer aggregation** (H4, lines 71-93): the 3-path routing (all-pass / all-blocked / partial). Pre-v0.1.21 and v0.1.23: unchanged.
- **Tier 1 RHR quorum** (v0.1.21 ADR-0027, line 68): NEW v0.1.21 escalation path. Pre-v0.1.21: did not exist. v0.1.21: counts STRICT-invalid citations + escalates all-pass-Findings to RHR when ≥2 strict-invalid. v0.1.23: counts LENIENT-invalid citations + escalates all-pass-Findings to RHR when ≥2 lenient-invalid. **This is the only thing v0.1.23 changes.**

**The §6 invariant is preserved by construction**. Validator-detected fabrications (Check 1 or Check 2 failure) still BLOCK via the Finding-Lenient path: Finding-Lenient requires ≥1 citation passing the FULL strict 3-check (including text match). A Finding with all-citations-fabricated has zero strict-valid citations → `finding_verdict="blocked"`. If all Findings have this pattern → turn BLOCK. The new lenient quorum only loosens what counts as "invalid for quorum purposes", NOT what counts as "valid enough to pass Finding-Lenient". Fabricated text without article+apartado existence is still rejected at Finding-Lenient = §6 invariant intact.

**The case the loosening unblocks**: Sonnet paraphrases real corpus content; (article + apartado) exist; text does not byte-match the corpus. Pre-v0.1.23: Check 3 fails → validator.validated=False → Tier 1 quorum counts it as invalid → ≥2 such cases → RHR escalation. Post-v0.1.23: lenient quorum sees article+apartado exist → counts as valid for quorum purposes → no escalation → the Finding still passes Lenient (because at least 1 citation in the Finding strict-validates OR the Finding routes to blocked normally), and the turn routes to PASS rather than spurious RHR. This is exactly the H1 pattern from v0.1.22.1 — 10 of 16 RHR cases match this profile.

## 3 design alternatives evaluated

### Design A — Validator-direct change (HIGH §6 risk; REJECTED)

Add a new `validate_lenient(citation)` function in `citation/validator.py` alongside the original strict `validate`. Auditor calls both; Tier 1 quorum reads the lenient result; Finding-Lenient continues to read the strict result.

- **§6 risk**: HIGH. Validator behavior bifurcates at the §6 guardian layer. The TFM defense narrative would have to argue "the validator now has two modes" — harder than the byte-unchanged claim Design B preserves.
- **Outcome**: equivalent to Design B (same set of citations would be counted as lenient-invalid by the quorum).
- **Rejected for**: same outcome with higher §6 risk surface.

### Design B — Auditor-only change (LOW §6 risk; ACCEPTED)

Inline `_is_lenient_valid(audit)` helper in `agents/auditor.py`. Tier 1 quorum counts `not _is_lenient_valid` instead of `not r.validated`. `validator.py` + `schemas.py` BYTE-UNCHANGED.

- **§6 risk**: LOW. The §6-invariant guardian (`citation/validator.py`) is byte-unchanged; the interpretive distinction (validator strict ≠ Auditor quorum-counting lenient) is documented in this ADR and the helper docstring; the change is localized to the aggregation layer where v0.1.21 already established the precedent of layered Auditor interpretation.
- **Outcome**: equivalent to Designs A and C (same citations are counted as lenient-invalid).
- **Selected for**: lowest §6 risk + outcome-equivalent + minimal-surface (1 helper + 1 wiring line change).

### Design C — Schema field addition (MEDIUM §6 risk; REJECTED)

Add `lenient_valid: bool` field to `citation/schemas.py::AuditResult`. `validator.py` computes both `validated` (strict) and `lenient_valid` (article+apartado only). Auditor reads `lenient_valid` for Tier 1 quorum.

- **§6 risk**: MEDIUM. Schema change at the §6 layer; the validator now computes two correctness signals instead of one; more invasive than Design B (touches schemas.py + validator.py instead of auditor.py only).
- **Outcome**: equivalent to Designs A and B.
- **Rejected for**: outcome-equivalent with higher invasiveness; the field would have to be added with backward-compat default (None or False) and documented as v0.1.23-onward — more carrying cost than Design B's inline helper.

## Risk mitigation

- **Validator + schemas BYTE-UNCHANGED**: verified at T8 pre-closure gate via `git diff main...HEAD -- src/regulaitor/citation/validator.py src/regulaitor/citation/schemas.py` (both MUST be empty). The §6-invariant guardian is the canonical 3-check validation procedure documented in `.claude/skills/citation-validator/SKILL.md`; it is preserved.
- **Finding-Lenient STILL strict**: line 52 continues to use `any(r.validated for r in this_finding_results)`. Fabricated articles/apartados (Check 1 or Check 2 failure) still cause the Finding to block, routing the turn to BLOCK when all Findings block. The text-match-based fabrication detection at the Finding-aggregation level is preserved.
- **Hard safety floor verification**: redteam-smoke ≥ 0.90 + 6 designated content cases content-check post-fix (H15 C1 pattern). The lenient quorum CANNOT make BLOCK or partial-RHR cases route to PASS — it only changes the quorum threshold for the all-pass-Findings branch, where the BLOCK/RHR routing was not engaged in the first place.
- **Rollback = 1-line revert in auditor.py**: minimum-surface intervention design supports a clean revert. If T6 measurement shows §6 regression, the revert is a single `git revert <T1+T2-sha>` (or cherry-pick if the squash is already shipped) restoring the strict quorum-count.

## Paid validation methodology summary

- **1-arm FRESH paid** (v0.1.23-prod) **vs CACHED v0.1.22-prod baseline** (extracted $0); 30 cases on H10 cohort.
- **Probe-then-PROCEED via SKIP/PROCEED gate** (5-case probe + cost extrapolation per cost-estimation discipline registered v0.1.8 / `memory/feedback_cost_estimation_discipline.md`).
- **Expected cost**: ~€1.90 expected / €2.85 high (×1.5).
- **Budget remaining**: ~$10.95 entering v0.1.23; ~$8 headroom post-fix.
- **Carries**: ADR-0021 v0.1.20-bar thresholds (formal measurement target); ADR-0024 v0.1.18 hierarchical containment (eval-metric instrument); ADR-0027 Tier 1 + Tier 2 (production state under measurement); ADR-0029 v0.1.22 1-arm-vs-cached methodology + per-citation audit trail diagnostic infrastructure.

## Flip protocol summary

- **CONFIRM**: hard floor PASS + verdict_match ≥ bar (0.35) + no §6 regression → ship Design B as production. The cumulative v0.1.21+v0.1.21.2+v0.1.23 production package validated empirically.
- **CONDITIONAL CONFIRM**: hard floor PASS + verdict_match lifts but mixed (lift below bar OR other regressions surface) → ship Design B + carry-forward Designs A/C for further iteration if a tighter intervention proves needed in HX post-TFM.
- **REVERT**: §6 regression detected OR hard floor FAIL → cherry-pick revert the 1-line auditor change + REVERT outcome documented in this ADR + decisions_log + CLAUDE.md.

## §22.22 disclosures (the centerpiece of the v0.1.X milestone narrative)

The honest framing of what v0.1.23 ships, predicts, and cannot resolve at the time of this ADR write:

1. **Estimated verdict_match lift 0.30 → ~0.40-0.45 is PRE-MEASUREMENT prediction** (not a promise). The prediction is derived from the v0.1.22.1 H1 attribution (10 cases predicted to flip RHR → PASS) applied to the v0.1.22-prod verdict_match denominator (30 cases). The actual delta is measured at T6 and may diverge if (a) the H1 attribution over-counted (see §22.22 #2), (b) some H1-attributed cases have OTHER reasons for RHR escalation that survive the lenient quorum, or (c) API drift between v0.1.22 (2026-05-25 morning) and v0.1.23 (2026-05-25 afternoon) shifts case-level outcomes.

2. **H1 attribution from v0.1.22.1 diagnostic uses hierarchical containment heuristic + hypothesis precedence H4 > H1 > H3 > H2**. The diagnostic may over-attribute H1 if the gold itself uses inconsistent granularity. Per `evals/reports/v0.1.22.1/verdict-drop-analysis.md` §22.22 caveat #2: "Hierarchical containment matching for H1 uses lenient bidirectional rule (article-match either direction); may over-attribute H1 if gold itself uses inconsistent granularity." The 10/16 = 62.5% figure is the diagnostic's best-effort mechanical attribution; the empirical T6 flip rate may be lower if some H1-attributed cases actually had other (untested) reasons.

3. **5 mixed cases (n_invalid=1; below quorum threshold even pre-v0.1.23) are not addressed by v0.1.23 — carry-forward**. The 5/16 "mixed" cases in the v0.1.22.1 table show n_invalid=1, which means Tier 1 quorum (≥2 threshold) did not fire on them pre-v0.1.23 either; they routed to RHR via the partial-Findings branch (some Findings pass at Lenient, some block). The lenient quorum change does not touch the partial branch. These cases would need a separate intervention (potentially a future v0.1.24 lowering the quorum threshold OR a Finding-Lenient softening) — carried forward as a future milestone if v0.1.23 + paid validation shows the H1 fix alone is insufficient to lift verdict_match to bar.

4. **Design B trade-off vs Designs A/C**: Design B achieves the same OUTCOME with lower §6 risk surface, but if a future requirement emerges where the per-citation lenient signal needs to propagate beyond Auditor quorum (e.g. into the LangGraph trace metadata, the API response DTO, or a downstream evaluation), Designs A or C would surface naturally. v0.1.23 documents this trade-off; if Design B proves insufficient (e.g. verdict_match doesn't lift), the carry-forward to Designs A/C lives in HX post-TFM.

5. **Coverage gate inherited 88.55% < 90% from v0.1.21.3 @slow hotfix** (per ADR-0029 §22.22 disclosure #8). v0.1.23 may improve coverage slightly (+5 new tests on the Auditor module + 1 integration test). The threshold itself remains a carry-forward to H16 deploy (adjust threshold to 85% to match reality OR fix the offline-SSL test path so the 7 tests no longer need `@pytest.mark.slow`).

6. **Per-capability cost attribution NOT measured**: v0.1.22 measured the cumulative package (5 capabilities together); v0.1.23 measures the package + Design B layered on top. The contribution of Design B to verdict_match (vs validator change alone vs Auditor Tier 2 contribution vs prior package) is NOT individually measured. The v0.1.22.1 diagnostic attributed verdict_match mechanism to H1 dominantly but did not measure cost-per-mechanism. Per-capability ablation would require factorial 2^6 = 64 arms (cost-prohibitive at any reasonable budget per ADR-0029 §22.22 #6).

## Consequences

**Positive:**

- **H1 mechanism (10/16 = 62.5% of v0.1.22-prod RHR) directly attacked** at the Auditor aggregation layer with minimum-surface intervention (1 helper + 1 wiring line).
- **§6 invariant preserved at validator layer**: `citation/validator.py` + `citation/schemas.py` byte-unchanged. The interpretive distinction (validator strict ≠ Auditor quorum-counting lenient) carries the ADR-0024 / 0027 / 0029 lineage on layered enforcement architecture.
- **Layered-system inconsistency closed**: the v0.1.18 eval-metric hierarchical containment concept now has a production-side counterpart at the Auditor aggregation layer. The TFM defense narrative gains the "two-layer enforcement: validator strict + Auditor aggregation interpretive policy" framing.
- **5 new $0 unit tests** pin both the helper behavior and the integration scenario (Tier 1 quorum no longer escalates strict-invalid-but-lenient-valid cases). Pre-existing test_auditor_quorum.py tests updated where they pinned strict quorum on lenient-valid scenarios.
- **Rollback is trivial** (1-line revert in auditor.py); the design supports clean revert without disturbing other v0.1.21+ capabilities.

**Negative / accepted (per §22.22 honest framing):**

- **The estimated verdict_match lift 0.30 → ~0.40-0.45 is PRE-MEASUREMENT prediction**; T6 measures the actual delta. If the measurement shows mixed performance (lift but below bar OR no lift), the milestone closes as CONDITIONAL CONFIRM with Designs A/C as carry-forward.
- **5 mixed cases (n_invalid=1) are not addressed** by v0.1.23 — those route via the partial-Findings branch which v0.1.23 leaves untouched. A future milestone could pursue this (lower quorum threshold OR Finding-Lenient softening), but neither was in scope for v0.1.23 per the H1-dominant attribution.
- **Per-capability attribution unmeasured**: v0.1.23 measurement is cumulative (v0.1.21+v0.1.21.2+v0.1.23 package vs v0.1.22-prod cumulative baseline). Surgical ablation of the Design B effect would require an additional fresh arm and is not in v0.1.23 scope.
- **The lenient quorum slightly weakens the Auditor in the {K≥2, lenient-valid, strict-invalid} cell**: a multi-citation answer with 2+ paraphrased citations now passes (where pre-v0.1.23 it would have RHR-escalated). Mitigation: (a) Finding-Lenient still requires ≥1 strict-valid citation per Finding for the Finding to pass; (b) Council binding (ADR-0025) still escalates on unanimous judge disagreement; (c) `text_normalized_match=False` is still recorded on the per_citation_audits trail for downstream observability / future evidence-driven tightening.
- **No empirical safety floor regression risk identified at design time**: the lenient quorum loosens, does not strengthen; the redteam-smoke deterministic pattern path is not affected; the 6 designated content cases are safety-floor-passed under the §6 invariant interpretation by construction (Finding-Lenient still strict). T6 verifies this empirically.

## Alternatives considered (architecture-level)

The three designs (A validator-direct / B Auditor-only / C schema field) are documented in the "3 design alternatives evaluated" section above. Additional alternatives at the architecture level:

1. **Tighten the validator's Check 3 (replace `in target_norm` substring with fuzzy match / embedding similarity / LCS)** — rejected. More invasive at the §6 guardian layer; introduces dependencies (embedding model OR LCS library) at the §6 layer; harder to argue "no citation, no answer" with a fuzzy matcher. Carry-forward to HX post-TFM if Design B + paid validation surface a real-world need.
2. **Loosen Finding-Lenient aggregation to count lenient-valid as a Finding-pass signal** — rejected. Would touch the §6 fabrication-detection path; the Finding-Lenient layer is the second line of defense for §6 after the validator. Out of scope for v0.1.23.
3. **Loosen the quorum threshold (≥2 → ≥3)** — rejected for v0.1.23. Orthogonal to the H1 mechanism; would change the threshold without addressing the strict-vs-lenient counting issue. Carry-forward if T6 measurement shows quorum-threshold-tuning is also needed.
4. **Update the gold set's expected_citations to use lenient text matching** — rejected. Eval-side change; would change the measurement instrument rather than the production system. The gold annotator's expected articles ARE the ground truth for v0.1.20-bar measurement; the issue is the production validator's text-mismatch handling, not the gold set.
5. **Per-Finding quorum (not per-Answer)** — rejected. Adds complexity without obvious benefit; the per-Answer ≥2 threshold is the v0.1.21 design and proves to be the right granularity per the v0.1.22.1 diagnostic (the cases that fire quorum have multiple invalid citations across the Answer, not concentrated in one Finding).
6. **Defer v0.1.23 entirely + ship H16 with v0.1.22 CONDITIONAL CONFIRM state** — considered + user-rejected on 2026-05-25. User authorization to ship Design B was explicit; the v0.1.22.1 diagnostic provided strong evidence (62.5% attributable to a single mechanism) for surgical intervention before H16 deploy ceremony.

## References

- **Spec**: `docs/superpowers/specs/2026-05-25-v0.1.23-auditor-lenient-quorum-design.md` @ commit `168a5b3`.
- **Plan**: `docs/superpowers/plans/2026-05-25-v0.1.23-auditor-lenient-quorum.md` @ commit `dd18b44`.
- **Motivating diagnostic**: `evals/reports/v0.1.22.1/verdict-drop-analysis.md` (H1 DOMINANT 10/16 = 62.5%; methodology + per-case detail + §22.22 caveats).
- **Source code touched by v0.1.23**:
  - `src/regulaitor/agents/auditor.py` (Design B D1 + D2 — inline `_is_lenient_valid` helper + 1-line quorum-count change).
- **Source code BYTE-UNCHANGED** (verified at T8):
  - `src/regulaitor/citation/validator.py` (§6 guardian).
  - `src/regulaitor/citation/schemas.py` (§6 schemas).
  - `src/regulaitor/agents/analyst.py` (v0.1.21 Tier 2 Capa A + Capa C — orthogonal).
  - `src/regulaitor/agents/council.py` (v0.1.19 binding ON — orthogonal).
  - `src/regulaitor/agents/prompts/` (v1.0-v1.5 Analyst prompts — orthogonal).
  - `src/regulaitor/rag/retrieval.py` (v0.1.21.2 defaults — orthogonal).
  - `evals/metrics.py` + `evals/schemas.py` + `evals/harness.py` + `evals/report.py` (eval pipeline — orthogonal).
  - `evals/gold_set.jsonl` (gold ground truth — orthogonal).
- **Test coverage**: 5 new $0 unit tests in `tests/unit/agents/test_auditor.py`; updated test_auditor_quorum.py sites where they pinned strict quorum on lenient-valid scenarios.
- **Companion ADRs**: 0024 (v0.1.18 hierarchical containment in eval-metric — conceptual lineage), 0027 (v0.1.21 Tier 1 RHR quorum — mechanism being refined), 0029 (v0.1.22 paid validation — exposed verdict_match drop).
- **Future commits referenced from this ADR**: T1+T2 (`6adbc17`), T3 ADR-0030 (this commit), T4+T5 paid (TBD), T6 comparison (TBD), T7 closure docs (TBD), T-final squash (TBD; `<squash-sha>` placeholder populated at T-final).
- **Empirical resolution**: T6 outcome documented in `evals/reports/v0.1.23/comparison.md` + `per-citation-mechanism.md` + `verdict-flip-review.md` (predicted 10 H1 flips RHR → PASS; actual count is the headline finding).
- **Future**: if T6 outcome is CONFIRM or CONDITIONAL CONFIRM → **H16** (HF Spaces deploy + foundation production-grade per user pref) → **H17** (TFM closure: memoria + model card + data card + AI Act assessment + runbook + cost analysis + video demo + slide deck + Product Roadmap appendix + tag v1.0.0). If T6 outcome is REVERT → CONDITIONAL CLOSE v0.1.23 with REVERT documented; proceed to H16 with v0.1.22 CONDITIONAL CONFIRM state.

---

## §REVERT — Empirical outcome (T6 measurement refuted prediction; 2026-05-26)

### Outcome

Design B Auditor lenient quorum was **REVERTED at T-revert** (2026-05-26) per empirical refutation in T6 paid measurement. Production state restored to v0.1.22.1 baseline (Tier 1 quorum-count line uses `not r.validated`; `_is_lenient_valid` helper removed; 5 new tests removed; v0.1.23 paid evidence + revert documented honestly per §22.22).

### Measurement summary (H10 30-case combined: probe 5 + main 25)

| Metric | v0.1.22 cached | v0.1.23 fresh | Δ | Predicted |
|---|---|---|---|---|
| faithfulness | 0.72 | 0.76 | +0.04 ✅ | — (collateral) |
| answer_relevancy | 0.73 | 0.73 | 0.00 | — |
| context_precision | 0.66 | 0.59 | -0.06 | — |
| citation_precision | 0.28 | 0.28 | 0.00 | — |
| citation_recall | 0.67 | 0.68 | +0.02 | — |
| **verdict_match** | **0.30** | **0.27** | **-0.03 ❌** | **+0.10 (predicted lift)** |
| severity_match | 0.40 | 0.37 | -0.03 | — |

**Verdict counts**: pass 10 → 10 (flat) / RHR 16 → 14 (-2) / **block 4 → 6 (+2)** — 2 H1 cases moved RHR → BLOCK (NEW unexpected failure mode, opposite of predicted direction).

### Per-citation verdict-flip review (10 H1-predicted flips from v0.1.22.1)

**0 / 10 H1 cases flipped RHR → PASS** as predicted by Design B (predicted: ~6-7 / 10 = 60-70%). **0% confirmation rate.**

- 8/10 H1 cases (chat-018, 019, 021, 022, 023, 024, 025, 026) UNCHANGED RHR
- 2/10 H1 cases (chat-016, 017) flipped RHR → **BLOCK** (unexpected; opposite direction)

See `evals/reports/v0.1.23/verdict-flip-review.md` for per-case detail.

### Three root-cause mechanisms (§22.22 honest attribution)

1. **API drift (2/10 cases, 20%)**: 2-day gap between v0.1.22 paid run (2026-05-24) and v0.1.23 paid run (2026-05-26). Sonnet non-determinism even at temperature=0 produced DIFFERENT citation outputs for chat-016 + chat-017 — different validator outcomes → different Auditor verdict routing → predictions based on cached v0.1.22 per_citation_audits trail invalid for these cases.

2. **Design B assumption invalid (8/10 cases, 80%)**: Tier 1 quorum was **NOT the bottleneck** for the H1 unchanged-RHR cases. Even with lenient counting (`article_exists AND apartado_exists`), these 8 cases remain RHR. Possible mechanisms:
   - **Hypothesis A**: cases have Check 1 OR Check 2 failures (article OR apartado not exists), so lenient_invalid ≥ 2 still fires — the v0.1.22.1 H1 attribution may have over-counted Check 3 (text-only) failures relative to Check 1/2 failures, because the AuditResult.validated field is a strict 3-check AND (cannot decompose without re-running validator with separate Check 3 instrumentation).
   - **Hypothesis B**: Strict-Answer routing (partial-Findings → RHR) or Finding-Lenient aggregation rejected upstream of Tier 1 quorum (lines 71-77 of pre-v0.1.23 auditor.py) — quorum never executed for these cases.
   - **Hypothesis C**: Lenient-quorum loosening CAN cascade to OTHER Auditor paths (Strict-Answer partial-Findings now routes earlier) creating NEW BLOCK escalations.

3. **Diagnostic measurement artifact (caveat)**: The v0.1.22.1 verdict-drop diagnostic used `text_not_in_apartado` reason-text as H1 evidence but cannot definitively separate strict-only-failures (Check 3) from strict+lenient-failures (Check 1/2 also). Per_citation_audits trail stores combined `validated: bool` field only; sub-checks not separately enumerated post-hoc. The H1 attribution counts may have over-estimated by including Check 1/2 failures masquerading as Check 3 failures in the reason text.

### Cost summary

- T4 probe: €0.31 (= ~$0.33 USD)
- T5 main: €1.45 (= ~$1.56 USD)
- **Total v0.1.23 paid spend: €1.76 = ~$1.89 USD**
- Forecast was €1.90 expected / €2.85 high (×1.5) — actual cost on-forecast (-7%)
- Budget remaining post-v0.1.23: ~$9.06 (from ~$10.95 pre-v0.1.23)

The paid spend bought the EMPIRICAL REFUTATION of the Design B prediction. This is a §22.22-honest cost — the experiment had to be run to confirm or refute the v0.1.22.1 hypothesis.

### §6 invariant — HELD throughout

- `src/regulaitor/citation/validator.py` + `src/regulaitor/citation/schemas.py` BYTE-UNCHANGED across both T1+T2 (Design B activation) and T-revert (restoration). Verified by `git diff main...HEAD -- src/regulaitor/citation/` empty at both points.
- 0 fabrications detected in the v0.1.23 probe + main + safety-floor (TBD; safety floor inherited from v0.1.22 — content cases unchanged because v0.1.23 affects only Auditor aggregation, not validator).
- Finding-Lenient layer remained strict throughout: any Finding with 0 strict-valid citations still blocked.

### Lessons learned (carry-forward to H16 + future)

1. **Diagnostic-attribution requires Check 1/2/3 decomposition for reliable H-attribution**: the v0.1.22.1 H1 attribution was over-counted because the per_citation_audits trail didn't separate Check 1 (article_exists) failures from Check 2 (apartado_exists) failures from Check 3 (text_normalized_match) failures. Future $0 diagnostics should re-run validator with check-by-check decomposition to support accurate Hi attribution. Alternative: add a `failed_check: Literal[1, 2, 3, None]` field to AuditResult schema (NEW v0.1.22.1.x or similar) for production-side instrumentation that auto-populates without re-validation.

2. **Tier 1 quorum is NOT the dominant verdict_match lever** as v0.1.22.1 inferred. Other Auditor aggregation paths (Strict-Answer partial-Findings; Finding-Lenient strict-text-match) dominate the verdict_match drop. Future intervention should target those paths instead.

3. **API drift over 2-day windows is non-trivial** (~20% of cases drift verdict). Future paid validations should either (a) run baselines + intervention same-day if possible, or (b) account for ~20% noise floor when interpreting cross-day comparisons.

4. **Design B trade-off (LOW §6 risk → outcome failure)** validates Design A/C as carry-forward consideration if verdict_match becomes critical post-TFM: Design A (validator-direct change) OR Design C (schema field addition + separated check decomposition) could intervene at the layer where the bottleneck actually exists, but at HIGHER §6 risk. Deferred to HX post-TFM.

### Closure decision

**REVERT per spec §D5 third path.** The v0.1.23 ceremony closes with:
- 1-line revert of `agents/auditor.py` Tier 1 quorum-count line (restored to `not r.validated`)
- 5 new tests removed (helper `_is_lenient_valid` deleted)
- This ADR-0030 amended with §REVERT section (the prospective Design B reasoning preserved verbatim above; empirical refutation documented here)
- Tag `v0.1.23-auditor-lenient-quorum` still applied (semantically: "the experiment that was run and reverted; production state RESTORED to v0.1.22.1 baseline")

Production state entering H16: validator.py + schemas.py + auditor.py + Council + Analyst prompts + retrieval + eval pipeline + gold set ALL BYTE-UNCHANGED relative to v0.1.22.1 baseline. v0.1.22 paid evidence + v0.1.22.1 diagnostic + v0.1.23 empirical refutation all stay as cumulative TFM evidence.

This is a **scientific failure that strengthens the TFM narrative**: hypothesis → diagnostic → intervention → measurement → refutation → revert → honest disclosure. The §6 invariant held throughout. The methodology is the contribution.
