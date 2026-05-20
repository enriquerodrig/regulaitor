# H15.2 — Retriever Eval Rede-design Study Report

**Milestone:** H15.2 (decimal, sibling of H15.1 — precedent H0.1 + H15.1; H16/H17 unchanged in roadmap).
**Branch:** `feat/h15-2-eval-redesign` → squash-merged to `main` → tag `v0.1.7-h15.2` on squash commit `<squash-sha>`.
**Status:** Closed 2026-05-20 with **partial outcome** honestly documented per §22.22.

---

## 1. Headline (§22.22 honest done-when)

H15.2 **shipped its primary contribution**: the surgical wiring fix that closes the §22.22 design-defect disclosed POST-SPEND in H15.1-T10/T11 — `DEFAULT_CONFIG.top_k`/`pre_rerank` now flow into the explicit-corpus `rag.retrieval.run()` via the default-`None` pattern (per-call attribute resolution). Production behavior remains byte-identical to `v0.1.6-h15.1` when `REGULAITOR_RETRIEVAL_CONFIG` is unset; eval-time behavior is now genuinely config-sensitive when the env is set. The keystone test (`tests/unit/test_explicit_config_wired.py`) asserts this end-to-end.

**The A/B re-experiment intended for T6–T8 did not complete its planned scope.** The probe (n=3, cand-1 `pre_rerank=80, top_k=8`) was executed cleanly and shows directional signal (faithfulness +0.23, verdict_match +0.40 vs the H15 frozen control), but n=3 is statistically too small for a defensible attribution. The full 30-case run crashed mid-flight at case ~24/30 with `anthropic.BadRequestError: credit_balance_too_low`, and because the harness writes its report only atomically at the end (no per-case checkpoint), the in-memory results of the cases that did complete were lost. Total Anthropic spend in T6: **€2.43** (the entire pre-existing balance), of which only €0.19 produced persistable evidence (the probe).

**This is a partial outcome that the spec §6 explicitly covered**: *"If no winner, the code change ships anyway — the measurement-design fix IS the H15.2 contribution"*. The wiring fix is shipped, the design-defect is closed, the keystone test pins the invariant under both env-unset and env-set states, T6 stays green unchanged, and §6 invariant (Auditor + citation/validator byte-unchanged) is 100% intact. The defendable measured A/B is deferred to a future paid-validation milestone (post-optimization-bundle).

---

## 2. Constraint reinterpretation (the keystone, ADR-0018)

H15.1 (ADR-0017) implemented the cross-corpus `corpus="auto"` path and introduced `RetrievalConfig` as the tuning-lever container, but kept the explicit-corpus `run()` function hardcoded to `PRE_RERANK=50` and function-default `top_k=5`, never consulting `DEFAULT_CONFIG`. H15.1's spec §4 intended the 30-case calibration A/B to measure the tuning lever on the explicit-corpus calibration set — but because the explicit path consumed `DEFAULT_CONFIG` in ZERO sites and the 30 calibration cases are all explicit-corpus, `REGULAITOR_RETRIEVAL_CONFIG` had no mechanism on the measurement. The €3.01 of cand-1+cand-2 deltas measured LLM-provider non-determinism, not a real tuning-lever signal.

The H15.1 §4.3 framing called the no-leakage guarantee (T6, `tests/unit/test_explicit_path_unchanged.py`) and the spec §4 A/B intent *"mutually exclusive as designed"*. On re-grounding for H15.2, T6 was found to assert EXACTLY two properties: (a) the WHERE-CLAUSE string equals `f"norma = '{corpus}' AND language = '{language}'"`; (b) an empty-rerank short-circuit returns `[]`. T6 does **not** assert `PRE_RERANK=50`, does **not** assert `top_k=5`, does **not** assert that `run()` is config-insensitive — the stub `_S.limit(_n)` ignores its argument and the test passes `top_k=5` explicitly. The §22.18/H14 no-leakage guarantee is fundamentally about cross-corpus contamination (the WHERE-CLAUSE), not about specific `top_k`/`pre_rerank` values.

**H15.2's contribution is recognizing this:** the H15.1 framing was the conservative implementation interpretation of T6's actual narrower scope. The architectural constraint is genuinely narrower than the H15.1 implementation chose. ADR-0018 records this constraint reinterpretation.

---

## 3. Wiring change shipped (T1–T5)

**The default-`None` pattern with per-call attribute resolution** ([src/regulaitor/rag/retrieval.py:177-225](src/regulaitor/rag/retrieval.py#L177-L225)):

```python
def run(query, corpus, language, top_k=None, pre_rerank=None):
    effective_top_k = top_k if top_k is not None else DEFAULT_CONFIG.top_k
    effective_pre_rerank = pre_rerank if pre_rerank is not None else DEFAULT_CONFIG.pre_rerank
    ...
    where_clause = f"norma = '{corpus}' AND language = '{language}'"  # BYTE-IDENTICAL
    candidates = table.search(query_vec).where(where_clause).limit(effective_pre_rerank).to_list()
    reranked = reranker.rerank(query, passages, top_n=effective_top_k)
    ...
```

| Task | Change | Outcome |
|---|---|---|
| **T1** | New `tests/unit/test_explicit_config_wired.py` (4 properties — env-unset defaults, env-set override, explicit per-call override, WHERE-CLAUSE byte-identical under BOTH env states) | 2 PASS by coincidence (env-unset matches), 2 FAIL by design (TDD red signal pre-T2). Commit `a371f4a`. |
| **T2** | `run()` wiring change: default-`None` pattern, per-call `DEFAULT_CONFIG` resolution, WHERE-CLAUSE byte-identical character-for-character (verified by `git show v0.1.6-h15.1` diff during code review). Commit `a67588b`. | T1 turns 4/4 PASS; T6 stays 1 PASS unchanged; 30 retrieval-domain tests green; **production-byte-identical to v0.1.6-h15.1 under env-unset** (the central H15.2 proof). |
| **T3** | Thread default-`None` through `RetrieverAgent.retrieve()` + `mcp_server.search_articles()` (signature-only changes; bodies unchanged). Rename + update over-constrained `test_retriever_agent_default_top_k_is_5` → `test_retriever_agent_default_top_k_passes_none_through` (asserts the architecturally-correct pass-through invariant). Fixed stale contract test `test_mcp_tool_schemas.py:23`. Commit `1c4b29c`. | 19 tests green; backward-compat for explicit-`top_k` callers verified. |
| **T4** | Pre-paid verification gate (no commit, verification only). | **782 pytest passed / 0 failed / 1 skipped (expected) / 93.51% coverage** ≥90%; **`mypy src` Success: 71 source files** exit 0; **redteam-smoke block_rate 0.92** (≥0.92 H15 frozen carry, ≥0.90 §16.2#4); 2 production callers (graph.py:99, document_graph.py:153) pass NO `top_k` → `None` propagates → resolves to `DEFAULT_CONFIG.top_k=5` under env-unset → byte-identical. |
| **T5** | ADR-0018 `docs/adr/0018-retriever-config-wired-into-explicit-path.md`. Commit `ee75033` (amended post-code-review for Decision section invariant restatement + References path-abbreviation cleanup). | Constraint reinterpretation decision documented; companion ADRs 0017/0016/0013; honest framing of H15.1's conservative interpretation. |

**§6 invariant**: Auditor + citation/validator byte-unchanged. `git diff main..HEAD -- src/regulaitor/agents/auditor.py src/regulaitor/citation/validator.py` is empty. The "no citation, no answer" invariant is 100% intact.

---

## 4. A/B re-experiment: probe vs full run (the partial outcome)

### 4.1 Probe (cand-1 `{pre_rerank:80, top_k:8}`, n=3, USER-GATED, MEASURED)

Frozen control = `evals/reports/h15/candidate-v1.2.md` (H15 30-calibration, Analyst v1.2, env-unset, total cost €1.51).

**Probe results** (`evals/reports/h15/h15_2-cand1-probe.md`, **n=3 cases chat-001..003**, MEASURED €0.19):

| Metric | H15 control (n=30) | Cand-1 probe (n=3) | Δ | Interpretation |
|---|---|---|---|---|
| faithfulness | 0.75 | **0.98** | **+0.23** | Directional positive — but n=3 vs n=30 not statistically comparable |
| answer_relevancy | 0.70 | **0.86** | **+0.16** | Same caveat |
| context_precision | 0.60 | 0.72 | +0.12 | Improvement consistent with `top_k=8` returning more relevant chunks |
| context_recall | 0.47 | 0.50 | +0.03 | Marginal |
| citation_recall | 0.71 | 0.67 | **−0.04** | **HARD-revert floor watch** — at n=3 could be noise (1 case dragging the mean) |
| citation_precision | 0.30 | 0.33 | +0.03 | Marginal |
| verdict_match | 0.27 | **0.67** | **+0.40** | Large directional improvement |
| severity_match | 0.42 | 0.33 | −0.09 | Same comparability caveat |
| cost/case | €0.050 | **€0.062** | **+24%** | Expected: `top_k=8` → more chunks → more Analyst output tokens |

**Honest reading**: Cand-1 shows directional positive signal on the primary metrics, but **n=3 is too small to be defensible**. Additionally, chat-001..003 are the FIRST cases of the calibration set and may not be representative of the full 30 distribution (potential selection-bias if early cases are easier). The `citation_recall` -0.04 is below the H15 carry-forward floor 0.71 but at n=3 this could be a single case dragging the mean. The full 30-case run was needed to settle these questions.

### 4.2 Full 30-case run (cand-1, USER-GATED, CRASHED mid-run)

**Configuration**: same as probe (`pre_rerank:80, top_k:8`, Analyst v1.2). Estimated cost €1.86 (extrapolated from probe €0.19 × 10), user-authorized with $2.62 ≈ €2.43 remaining balance.

**Actual outcome**: process ran **~5 hours** of wall time, completed ~20-25 cases internally (exact count uncertain — counted `Evaluating: 0%|` tqdm batches gave 24 but did not verify per-case batch ratio), then crashed at `anthropic.BadRequestError: Error code: 400 - 'Your credit balance is too low'` during a Haiku judge invocation inside `compute_chat_metrics._ragas_metrics_chat` ([evals/harness.py:140](evals/harness.py#L140)).

**Lost data**: the harness writes `evals/reports/latest.md` only atomically at the end via `_REPORT_PATH.write_text(markdown, ...)` ([evals/harness.py:325](evals/harness.py#L325)). When `main()` raised before reaching that line, the `chat_results: list` in RAM was lost. **Zero disk artifact of the full run**.

**Total H15.2 paid spend**: €2.43 (entire balance), of which €0.19 (probe) is the only persisted measured data. Effective cost per usable data point: ~€0.81/case (vs H15 baseline €0.050/case — 16× worse), driven entirely by the crash.

### 4.3 Why the run failed — three converging causes

1. **Bad cost-estimation extrapolation (the dominant cause)**. I extrapolated linearly from a probe of just 3 cases (€0.19 / 3 = €0.063/case → 30 × €0.063 = €1.90 estimate). I knew `latency_p95 = 391s` from H15 signaled high per-case variance and ignored it. Actual per-case rate in the full run was ~€0.093 (+50%), pushing the run to ~€2.40+ before crash — outside the user's €2.43 balance. I did not present an upper-bound to the user before authorization, nor did I refuse the "lets go" when the upper bound (€1.90 × 1.5 = €2.85) clearly exceeded the available balance.
2. **Harness has no per-case checkpoint**. The H8 harness writes the report only atomically at the end. Any exception in the main loop before that point loses all in-progress data. This was always a known operational risk; H15.2 just surfaced it expensively.
3. **`compute_chat_metrics` calls `_ragas_metrics_chat` without try/except** ([evals/harness.py:286-297](evals/harness.py#L286-L297)). The ragas call uses Anthropic Haiku via langchain — when Haiku 429-on-credits, the exception propagates through ragas's tenacity retries, kills the main loop, no report.

The proximate fault is mine (bad estimation, weak authorization gating). The structural faults (no checkpoint, no try/except in judge path) are documented as deferred-microhito follow-ups (next milestone `v0.1.8`).

---

## 5. §22.22 honest disclosures

This section is the TFM-defensible honesty payload. None of these are excuses — they are documented failures and the disciplines registered against them.

### 5.1 The measurement-design gap was disclosed POST-SPEND in H15.1, AND H15.2 itself replicated a similar gap

H15.1's design-defect (the explicit-path A/B couldn't measure the lever) was caught only after €3.01 of paid measurement had been spent. H15.2 was designed precisely to close this gap. **H15.2 itself then replicated a related failure**: the budget-estimation methodology gap (probes too small to extrapolate reliably) was caught only after the user's entire remaining budget had been consumed by a single full run that crashed mid-flight.

The cross-milestone honest lesson is the same: per-task reviews validate per-task correctness; they do NOT validate cross-task design coherence (H15.1) or cost-estimation discipline (H15.2). Both must be reviewed separately and explicitly.

### 5.2 The cost-estimation discipline now hard-coded for future paid runs

Effective from this milestone forward (recorded in the next milestone `v0.1.8` decisions log):

- **Probe minimum N = 5** (not 3) — per-case variance in this gold set is high; small probes mislead.
- **Cost estimates ALWAYS as a range** (low / expected / **high = expected × 1.5**) not a point estimate.
- **If user budget < high-estimate → DO NOT recommend "proceed"**, recommend SKIP or smaller scope. The agent's job is to protect the budget, not to ride it to the edge.
- **No paid run is authorized until harness checkpoint per-case is shipped** (deferred-microhito `v0.1.8`).

### 5.3 The probe n=3 signal is informative but not defensible as "measured improvement"

The probe shows directional positive (faith +0.23, verdict_match +0.40) but **n=3 cannot defend an "improvement" claim** to a TFM tribunal. The honest framing is: *"The probe suggested directional positive signal that could not be statistically confirmed before the full run terminated. Confirmation is deferred to a future paid-validation milestone."* This is what gets reported in the final memoria — not "+0.23 measured improvement", which would be unsupported and §22.22-violating.

---

## 6. Deferred microhito follow-ups (the post-H15.2 roadmap)

Per the user-confirmed maximalist plan, the following microhitos are queued as decimal milestones, each implemented `$0`, single paid validation at the end when budget recharges. Sequencing prioritizes safety (harness checkpoint first) and non-baseline-invalidating changes first (so the final paid validation can compare to the existing H15 control):

| # | Microhito | Tag | Baseline impact | Notes |
|---|---|---|---|---|
| 1 | **Harness checkpoint per-case** | `v0.1.8` | None | Trivial ceremony; resolves the structural cause of H15.2's data loss; **MANDATORY before next paid run** |
| 2 | **xcorpus-002 investigation + retriever local re-tuning** | `v0.1.9` | None (`auto` path only) | Closes H15.1 open question; purity_threshold sweep + reranker behaviour diagnosis on n=1 |
| 3 | **Gold-set extension auto-path** | `v0.1.10` | None (additive only) | Adds N≥10 auto-path cases; rejected for H15.2 (spec §8 option B) but valuable as own milestone |
| 4 | **§17 thresholds + LLM-judge same-provider-family** | `v0.1.11` | INVALIDATES H15 baseline | Changes judge; future paid runs need fresh baseline |
| 5 | **No-Answer-residual robustness** | `v0.1.12` | INVALIDATES if Analyst prompt v1.2 changes | Strengthens Analyst→Auditor contract |
| 6 | **Document segmenter overhaul** | `v0.1.13` | None (doc-mode only; H15/H15.1/H15.2 chat-only) | Closes H5 "0 segmentos" confound; enables doc-mode A/B |
| 7 | **Citation granularity confound** | `v0.1.14` | INVALIDATES H15 baseline | Requires manual gold-set re-annotation (human time, not $0 in user-effort) |
| 8 | **Auditor RHR-aggregation + Council binding** | `v0.1.15` | INVALIDATES H15 baseline; touches §6 | Heavy design; full ceremony brainstorming → spec → plan; needs dedicated ADR |
| 9 | **Single paid validation A/B** | `v0.1.16` | — | Full cumulative system vs H15 (or re-baseline if any of 4/5/7/8 shipped); single accountable spend; bundle-level attribution accepted |

Each milestone follows the established H15.1/H15.2 pattern with ceremony scaled to scope (trivial / medium / full brainstorming-spec-plan-subagent-driven-finishing per CLAUDE.md §22.1-2 discipline). After `v0.1.16`, the roadmap returns to **H16 (deploy MVP)** and **H17 (TFM closure)** per CLAUDE.md §16.3.

---

## 7. Cost accounting

| Item | Estimated | Measured |
|---|---|---|
| T1-T5 implementation ($0) | $0 | $0 |
| T4 verification gate ($0) | $0 | $0 |
| T6 probe (cand-1 n=3) | €0.15 | **€0.19** (+27%) |
| T6 full (cand-1 n=30 planned) | €1.86 | **€2.24** consumed before crash (+20% per-case rate, +0% completed cases) |
| T7 (cand-2 probe + full) — CANCELLED | €1.65 | €0 (budget exhausted before T7) |
| T8 (holdout if winner) — CANCELLED | €0.85 | €0 |
| **Total H15.2 paid spend** | €4.51 envelope | **€2.43 actual** |
| **Persisted data on disk** | 30-case + 14-holdout reports | **3-case probe report only** |
| **Effective €/persisted-case** | €0.075 expected | **€0.81 actual** (10.8× worse) |

The cost analysis is included in the next iteration of `docs/cost_analysis.md` (H17 work).

---

## 8. References

- **Spec**: `docs/superpowers/specs/2026-05-20-h15-2-eval-redesign-design.md`
- **Plan**: `docs/superpowers/plans/2026-05-20-h15-2-eval-redesign.md`
- **ADR**: `docs/adr/0018-retriever-config-wired-into-explicit-path.md`
- **Keystone test**: `tests/unit/test_explicit_config_wired.py`
- **T6 invariant test (carried unchanged)**: `tests/unit/test_explicit_path_unchanged.py`
- **Probe evidence**: `evals/reports/h15/h15_2-cand1-probe.md`
- **H15 frozen control**: `evals/reports/h15/candidate-v1.2.md`
- **Decisions log**: `docs/technical_decisions_log.md` §H15.2
- **Predecessor study reports**: `docs/auditor_calibration.md` (H15), `docs/retriever_optimization.md` (H15.1 — predecessor whose §22.22 design-defect this milestone closes; H15.1's report is **unchanged at its time** for historical accuracy; H15.2 corrects the underlying constraint interpretation here)
- **Companion ADRs**: 0016 (H15 calibration + C1 safety backstop carried), 0017 (H15.1 cross-corpus auto path), 0013 (router env-override seam precedent)
