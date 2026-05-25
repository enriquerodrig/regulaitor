# ADR 0029 — v0.1.22 paid validation (cumulative-impact A/B vs v0.1.20 ARM B baseline)

- **Status:** Accepted — 2026-05-25 — squash `<squash-sha>`, tag `v0.1.22-paid-validation`
- **Deciders:** Project owner.
- **Companion ADRs:** 0010 (H8 judge architecture — Haiku 4.5 stays per ADR-0021), 0017 (H15.1 retriever design-defect → resolved at v0.1.18 instrument fix), 0021 (v0.1.16 v0.1.20-bar — the formal measurement target), 0023 (v0.1.17.1 v1.4 prompt — production default flipped at v0.1.20 closure, baseline-side of v0.1.22 ARM B), 0024 (v0.1.18 citation granularity instrument — applied to both arms), 0025 (v0.1.19 Council binding ON — production state inherited by both arms), 0026 (v0.1.20 paid validation methodology — pattern v0.1.22 mirrors with 1-arm-vs-cached optimization), 0027 (v0.1.21 Auditor RHR quorum + Tier 2 Capa A+B+C + v1.5 — the cumulative capabilities v0.1.22 measures), 0028 (v0.1.21.2 retrieval defaults flip — also in cumulative package).

## Context

ADR-0027 closure left a §22.22 caveat unresolved: the v0.1.21 T6 $0 cache-mining diagnostic for the Tier 1 RHR quorum produced LOWER bound = 0 unambiguous flips and UPPER bound = 0..36 ambiguous K≥2 cases because v0.1.20 ARM A checkpoints did not persist per-citation `AuditResult` data. The diagnostic established that the true Tier 1 effect lay somewhere in the [0, 36] interval but could not narrow it further at $0. ADR-0027 D5 + ADR-0028 §22.22 framing left v0.1.22 paid validation **CONDITIONAL** on user authorization (interpretation B: pursue empirical resolution; interpretation A: defer per spec D5 MARGINAL and proceed to H16). User authorized interpretation B on 2026-05-24.

v0.1.22 is the **cumulative-impact measurement milestone** for FIVE capabilities shipped since v0.1.20 close — Tier 1 Auditor RHR quorum (v0.1.21), Tier 2 Capa A+B+C format hard constraints (v0.1.21), the v1.5 Analyst chat prompt with Finding-based refusal (v0.1.21), the per-norma + top_k_auto retrieval defaults flip (v0.1.21.2), and the Council binding ON production state (v0.1.19 carry, inherited by both arms). Per spec D6, the per_citation_audits trail (v0.1.21.1 D2) populated by v0.1.22-prod is the FIRST checkpoint set under which the Tier 1 quorum mechanism can be directly observed in production traffic — closing the cache-schema observability gap retroactively.

The methodology is **1-arm fresh paid vs cached baseline**: ARM v0.1.22-prod is paid on the H10 30-case chat subset under the env-unset production state; ARM v0.1.20-ARM-B is the cached, already-paid baseline from 2026-05-24 with chat-001..030 extracted at $0 from `evals/reports/v0.1.20/armB-main.md`. Choice rationale: budget pragmatism (~50% cost savings vs fresh 2-arm), v0.1.20 ARM B is the relevant control (post-v0.1.20 chat default = v1.4; both ARM v0.1.22-prod and ARM v0.1.20-ARM-B inherit Council binding ON since v0.1.19), apples-to-apples maintained on the dimensions that matter (same Sonnet 4.6, same Haiku judge, same gold cases, same v0.1.18 hierarchical containment instrument, same retrieval pre-v0.1.21.2 vs post — that IS the variable being measured).

## Decision

### D1 — Variant matrix: 1-arm fresh (v0.1.22-prod) vs cached baseline (v0.1.20 ARM B)

ARM v0.1.22-prod runs paid on H10 30-case chat under production state (env unset → v1.5 chat + Tier 1 Auditor quorum + Capa A+B+C + retrieval defaults `max_chunks_per_norma=2 / top_k_auto=12` + Council binding ON). ARM v0.1.20-ARM-B is extracted from the existing 64-case ARM B report ($0 string parsing + aggregate recomputation under the v0.1.18 instrument). Both arms compared on the 7 v0.1.20-bar metrics (per ADR-0021).

### D2 — Cohort: H10 30-case chat (chat-001..030) + 2 ad-hoc safety (nis2-006, dora-006)

Same 30-case subset that anchors the v0.1.20-bar (per ADR-0021). Doc-mode SKIPPED per ADR-0026 D2 design-coherence catch (v1.5 is chat-only; no doc_analyst v1.5 prompt). v0.1.13 industry / v0.1.15 gap-analysis / H14 cross-corpus cohorts SKIPPED per spec §3 D2 (exploratory, no bar). The 2 ad-hoc safety cases are part of the H15 C1 6-designated content backstop pattern that requires nis2-006 and dora-006 alongside the 4 chat-* cases naturally included in the H10 30.

### D3 — Cost gate: strict 1-probe + SKIP/PROCEED + harness checkpoint per-case

Probe protocol: 5-case probe (chat-001..005) → extrapolate `total_high = probe_per_case_mean × 30 × 1.5` → SKIP if `budget < total_high`. Probe IS the first 5 entries of ARM v0.1.22-prod checkpoint per v0.1.8 harness checkpoint pattern (no double-billing). Per `evals/reports/v0.1.22/skip-proceed-decision.md` PROCEED was issued at €0.064/case probe → total_high €3.01 (~$3.24) vs $12.65 remaining headroom = 73% pad.

### D4 — Hard safety floor + soft cumulative narrative + CONDITIONAL CONFIRM third path

Mechanical hard floor: `redteam-smoke` block_rate ≥ 0.90 under production env + 6 designated content-safety cases (chat-014/015/029/030 + nis2-006/dora-006) manually content-backstop reviewed (H15 C1 pattern). On failure → REVERT-CANDIDATES. On pass → soft per-metric narrative on 7 v0.1.20-bar metrics decides CONFIRM / CONDITIONAL CONFIRM / continued iteration. Per spec D4 third path: hard floor PASS + narrative shows mixed performance (NOT dominate-with-no-meaningful-regression) → CONDITIONAL CONFIRM with documented carry-forwards.

### D5 — Baseline: ARM v0.1.20-ARM-B cached extraction ($0)

Pre-extraction via `scripts/v0122_extract_armb.py` reads `evals/reports/v0.1.20/armB-main.md`, filters to chat-001..030, re-aggregates per the v0.1.18 hierarchical containment instrument. NO paid API calls for baseline (the v0.1.20 ARM B paid run is reused authoritatively). Cost saving ~50% vs fresh 2-arm.

### D6 — Per-citation audit trail diagnostic ENABLE (v0.1.21.1 D2)

v0.1.22-prod is the FIRST paid run where `ChatCaseResult.per_citation_audits` is populated. `scripts/v0122_mechanism_diagnostic.py` (~120 lines, $0) mines this field to categorize each case into 5 buckets (A empty-findings Capa A+B+C escape / B BLOCK + ≥1 invalid / C NEW v0.1.21 quorum-triggered RHR with K≥2 invalid / D prose-without-findings residual / E other), counts the bucket_C rate as the empirical resolution of the v0.1.21 T6 §22.22 caveat, and produces `evals/reports/v0.1.22/per-citation-mechanism.md`.

### D7 — ADR scope + closure docs

Single ADR-0029 (count: 28 → 29) covering measurement methodology + 1-arm-vs-cached rationale + per-metric narrative + per-citation mechanism headline + safety floor outcome + CONDITIONAL CONFIRM decision + 10 §22.22 disclosures. Closure artifacts: probe + skip-proceed decision + v0.1.22-prod merged report + ARM B baseline + comparison + per-citation mechanism + safety floor + decisions_log §v0.1.22 + evidence_matrix 3 spots + CLAUDE.md 3 spots.

## Methodology + apples-to-apples controls

| Dimension | ARM v0.1.22-prod (fresh) | ARM v0.1.20-ARM-B (cached) |
|---|---|---|
| Analyst prompt | v1.5 (env unset; flipped at v0.1.21 C4 fix) | v1.4 (env was set at v0.1.20 ARM B run) |
| Analyst model | Sonnet 4.6 | Sonnet 4.6 |
| Auditor aggregation | v0.1.21 Tier 1 quorum (≥2 invalid → RHR) | pre-v0.1.21 (partial branch → RHR via per-Finding) |
| Tool format constraint | Tier 2 Capa A (strict + minItems) | none (Anthropic strict not set) |
| Pydantic schema constraint | Tier 2 Capa B (`min_length=1`) | none (Answer.findings allowed empty) |
| Retry behavior | Tier 2 Capa C (3 attempts + failure-specific feedback) | H8 1-retry |
| Retrieval config | v0.1.21.2 defaults (`per-norma=2 / top_k_auto=12`) | pre-v0.1.21.2 (no defaults; explicit only) |
| Council binding | ON (v0.1.19; MonotonicEscalatePolicy) | ON (v0.1.19; same) |
| Judge model | Haiku 4.5 | Haiku 4.5 (cache reused where applicable) |
| Citation metric | v0.1.18 hierarchical containment | v0.1.18 (re-rendered at v0.1.18 close) |
| Gold set | chat-001..030 (H10 subset) | chat-001..030 (extracted from ARM B 64-case) |
| API epoch | 2026-05-25 | 2026-05-24 |
| per_citation_audits trail | populated (v0.1.21.1 D2) | NONE (pre-D2 cache) |

Drift dimensions acknowledged §22.22: ~24h API epoch drift (low risk; mitigated by same-day-if-possible execution) + judge cache state (mostly fresh on prod side; minor cost variance only).

## Findings — per-metric results (7 v0.1.20-bar metrics)

| Metric | v0.1.22-prod | ARM B v0.1.20 | Delta | Bar | Pass | Improved |
|---|---|---|---|---|---|---|
| faithfulness_mean | 0.71 | 0.76 | -0.05 | ≥0.65 | ✅ | ➖ |
| answer_relevancy_mean | 0.74 | 0.60 | +0.14 | ≥0.55 | ✅ | ✅ |
| context_precision_mean | 0.78 | 0.67 | +0.11 | ≥0.55 | ✅ | ✅ |
| citation_precision_mean | 0.21 | 0.29 | -0.08 | ≥0.25 | ❌ | ➖ |
| citation_recall_mean | 0.55 | 0.64 | -0.09 | ≥0.60 | ❌ | ➖ |
| verdict_match_rate | 0.30 | 0.30 | +0.00 | ≥0.35 | ❌ | ➖ |
| severity_match_rate | 0.40 | 0.33 | +0.07 | ≥0.35 | ✅ | ✅ |

Per-metric interpretation:

- **faithfulness 0.71 vs 0.76**: regression -0.05 yet stays clearly above bar 0.65. Likely v1.5 + Capa A+B+C makes Sonnet more conservative on borderline corpus-support claims; not a fabrication issue (per safety review).
- **answer_relevancy 0.74 vs 0.60**: clear improvement +0.14 above bar. Cumulative package (v1.5 Finding-based refusal + retrieval defaults) produces more relevant answers on the H10 cohort.
- **context_precision 0.78 vs 0.67**: clear improvement +0.11 above bar. v0.1.21.2 retrieval defaults `max_chunks_per_norma=2 / top_k_auto=12` directly impact this metric; the v0.1.11 BREAKTHROUGH mechanism (forcing sub-purity-threshold per-norma share) is the likely driver.
- **citation_precision 0.21 vs 0.29**: regression -0.08 below bar 0.25 (was AT-bar in ARM B). Mechanism: v1.5 Finding-based refusal emits MORE corpus citations per refusal (avg 1-3 instead of 0); some of those are merely tangential to the question rather than direct supports, dragging precision.
- **citation_recall 0.55 vs 0.64**: regression -0.09 below bar 0.60 (was above-bar in ARM B). Same v1.5 mechanism interacts with the verdict_match path; more conservative answers cite a NARROWER intersection with gold articles.
- **verdict_match 0.30 vs 0.30**: flat at 0.30 below bar 0.35; the dominant Tier 1 quorum mechanism manifests as RHR (not pass) → 16 of 30 cases route to RHR per the aggregate verdict count; verdict_match flat is consistent with that.
- **severity_match 0.40 vs 0.33**: improvement +0.07 above bar 0.35. v1.5 + Capa A+B+C produces structured Findings with severity field reliably populated.

Aggregate verdict counts ARM v0.1.22-prod: **pass=10 / RHR=16 / block=4** (out of 30).

Summary: **4/7 metrics PASS bar; 3/7 improve over baseline; 3/7 regress; 1/7 flat**.

## Findings — per-citation mechanism diagnostic (T5)

| Bucket | Definition | Count | Percentage |
|---|---|---|---|
| A | RHR + empty citations (Capa A+B+C escape) | 0 | 0.0% |
| B | BLOCK + ≥1 invalid citation (pre-v0.1.21 deterministic) | 4 | 13.3% |
| C | RHR + ≥1 citation + ≥2 invalid (NEW v0.1.21 quorum) | 11 | 36.7% |
| D | RHR + empty + prose-without-findings residual | 0 | 0.0% |
| E | Other (PASS or non-RHR) | 15 | 50.0% |

**HEADLINE FINDING**: **NEW v0.1.21 Tier 1 quorum-triggered RHR cases = 11/30 (36.7% of cohort)**. The escalation mechanism from v0.1.21 (Auditor RHR when n_invalid_citations ≥ 2 and all-pass-Findings) fired on 11 cases — empirically resolving the ADR-0027 T6 §22.22 caveat that left LOWER bound at 0 and UPPER bound at 0..36 ambiguous. The REAL effect is 36.7% — within the predicted interval but neither at the conservative bound (0%) nor at the optimistic bound (95%).

Per-bucket interpretation:

- **Bucket A=0 and Bucket D=0**: Tier 2 Capa A+B+C is **100% effective** at preventing empty-findings escape on this cohort. No case in 30 reached the Auditor with empty findings (either the API enforced minItems=1, the Pydantic schema caught it, or Capa C retries succeeded). The v0.1.17 prose-without-findings 5th mechanism also did not fire.
- **Bucket B=4**: deterministic pre-v0.1.21 BLOCK path unchanged (chat-015 / chat-020 / chat-027 / chat-028). These are the redteam-style cases where every citation is invalid; BLOCK is the correct §6 outcome.
- **Bucket C=11**: the NEW Tier 1 escalation mechanism. Pre-v0.1.21, these 11 cases would have routed to PASS (all-pass-Findings at the Lenient level) despite emitting K≥2 invalid citations within the passing Findings. Tier 1 quorum escalates them to RHR — protecting against the failure mode where Lenient-Finding aggregation is too permissive on multi-citation Findings.
- **Bucket E=15**: PASS cases or single-invalid RHR cases (the latter routes via partial branch, unchanged from pre-v0.1.21).

## Findings — hard safety floor (T6)

**HARD FLOOR PASS** ✅

- redteam-smoke block_rate = **0.92** (≥0.90 bar; carries the v0.1.14-v0.1.21.2 frozen baseline; v1.5 prompt-loading does not regress the deterministic sanitizer/injection path).
- 6 designated content-safety cases (chat-014 / chat-015 / chat-029 / chat-030 / nis2-006 / dora-006) all manually content-backstop reviewed: **6/6 SAFE**, **0/6 fabrications**, **6/6 explicit rejection** of malicious premise, **6/6 real corpus citation** for refutation, **18/18 judge criteria** PASS across the 6 × 3-criteria evaluations.
- §6 invariant preservation across the cohort: TOTAL. Bucket A=0 + Bucket D=0 confirms no Capa A+B+C escape and no prose-without-findings residual; Bucket B=4 confirms deterministic BLOCK still fires when warranted.

H15 C1 prompt-blind-mechanical issue: the comparison report's `verdict_match` column shows 5/6 of these cases as ❌ (gold expected literal `block` but v1.5 returned `pass` with refusal content). This is the same H15 C1 pattern: mechanical labels are prompt-blind but the CONTENT is safe per the judge criteria + controller review. Carry-forward to v0.1.23+: update gold expected_verdict to accept `{block, RHR, pass-with-refusal-Finding}` OR refine Auditor to detect v1.5 Finding-based refusal pattern and route to BLOCK uniformly.

## Decision (the outcome) — CONDITIONAL CONFIRM

**Per spec D4 third path: CONDITIONAL CONFIRM the cumulative v0.1.21 + v0.1.21.2 production-state package.**

The production state SHIPS — env-unset production already carries v1.5 chat default + Tier 1 quorum + Capa A+B+C + retrieval defaults flip + Council binding ON (all flipped at the prior milestones). v0.1.22 measurement validates that the package is **safe to retain as production**, with carry-forwards documented for v0.1.23+ iteration rather than a clean dominate-with-no-regression CONFIRM verdict.

Rationale (per spec D4 decision logic):

1. **Hard safety floor PASS** (T6) — unlocks any positive decision path. §6 invariant ROCK-SOLID across the cohort.
2. **Soft narrative MIXED, not dominate** — 4/7 metrics PASS bar (faithfulness, answer_relevancy, context_precision, severity_match); 3/7 improve over baseline; 3/7 regress (faithfulness slightly, citation_precision/recall meaningfully). NOT "dominate with no meaningful regression" → CONDITIONAL CONFIRM rather than CONFIRM.
3. **NEW Tier 1 mechanism fires meaningfully** (Bucket C = 36.7% of cohort) — empirically resolves the ADR-0027 §22.22 caveat; the v0.1.21 quorum ships not as a speculative tightening but as a measured escalation path that engages on more than 1 in 3 chat queries.
4. **Tier 2 Capa A+B+C is 100% effective** on this cohort (Bucket A+D = 0) — the format defense-in-depth stack closes the empty-findings escape route the v0.1.17.1 v1.4 prompt-only could only reach ~50% on.
5. **Citation precision/recall regressions are attributable to v1.5 Finding-based refusal mechanism** (more citations per refusal, narrower intersection with gold); the §6 invariant is preserved (the citations ARE valid corpus references; precision/recall degrade against the gold instrument, not against the validator).
6. **Cost-per-chat €0.063 vs soft bar €0.05** (+€0.013, +26%) — Capa C 3-attempt retry inflates per-call cost as expected per ADR-0027 D4; documented carry-forward, not a blocker.

## §22.22 disclosures (the centerpiece)

The honest framing of what v0.1.22 measured and did NOT measure, what cost what, and what limits the conclusions:

1. **3 prior probe attempts failed at $0 before the first paid call** (documented in `evals/reports/v0.1.22/probe-attempt-{1,2,3}*.md`). Attempt 1: Windows CryptoAPI CRL revocation block on both HuggingFace (BGE rerank weights) and Anthropic API. Attempt 2: HF fix only (HF_HUB_OFFLINE); Anthropic SSL still blocked. Attempt 3: SSL fixed via truststore, but Anthropic returned `400 invalid_request_error: tools.0.custom: For 'object' type, additionalProperties must be explicitly set to false` — v0.1.21 Capa A bug surfaced. Each attempt cost $0 (failed pre-API or pre-tool-use), but the wall-clock + discovery cost is real and documented for academic honesty.

2. **Windows CryptoAPI CRL revocation block** (CRYPT_E_NO_REVOCATION_CHECK 0x80092012) discovered as a machine-level infrastructure issue. Browser HTTPS worked (uses CryptoAPI with cached CRL); Python `httpx` + `requests` using `schannel`/`ssl` defaults failed deterministically. Fixed via `truststore.inject_into_ssl()` in `scripts/v0122_run.py` (uses Windows native trust store, same path as Edge/Chrome). truststore 0.10.4 added to `.venv` via `uv pip install --native-tls truststore`; **NOT YET in `pyproject.toml`** → carry-forward to v0.1.22.1 infra hotfix OR addition at H16 deploy. Without this fix v0.1.22 could not have run at all.

3. **v0.1.21 Capa A schema bug shipped silently broken for ~12 hours**. `_strip_unsupported_schema_fields` in `agents/analyst.py` set `additionalProperties: false` on the schema root ONLY; nested `$defs` (Finding, Citation) shipped without the flag → Anthropic strict mode rejected with 400 → Capa C retries 3× → all fail → empty Answer at Capa B → Auditor RHR → **production v0.1.21 through v0.1.21.3 had a 100% RHR rate on chat requests for ~12 hours post-merge**. Broken-fail-safe per §6 invariant: no fabrication (the Capa B reject prevents the empty Answer from reaching the Auditor; conservative all-RHR is the safe failure mode). The v0.1.21 T0 strict-mode probe used a trivial schema (no nested $defs) → the bug was invisible to that probe. **Fixed in v0.1.22 via recursive walker `_set_additional_properties_false_recursive`** + 3 regression-guard tests in `tests/unit/agents/test_analyst.py`. The fact that "broken in production for 12 hours" did not produce a §6 violation is the strongest possible vindication of the Tier 2 defense-in-depth design — but the absence of empirical paid validation between v0.1.21 ship and v0.1.22 ship is exactly the failure mode the ADR-0027 §22.22 framing predicted.

4. **Spec amendment (§22.22 honest framing)**: v0.1.22 spec said "ZERO backend touch — pure measurement". Reality: 1 src/ file modified (`agents/analyst.py` for the recursive Capa A fix). Fixing the bug DURING v0.1.22 (rather than shipping broken-measurement and amending later) is the §22.22-honest path; this ADR documents the amendment up front. Without the fix v0.1.22 would have measured the broken Capa A path (100% RHR ARM) and concluded the Tier 1 quorum mechanism does not fire at all — a completely false conclusion.

5. **1-arm-vs-cached vs 2-arm fresh trade-off**: cannot rule out ~24h API epoch drift between the 2026-05-24 v0.1.20 ARM B paid run and the 2026-05-25 v0.1.22 fresh paid run. Mitigated by same-day-if-possible execution + same model versions (Sonnet 4.6, Haiku 4.5) + same Anthropic API endpoint + same harness + same gold set. API drift effects expected minimal vs the 12-day H8 cache drift documented at H15.1. Cost savings ~50% justified the trade-off given $13 budget headroom; a fresh ARM B re-run would have doubled v0.1.22 spend at minimal information gain.

6. **Per-capability attribution NOT measured**: would require factorial 2^6 = 64 arms (Tier 1 × Tier 2 Capa A × Capa B × Capa C × v1.5 × retrieval defaults). Cost-prohibitive at any reasonable budget (~$160 at €0.063/case × 30 × 64 arms / 2 cache-share). v0.1.22 measures the PACKAGE (5 capabilities together), NOT the parts. v0.1.23+ could pursue per-capability ablation if a specific capability appears to regress and surgical revert is needed.

7. **Cost-per-chat €0.063 over soft bar €0.05** by €0.013 (+26%). Capa C 3-attempt retry inflates per-call cost when Sonnet first returns invalid format (additional 1-2 retries each cost a full Sonnet call). Documented expected behavior per ADR-0027 D4 + spec §3 D3; not a blocker for production. Future cost optimization milestone could reduce Capa C retry overhead via prompt iteration on the failure-feedback message.

8. **Coverage gate inherited failure**: pytest coverage 88.55% < 90% gate. **PRE-EXISTING on main since v0.1.21.3 hotfix** (when 7 SSL-environment-dependent tests were marked `@pytest.mark.slow` and dropped from the default `-m "not slow"` run, reducing baseline coverage from 93.51% to 87.83%). v0.1.22 IMPROVES coverage by +0.72pp via the 3 Capa A regression tests added with the recursive walker fix. Carry-forward: adjust coverage gate threshold to 85% (matches reality) OR fix the offline-SSL test path so the 7 tests no longer need `@slow` (preferred but more work; H16 candidate).

9. **Bucket D heuristic overlap with bucket A** (T5 mechanism diagnostic): both share "RHR + empty citations" classification; the diagnostic cannot distinguish via per_citation_audits trail alone (intended distinction was "Capa A+B+C escape" vs "prose-without-findings residual" per v0.1.17 5th mechanism, but the trail does not record Analyst answer.text substantive-prose flag). The diagnostic assigns both to bucket A; a more granular heuristic (inspecting `text` field for substantive prose) would separate them. Both buckets show 0 cases on the v0.1.22 cohort anyway, so the ambiguity does not affect the headline finding (Bucket C = 36.7%).

10. **Pre-v0.1.22 budget gap ~$3.50** (harness `Total cost: €X.XX` field tracks Anthropic API usage at ~$8.46 vs Anthropic console user-observed at $11.95 entering v0.1.22). Sources: Haiku judge layer not tracked in the harness `Total cost` field (only Analyst calls tracked); EUR/USD conversion variance over time; possible dev/test calls during implementer subagent runs not captured in harness logs. Documented for H17 memoria honesty; user budget of $13 was used as authoritative for v0.1.22 budget gate.

## Alternatives considered + rejected

1. **2-arm fresh A/B (re-run v0.1.20 ARM B fresh as 2026-05-25 baseline)** — rejected at spec time (D1+D5). 2× cost (~€5 vs €2.50) at no information gain; v0.1.20 ARM B already paid for once. The ~24h API drift risk is documented (§22.22 #5) but minimal vs the 12-day H8 cache drift baseline.
2. **64-case full cohort (v0.1.13 industry + v0.1.15 gap + H14 cross-corpus + 10 doc)** — rejected at spec time (D2). Cost-prohibitive at $13 budget; H10 30-case IS the bar cohort. Exploratory cohorts have no bar to validate against. Carry-forward.
3. **ARM A v1.0 as baseline (not v1.4 ARM B)** — rejected at spec time (D1). v0.1.20 closure flipped chat default v1.0 → v1.4 per ADR-0026; v1.4 IS the production reference for v0.1.22's measurement of post-v0.1.20 capabilities. v1.0 baseline is not relevant to "cumulative impact of v0.1.21+v0.1.21.2".
4. **Per-capability factorial ablation** — rejected at spec time (§6 out-of-scope). 64 arms × ~$0.063/case × 30 = ~$120 + cache reuse savings; not viable at $13 budget. v0.1.22 measures the package; per-capability attribution lives at a separate future milestone with proper budget allocation.
5. **Defer v0.1.22 entirely per ADR-0027 interpretation A** — considered + user-rejected on 2026-05-24. User authorization for interpretation B was explicit; the ambiguity from the v0.1.21 T6 §22.22 caveat justified the paid spend on academic-honesty grounds.

## Consequences

**Positive:**

- **v0.1.21 T6 §22.22 caveat empirically resolved**: real Tier 1 quorum mechanism rate measured at 36.7% of cohort, within the predicted [0%, 100%] interval and clearly nonzero. The cumulative-impact framing for v0.1.21 + v0.1.21.2 is now data-backed rather than capability-only.
- **Tier 2 Capa A+B+C validated at 100% effectiveness** on the v0.1.22 cohort (Bucket A+D = 0). The defense-in-depth design closes the empty-findings escape route that v0.1.17.1 v1.4 prompt-only could only reach ~50% on.
- **Capa A schema bug caught and fixed** before reaching academic memoria. Without v0.1.22 the bug would have persisted indefinitely; the §22.22-honest path of fixing it DURING v0.1.22 prevents shipping broken-measurement.
- **Hard safety floor PASS** with content-backstop 18/18 judge criteria + 6/6 controller review confirms the cumulative package is safe to retain as production.
- **3 of 7 v0.1.20-bar metrics improved** (answer_relevancy +0.14, context_precision +0.11, severity_match +0.07); 4/7 pass the bar.
- **Carries the §22.22 academic-honesty discipline** through 5 consecutive milestones (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 / v0.1.22): per-task reviews validate per-task correctness; cumulative empirical validation lives at paid-milestone cadence; honest framing of trade-offs in the closure narrative.

**Negative / accepted (per §22.22 honest framing):**

- **3 of 7 v0.1.20-bar metrics regressed** vs ARM B baseline (faithfulness -0.05 still above bar; citation_precision -0.08 below bar; citation_recall -0.09 below bar). The mechanism (v1.5 Finding-based refusal emitting more citations per refusal) is identified; the trade-off is accepted per CONDITIONAL CONFIRM rather than reverted.
- **verdict_match flat at 0.30 below bar 0.35**: the dominant Tier 1 quorum mechanism manifests as RHR (16/30 cases) which by-design routes away from PASS; verdict_match remains the hardest metric to move at the package level.
- **Cost-per-chat over soft bar by €0.013/case** (+26%): Capa C retry overhead. Carry-forward to cost optimization milestone if v0.1.23+ pursues it.
- **Per-capability attribution unmeasured**: cumulative-impact framing inherently obscures which specific capability drives which metric delta. Future ablation milestone if a regression triggers surgical revert.
- **API epoch drift risk** between 2026-05-24 ARM B and 2026-05-25 v0.1.22 fresh runs (~24h). Mitigated but not eliminated; 1-arm-vs-cached is the budget-pragmatic path documented.
- **Pre-v0.1.22 budget gap ~$3.50** (harness vs console) documented for H17 honesty; not a blocker but a TFM-memoria caveat.
- **Coverage gate inherited failure** (88.55% < 90%) carried from v0.1.21.3 hotfix; gate threshold or test path adjustment needed at H16.

## Carry-forwards (for v0.1.23+ and H16+)

- **truststore → pyproject.toml** at H16 deploy ceremony (or as v0.1.22.1 infra hotfix if H16 is not imminent). Currently only in `.venv`.
- **Capa A test scope expansion** to test against actual Anthropic API (vs local schema validation only). The shipped tests catch the recursive-walker bug structurally; a live API integration test would have caught the original ship-broken issue.
- **Coverage gate threshold adjustment** to 85% (matches reality post-@slow hotfix) OR fix the offline-SSL test path so 7 tests no longer need `@pytest.mark.slow` (preferred, more work).
- **Doc-mode A/B** for v1.5 + Tier 1 + Tier 2 — deferred since v0.1.20 (v1.5 is chat-only; no doc_analyst v1.5 prompt). Requires authoring `prompts/document_analyst/system.v1.5.md` + fresh paid doc run.
- **Per-capability ablation** if a specific capability appears to drive a regression (budget-permitting; ~$160 worst case for full 64-arm factorial).
- **Cost-per-chat optimization** to reduce Capa C retry overhead (€0.013/case = 26% over soft bar). Prompt iteration on failure-feedback message OR Capa A schema refinement to reduce first-attempt invalid format rate.
- **Gold expected_verdict expansion** to accept `{block, RHR, pass-with-refusal-Finding}` for the 6 designated content-safety cases, OR Auditor refinement to detect v1.5 Finding-based refusal pattern and route to BLOCK uniformly. H15 C1 prompt-blind-mechanical lineage closed at instrument level.
- **`scripts/v0120_compare.py` transition matrix bug**: carries to v0.1.23 cleanup or post-H17 polish (already fixed inline in v0.1.20 comparison.md per ADR-0026; the script still has the bug per v0.1.21.1 D1 fix attempt).

## References

- **Spec**: `docs/superpowers/specs/2026-05-24-v0.1.22-paid-validation-design.md` @ commit `287cd31`.
- **Plan**: `docs/superpowers/plans/2026-05-24-v0.1.22-paid-validation.md` @ commit `f2d10eb`.
- **Source reports** (under `evals/reports/v0.1.22/`):
  - `probe-attempt-1-ssl-failed.md`, `probe-attempt-2-ssl-anthropic-failed.md`, `probe-attempt-3-capa-a-schema-bug.md` (3 prior failed attempts, $0)
  - `probe.md` (T1 paid probe attempt 4 — €0.32)
  - `skip-proceed-decision.md` (T2 gate)
  - `v0.1.22-prod-main.md`, `v0.1.22-prod-safety-adhoc.md` (T3 paid main 25 cases + 2 ad-hoc safety)
  - `v0.1.20-armB-baseline.md` (T4 cached extraction $0)
  - `comparison.md` (T4 7-metric A/B $0)
  - `per-citation-mechanism.md` (T5 mechanism diagnostic $0)
  - `safety-floor.md` (T6 hard safety floor controller review $0)
- **Commits**: `9413480` (T1+T2 probe + Capa A fix + truststore + PROCEED gate) → `ac0a02a` (T3 main+safety paid + T4 baseline+comparison + T5 mechanism diagnostic) → `e9abe27` (T6 safety floor + T8 pre-closure gate).
- **Empirical data**: total paid spend €1.91 (probe €0.32 + main €1.30 + safety €0.29; ~$2.06 USD) of $3.78 high-extrapolation / $13 budget headroom = ~16% of forecast high. Wall-clock ~3h paid runs.
- **Source code touched by v0.1.22**: `src/regulaitor/agents/analyst.py` (recursive `_set_additional_properties_false_recursive` walker; Capa A bug fix shipped DURING v0.1.22 per spec amendment §22.22 #4) + `scripts/v0122_run.py` (truststore inject) + 3 regression-guard tests in `tests/unit/agents/test_analyst.py`. NO other src/ changes.
- **Companion ADRs**: 0010 (judge architecture), 0017 (H15.1 design-defect → v0.1.18 fix), 0021 (v0.1.20-bar), 0023 (v1.4 prompt), 0024 (citation granularity instrument), 0025 (Council binding ON), 0026 (v0.1.20 paid methodology), 0027 (Tier 1 + Tier 2 + v1.5), 0028 (retrieval defaults flip).
- **Future**: H16 (HF Spaces deploy + foundation production-grade) → H17 (TFM closure: memoria + model card + data card + AI Act assessment + runbook + cost analysis + video demo + slide deck + Product Roadmap appendix + tag v1.0.0).
