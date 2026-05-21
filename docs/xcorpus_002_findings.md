# xcorpus-002 — findings consolidados v0.1.9 → v0.1.11 (memoria-ready)

Hand-authored synthesis + WHAT/WHY/HOW/IMPACT blocks for the xcorpus-002 cross-corpus retrieval investigation. Sister document to `xcorpus_002_investigation.md` (auto-generated raw diagnostic data; that doc gets overwritten on every diagnostic re-run, this one does not).

Read alongside `xcorpus_002_investigation.md` for the raw measurement table (8 calls so far, $0 local CPU).

---

## The cross-corpus question being studied

**Query**: "Operador de infraestructura digital sujeto a NIS2 con incidente que implica fuga de datos personales. ¿Notificar solo al CSIRT (NIS2) o también a la APD (RGPD)?"

**Expected (per gold set xcorpus-002)**: cite `nis2.23` (incident notification to CSIRT) + `nis2.35` (cross-reference to data-protection authorities) + `gdpr.33` (72h breach notification). Verdict expected = `requires_human_review` (complex normative interaction).

**H15.1 baseline result**: 1/3 expected articles surfaced (NIS2 art 23 only), verdict regressed RHR ✅ → block ❌.

---

## v0.1.9 finding (diagnostic only — documentation, NO production change)

- **WHAT** — diagnosed: standard `BAAI/bge-reranker-v2-m3` cross-encoder fails on cross-corpus multi-regulation queries (single-article dominance pattern).
- **WHY** — measured evidence (Calls 1+2+3): for the personal-data-breach query, the reranker scores 5 different paragraphs of NIS2 art 23 higher than any chunk of NIS2 art 35 or GDPR art 33. Lowering `purity_threshold` 0.6→0.5 produces an IDENTICAL emitted set; the dense pool DOES contain all 3 expected articles.
- **HOW** — three candidate fixes identified: (A) per-article cap; (B) MMR; (C) hybrid score. Option A was the surgical next step.
- **IMPACT** — v0.1.9 shipped diagnostic + slow regression test only; NO production change; 1/3 expected articles surfaced (NIS2 23) unchanged.

## v0.1.10 finding (per-article cap shipped — capability landed, xcorpus-002 NOT fixed alone)

- **WHAT** — implemented: per-article deduplication cap via `RetrievalConfig.max_chunks_per_article: int | None = None`. Default `None` = no cap = production-byte-identical to v0.1.9.
- **WHY** — surgical follow-up to v0.1.9. Hypothesis: limiting NIS2 art 23 to ≤2 chunks frees slots for NIS2 art 35 and GDPR art 33. Pure deterministic helper; $0; backward-compat default.
- **HOW** — `_apply_per_article_dedup(ranked_triples, max_per_article)` operates on `(norma, article, payload)` best-first triples, preserves order, drops chunks beyond the cap for each `(norma, article)` key. Wired into `run_auto` BEFORE `_apply_purity_gate` when `cfg.max_chunks_per_article is not None`.
- **IMPACT** — measured (Calls 4+5):
  - Algorithm-level SUCCESS: cap=2 emits 4 distinct NIS2 articles (`nis2.23, nis2.23, nis2.30, nis2.13, nis2.10`) instead of `5×nis2.23`. Article diversity within norma recovered.
  - System-level FAILURE: top-5 deduped is still 5/5 NIS2 (just diversified) → purity gate still collapses → NIS2 35 / GDPR 33 never surface. Even cap=2 + purity_threshold=0.5 produces identical output.
  - **1/3 expected articles surfaced — unchanged from baseline.** Production defaults unchanged.
  - **Deeper finding**: reranker bias on this query is at NORMA level, not just article level.

## v0.1.11 finding (per-norma cap shipped — 1/3 → 2/3 REAL measured improvement)

- **WHAT** — implemented: per-norma deduplication cap via new `RetrievalConfig.max_chunks_per_norma: int | None = None`. Default `None` = no cap = backward-compat with v0.1.10.
- **WHY** — surgical follow-up to v0.1.10 (cap-per-article recovered article diversity but NORMA-level reranker bias still collapsed the gate). Hypothesis: cap_per_norma=N with top_k=5 forces max-norma share ≤ N/5; with N=2 the share = 0.4 < 0.6 default threshold → gate guaranteed multi-corpus emission.
- **HOW** — `_apply_per_norma_dedup(ranked, max_per_norma)` operates on `(norma, payload)` pairs (matching the per-article helper's output and the purity gate's input), preserves best-first order, drops chunks beyond the cap for each norma. Wired into `run_auto` AFTER per-article dedup (composes cleanly) and BEFORE the purity gate.
- **IMPACT** — measured (Calls 6, 7, 8):
  - **Boundary discovery** (Calls 6 + 7): cap_per_norma=3 + top_k=5 produces max-share = 3/5 = 0.6 **exactly at the threshold** (inclusive) → gate STILL collapses → 1/3 unchanged. The math matters: cap must put the dominant-norma share STRICTLY BELOW the threshold.
  - **Sub-threshold breakthrough** (Call 8): cap_per_norma=**2** + top_k=5 → max-share = 2/5 = 0.4 < 0.6 → gate **multi-corpus** → resolved_normas = `[dora, gdpr, nis2]` → emitted `nis2.23, nis2.23, dora.19, dora.22, gdpr.33` → **2/3 expected articles surfaced (NIS2 23 + GDPR 33)** — real measured improvement over the 1/3 baseline.
  - **NIS2 art 35 still missed** — the reranker positions NIS2 art 35 BELOW DORA arts 19 and 22 (semantically adjacent: "ICT incident notification" DORA vs "incident notification" NIS2). This is the actual deeper ceiling.
  - **Recommended config for cross-corpus demos**: `RetrievalConfig(max_chunks_per_norma=2)`. Production default stays `None` for backward-compat; the cap is opt-in. Updating the production default to 2 is a candidate paid-validation question for the bundle's final A/B (would invalidate the H15 baseline; intentionally deferred).

## v0.1.12 finding (capability shipped — empirical xcorpus-002 measurement DEFERRED)

- **WHAT** — implemented: `RetrievalConfig.top_k_auto: int | None = None` field. When set, `run_auto` uses this value as the purity-gate window AND final output size INSTEAD of `cfg.top_k`. The explicit-corpus `run()` path ignores this field entirely (T6 byte-identical guarantee preserved). Backward-compat default `None` = use `cfg.top_k` exactly as v0.1.11.
- **WHY** — surgical follow-up to v0.1.11 ceiling (NIS2 art 35 still missed at top_k=5 even with cap_per_norma=2 — reranker scores it below DORA 19/22). Hypothesis: with top_k_auto=12 + cap_per_norma=3, max-share = 3/12 = 0.25 < 0.6 threshold, so the gate stays multi-corpus AND 12 slots give the relaxed cap room for NIS2 art 35 if the reranker positions it within the per-norma top-3.
- **HOW** — `dataclasses.replace(cfg, top_k=cfg.top_k_auto)` builds a temporary `gate_cfg` only when `cfg.top_k_auto is not None`; the gate operates on this `gate_cfg` (using `gate_cfg.top_k` for its window + output size). The explicit `cfg.top_k` and the explicit-corpus `run()` path stay untouched. Two new unit-test modules (12 tests total): `test_retrieval_config_top_k_auto_field.py` (field defaults, validation, composition) + `test_top_k_auto_in_run_auto.py` (wiring contract with mocked rerank).
- **IMPACT** — **capability shipped + wiring algorithmically verified; empirical xcorpus-002 measurement DEFERRED**.
  - The unit tests prove the wiring works at the algorithm level: top_k_auto=12 + per-norma cap composes correctly to 12 chunks across 4 normas (mocked), gate computes share over the 12-window correctly, explicit-corpus path is unaffected.
  - **The empirical question** (does top_k_auto=12 + cap_per_norma=3 actually surface NIS2 art 35 on the real LanceDB index?) **was NOT measured** in v0.1.12. The 12-call diagnostic (Calls 9-12 of `scripts/diagnose_xcorpus_002.py`) was killed at 41 min wall time due to repeated CPU-rerank underestimation on my side (see §22.22 disclosure below). Re-measurement deferred to either (a) a separate dedicated session with proper timing budget for ~15-20 min minimum, or (b) the v0.1.20 paid bundle validation which will exercise the cumulative config at real-eval scale.
  - **Recommended demo-mode config when measurement confirms**: `RetrievalConfig(top_k_auto=12, max_chunks_per_norma=3, max_chunks_per_article=2)`. Production defaults stay `None` for all three (backward-compat); the recommended values are opt-in via env override or explicit config.

## v0.1.12 §22.22 honest disclosure (CPU rerank cost discipline)

Pattern that surfaced in v0.1.9 + v0.1.10 + v0.1.12: I have consistently underestimated CPU-rerank cost by 3-10×. Per-call cost of `reranker.rerank(passages_50, top_n=50)` on CPU is **~15-30s sustained**, not the "5-10s" I kept assuming. Multi-call diagnostics scale linearly: 12 sequential calls = ~3-6 min minimum, but with warmup + state accumulation the actual wall time was 41+ min before kill. The slow tests in `tests/integration/test_xcorpus_002_diagnostic.py` exclude themselves from the default `pytest -m "not slow"` gate precisely to avoid this cost during normal CI; explicit invocation `pytest -m slow` is the right place to incur it.

New hard rule registered in memory `feedback_local_cpu_rerank_cost.md`: ANY local-CPU diagnostic that calls `reranker.rerank` more than 3 times sequentially should be estimated as **N × 30s minimum** (be conservative, communicate range) AND if total estimate exceeds 5 min, should be redesigned to run only 1-2 critical configs rather than full sweeps.

## Ceiling carried to v0.1.13+

NIS2 art 35 still missing from xcorpus-002 emit (last measured baseline: v0.1.11 cap_per_norma=2 → 2/3 expected). v0.1.12 capability shipped but empirical fix not yet measured. Next candidate intervention if v0.1.12 measurement (eventually) shows ≤2/3: try different reranker model (large milestone), or accept the architectural ceiling and document for memoria + industry demo as "we identified single-article + single-norma dominance failure modes in standard bge-reranker-v2-m3 on cross-corpus multi-regulation queries; our two-axis cap mitigates GDPR-side missing articles but the reranker's specific NIS2-art-35 ranking is below mitigation through tuning levers alone".

## Cumulative score

| Milestone | xcorpus-002 expected articles surfaced |
|---|---|
| H15.1 baseline (no cap) | 1/3 (NIS2 23 only) |
| v0.1.10 cap_per_article=2 | 1/3 (unchanged) |
| **v0.1.11 cap_per_norma=2** | **2/3 (NIS2 23 + GDPR 33)** ← real progress |
| v0.1.12 (if raise top_k 5→12) | TBD (hypothesis: 3/3) |

## Linked artefacts

- Raw diagnostic data: [`xcorpus_002_investigation.md`](xcorpus_002_investigation.md) (auto-generated; re-run via `uv run python -m scripts.diagnose_xcorpus_002`)
- Implementation: `src/regulaitor/rag/retrieval.py` (`_apply_per_article_dedup` v0.1.10, `_apply_per_norma_dedup` v0.1.11, `RetrievalConfig.max_chunks_per_article`/`max_chunks_per_norma`)
- Regression pins: `tests/integration/test_xcorpus_002_diagnostic.py` (`@pytest.mark.slow`, $0)
- Unit tests: `tests/unit/test_per_article_dedup.py`, `tests/unit/test_per_norma_dedup.py`, `tests/unit/test_retrieval_config_dedup_field.py`, `tests/unit/test_retrieval_config_per_norma_field.py`
