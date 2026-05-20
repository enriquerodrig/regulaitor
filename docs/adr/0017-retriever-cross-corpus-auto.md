# ADR 0017 — Retriever cross-corpus auto path + post-rerank purity gate (H15.1)

- **Status:** Accepted — 2026-05-19 — squash `<squash-sha>`, tag `v0.1.6-h15.1`
- **Deciders:** Project owner.
- **Companion ADRs:** 0004 (RAG architecture — the retrieval pipeline this directly
  extends), 0016 (H15 Auditor calibration study — the system-level ceiling this
  optimization phase attacks; the same frozen-control A/B discipline is carried),
  0013 (router multi-LLM — the `REGULAITOR_ROUTER_MODE` eval-override seam whose
  design precedent the `corpus="auto"` opt-in directly mirrors).

## Context

CLAUDE.md §22.18 (single-corpus no-leakage) and H14 (ADR 0015) verified that the
4-corpus LanceDB index (1569 chunks: ai_act 687 + gdpr 324 + nis2 244 + dora 314)
has zero cross-corpus contamination on scoped queries. That property is correct and
must be preserved.

However, it exposed a **structural gap**: `corpus` is a *required, caller-specified*
`Literal["ai_act","gdpr","nis2","dora"]` field at every API surface
(`api/schemas.py AskRequest`, `graph.run(corpus=…)`,
`mcp_server.search_articles(corpus)`). A question that spans two norms — e.g. "how
do NIS2 and DORA interact?" — can only be asked against one corpus today; the
retriever structurally cannot cite both. The H14 gold-set cross-corpus cases
(xcorpus-001/002) retrieved context 0.00 under any single-corpus assignment.

The H15 calibration study (ADR 0016) documented the dominant remaining system-level
lever: `context_precision ≈ 0.60 < 0.80`, dragging faithfulness / answer_relevancy /
recall. The study deferred retriever re-tuning (**Intervention C, measured-only in
H15**) and named it the top post-H15 engineering target. The user approved H15.1 as a
**decimal optimization milestone** (no renumber — precedent H0.1; roadmap decision
committed on `5fd2fad`, decisions log §H15.1) with two separable goals:

1. **Correctness fix:** enable a `corpus="auto"` path so cross-corpus questions
   structurally can retrieve and cite from multiple norms.
2. **Tuning levers:** `RetrievalConfig` (`pre_rerank` (the `RetrievalConfig.pre_rerank`
   field, default = the former module-level `PRE_RERANK` constant), `top_k`, purity
   threshold, deterministic query normalization) as A/B-measured improvements vs
   the frozen H15 control.

No re-embed, no re-chunk: the 4-corpus LanceDB index is **not** touched.

## Decision

Five design decisions (brainstorming closed 2026-05-19; full rationale + amendments
in `docs/technical_decisions_log.md §H15.1`; canonical study write-up in
`docs/retriever_optimization.md`):

### D1 — Scope: retriever only; chat-only A/B

The only component changed is the **retriever layer** (logic change:
`rag/retrieval.py`; type-widening pass-through only: `citation/schemas.py`,
`api/schemas.py`, `routes_ask.py`, `graph.py`, `agents/retriever.py`,
`mcp_server/tools.py`; eval wiring: `evals/harness.py`, `evals/gold_set.jsonl`).
**Out of scope for H15.1**: the segmenter / no-Answer-residual
robustness / Auditor-RHR-aggregation / `MonotonicEscalatePolicy` (`_COUNCIL_BINDING`
seam stays OFF — ADR 0014 lineage unchanged) / doc-mode A/B (blocked by the
deferred segmenter confound). The Auditor and citation validator are **byte-identical**
to pre-H15.1 production. The A/B is **chat-only**, exactly as H15 was.

### D2 — Contained levers only; query construction stays deterministic

In scope: the new `corpus="auto"` path + the `RetrievalConfig` dataclass
(`pre_rerank`, `top_k`, `purity_threshold`, `query_normalization`). **Out**: chunking
strategy change, embedding / reranker model change, any LanceDB re-ingest (the
4-corpus index is frozen per §22.18). Query construction stays **deterministic**
(normalization-only — no LLM query expansion), preserving the deliberate
"retriever calls no LLM" architecture principle documented in the
`RetrieverAgent` docstring.

### D3 — Post-rerank purity gate; explicit-corpus path byte-identical

When `corpus` is one of the four norm literals (today's entire behavior) the
retrieval code path is **byte-identical** to `v0.1.5-h15` — single-`norma`
`where`-clause, no purity gate. Existing scoped requests have **zero behavior
change**; single-corpus no-leakage (§22.18 / H14-verified) is preserved
*by construction*.

A new `corpus="auto"` value triggers: retrieve `pre_rerank` candidates across all
4 corpora (language-filtered, no `norma` filter) → existing `bge-reranker-v2-m3`
cross-encoder → deterministic `_apply_purity_gate(reranked_with_norma, threshold,
top_k)`:

- `share(norma)` = count of that `norma`'s chunks among the top-`top_k` reranked /
  `top_k` (count-based, deterministic).
- If `max_share ≥ purity_threshold` → keep only that `norma`'s chunks within `top_k`
  (no-leakage restored even on the auto path).
- Else → genuine cross-corpus `top_k` (each `RetrievedChunk` already carries `.norma`
  for downstream Auditor validation).

`top_k ≥ 1` is enforced as an invariant at `RetrievalConfig` construction.
`Context.resolved_normas: list[Norma]` (populated from returned chunks' `.norma`)
provides retrieval-transparency to callers. Frozen defaults of `RetrievalConfig` are today's values, guaranteeing the
explicit path is preserved by construction (no code path touches the explicit
single-`norma` route) **and additionally verified by the explicit-path-unchanged
regression assertion test (H15.1 T6)**.

### D4 — Budget & A/B discipline (carried from H15 D4)

The frozen control is the **already-committed** H15 evidence
(`evals/reports/h15/candidate-v1.2.md` 30-calibration +
`evals/reports/h15/holdout-v1.2-chat.md` 14-holdout). H15.1 branches from
`v0.1.5-h15` with no intervening code change, so these **are** a clean baseline;
**no paid re-baseline** (saves ≈€1.85). Single variable: only the retriever
changes (Analyst stays H15-frozen v1.2; Auditor / judge / gold unchanged except
xcorpus-001/002 → `"auto"`). Calibration set = 30 chat cases (chat-001..030,
xcorpus-001/002 on `"auto"`); holdout = 14 H14 chat measured **once, never
iterated**. ≤3 `RetrievalConfig` candidate iterations; `--limit 3` probe + hard
`--limit N` cap before every paid run; running cost-tally + explicit user OK +
user credit confirmation before any paid spend (USER-GATED). Controller runs paid
eval jobs as persistent background processes (H14 operational lesson — not delegated
to subagents). Real cost measured via the existing H15 router accumulator
(`models/router.py` `_record_cost_eur` / `get_accumulated_cost_eur`) — no new
instrument. Realistic spend envelope: ≤3 candidates × ≈€1.5 per 30-case run +
a 14-case holdout ≈€0.78 + probes ≈€0.5 → expected ≈€5–6 of the available
credit; ceiling anchored at the H15 budget precedent (~€7.5 / ~$8, ADR 0016).

### D5 — Done-when (honest, §22.22)

Rigorous documented A/B vs the committed frozen control. The **cross-corpus
correctness fix** is defended by **correctness** (per-case xcorpus-001/002 results,
NOT folded into the 30-mean — H15's 6-RHR-designated-cases discipline). The
**tuning levers** are defended by **measured A/B improvement**. HARD
non-regressions: (a) redteam-smoke `block_rate` must not drop below the frozen
0.92 (§16.2#4); (b) the 6 H15-designated block cases (chat-014/015/029/030 +
holdout nis2-006/dora-006) remain content-safe (C1 content-based manual backstop
carried from H15 — C1: the content-based safety determination introduced in ADR
0016 Consequences — authoritative over the mechanical `safety_ok` rule — a
retriever change must not let an attack retrieve something that flips a grounded
refusal); (c) explicit-corpus path output is unchanged. **Any
candidate that improves a metric but regresses no-leakage or safety is reverted.**
Gate `uv run pytest -m "not slow"` ≥90% coverage green. **No promised metric
number** — the defended outcome is a measured improvement OR a documented deeper
system-level ceiling (both defend equally).

## Consequences

**Positive:**

- The `corpus="auto"` path is purely **additive and opt-in** — no caller is forced
  to use it; any existing integration that passes a specific `Literal["…"]` corpus
  is regression-zero by construction.
- The explicit-corpus path (today's entire behavior) is **byte-identical** to
  `v0.1.5-h15`: no logic added, no gate applied — single-corpus no-leakage
  (§22.18 / H14-verified) is preserved by construction (frozen `RetrievalConfig`
  defaults guarantee no code path touches the explicit single-`norma` route) and
  additionally verified by the explicit-path-unchanged regression assertion test
  (H15.1 T6).
- The **LLM-free retriever principle** is preserved: `RetrieverAgent` calls no LLM
  at retrieval time; `_apply_purity_gate` is a pure deterministic helper with no
  model call.
- The **§6 "no citation, no answer" Auditor/citation-validator invariant is 100%
  intact**: those components are byte-unchanged; they already validate every emitted
  citation against its own corpus, per-chunk. Multi-corpus retrieval only widens
  what the Analyst *can* ground in; every citation still goes through the full
  validation chain.
- No LanceDB re-ingest: the 4-corpus 1569-row index (§22.18) is untouched — the
  BGE-M3 embeddings and bge-reranker-v2-m3 cross-encoder are reused as-is.
- `Context.resolved_normas` adds retrieval transparency to the API response —
  callers can inspect which corpora the auto path actually drew from.
- **Pre-existing strict-mypy gate finding surfaced and fixed (§22.22):** A `mypy src`
  gate that had been red since H13 (`db991dc`, council.py annotation debt — invisible
  because the H13/H14/H15 "gate green" used `pytest -m "not slow"`, which does not
  run mypy) was surfaced during H15.1-T4 and fixed annotation-only (zero behaviour
  change), clearing cross-milestone gate-hygiene debt (§22.22).

**Negative / accepted (documented honestly, not re-run — §22.22, H12 / H13 / H14 /
H15 precedent):**

- **Purity threshold is a tuned heuristic** — an A/B lever, default 0.6 (initial
  justified value, pinned in the plan; then an A/B-measured parameter). A
  mis-tuned threshold either leaks cross-corpus noise on single-corpus auto
  queries or starves a genuinely needed corpus. Mitigation: unit-tested threshold
  boundary + ties + empty-rerank + dominance + genuine-cross-corpus cases; the
  explicit path is unaffected regardless.
- **`top_k ≥ 1` invariant enforced at `RetrievalConfig` construction** (constructor
  raises on violation) — not a runtime guard in the gate itself, by design.
- **xcorpus N=2 is too small to move the 30-aggregate** — accepted. Defended by
  per-case correctness for xcorpus-001/002, not by aggregate delta (D5); the
  H15 6-RHR discipline precedent.
- **Auto path reranks more candidates (`pre_rerank` across 4 corpora)** — local CPU
  latency increase on the auto path only. No API cost ($0 reranker — local model).
  The explicit path is unchanged.
- **Citation-metric article-vs-apartado granularity confound persists** on the
  xcorpus expected-articles and is **documented, not fixed** (eval-instrument
  quality; requires a full A/B re-baseline if the metric/gold convention ever
  changes — not touched in H15.1; same caveat as ADR 0016 Consequences).
- Measured A/B results (candidate vs frozen control numbers, real costs, per-case
  xcorpus analysis, tuning-lever deltas, no-leakage + safety non-regression
  evidence) are produced in Tasks 8–10 and reported in `docs/retriever_optimization.md`.
  This ADR records the **decision and framework**; outcome numbers are not yet
  measured at ADR-write time — referencing the H15 baseline as the documented prior
  context, not as H15.1 results.

## Alternatives considered

- **Pre-retrieval centroid router** — embedding-based query-vs-centroid (one
  centroid per corpus). Rejected: routes on a weaker signal than the full
  cross-encoder rerank over real retrieved passages; introduces centroid maintenance,
  an extra component, and a tuned threshold that cannot exploit the reranker's
  passage-level discrimination.
- **LLM-based pre-retrieval router** — classify the query corpus before retrieval
  using an LLM. Rejected: puts a non-deterministic model call in the retrieval hot
  path (latency + token cost on every query, versioned prompt, non-reproducible
  routing), violates the deliberate "retriever calls no LLM" principle that the
  `RetrieverAgent` docstring documents, and is out of scope for H15.1 (D2).
- **Always-multi-corpus retrieve + rerank, no purity gate** — drop the `norma`
  filter unconditionally, cross-corpus on every query. Rejected: regresses
  single-corpus no-leakage (§22.18 / H14-verified) for explicitly-scoped requests —
  exactly what the opt-in `corpus="auto"` + purity gate is designed to avoid. The
  explicit path byte-identical guarantee would be impossible.

## References

- Spec: `docs/superpowers/specs/2026-05-19-h15-1-retriever-optimization-design.md`
- Plan: `docs/superpowers/plans/2026-05-19-h15-1-retriever-optimization.md`
- Decisions log `§H15.1` (D1–D5, purity-gate design, budget discipline, mypy
  gate-hygiene finding, A/B results expansion post-Tasks-8–10)
- ADR 0016 (H15 Auditor calibration — the system-level ceiling this milestone attacks;
  the frozen-control A/B discipline and C1 safety backstop carried)
- ADR 0014 (Council of Judges — the `_COUNCIL_BINDING`/`MonotonicEscalatePolicy` seam
  stays OFF, per D1)
- ADR 0004 (RAG architecture — the retrieval pipeline H15.1 extends)
- `src/regulaitor/rag/retrieval.py` (`RetrievalConfig`, `_apply_purity_gate`,
  `corpus="auto"` path)
- `evals/reports/h15/candidate-v1.2.md`, `evals/reports/h15/holdout-v1.2-chat.md`
  (frozen control)
- `docs/retriever_optimization.md` (study report — produced in Tasks 8–10)
