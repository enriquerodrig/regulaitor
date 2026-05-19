# H15.1 — Retriever optimization (cross-corpus `auto` path + tuning) — Design

**Status:** Design approved 2026-05-19 (brainstorming). Branch base: `main` @ `5fd2fad` (post-H15-close, tag `v0.1.5-h15` @ `76fc6e7`).
**Milestone:** H15.1 (decimal, no renumber — precedent H0.1; roadmap decision `5fd2fad`, decisions log §H15.1).
**Successor docs:** ADR-0017, decisions §H15.1 (expand), `docs/retriever_optimization.md` (study report), evidence_matrix, CLAUDE.md §27 → H16. Tag `v0.1.6-h15.1`.

---

## 1. Goal & honest framing

Lift the **real retrieval quality** of RegulAItor against the frozen `v0.1.5-h15`
control, attacking the dominant remaining system-level lever the H15 study
documented (context_precision ~0.60 < 0.80, which drags faithfulness / recall /
answer_relevancy). Per CLAUDE.md §22.22 "métricas = que el sistema funcione lo
más preciso posible", never metric-gaming/overfitting.

This is an **optimization milestone** (not a study like H15). It makes two kinds
of change, justified differently and honestly (the approved done-when, §6):

- A **correctness fix**: today the retriever cannot serve a cross-corpus
  question. `corpus` is a *required, caller-specified* field everywhere
  (`api/schemas.py` `Literal["ai_act","gdpr","nis2","dora"]`,
  `graph.run(corpus=…)`, `mcp_server.search_articles(corpus)`), so a question
  spanning two norms (e.g. "how do NIS2 and DORA interact?") can only ever be
  asked against one corpus → it structurally cannot cite both
  (xcorpus-001/002 retrieve context 0.00). Justified by **correctness**, not by
  aggregate-metric movement (N=2; reported per-case).
- **Tuning levers** (`PRE_RERANK`, `top_k`, purity threshold, deterministic
  query construction): justified by **measured A/B improvement** vs the frozen
  control.

No re-embed, no re-chunk: the 4-corpus LanceDB index (§22.18) is **not** touched.

## 2. Decisions (D1–D5)

- **D1 — Scope = retriever only.** Segmenter / no-Answer-residual robustness /
  Auditor-RHR-aggregation are **out** (later decimals H15.2+ or deferred —
  user-approved decomposition; the Auditor lever touches the §6 invariant and
  deserves its own milestone). Doc-mode A/B is **out** (blocked by the deferred
  segmenter confound) — H15.1 measures **chat-only**, exactly as H15 did.
- **D2 — Contained levers only.** In scope: a new `corpus="auto"` path +
  `RetrievalConfig` params (`PRE_RERANK`, `top_k`, purity threshold,
  deterministic query construction). **Out**: chunking change, embedding/reranker
  model change, any LanceDB re-ingest (§22.18 4-corpus index untouched). Query
  construction stays **deterministic** (normalization only — no LLM query
  expansion; preserves the deliberate "retriever calls no LLM" architecture
  principle, `RetrieverAgent` docstring).
- **D3 — Post-rerank purity gate; explicit path byte-identical.** When `corpus`
  is one of the four norms (today's only behavior) the retrieval code path is
  **byte-identical** to `v0.1.5-h15` (single-`norma` where-clause, no gate) →
  existing scoped requests have **zero behavior change**; single-corpus
  no-leakage (§22.18 / H14-verified) is preserved *by construction*. A new
  `corpus="auto"` value triggers: retrieve `PRE_RERANK` across all 4 corpora
  (language-filtered) → existing `bge-reranker-v2-m3` cross-encoder → a
  deterministic `_apply_purity_gate`: if the top reranked overwhelmingly belong
  to one `norma` (≥ tunable threshold) → collapse to that corpus (no-leakage
  restored even on the auto path); else → genuine cross-corpus top-k.
- **D4 — Budget & A/B discipline (carried from H15 D4).** The frozen control is
  the **already-committed** H15 evidence (`evals/reports/h15/candidate-v1.2.md`
  30-calibration + `holdout-v1.2-chat.md` 14-holdout) — H15.1 branches from
  `v0.1.5-h15` with no intervening code, so these **are** a clean control; **no
  paid re-baseline** (saves ≈€1.85). Single variable: only the retriever
  changes (Analyst stays the H15-frozen v1.2; Auditor/judge/gold unchanged
  except xcorpus→`"auto"`). Iterate on the 30 calibration (chat-001..030,
  xcorpus-001/002 on `"auto"`); **holdout = 14 H14 chat measured ONCE, never
  iterated**. ≤3 `RetrievalConfig` candidate iterations. `--limit 3` probe +
  hard `--limit N` cap before every paid run; running cost-tally + explicit
  user OK + user credit confirmation before any paid spend (USER-GATED).
  Controller runs long paid eval jobs as persistent background (H14 lesson — not
  delegated to a subagent). Real cost via the existing H15 router accumulator
  (no new instrument). Realistic spend ≈ €5–6 of ~$10 available.
- **D5 — Done-when (honest, §22.22).** Rigorous documented A/B vs the committed
  frozen control; the cross-corpus fix is defended by **correctness** (per-case
  xcorpus-001/002, not folded into the aggregate — H15's 6-RHR discipline); the
  tuning levers by **measured improvement**. HARD non-regression: redteam-smoke
  block_rate must not drop below the frozen 0.92 (§16.2#4) AND the 6 H15
  designated block cases stay content-safe (C1 content-based manual backstop
  carried) AND the explicit-corpus path output is unchanged. **Any candidate
  that improves a metric but regresses no-leakage or safety is reverted.** Gate
  `uv run pytest -m "not slow"` ≥90% coverage green. **No promised metric
  number** — defended outcome = a measured improvement OR a documented deeper
  system-level ceiling (both defend).

## 3. Architecture

**The `"auto"` path is purely additive; the explicit-corpus path is byte-identical.**

| File | Change |
|---|---|
| `src/regulaitor/rag/retrieval.py` | `run()`: `corpus != "auto"` → **current code verbatim** (single-`norma` where-clause, no gate). `corpus == "auto"` → drop `norma` filter (keep `language`), `limit(PRE_RERANK)` across the 4 corpora → existing reranker → new pure helper `_apply_purity_gate(reranked_with_norma, threshold, top_k)`. Module-level `RetrievalConfig` (frozen defaults = today's values). |
| `src/regulaitor/citation/schemas.py` | `Context.corpus`: widen to `Norma \| Literal["auto"]`; add `resolved_normas: list[Norma]` (transparency — which corpora the returned chunks came from). `RetrievedChunk` already carries `.norma` per chunk (no change). |
| `src/regulaitor/api/schemas.py` + `routes_ask.py` | add `"auto"` to the `corpus` Literal; the route already forwards `corpus=payload.corpus` (no logic change). |
| `src/regulaitor/orchestration/graph.py` | `ChatState.corpus` type widen; `_retriever_node` already forwards `state.corpus` (no logic change); `run()` cast widened. |
| `src/regulaitor/agents/retriever.py` | `RetrieverAgent.retrieve` signature type widen; forwards through (no logic change); populates `Context.resolved_normas` from the returned chunks' `.norma`. |
| `src/regulaitor/mcp_server/tools.py` | `search_articles` `corpus` type widen; forwards to `rag_retrieval.run` (no logic change). |
| `evals/harness.py` + `evals/gold_set.jsonl` | xcorpus-001/002 → `corpus="auto"`; harness threads `"auto"` end-to-end (eval zone, like H15's harness extensions). |
| `docs/adr/0017-retriever-cross-corpus-auto.md` | new ADR for the `corpus="auto"` + purity-gate architecture (mirrors H15's ADR-0016). |

**`RetrievalConfig` (tuning levers, frozen defaults = today's values):**
`pre_rerank` (default 50 — current `PRE_RERANK`), `top_k` (default 5 — current
default), `purity_threshold` (auto-path only; default chosen so a clearly
single-corpus query collapses — pinned in the plan with a justified initial
value, then an A/B lever), `query_normalization` (default identity = current
behavior; optional deterministic normalization is an A/B lever, never LLM).
Frozen defaults guarantee the explicit path is provably unchanged; the auto
path and any tuned value are the A/B variable.

**Data flow (auto path):** query → `graph(corpus="auto")` →
`RetrieverAgent.retrieve` → `rag_retrieval.run(auto)`: embed query → LanceDB
search (language filter only, no `norma` filter) `limit(pre_rerank)` →
`reranker.rerank` → `_apply_purity_gate`: **`share(norma)` = the count of that
`norma`'s chunks among the top-`top_k` reranked, divided by `top_k`** (count-
based, deterministic; score-mass weighting is an explicit A/B alternative the
plan may pin as a candidate iteration, not the default). If
`max_share ≥ purity_threshold` → keep only that `norma`'s chunks and take
`top_k` within it (no-leakage restored); else → multi-corpus `top_k` →
`RetrievedChunk[]` (each self-describes `.norma`) →
`Context(corpus="auto", resolved_normas=[…])` → Analyst → Auditor.

**Invariant (explicit, §6):** the **Auditor and the citation validator are NOT
touched**. They already validate every emitted citation against its own corpus.
Multi-corpus retrieval only widens what the Analyst *can* ground in; "no
citation, no answer" stays 100% intact, exactly as H15 kept it.

## 4. A/B method

- **Frozen control:** committed `evals/reports/h15/candidate-v1.2.md` (30
  calibration) + `holdout-v1.2-chat.md` (14 holdout). Their xcorpus-001/002
  numbers were measured under single-corpus, so the xcorpus delta specifically
  isolates the cross-corpus fix.
- **Single variable:** only the retriever (`RetrievalConfig` / auto-path).
- **Two separable effects, reported separately:** (a) cross-corpus correctness
  — xcorpus-001/002 on `"auto"`, **per-case** (not folded into the 30-mean);
  (b) tuning-lever effect — 28 explicit-corpus calibration + 12 explicit
  holdout chat, judged by measured A/B improvement.
- **Sets:** calibration = 30 chat (chat-001..030; xcorpus-001/002 → `"auto"`);
  holdout = 14 H14 chat (`evals/h15_holdout_chat_ids.txt`) measured ONCE.
- **Cost:** measured via the existing router accumulator. ≈€0.05/chat-case
  (H15 actuals) → ≈€1.5 per 30-case candidate, ≤3 iterations, holdout 14
  ≈€0.78, probes ~€0.5 → realistic ≈€5–6; re-baseline NOT needed.

## 5. HARD guards & testing

- **No-leakage non-regression (structural + asserted):** explicit-corpus path
  byte-identical → the 28 explicit calibration + 12 explicit holdout cases are
  regression-zero *by construction*; additionally asserted by a test proving
  explicit-corpus retrieval output is identical pre/post. The auto-path purity
  gate is unit-tested: single-corpus-dominant query → gate collapses to one
  `norma` (no leakage); genuine cross-corpus query → multi-corpus returned.
- **Safety non-regression (HARD, H15 pattern):** redteam-smoke block_rate must
  not drop below the frozen 0.92 (§16.2#4); the 6 H15 designated block cases
  (chat-014/015/029/030 + holdout nis2-006/dora-006) stay content-safe
  (C1 content-based manual backstop carried — a retriever change must not let
  an attack retrieve something that flips a grounded refusal). **Revert** any
  candidate that improves a metric but regresses no-leakage or safety.
- **Testing (TDD where applicable):** `_apply_purity_gate` is a pure function —
  unit tests for threshold boundary, ties, empty rerank, single-corpus
  dominance, genuine multi-corpus. Explicit-path-unchanged assertion. Harness
  `"auto"` end-to-end threading test. $0 mocked/local unit tests; the paid A/B
  runs are USER-GATED execution steps, not unit tests. Full
  `uv run pytest -m "not slow"` ≥90% coverage is the authoritative gate.

## 6. Done-when

Rigorous documented A/B vs the committed frozen control; cross-corpus fix
defended by correctness (per-case xcorpus), tuning levers by measured
improvement; HARD no-leakage + safety + gate ≥90% green; outcome = measured
improvement OR documented deeper ceiling (both defend); NO promised number;
revert any candidate that regresses no-leakage/safety. Closure: honest
`docs/retriever_optimization.md` study report + ADR-0017 + decisions §H15.1
expansion + evidence_matrix + CLAUDE.md §27 → H16 + memory roll-forward
`h15_closed_h16_starting.md` → `h15-1_closed_h16_starting.md` + MEMORY.md +
tag `v0.1.6-h15.1`.

## 7. Deliverables

1. `src/regulaitor/rag/retrieval.py` — `corpus="auto"` path + `RetrievalConfig`
   + pure `_apply_purity_gate`; explicit path byte-identical.
2. `citation/schemas.py`, `api/schemas.py`, `routes_ask.py`, `graph.py`,
   `agents/retriever.py`, `mcp_server/tools.py` — `"auto"` threaded through;
   `Context.resolved_normas`.
3. `evals/harness.py` + `evals/gold_set.jsonl` — `"auto"` end-to-end;
   xcorpus-001/002 → `"auto"`.
4. `docs/adr/0017-retriever-cross-corpus-auto.md` (mirror ADR-0016 structure).
5. `docs/retriever_optimization.md` — the honest study report (anatomy of the
   context_precision ceiling, the A/B vs frozen control, the per-case
   cross-corpus result, tuning-lever deltas, no-leakage + safety
   non-regression, honest interpretation incl. documented deeper ceiling if
   no improvement, real measured cost, caveats).
6. Closure: decisions §H15.1 expansion, evidence_matrix, CLAUDE.md §27 → H16,
   memory roll-forward, tag `v0.1.6-h15.1`.

## 8. Out of scope (explicit)

Segmenter / extractor; no-Answer-residual robustness; Auditor RHR-aggregation +
the `MonotonicEscalatePolicy`/`_COUNCIL_BINDING` seam (stays OFF); any LanceDB
re-ingest (re-embed / re-chunk); chunking-strategy change; embedding/reranker
model change; LLM-based routing; language routing; doc-mode A/B (measured
chat-only, like H15); the citation-metric granularity confound (eval-instrument,
documented at H15 closure, requires full re-baseline if changed). Auditor /
citation validator byte-unchanged.

## 9. Risks

- **Purity-gate threshold mis-tuned** → either leakage on single-corpus auto
  queries or starving a genuinely-needed corpus. Mitigation: it is an explicit
  A/B-tuned param with unit-tested boundaries; the explicit (non-auto) path is
  unaffected.
- **`PRE_RERANK` starvation across 4 corpora** on the auto path (one corpus's
  candidates crowd out another's before rerank). Mitigation: `pre_rerank` is a
  tuning lever; consider per-corpus candidate floors as a candidate iteration
  (pinned in the plan, A/B-measured, not assumed).
- **xcorpus N=2 too small** to move the aggregate. Accepted: defended by
  correctness per-case, not aggregate (D5).
- **No measurable tuning improvement** → honest documented deeper ceiling +
  ship only the correctness fix (D5; the H15 honest-ceiling precedent).
- **Schema widening regressions** in API/MCP/graph consumers. Mitigation: the
  full `uv run pytest -m "not slow"` ≥90% gate + the explicit-path-unchanged
  assertion + contract tests.
