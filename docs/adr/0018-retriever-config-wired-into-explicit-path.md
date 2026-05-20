# ADR 0018 — Retriever `RetrievalConfig` wired into explicit-corpus `run()` path (H15.2)

- **Status:** Accepted — 2026-05-20 — squash `0bf8081`, tag `v0.1.7-h15.2`
- **Deciders:** Project owner.
- **Companion ADRs:** 0017 (H15.1 — the milestone whose §22.22 design-defect this
  ADR closes), 0016 (H15 — the calibration study + C1 content-based safety
  backstop carried), 0013 (router multi-LLM — the
  `REGULAITOR_ROUTER_MODE` eval-override seam precedent for env-driven config).

## Context

H15.1 (ADR-0017) added the opt-in `corpus="auto"` cross-corpus retrieval path and
introduced `RetrievalConfig` (`pre_rerank`, `top_k`, `purity_threshold`,
`query_normalize`) as the contained tuning levers, with the explicit-corpus path
kept byte-identical to `v0.1.5-h15` "by construction" — the explicit `run()`
function continued to use the module-level `PRE_RERANK = 50` constant and the
function-parameter default `top_k = 5`, never consulting `DEFAULT_CONFIG`.

H15.1's spec §4 intended the 30-case calibration A/B to measure the tuning lever
on the explicit-corpus calibration set. The A/B ran (~€3.01) and surfaced a
**milestone-consequential design-defect §22.22** in H15.1-T10/T11 (POST-SPEND):
because the explicit-corpus path consumed `DEFAULT_CONFIG` in ZERO sites and the
30 calibration cases are all explicit-corpus, `REGULAITOR_RETRIEVAL_CONFIG` had
no mechanism on the measurement — the €3.01 of cand-1+cand-2 deltas measured
LLM-provider non-determinism, NOT a real tuning-lever signal.

The H15.1 §4.3 framing called the no-leakage guarantee (T6,
`tests/unit/test_explicit_path_unchanged.py`) and the spec §4 A/B intent
"mutually exclusive as designed". On re-grounding for H15.2, T6 was found to
assert EXACTLY two properties: (a) the WHERE-CLAUSE string equals
`f"norma = '{corpus}' AND language = '{language}'"` ; (b) an empty-rerank
short-circuit returns `[]`. T6 does **not** assert `PRE_RERANK=50`, does **not**
assert `top_k=5`, does **not** assert that `run()` is config-insensitive — the
stub `_S.limit(_n)` ignores its argument and the test passes `top_k=5`
explicitly. The §22.18/H14 no-leakage guarantee is fundamentally about
cross-corpus contamination (the WHERE-CLAUSE), not about specific
`top_k`/`pre_rerank` values.

The H15.1 framing was the conservative implementation interpretation of T6's
actual narrower scope. The architectural constraint is genuinely narrower than
the H15.1 implementation chose.

## Decision

Wire `DEFAULT_CONFIG.top_k` and `DEFAULT_CONFIG.pre_rerank` into the explicit
`rag.retrieval.run()` via the default-`None` parameter pattern, with per-call
attribute resolution. Production behavior remains byte-identical to
`v0.1.6-h15.1` when `REGULAITOR_RETRIEVAL_CONFIG` is unset; eval-time behavior
becomes genuinely config-sensitive when the env is set.

`run(query, corpus, language, top_k=None, pre_rerank=None)`. `top_k=None` →
resolves to `DEFAULT_CONFIG.top_k` AT CALL TIME. `pre_rerank=None` → resolves to
`DEFAULT_CONFIG.pre_rerank` AT CALL TIME. Explicit non-`None` values win
(backward-compat). Call-time resolution (NOT function-definition-time capture)
is what makes the eval harness's `REGULAITOR_RETRIEVAL_CONFIG` env-override flow
through. `RetrieverAgent.retrieve` and `mcp_server.tools.search_articles` adopt
the same default-`None` pass-through pattern.

The WHERE-CLAUSE construction line stays byte-identical character-for-character
under any env state — the no-leakage-critical line. The architectural invariant being preserved is cross-corpus isolation (the WHERE-CLAUSE construction), not the specific values of `top_k` or `pre_rerank` — which was the conservative interpretation H15.1's implementation chose and H15.2 corrects. `_enrich`, `run_auto`,
`_apply_purity_gate`, `RetrievalConfig`, `_config_from_env`, `DEFAULT_CONFIG`
initialization, `PRE_RERANK` module constant, all unchanged. §6 (Auditor +
`citation/validator`) byte-unchanged. No LanceDB re-ingest.

The keystone assertion is `tests/unit/test_explicit_config_wired.py`: env-unset
→ defaults (production-byte-identical); env-set → override flows through;
WHERE-CLAUSE byte-identical under BOTH env states. T6
(`tests/unit/test_explicit_path_unchanged.py`) is unchanged and continues to
pass — it already asserted exactly what H15.2 preserves.

## Consequences

**Positive:**

- The H15.1 §22.22 design-defect is closed: the 30-case calibration A/B is now
  genuinely capable of measuring the tuning lever on the explicit-corpus path.
  The H15.2 re-experiment (T6–T8) produces real signal where H15.1's measured
  €3.01 was provably non-determinism noise.
- Production behavior is byte-identical to `v0.1.6-h15.1` when
  `REGULAITOR_RETRIEVAL_CONFIG` is unset — verified by the new keystone test
  asserting `top_k=5, pre_rerank=50` under env-unset and by T6 continuing to
  pass unchanged.
- The §22.18/H14 no-leakage guarantee is preserved at its actual scope (the
  WHERE-CLAUSE) under BOTH env-unset and env-set — the keystone test extends
  T6's invariant to the env-set case.
- The §6 "no citation, no answer" Auditor / citation-validator invariant is 100%
  intact: those components are byte-unchanged.
- The LLM-free retriever principle is preserved: `run()` calls no LLM; the
  config resolution is a pure attribute access.
- The `REGULAITOR_RETRIEVAL_CONFIG` env seam (ADR-0017) now has end-to-end
  effect on both the auto path AND the explicit path — the H15.1 surface remains
  exactly the same, with the H15.2 wiring making the surface genuine.

**Negative / accepted (documented honestly per §22.22):**

- The H15.1 implementation's conservative interpretation of T6 was a
  measurement-design gap that cost €3.01 of paid LLM time before being
  surfaced. The honest TFM-defense framing is: H15.1's per-task reviews
  validated per-task correctness but did not check cross-task design
  coherence (the A/B's ability to actually measure what the spec said it
  measured); H15.2 surfaces and closes that gap. Discipline: any future
  measurement-design choice involving multiple integration sites (env →
  config → consuming code path) should be reviewed for end-to-end effect
  BEFORE paid measurement (a new follow-up registered at H15.2 closure).
- Two production wrappers (`RetrieverAgent.retrieve` and `search_articles`)
  changed signature default from `top_k=5` to `top_k=None`. This is observable
  from the outside via reflection or `inspect.signature` but **not** from any
  test that calls with explicit `top_k=N` (the dominant pattern in the
  codebase). One existing test (`test_retriever_agent_default_top_k_is_5`) was
  updated to assert the new (correct) pass-through behavior — the old name was
  over-constrained (it asserted "5 specifically" rather than "the default flowed
  through to DEFAULT_CONFIG"); the renamed test
  `test_retriever_agent_default_top_k_passes_none_through` asserts the
  architectural invariant the wrapper actually upholds.
- Measured A/B results: **probe n=3 PRODUCED MEASURED €0.19 directional positive**
  (faith +0.23, verdict_match +0.40 vs control H15; NOT defensible as "improvement"
  at n=3). T6 full 30-case **CRASHED mid-flight** with credit exhaustion at case
  ~24/30; T7+T8 cancelled. Total €2.43 spent (entire balance), only probe persisted.
  Single paid validation deferred to `v0.1.16` per user-confirmed maximalist
  microhito plan. This ADR records the **decision and framework**; the canonical
  outcome narrative is in `docs/retriever_h15-2_redesign.md`.

## Alternatives considered

- **Re-architect `run()` to take a `RetrievalConfig` parameter explicitly** —
  rejected (YAGNI, breaking change at every call site). The default-`None`
  pattern preserves the existing signatures' positional shape while threading
  the config seam through.
- **Extend the gold-set with auto-path cases at N≥15 (Option B from H15.2
  brainstorming)** — rejected for H15.2. The tuning lever is now measurable on
  the existing 30-calibration set via the surgical wiring fix, so gold-set
  extension is not needed for H15.2's success condition (it would also require
  paid re-baseline, blowing the budget). Registered as a future fase-optimización
  microhito option (not the chosen next step at H15.2 closure — that is the
  user's decision at closure time, among the deferred items).
- **Capture `DEFAULT_CONFIG` values at function-definition time** (e.g.
  `def run(top_k: int = DEFAULT_CONFIG.top_k, ...)`) — rejected. Function
  defaults are evaluated once at module import; the env-override would only
  work if set BEFORE the first `import regulaitor.rag.retrieval`. The
  per-call attribute resolution is the architecturally-correct choice for
  the env-override seam.
- **Modify T6 to assert the broader "config-insensitivity" invariant** —
  rejected. T6's actual narrow scope IS the right architectural invariant
  (the WHERE-CLAUSE no-leakage line); broadening it would re-encode the
  H15.1 conservative implementation interpretation as architecture, which
  is exactly what H15.2 corrects.

## References

- Spec: `docs/superpowers/specs/2026-05-20-h15-2-eval-redesign-design.md`
- Plan: `docs/superpowers/plans/2026-05-20-h15-2-eval-redesign.md`
- Decisions log `§H15.2` (D1–D5, constraint reinterpretation, A/B re-experiment
  results, named microhito follow-ups — populated post-Tasks-6–10)
- ADR 0017 (H15.1 — the milestone whose §22.22 design-defect this ADR closes)
- ADR 0016 (H15 — calibration study + C1 content-based safety backstop carried)
- `src/regulaitor/rag/retrieval.py` (`run()` per-call DEFAULT_CONFIG resolution)
- `tests/unit/test_explicit_config_wired.py` (keystone proof)
- `tests/unit/test_explicit_path_unchanged.py` (T6 — unchanged, continues to pass)
- `evals/reports/h15/h15_2-cand1-probe.md` (probe n=3 PRODUCED, MEASURED €0.19). Files `h15_2-cand1.md` (full T6), `h15_2-cand2.md` (T7), and `h15_2-holdout.md` (T8) were **NOT produced** — T6 full run crashed mid-flight with credit exhaustion at case ~24/30; T7+T8 cancelled for budget exhaustion. See `docs/retriever_h15-2_redesign.md` §4.2 for the honest partial-outcome narrative; the single paid validation is deferred to `v0.1.16` per the user-confirmed maximalist microhito plan.
- `docs/retriever_h15-2_redesign.md` (study report — produced in T9; canonical narrative)
