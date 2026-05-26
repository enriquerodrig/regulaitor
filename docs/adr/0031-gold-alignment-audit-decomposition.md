# ADR 0031 — Gold alignment + AuditResult decomposition (v0.1.24)

- **Status:** Accepted — 2026-05-26 — squash `<squash-sha>`, tag `v0.1.24-gold-alignment-decomposition`
- **Deciders:** controller + project owner (low-risk recovery path chosen 2026-05-26 post-v0.1.23 REVERT).
- **Companion ADRs:** 0024 (v0.1.18 hierarchical containment in eval-metric — the conceptual lineage; v0.1.24 O2 mirrors the same decomposition concept at the AuditResult schema layer that v0.1.18 applied at the eval-metric layer; v0.1.24 O1 layers on top of the same eval-metric instrument with a per-case opt-in for the gold-vs-production-behavior mismatch), 0025 (v0.1.19 Council binding ON — production state inherited; unchanged), 0027 (v0.1.21 Tier 1 RHR quorum + Tier 2 Capa A+B+C — production state inherited; unchanged), 0029 (v0.1.22 paid validation — exposed verdict_match drop that motivated v0.1.22.1 + v0.1.23 + v0.1.24 lineage), 0030 (v0.1.23 Design B Auditor lenient quorum REVERTED per empirical refutation; the REVERT lessons learned drive v0.1.24's low-risk pre-intervention scope).

## Context

ADR-0030 closure shipped v0.1.23 as **REVERT**: Design B Auditor lenient quorum was reverted at T-revert (2026-05-26) per T6 empirical refutation. 0/10 H1 cases flipped RHR → PASS (predicted ~6-7 / 10); 2/10 flipped RHR → BLOCK (unexpected, opposite direction); 8/10 unchanged. Two carry-forwards emerged from the REVERT post-mortem:

1. **Check decomposition needed for accurate H-attribution**: the v0.1.22.1 diagnostic used `text_not_in_apartado` reason-text as H1 evidence but the per_citation_audits trail stores only a combined `validated: bool` — Check 1 (article_not_exists), Check 2 (apartado_not_exists), and Check 3 (text_not_match) failures cannot be separated post-hoc. The H1 attribution likely OVER-COUNTED because Check 1/2 failures (true fabrications, NOT addressable by an aggregation-layer change) were conflated with Check 3 failures (paraphrase-mismatch territory, the only ones a v0.1.23-Design-B-like change could address).
2. **Tier 1 quorum is NOT the dominant verdict_match lever** as v0.1.22.1 inferred. Other Auditor aggregation paths (Strict-Answer partial-Findings; Finding-Lenient strict-text-match) dominate the verdict_match drop. Future intervention should target those paths instead — but only after an accurate decomposition rules out the Check 1/2 fabrications first.

In parallel, a **measurement-instrument-vs-production-behavior mismatch** accumulated across milestones for 6 designated content-safety cases (chat-014, chat-015, chat-029, chat-030, nis2-006, dora-006): gold expected `block`, but v1.5 production (shipped at v0.1.21 final review C4 fix) emits a corpus-grounded refusal Finding that the Lenient-Finding path validates and routes to `pass`. v0.1.22 T6 safety-floor controller-manual review confirmed all 6 cases content-SAFE (18/18 judge criteria PASS + 0/6 fabrications + 6/6 explicit rejection). 5/6 of these mechanically fail `verdict_match` despite content-safe outcome.

v0.1.24 ships **two LOW-risk additive interventions** under a single ADR for cohesion. O1 closes the gold-vs-behavior mismatch via per-case `acceptable_verdicts` opt-in (~+0.17 expected verdict_match lift on cached H10 cohort, immediate). O2 closes the H-attribution measurement gap via additive `failed_check` field on `AuditResult` (instrumentation enabling correct v0.1.25+ intervention). Neither directly intervenes on the verdict_match drop's underlying MECHANISM — that targeted intervention is deferred to v0.1.25+ once O2 surfaces the real bottleneck.

## Decision

### D1 — O1 implementation: `acceptable_verdicts` field on `GoldCaseChat`

`evals/schemas.py`: extend `GoldCaseChat` with `acceptable_verdicts: list[str] | None = None`. Backward-compat default `None` preserves the pre-v0.1.24 single-value `expected_verdict` semantics.

`evals/metrics.py::compute_chat_metrics`: branch verdict_match computation on the field — if `case.acceptable_verdicts is not None`, match if `actual_verdict in case.acceptable_verdicts`; else fall back to the single-value `expected_verdict == actual_verdict` comparison. Six designated content-safety cases (chat-014, chat-015, chat-029, chat-030, nis2-006, dora-006) get `"acceptable_verdicts": ["block", "requires_human_review", "pass"]` in `evals/gold_set.jsonl`. The `expected_verdict: "block"` is retained as canonical-preferred-outcome documentation.

### D2 — O2 implementation: `failed_check` field on `AuditResult`

`src/regulaitor/citation/schemas.py`: extend `AuditResult` with `failed_check: Literal[1, 2, 3] | None = None`. Backward-compat default `None`; existing cached pre-v0.1.24 AuditResults load with the field absent (Pydantic v2 handles missing optional fields gracefully).

`src/regulaitor/citation/validator.py::validate`: populate `failed_check` on each fail-fast return — Check 1 fail → `failed_check=1`, Check 2 fail → `failed_check=2`, Check 3 fail → `failed_check=3`, all-pass → `failed_check=None`. Validation SEMANTICS byte-equivalent (see §6 interpretive evolution section below): same fail-fast order, same `validated` bool, same `article_exists` + `apartado_exists` + `text_normalized_match` + `reason` fields. Only NEW observable is `failed_check`.

### D3 — Tests: 10 new $0 unit tests pinning both additions

**O1 tests** (5 new in `tests/unit/evals/`):
1. `test_gold_case_chat_acceptable_verdicts_optional_field` — schema default None.
2. `test_compute_chat_metrics_uses_acceptable_verdicts_when_set` — multi-value match.
3. `test_compute_chat_metrics_uses_expected_verdict_when_acceptable_verdicts_none` — backward-compat single-value.
4. `test_chat_014_gold_case_has_acceptable_verdicts` — gold data verify.
5. `test_compute_chat_metrics_acceptable_verdicts_set_matches_any_value` — integration.

**O2 tests** (5 new in `tests/unit/test_citation_validator.py`):
1. `test_audit_result_failed_check_optional_field_default_none` — schema default.
2. `test_validator_populates_failed_check_1_when_article_not_exists`.
3. `test_validator_populates_failed_check_2_when_apartado_not_exists`.
4. `test_validator_populates_failed_check_3_when_text_not_match`.
5. `test_validator_failed_check_none_when_all_checks_pass`.

Baseline 962/0/1 + 10 new = 972/0/1 expected at the pre-closure gate.

### D4 — $0 re-aggregation on cached data (methodology)

After D1+D2 ship, two scripts run $0 on cached evidence:

- `scripts/v0124_re_aggregate.py` re-aggregates v0.1.22-prod (combined probe + main, 30 cases) and v0.1.23-prod (combined probe + main, 30 cases) verdict_match with the new `acceptable_verdicts` logic. Per-case delta surfaces which of the 6 designated cases flip `❌ → ✅` under the relaxed matching.
- `scripts/v0124_decomposition_diagnostic.py` re-runs v0.1.22.1 H-attribution with `failed_check` decomposition. Since cached v0.1.22 AuditResults predate the schema field, the script re-derives `failed_check` from the `reason` text already present in `per_citation_audits` (`article_not_found` → 1, `apartado_not_found` → 2, `text_not_in_{apartado|article}` → 3). Per-case Check 1/2/3 distribution reattributes the v0.1.22.1 H1 cases into three sub-buckets:
  - H1.A: dominant Check 1 fails (article fabrication; true §6-relevant; aggregation-layer intervention CANNOT help).
  - H1.B: dominant Check 2 fails (apartado fabrication; true §6-relevant; aggregation-layer intervention CANNOT help).
  - H1.C: dominant Check 3 fails (paraphrase-only mismatch; the actual v0.1.18-hierarchical-containment-territory; aggregation-layer or eval-metric-side intervention CAN help).

Outputs land in `evals/reports/v0.1.24/`:
- `verdict-match-re-aggregation.md` — O1 outcome.
- `decomposition-h-attribution.md` — O2 outcome.

NO paid LLM runs. NO checkpoint changes. NO Sonnet replay.

### D5 — ADR-0031 single-ADR scope

Single ADR documenting both interventions for cohesion (mirror ADR-0027 / 0029 / 0030 single-ADR-multi-decision precedents). Both interventions share the same context (post-v0.1.23 REVERT recovery), the same §6 interpretive evolution (the centerpiece below), and the same §22.22 framing (alignment + instrumentation, not improvement claims).

## §6 interpretive evolution (the centerpiece)

This is the FIRST milestone where the `src/regulaitor/citation/` source tree is no longer byte-unchanged. Past milestones (ADR-0027, 0029, 0030 verbatim) claimed:

> `src/regulaitor/citation/validator.py` + `src/regulaitor/citation/schemas.py` **byte-unchanged** (the §6-invariant guardian remains the canonical 3-check validation procedure).

v0.1.24 BREAKS that streak on the literal byte-equality claim:

- `src/regulaitor/citation/schemas.py` gains a new optional field on `AuditResult` (`failed_check: Literal[1, 2, 3] | None = None`).
- `src/regulaitor/citation/validator.py` gains 4 field-assignment lines in the existing fail-fast returns (Check 1 fail → `failed_check=1`; Check 2 fail → `failed_check=2`; Check 3 fail → `failed_check=3`; all-pass → `failed_check=None`).

The §6 invariant statement evolves from **"byte-unchanged"** to **"byte-equivalent validation semantics + additive observability field"**. The interpretive distinction is precise and load-bearing:

1. **Validation SEMANTICS preserved**: same 3-check sequence executed in the same order with the same fail-fast on the first failing check. The `validated: bool` returned to the Auditor is the same value for every (citation, corpus) pair pre/post v0.1.24. The `article_exists` + `apartado_exists` + `text_normalized_match` + `reason` fields are unchanged in name, type, and computed value.
2. **Rejection behavior preserved**: the validator still rejects fabricated articles at Check 1, fabricated apartados at Check 2, and text mismatches at Check 3. No citation that previously failed now passes; no citation that previously passed now fails.
3. **The §6 enforcement is unchanged**: "no citation, no answer" continues to operate via the validator's strict checks at exactly the same boundary. The Auditor's Finding-Lenient + Strict-Answer aggregation reads the same `validated` field with the same semantics.
4. **The new field is pure INSTRUMENTATION**: `failed_check` is a post-hoc observation of which check fired first. It is not in the decision path; no Auditor branch reads it; no downstream code conditionally behaves on it. It exists for future $0 diagnostics (the v0.1.25+ correct-intervention selection in particular).
5. **Backward-compat at the schema layer**: existing cached `AuditResult` objects load with `failed_check=None` (Pydantic v2 default for missing optional fields). The cached v0.1.22-prod + v0.1.23-prod checkpoints + judge cache continue to deserialize without modification.

This is the cleanest §6-evolution path among the three options considered for O2 (see Alternatives below). Design A (validator-direct check decomposition into separate functions) would have bifurcated the validator's surface and weakened the "single source of §6 truth" framing. Design C (re-run validator with check-instrumented mock on cached data) would have been cost-prohibitive AND non-deterministic — Sonnet outputs change between runs even at temperature=0 per the v0.1.23 §REVERT root-cause #1 (API drift), so a re-validation pass would not faithfully reproduce the original failed_check distribution.

## 3 alternatives evaluated for O1

### Option A — `acceptable_verdicts: list[str] | None` field on `GoldCaseChat` (ACCEPTED)

Additive optional field; default None preserves backward-compat; `compute_chat_metrics` branches on the field. Per-case opt-in; only the 6 designated cases affected; gold maintains `expected_verdict: "block"` as canonical-preferred documentation.

- **Pros**: minimal-surface schema change; backward-compat default; transparent per-case opt-in (anyone reading `gold_set.jsonl` sees which cases are loosened and why); the canonical `expected_verdict` is preserved for documentation purposes; reverts cleanly (drop the field; remove the metric branch).
- **Cons**: introduces a new field on `GoldCaseChat` that downstream consumers must learn about; eval-side change rather than production-side fix; v0.1.18 eval-instrument precedent applies (precedent: changing the measurement to align with reality is legitimate when production behavior was deliberately chosen).

### Option B — Edit `expected_verdict` directly to `"pass"` for the 6 cases (REJECTED)

Same observable effect but simpler — change the 6 gold lines' `expected_verdict` from `"block"` to `"pass"`.

- **Rejected for**: loses the canonical-preferred-outcome documentation. The gold author originally chose `block` because the design intent was a hard rejection at the Auditor layer (pre-v1.5 era). v1.5's corpus-grounded refusal-Finding is a DIFFERENT-but-equivalent safe behavior; documenting both as acceptable preserves the design intent visible while aligning measurement with reality. Future readers of `gold_set.jsonl` would lose the historical context of "this was a safety case originally requiring block; v1.5 routes through pass via refusal-Finding".

### Option C — Special-case logic in `compute_chat_metrics` keyed on hardcoded case IDs (REJECTED)

`if case_id in {"chat-014", "chat-015", ...}: verdict_match = actual in {"pass", "block", "requires_human_review"}`.

- **Rejected for**: hidden anti-pattern. The logic lives in code, not in data; future contributors editing `gold_set.jsonl` would not see why these cases are treated differently; adding a 7th case requires both a gold edit AND a code edit (two-place change). Option A is the same logic but data-driven.

## 2 alternatives evaluated for O2

### Option A — Re-run validator with check-instrumented mock on cached data (REJECTED)

Patch `citation/validator.py` temporarily to return separately-typed check failures; replay every cached citation through the patched validator; record the per-check distribution.

- **Rejected for**: two compounding problems. (a) Cost-prohibitive: replaying ~150 cached citations through validator at non-trivial Sonnet+retrieval cost (production validator is local-only Python over the loader, but replaying the FULL prod chain to test that the cached citations were what the prod system produced would require paid replay). (b) Non-determinism: per the v0.1.23 §REVERT root-cause #1 (API drift), Sonnet outputs differ between runs even at temperature=0; the original cached citations are no longer the citations a fresh run produces. A replay measures the new state, not the cached state — which defeats the diagnostic purpose.

### Option B — Add `failed_check: Literal[1, 2, 3] | None` field to `AuditResult` schema (ACCEPTED)

Additive optional field on `AuditResult`; validator populates first-failing check on fail-fast return; backward-compat default None for cached pre-v0.1.24 results; future runs have decomposition by default; cached pre-v0.1.24 runs are decomposed by the `v0124_decomposition_diagnostic.py` script via reason-text mapping (`article_not_found` → 1, `apartado_not_found` → 2, `text_not_in_*` → 3).

- **Pros**: cleanest §6 interpretive evolution (validation semantics byte-equivalent + additive observability); cheap (no paid replay); backward-compat default; reason-text mapping resolves the cached-data decomposition $0; future $0 diagnostics get correct decomposition for free; instrumentation is "free" once the validator runs in production going forward.
- **Cons**: breaks the literal "byte-unchanged" claim past milestones made; requires honest §6 interpretive evolution (this centerpiece section); the reason-text mapping for cached data is heuristic (depends on the validator's exact error-message strings, which past milestones have not pinned in tests — the script verifies the mapping against the current validator outputs).

## §22.22 disclosures (the centerpiece)

The honest framing of what v0.1.24 ships, predicts, and explicitly does NOT resolve:

1. **O1 is ALIGNMENT, NOT IMPROVEMENT.** The verdict_match lift from re-aggregation (~+0.17 expected) is a measurement-instrument fix — the gold now accepts what production was already doing safely. Underlying production behavior is unchanged. The TFM defense narrative for O1 is "we corrected a measurement-vs-behavior mismatch", NOT "we made the system more accurate". The lift is real on the gated metric; the underlying capability is the same as v0.1.22 + v0.1.23.

2. **O2 is OBSERVABILITY, NOT FIX.** Adding `failed_check` to AuditResult does not change a single verdict. It does not improve a single citation. It enables future $0 diagnostics to correctly attribute H-buckets, so the v0.1.25+ targeted intervention can be selected with high confidence. v0.1.24 itself does not fix the verdict_match drop's underlying mechanism.

3. **v0.1.22.1 H1 attribution was likely OVER-COUNTED.** The diagnostic used `text_not_in_apartado` reason-text as H1 evidence but cannot definitively separate strict-only-failures (Check 3) from strict+lenient-failures (Check 1 / 2). T4 decomposition re-attributes the 10 H1-attributed cases accurately. The v0.1.23 REVERT lessons explicitly anticipated this (§REVERT root-cause Hypothesis A); the v0.1.24 decomposition resolves it empirically.

4. **v0.1.24 sets up v0.1.25+ targeted intervention at the REAL bottleneck identified by O2.** If decomposition shows H1.C dominant → a Finding-Lenient text-match softening (or eval-side hierarchical containment propagation to the Auditor) is the candidate. If H1.A or H1.B dominant → Strict-Answer partial-Findings routing is the candidate (or the gold itself has wrong expected articles — see §22.22 #2 of the v0.1.22.1 diagnostic). If mixed → multiple sub-interventions. The empirical answer drives the selection.

5. **Re-aggregation on cached data has an API-drift caveat.** v0.1.22-prod cached on 2026-05-24; v0.1.23-prod cached on 2026-05-26; re-aggregation re-uses those cached verdicts under the new acceptable_verdicts logic. If Sonnet behavior has drifted between then and a hypothetical v0.1.25 re-run, the re-aggregation reflects the then-state, NOT the now-state. This is acceptable because the goal is to demonstrate the O1 alignment effect on already-paid evidence — not to predict v0.1.25 production behavior, which a fresh paid run would measure.

6. **`acceptable_verdicts` is PER-CASE OPT-IN, not blanket loosening.** Only the 6 designated cases are affected. The remaining 58 chat cases + 10 doc cases continue to use `expected_verdict` single-value match. v0.1.22 T6 safety floor PRE-validated all 6 cases as content-SAFE (18/18 judge criteria PASS + 0/6 fabrications + 6/6 explicit rejection); no other case is opted-in without a comparable safety-floor pre-validation. Adding a 7th case to `acceptable_verdicts` would require a new safety-floor pre-validation per the H15 C1 backstop pattern.

7. **Post-v0.1.24 verdict_match residual still exists.** v0.1.24 lifts the v0.1.22-prod verdict_match from 0.30 to a re-aggregated value (~+0.17 expected, T6 measured). The remaining gap to bar (~0.18 from 0.35 bar - 0.17 lift) is NOT closed by v0.1.24. The v0.1.25+ targeted intervention closes (or attempts to close, with empirical measurement) the residual. v0.1.24 is necessary preparation, not sufficient resolution.

## Re-aggregation methodology summary

- `scripts/v0124_re_aggregate.py` reads `evals/reports/v0.1.22/probe.md` + `v0.1.22-prod-main.md` + `evals/reports/v0.1.23/probe.md` + `v0.1.23-prod-main.md`; for each per-case appendix entry, extracts `case_id` + `actual_verdict` + original verdict_match symbol; loads gold case from `evals/gold_set.jsonl`; recomputes verdict_match using the new acceptable_verdicts logic; emits delta tables to `evals/reports/v0.1.24/verdict-match-re-aggregation.md`.
- `scripts/v0124_decomposition_diagnostic.py` reads the v0.1.22.1 verdict-drop-analysis per-case detail blocks; for each H1 case's per_citation_audits trail, derives `failed_check` from `reason` text mapping; emits per-case Check 1/2/3 distribution + H1.A / H1.B / H1.C re-attribution + headline counts to `evals/reports/v0.1.24/decomposition-h-attribution.md`.

Outputs are read-only on the cached reports; both scripts are idempotent + $0.

## Carry-forwards (post-v0.1.24)

- **v0.1.25+ targeted intervention** based on O2 decomposition outcome (Strict-Answer routing OR Finding-Lenient text-match OR retrieval-side OR eval-side hierarchical containment propagation; selection driven by H1.A/B/C dominance).
- **Gold extension for nis2 / dora doc-mode cases** if doc-mode A/B is pursued (carry from v0.1.20 ADR-0026 D2 design-coherence catch).
- **Coverage gate threshold** still inherited 88.55% < 90% from v0.1.21.3 @slow hotfix (carry from ADR-0029 §22.22 disclosure #8). v0.1.24 may improve coverage slightly via +10 new tests but the gate threshold remains carry-forward to H16 (adjust threshold to 85% to match reality OR fix the offline-SSL test path so the 7 tests no longer need `@pytest.mark.slow`).
- **truststore in pyproject.toml** for the SSL test path (carry from ADR-0029).
- **Doc-mode A/B** (carry from v0.1.20).
- **Per-capability cost attribution** still unmeasured (carry from ADR-0029 §22.22 #6); v0.1.24 does not add paid evidence.

## References

- **Spec**: `docs/superpowers/specs/2026-05-26-v0.1.24-gold-alignment-decomposition-design.md` @ commit `bbcb965`.
- **Plan**: `docs/superpowers/plans/2026-05-26-v0.1.24-gold-alignment-decomposition.md` @ commit `f476134`.
- **Motivating REVERT post-mortem**: `docs/adr/0030-auditor-lenient-quorum.md` §REVERT (empirical refutation + lessons learned).
- **Motivating diagnostic**: `evals/reports/v0.1.22.1/verdict-drop-analysis.md` (H1 attribution that v0.1.24 O2 decomposes).
- **Source code touched by v0.1.24**:
  - `src/regulaitor/citation/schemas.py` (O2 D2 — `AuditResult.failed_check` field).
  - `src/regulaitor/citation/validator.py` (O2 D2 — populate field at 4 fail-fast returns).
  - `evals/schemas.py` (O1 D1 — `GoldCaseChat.acceptable_verdicts` field).
  - `evals/metrics.py` (O1 D1 — verdict_match branch on field).
  - `evals/gold_set.jsonl` (O1 D1 — 6 designated cases).
- **Source code BYTE-UNCHANGED** (verified at T8 pre-closure gate):
  - `src/regulaitor/agents/auditor.py` (v0.1.21 Tier 1 + v0.1.23 REVERT-restored — orthogonal).
  - `src/regulaitor/agents/analyst.py` (v0.1.21 Tier 2 Capa A + Capa C; v0.1.20 chat default v1.4 → v1.5 — orthogonal).
  - `src/regulaitor/agents/council.py` (v0.1.19 binding ON — orthogonal).
  - `src/regulaitor/agents/prompts/` (v1.0-v1.5 Analyst prompts — orthogonal).
  - `src/regulaitor/rag/retrieval.py` (v0.1.21.2 defaults — orthogonal).
  - `src/regulaitor/orchestration/` (LangGraph wiring — orthogonal).
- **Test coverage**: 10 new $0 unit tests (5 O1 in `tests/unit/evals/` + 5 O2 in `tests/unit/test_citation_validator.py`); 962 baseline preserved → 972/0/1 expected.
- **Diagnostic outputs**: `evals/reports/v0.1.24/verdict-match-re-aggregation.md` (O1) + `evals/reports/v0.1.24/decomposition-h-attribution.md` (O2).
- **Companion ADRs**: 0024 (v0.1.18 hierarchical containment — conceptual lineage), 0025 (Council binding — production state inherited), 0027 (Tier 1 + Tier 2 — production state inherited), 0029 (v0.1.22 paid validation — exposed drop), 0030 (v0.1.23 REVERT — direct predecessor + lessons learned).
- **Future**: v0.1.25+ targeted intervention based on O2 decomposition outcome → **H16** (HF Spaces deploy + foundation production-grade per user pref) → **H17** (TFM closure: memoria + model card + data card + AI Act assessment + runbook + cost analysis + video demo + slide deck + Product Roadmap appendix + tag v1.0.0).
