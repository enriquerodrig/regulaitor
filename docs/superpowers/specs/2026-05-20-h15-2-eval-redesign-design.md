# H15.2 — Eval rede-design (surgical constraint reinterpretation) — Design

**Status:** Design approved 2026-05-20 (brainstorming). Branch base: `main` @ `2540dcb` (post-H15.1-close, tag `v0.1.6-h15.1` @ `e283412`).
**Milestone:** H15.2 (decimal, no renumber — sibling of H15.1; precedent H0.1+H15.1). H16/H17 stay unchanged. Tag previsto `v0.1.7-h15.2`.
**Successor docs:** ADR-0018, decisions §H15.2 expansion, `docs/retriever_h15-2_redesign.md` (H15.2 study report), evidence_matrix, CLAUDE.md §27 → next deferred-fase-optimización item (chosen at H15.2 closure).

---

## 1. Goal & honest framing

Close the milestone-consequential design-defect §22.22 disclosed POST-SPEND in H15.1-T10/T11 by a **surgical reinterpretation of the T6 invariant at its actual narrower scope** (the no-leakage WHERE-CLAUSE) and a small backend wiring change that lets `DEFAULT_CONFIG.top_k`/`pre_rerank` flow into the explicit-corpus `run()` path. Production behavior remains byte-identical to `v0.1.6-h15.1` when `REGULAITOR_RETRIEVAL_CONFIG` is unset (the env default). With the env set in eval mode, the existing 30-case calibration A/B genuinely exercises the tuning lever for the first time, closing the measurement-design gap H15.1 honestly disclosed.

**Honest TFM-defense framing**: H15.1 caught that the implementation was over-constrained relative to what T6 actually asserts (the WHERE-CLAUSE string + empty short-circuit — NOT the absence of `DEFAULT_CONFIG` consumption). H15.2 corrects that conservative implementation interpretation rigorously. The H15.1 §4.3 "mutually exclusive as designed" framing was accurate for the chosen H15.1 implementation; H15.2 demonstrates that the underlying constraint (no-leakage byte-identical WHERE-CLAUSE) is genuinely narrower than the implementation chose, and the correction is small, safe, and well-scoped.

**Single focus**: this milestone is solely the measurement-design fix. xcorpus-002 verdict regression, document segmenter, no-Answer-residual robustness, Auditor RHR-aggregation, citation-granularity confound, and §17 thresholds + LLM-judge same-provider all remain DEFERIDO in the user-confirmed fase-optimización bundle — they will be registered as named follow-ups at H15.2 closure (next milestone chosen from them at closure time; H16/H17 untouched).

## 2. Decisions (D1–D5)

- **D1 — Scope = surgical reinterpretation only (single focus).** In scope: wire `DEFAULT_CONFIG.top_k`/`pre_rerank` into the explicit `run()` via the default-None param pattern; preserve the WHERE-CLAUSE byte-identical (T6 stays green); add a corollary test pinning the wiring and the no-leakage carry; re-run the H15.1 candidate A/B (cand-1+cand-2) on the existing 30-calibration set (which NOW genuinely exercises the lever). Out: xcorpus-002 investigation (deferred microhito); document segmenter (deferred); no-Answer-residual; Auditor RHR-aggregation; citation-granularity confound; §17 thresholds; gold-set extension (option B from brainstorming, explicitly rejected for this milestone).
- **D2 — Constraint reinterpretation (the keystone).** The T6 invariant (`tests/unit/test_explicit_path_unchanged.py`) asserts EXACTLY two things: (a) the explicit-corpus path's LanceDB where-clause is the literal `f"norma = '{corpus}' AND language = '{language}'"`; (b) the empty-rerank short-circuit returns `[]`. T6 does **NOT** assert `PRE_RERANK=50` (the `_S.limit(_n)` stub ignores its argument), does **NOT** assert `top_k=5` (the test passes it explicitly), and does **NOT** assert that `run()` is config-insensitive. The §22.18/H14 no-leakage guarantee is fundamentally about cross-corpus contamination (the where-clause), not about specific `top_k`/`pre_rerank` values. The H15.1 §4.3 "mutually exclusive as designed" wording was the conservative implementation interpretation, not what T6 actually enforces. H15.2's contribution is to honestly recognize this narrower-than-assumed constraint and implement the correction.
- **D3 — Implementation: default-None pattern; production-byte-identical via env-unset.** `rag/retrieval.run(query, corpus, language, top_k=None, pre_rerank=None)`: when `None`, read from `DEFAULT_CONFIG.top_k` / `DEFAULT_CONFIG.pre_rerank`. `RetrieverAgent.retrieve(query, corpus, language, top_k=None)`: pass through `None`. `mcp_server.search_articles(query, corpus, language, top_k=None)`: same pattern. With `REGULAITOR_RETRIEVAL_CONFIG` unset, `DEFAULT_CONFIG` is `RetrievalConfig(pre_rerank=50, top_k=5, ...)` → production behavior is byte-identical to v0.1.6-h15.1. With env set in eval mode, the explicit path now genuinely sees the override. **WHERE-CLAUSE preserved exactly** under both env states (the no-leakage carry; the central proof of H15.2). **§6 Auditor/citation-validator BYTE-UNCHANGED.** NO LanceDB re-ingest. 4-corpora stable §22.18 preserved.
- **D4 — A/B re-experiment discipline (carry H15 D4).** Frozen control = the already-committed `evals/reports/h15/candidate-v1.2.md` (H15 30-calibration baseline; **no paid re-baseline** because production-byte-identical-under-env-unset means the existing control is still valid for the H15.2 implementation when env is unset; the only thing that changed for the candidate runs is whether the env override actually has effect — and now it does). Single variable: only `REGULAITOR_RETRIEVAL_CONFIG`. Analyst stays H15-frozen v1.2; judge stays Haiku 4.5; gold-set unchanged; corpus index frozen. Re-run cand-1 (`{"pre_rerank":80,"top_k":8}`) and cand-2 (`{"pre_rerank":80,"top_k":3}`) on the 30 calibration cases — same hypotheses as H15.1, NOW genuinely measuring the lever. ≤2 candidate runs (D4 budget ≤3 honored with cushion). **USER-GATED probe-first discipline** before every paid run: per-candidate `--limit 3` probe (~€0.15) + cost-tally + explicit user OK + user credit confirmation, then full 30-case run on user OK. Controller runs paid jobs as persistent background (NOT delegated to a subagent — H14 lesson). Real cost via the existing H15 router accumulator. If a candidate wins (improves key metrics vs control without regressing no-leakage/safety): re-run 14-case holdout (`evals/h15_holdout_chat_ids.txt`) on the winning config (~€0.85, USER-GATED) for HARD-revert verification; if clean, update production `RetrievalConfig` defaults to the winning values. Realistic envelope (sequencing: probe1 → cand1 → probe2 → cand2 [→ holdout if winner]): ~€3.30 if no winner (2 × ~€0.15 probes + 2 × ~€1.5 candidates), ~€4.15 if winner ships (+ ~€0.85 holdout). User reaffirms credits before each paid step (estimates are unreliable historically — actual cost measured via probe).
- **D5 — Done-when (§22.22 honest, H15-style).** Code: explicit `run()` reads `DEFAULT_CONFIG` via default-None; T6 stays green unchanged; new corollary test green; production byte-identical to v0.1.6-h15.1 under env-unset; full gate `uv run pytest -m "not slow"` ≥90% + `uv run mypy src` exit 0 (cross-milestone gate-hygiene pattern from H15.1-T4, carried explicitly). Measurement-design fix lands: the A/B now genuinely measures the lever (the closing of the H15.1 §4 disclosure). HARD non-regression checks NONE fire (T6 WHERE-CLAUSE byte-identical under env-unset AND env-set; H15 30-calib `citation_recall` floor carry-forward ≥0.71 — the H15-measured 30-calib baseline floor, distinct from the looser §16.2#5 MVP gate ≥0.40; redteam-smoke 0.92 prompt-blind; 6 H15 designated block cases content-safe — all re-verified on winning config if production defaults change). **NO promised metric number** — defended outcome = measured improvement on the now-genuine A/B OR documented deeper system-level ceiling (both defend, H15-style). **REVERT any candidate that improves a metric but regresses no-leakage/safety.** If no winner, the code change ships anyway — the measurement-design fix is itself the H15.2 contribution (the H15.1 design-defect is closed regardless of A/B outcome).

## 3. Architecture

**The wiring is purely additive at the API surface; observable production behavior unchanged.**

| File | Change |
|---|---|
| `src/regulaitor/rag/retrieval.py` | `run(query, corpus, language, top_k=None, pre_rerank=None) -> list[RetrievedChunk]` — params optional; `None` → `DEFAULT_CONFIG.top_k` / `DEFAULT_CONFIG.pre_rerank` resolved INSIDE `run()`. The internal use of `PRE_RERANK = 50` module constant becomes `DEFAULT_CONFIG.pre_rerank` lookup at call time (the module constant stays as the documented default value of `RetrievalConfig.pre_rerank` — backward-compatible). WHERE-CLAUSE construction byte-identical: `f"norma = '{corpus}' AND language = '{language}'"`. `_enrich`/`run_auto`/`_apply_purity_gate` byte-unchanged. |
| `src/regulaitor/agents/retriever.py` | `RetrieverAgent.retrieve(query, corpus, language, top_k=None) -> Context` — `top_k` default `None`; pass-through to `rag_retrieval.run(query, corpus, language, top_k=top_k)`. The `auto` branch (calls `run_auto(query, language, DEFAULT_CONFIG)`) unchanged. |
| `src/regulaitor/mcp_server/tools.py` | `search_articles(query, corpus, language, top_k=None) -> list[RetrievedChunk]` — same default-None pattern; pass-through. The `auto` branch unchanged. |
| `tests/unit/test_explicit_path_unchanged.py` (T6) | **UNCHANGED**. T6 already asserts only the WHERE-CLAUSE + empty-rerank short-circuit. It continues to pass under the H15.2 implementation by construction (the wiring change does not touch the WHERE-CLAUSE construction). |
| `tests/unit/test_explicit_config_wired.py` (NEW) | The keystone proof. Asserts: (a) **env UNSET** → explicit `run()` consults `DEFAULT_CONFIG` defaults `top_k=5, pre_rerank=50` (production-byte-identical to v0.1.6-h15.1); (b) **env set** to e.g. `{"top_k":3,"pre_rerank":80}` → explicit `run()` uses `top_k=3, pre_rerank=80`; (c) **WHERE-CLAUSE still exactly `f"norma = '{corpus}' AND language = '{language}'"` under BOTH env states** (the no-leakage carry — the central H15.2 proof). |
| `docs/adr/0018-retriever-config-wired-into-explicit-path.md` (NEW) | The constraint reinterpretation ADR: T6 invariant scope clarified (WHERE-CLAUSE only); DEFAULT_CONFIG wiring justified; H15.1 §4.3 "mutually exclusive" framing honestly revisited as conservative implementation interpretation; §6 / T6 untouched; backward-compat preserved. |
| `docs/retriever_h15-2_redesign.md` (NEW H15.2 study report) | The honest H15.2 narrative: constraint-reinterpretation framing + A/B re-experiment + honest verdict. H15.1's `docs/retriever_optimization.md` stays unchanged (historical accuracy at H15.1's time); the H15.2 study references and corrects it. |

**Data flow (production, env unset)**: identical to v0.1.6-h15.1. Caller → `RetrieverAgent.retrieve(top_k=None)` → `rag_retrieval.run(corpus, language, top_k=None, pre_rerank=None)` → resolves `top_k=DEFAULT_CONFIG.top_k=5`, `pre_rerank=DEFAULT_CONFIG.pre_rerank=50` (env unset) → embed → LanceDB search filtered by exact WHERE-CLAUSE `f"norma = '{corpus}' AND language = '{language}'"` `.limit(pre_rerank)` → rerank `top_n=top_k` → `_enrich` → return.

**Data flow (eval, env set)**: identical except `DEFAULT_CONFIG.top_k`/`pre_rerank` resolved from the env JSON override → explicit path uses the override values → A/B now measures the lever genuinely.

**Invariant**: under any env state, the WHERE-CLAUSE construction is `f"norma = '{corpus}' AND language = '{language}'"` byte-for-byte — the §22.18/H14 no-leakage guarantee. The new corollary test asserts this explicitly.

## 4. A/B re-experiment method

- **Frozen control**: `evals/reports/h15/candidate-v1.2.md` (H15-frozen, 30 chat-001..030, Analyst v1.2, env unset → `top_k=5, pre_rerank=50`). Still valid as H15.2's control because H15.2's env-unset behavior is byte-identical to v0.1.5-h15 / v0.1.6-h15.1 (proven by the new corollary test).
- **Single variable**: only `REGULAITOR_RETRIEVAL_CONFIG`. Analyst stays v1.2-frozen; judge stays Haiku 4.5; gold stays unchanged; corpus index frozen.
- **Re-experiments** (USER-GATED, probe-first):
  - `--limit 3` probe of cand-1 (~€0.15, ~6 min/case at v1.2) → cost-tally → user OK → full 30-case cand-1 (~€1.5).
  - Cost-tally + ab_delta vs control → user OK → `--limit 3` probe of cand-2 → full 30-case cand-2 (~€1.5).
  - Both candidates: `REGULAITOR_RETRIEVAL_CONFIG={"pre_rerank":80,"top_k":<8 or 3>}`, Analyst v1.2, same gold + judge + control as H15.1.
- **Winner criterion** (§22.22, no promised number): a candidate wins if it improves on the H15 frozen control on the canonical metrics (faithfulness/answer_relevancy/context_precision/context_recall/citation_precision/citation_recall/verdict_match/severity_match) without regressing the floors (citation_recall ≥0.71, T6 WHERE-CLAUSE unchanged, redteam-smoke ≥0.92 prompt-blind, 6 H15 block-cases content-safe).
- **If a candidate wins**: USER-GATED holdout on the winning config (`evals/h15_holdout_chat_ids.txt`, 14 H14 chat, ~€0.85, once-never-iterated D3 holdout discipline carried). HARD-revert verification (citation_recall floor, T6, redteam-smoke on winning defaults, the 6 block cases re-verified content-safe under winning config). If clean, update production `RetrievalConfig` defaults to the winning values + that becomes H15.2's measured contribution.
- **If no winner**: production defaults stay `top_k=5, pre_rerank=50`; the contribution is the surgical code change + the now-genuine measurement showing the H15-documented system-level ceiling holds even under a properly-exercised tuning sweep (documented deeper ceiling — H15-style "both defend").

## 5. HARD guards & testing

- **Structural invariant (the central H15.2 proof)**: WHERE-CLAUSE byte-identical under env-unset AND env-set; asserted by the new `test_explicit_config_wired.py` (under both env states); T6 stays green unchanged (it already asserts the env-unset WHERE-CLAUSE).
- **No-leakage carry-forward (D5)**: citation_recall floor on 30-calib ≥0.71 (carry from H15); a candidate regressing below it → REVERTED.
- **Safety carry-forward (D5)**: redteam-smoke block_rate ≥0.92 (re-verified on winning config if production defaults change; prompt-blind/sanitizer/injection layers — retriever change does not affect, but verify). The 6 H15 designated block cases (chat-014/015/029/030 + nis2-006/dora-006) must stay content-safe under the winning config (C1 manual backstop carried).
- **§6 invariant**: Auditor + citation-validator byte-unchanged — verified by `git diff main...HEAD -- src/regulaitor/agents/auditor.py src/regulaitor/citation/validator.py` showing empty diff at final whole-branch review.
- **Testing strategy**:
  - **$0 TDD** (the new `test_explicit_config_wired.py`): env-unset → defaults; env-set → override values; WHERE-CLAUSE byte-identical under both. Pure unit tests, no LLM, no network, no paid. The keystone H15.2 proof.
  - **Full gate**: `uv run pytest -m "not slow"` ≥90% coverage + `uv run mypy src` exit 0 (T4 cross-milestone gate-hygiene pattern carried — both run explicitly at closure).
  - **Paid runs**: USER-GATED, controller-run persistent background jobs (NOT delegated to subagents — H14 lesson). Probe-first before every paid run (H15 D4).

## 6. Done-when

- Code: explicit `run()` reads `DEFAULT_CONFIG`; T6 stays green unchanged; `test_explicit_config_wired.py` green; production byte-identical to v0.1.6-h15.1 when env unset; full gate `pytest -m "not slow"` ≥90% green + `mypy src` exit 0.
- Measurement-design fix lands: A/B genuinely measures the lever (the closing of H15.1 §4 disclosure — verified by the wiring test + the actual A/B re-experiment producing config-induced behavior change).
- HARD-revert checks NONE fire (WHERE-CLAUSE/T6, citation_recall floor, redteam-smoke, 6 block cases content-safe under any chosen winning config).
- Outcome: measured improvement on now-genuine A/B + holdout-if-winner OR documented deeper system-level ceiling — both defend (H15-style honest done-when, NO promised number).
- Closure: ADR-0018; `docs/retriever_h15-2_redesign.md` study report; decisions §H15.2 expansion + named microhito follow-ups (xcorpus-002, segmenter, no-Answer, Auditor-RHR, citation-granularity, LLM-judge same-provider); evidence_matrix H15.2 row + ADR-count gate → 18; CLAUDE.md §27 (move H15.2 to "Hitos cerrados", set "Hito siguiente" to whichever deferred item the user chooses at closure — H16/H17 unchanged); memory roll-forward `h15-1_closed_h15-2_starting.md` → `h15-2_closed_<next>_starting.md`; tag `v0.1.7-h15.2`.

## 7. Deliverables

1. Code (3 src files + 1 new test, ~50-100 lines net):
   - `src/regulaitor/rag/retrieval.py` — `run()` signature evolution + DEFAULT_CONFIG resolution; WHERE-CLAUSE/`_enrich`/`run_auto`/`_apply_purity_gate` byte-unchanged.
   - `src/regulaitor/agents/retriever.py` — `RetrieverAgent.retrieve()` default-None pattern.
   - `src/regulaitor/mcp_server/tools.py` — `search_articles()` default-None pattern.
   - `tests/unit/test_explicit_config_wired.py` (NEW) — the keystone wiring + no-leakage-carry proof.
2. ADR-0018 — constraint reinterpretation decision.
3. `docs/retriever_h15-2_redesign.md` — the honest H15.2 study report (~250-350 lines; smaller than H15.1's ~520 because tighter scope; mirrors `docs/auditor_calibration.md` / H15.1 structure).
4. Evidence force-add: `evals/reports/h15/h15_2-cand1-probe.md`, `h15_2-cand1.md`, `h15_2-cand2-probe.md`, `h15_2-cand2.md`, `h15_2-holdout.md` (if winner) — gitignored, force-added per H12/H15/H15.1 evidence-tracking precedent.
5. Closure docs: decisions §H15.2 expansion + named microhito follow-ups; evidence_matrix H15.2 row + ADR-count + decisions-log line-count update; CLAUDE.md §16.3 (H15.2 marked done; no new entry — the next milestone is chosen at closure) + §27 (Hitos cerrados H15.2 bullet + Hito siguiente = chosen deferred-fase-optimización item; H16/H17 untouched).
6. Tag `v0.1.7-h15.2`.

## 8. Out of scope (explicit)

- Document segmenter (the "0 segmentos" confound from H15 probe) — DEFERIDO; registered as named microhito at H15.2 closure.
- xcorpus-002 verdict regression (RHR→block on auto path) — DEFERIDO; registered as microhito at H15.2 closure (n=1 purity_threshold sweep + reranker diagnosis, ~€0.5 when executed).
- No-Answer-residual robustness (2/14 holdout empty-answer from H15) — DEFERIDO; named microhito.
- Auditor RHR-aggregation + `MonotonicEscalatePolicy`/`_COUNCIL_BINDING` seam (still OFF) — DEFERIDO; the §6-invariante-adjacent work merits its own milestone.
- Citation-metric granularity confound (gold H8 apartado-level vs H14 article-level) — DEFERIDO eval-instrument work; requires full A/B re-baseline if changed.
- §17 thresholds + LLM-judge same-provider-family (Haiku judge vs Sonnet prod, ADR-0010) — DEFERIDO; router-multi-LLM-judge future milestone.
- Gold-set extension with auto-path cases at N≥15-20 (option B from brainstorming) — explicitly rejected for H15.2; tuning lever now measurable on the existing 30 calibration via the wiring fix, so the gold extension is not needed for H15.2's success condition.
- Doc-mode A/B — blocked by the segmenter confound; deferred until the segmenter microhito lands.
- Production `RetrievalConfig` field additions (e.g. new tuning knobs) — YAGNI; the 4 existing fields are the in-scope levers.

## 9. Risks

- **Test asserting where-clause regresses inadvertently** (e.g. someone refactors the f-string later breaking the literal). Mitigation: T6 already pins it; the new corollary test pins it under env-set too; mypy strict gate; full pytest gate.
- **Production behavior subtly differs from v0.1.6-h15.1 under env-unset** despite the intent. Mitigation: the new corollary test explicitly asserts production-byte-identical behavior under env-unset; full pytest + mypy gate; final whole-branch review's spot-checks include this property.
- **Both candidates fail to improve on the H15 frozen control** even with the genuine measurement — i.e. cand-1 (top_k=8) AND cand-2 (top_k=3) both regress or are flat. This is the "documented deeper ceiling" outcome (H15-style honest done-when — both defend). NOT a milestone failure; the contribution is the measurement-design fix + the now-genuine evidence that the H15-documented ceiling is real.
- **A candidate wins on most metrics but regresses citation_recall floor or the 6 block cases**. The HARD-revert triggers; that candidate is reverted; the other candidate becomes the winner if it cleared the bar, else "documented deeper ceiling".
- **Production callers passing `top_k` explicitly** (vs default-None) might mask the DEFAULT_CONFIG wiring. Mitigation: grep at design + test time confirms which callers pass explicit `top_k`; production callers (graph + retriever + mcp tool) should all pass `None` after H15.2 (the wiring point); explicit-`top_k` callers stay backward-compatible (override-per-call still works).
- **The H15 frozen control was measured under the H15.1 code (which had `top_k=5` hardcoded)**; H15.2's env-unset behavior MUST be byte-identical. Mitigation: the new corollary test asserts this; the full gate runs; if it doesn't hold, a paid re-baseline would be needed (~€1.5) — but the wiring change is small enough that drift is extremely unlikely.
- **Scope creep into the deferred fase-optimización items** mid-milestone. Mitigation: §8 "out of scope" is explicit; subagent-driven-development discipline; review per task.
