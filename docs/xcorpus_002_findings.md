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

## Ceiling carried to v0.1.12

NIS2 art 35 still missing from cross-corpus xcorpus-002 output even with cap=2. The dense pool DOES contain it (Call 3 unchanged across all v0.1.9-v0.1.11 runs). The reranker scores it BELOW DORA 19/22 chunks at this query.

**v0.1.12 candidate fix**: raise `top_k` 5→12. NIS2 art 35 may surface in deduped positions 6-12 since the dense pool has it. Trade-off: increases Analyst context size + chunk-budget assumptions downstream.

**v0.1.13 fallback** (if v0.1.12 insufficient): different reranker model (larger ceremony, requires paid re-baseline).

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
