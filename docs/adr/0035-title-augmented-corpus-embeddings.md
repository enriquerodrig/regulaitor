# ADR-0035 — Title-augmented corpus embeddings

- **Status:** ACCEPTED then REVERTED per T6 empirical refutation — 2026-05-28 — squash `c398c85`, tag `v0.1.30-title-augmented-embeddings` (retained as scientific record per ADR-0030 §REVERT precedent)
- **Milestone:** v0.1.30 (Stage 2 per agreed post-v0.1.29 ordering; bridges descriptive-doc-segment → obligation-corpus-article semantic gap)
- **Spec/plan:** inline (light pattern; ADR-0034 / ADR-0033 precedent)
- **Companion ADRs:** [0004](0004-rag-architecture.md) (H2 RAG base — BGE-M3 + reranker + LanceDB); [0019](0019-segmenter-numbered-section-heading-detection.md) (segmenter detects Spanish numbered headings; supplies titles for the v0.1.28 query-side prepend); [0017](0017-retriever-cross-corpus-auto.md) (RetrievalConfig palancas; auto-path); [0033](0033-doc-analyst-v1-6-refusal.md) (v0.1.28 SHIPPED title-prepend query-side at `document_graph._build_doc_retrieval_query` — this ADR mirrors symmetrically at the corpus-side); [0024](0024-citation-granularity.md) (eval-side hierarchical containment; reference for "what changes vs what stays byte-equivalent" framing).

## Context

**v0.1.28 paid validation (doc-mode N=10, ADR-0033)** shipped two retrieval interventions:

- **T4-bis** (SHIPPED): title-prepend at QUERY construction — `f"{seg.title}\n{seg.text}"` in `orchestration/document_graph.py`. Lifted citation_recall 0 → 0.33 on doc-mode N=10 main. Bridges descriptive-doc-segment → obligation-corpus-article semantic gap on the **query side**.
- **T4-extra α+β** (REVERTED): top_k=15 + max_chunks_per_norma=5 retrieval breadth. Caused context dilution; citation_precision 0.17 → 0.00. REVERTED.
- **T4-bis-v2 cleanup** (REVERTED): strip-number + skip-dup title processing. Lost doc-002 50.1 gold hit; citation_precision 0.33 → 0.17. REVERTED.

**Deeper finding (§22.22 disclosure #4 in ADR-0033)**: 3/5 production-compliance docs (doc-006, doc-008, doc-009) missed gold articles even with title-prepend on the query side. The descriptive-doc-segment → obligation-corpus-article semantic gap is **fundamental at the embedding-similarity level**: the BGE-M3 vector for a doc segment that descriptively says "el sistema realiza supervisión humana de las decisiones automatizadas del personal" does not align well with the vector for the corpus chunk that prescriptively says "los proveedores garantizarán que los sistemas de IA de alto riesgo se diseñen y desarrollen de tal modo que personas físicas puedan vigilarlos...".

**The symmetric intervention** is to prepend the same kind of contextual heading to the CORPUS chunks at embedding time so the corpus vectors also encode the article's topic identity ("Artículo 14 — Supervisión Humana") instead of only its prescriptive body text. v0.1.28 ADR-0033 §22.22 carry-forward enumerated this as the next thing to try if budget permitted; v0.1.30 is the user-approved Stage 2 attempt.

## Decision

### D1 — Helper-based title-prepend at embedding time

NEW top-level `_text_to_embed(chunk: Chunk, parsed: ParsedArticle) -> str` helper in `src/regulaitor/rag/build.py`. Returns:

- `f"Artículo {chunk.articulo} - {parsed.title}\n\n{chunk.text}"` when `parsed.title` is truthy.
- `chunk.text` unchanged when `parsed.title` is None or empty (fallback; preserves pre-v0.1.30 behavior for articles without titles like preambles).

Applied at the `run()` orchestrator line ~123: `embeddings.embed([_text_to_embed(ch, parsed) for ch in chunks])` (was `embeddings.embed([ch.text for ch in chunks])`).

### D2 — `Chunk.text` byte-unchanged

The `Chunk.text` field stored in LanceDB stays exactly the original article/apartado text. The prepended title is added ONLY at the embedding-input string passed to `embeddings.embed()`. The string is consumed and discarded by the embedder; the resulting vector is what gets stored alongside the unchanged `Chunk.text`.

**Critical §6-invariant consequence**: `citation/validator.py`'s strict text-match path (which looks up the cited text against `Chunk.text` from the store) is UNAFFECTED. No citation that previously failed strict validation now passes, and vice versa. The §6 enforcement boundary at Layer (a) is preserved BYTE-EQUIVALENT.

### D3 — Symmetric query/corpus title context

v0.1.28 prepends title at query side (`document_graph._build_doc_retrieval_query`); v0.1.30 prepends matching title at corpus side. Both vectors now encode article topic identity, improving cosine similarity for descriptive-doc-segment ↔ obligation-corpus-article pairs.

### D4 — No config flag; atomic rebuild + snapshot revert

Full corpus re-embed in place at `corpus/indexes/regulaitor.lance/chunks` table. Pre-v0.1.30 index snapshot at `corpus/indexes/regulaitor.lance.pre-v0.1.30/` (manual cp -r). Revert if needed = `mv` snapshot back over live index. No config flag (simpler than A/B switching; established discipline: ship/revert atomically per outcome).

### D5 — Validation cohort + decision criterion

- **Probe** ~€0.40: doc N=3 (doc-001..003) + chat N=3 (chat-001..003) for plumbing sanity + early signal
- **Main** ~€1.40: doc N=10 (full doc gold set doc-001..010) + chat N=10 (chat-001..010 subset for chat sanity no-regression)

**SHIP criterion** (CONFIRM):
- Doc-mode citation_recall lift ≥ +0.05 vs v0.1.28 baseline 0.33 (target ≥0.38)
- Chat-mode: no v0.1.20-bar metric regresses >0.05 vs v0.1.29 baseline

**REVERT criterion**:
- Doc-mode citation_recall does NOT improve (≤0.33) OR
- Chat-mode any v0.1.20-bar metric regresses >0.05

If REVERT: `mv corpus/indexes/regulaitor.lance.pre-v0.1.30 corpus/indexes/regulaitor.lance` restores baseline atomically; ADR-0035 amended with §REVERT section per v0.1.23 precedent.

## §6 risk assessment: LOW

- **Layer (a) validator** — `citation/validator.py` BYTE-UNCHANGED (this ADR does not touch it; reads `Chunk.text` which is also byte-unchanged).
- **Layer (b) Finding-Lenient** — `agents/auditor.py` `any(r.validated)` line BYTE-UNCHANGED.
- **Layer (c) Turn-level aggregation policy** — BYTE-UNCHANGED (v0.1.25 D2 + v0.1.29 D Mirror state preserved).
- **Layer (d) prompt-level forbid** — `prompts/analyst/system.v1.5.md` + `prompts/document_analyst/system.v1.6.md` BYTE-UNCHANGED.
- The change is exclusively at the EMBEDDING input construction. By construction the validator cannot accept a fabricated citation just because retrieval surfaces it; the validator re-checks `Chunk.text` independent of the embedding vector.

**Lowest §6 risk surface intervention attempted post-H4 since v0.1.28 title-prepend query-side.**

## §22.22 honest disclosures (5)

1. **N=10 doc gold set is small** — any conclusions about doc-mode lift carry overfitting risk. The mitigation is the chat-mode no-regression sanity check on N=10 cases that share the same retrieval stack.

2. **Cost ~€2.00 expected, €3.00 high** (= expected × 1.5 per `feedback_cost_estimation_discipline.md`). Budget post-worst ~$5.95 USD remaining; sufficient for H17 emergencies.

3. **REVERT precedent applies** (v0.1.23 ADR-0030 §REVERT section). If paid measurement refutes the prediction, snapshot revert is atomic + ADR-0035 amended with §REVERT section as scientific record. The methodology contribution is the discipline of measuring + honest disclosure regardless of outcome direction.

4. **Cumulative state**, not isolated title-augmented embeddings — v0.1.30 = v0.1.29 (D Mirror) + v0.1.28 (v1.6 doc + T4-bis title-prepend query-side) + v0.1.25 (D2 partial) + Tier 1 quorum + Tier 2 Capa A+B+C + v1.5 chat + Council binding + retrieval defaults + title-augmented embeddings. Factorial attribution to title-augmented alone NOT measured (would require ablation arm not in scope).

5. **2-day API drift not applicable here** (v0.1.30 main runs same-day as v0.1.29 if executed quickly; if delayed, ~20% noise floor per v0.1.23 §REVERT root cause #1 applies).

## Alternatives considered

### Alternative A: HyDE (Hypothetical Document Embeddings)

**Rejected for v0.1.30** (carry-forward to HX). HyDE asks the LLM to draft a hypothetical "regulatory-obligation answer" from the doc segment, then uses THAT as the query (not the doc segment text). Theoretically powerful but requires per-query LLM call → adds €0.005-€0.01 per query (~+15% cost). Title-augmented embeddings achieve a similar effect ($0 at query time after the one-shot re-embed) so is the cheaper first attempt. HyDE remains HX if v0.1.30 underperforms.

### Alternative B: Hybrid BM25 + dense retrieval

**Rejected for v0.1.30** (carry-forward to HX). Adds significant code complexity (tantivy or rank-bm25 integration; score fusion); higher implementation cost than title-augmented embeddings (a 1-line change). The two approaches are complementary not exclusive; v0.1.30 first as low-risk fast iteration.

### Alternative C: Custom legal-pair reranker fine-tune

**Rejected for v0.1.30** (HX post-TFM). Requires labeled training pairs (regulatory-text → applicable-article) which we don't have; would need bootstrapping via the existing gold set + augmentation. Significant ML engineering investment incompatible with current ceremony.

### Alternative D: Config flag for A/B embedding strategy

**Rejected for v0.1.30** (simpler ship/revert atomic). Adding `RetrievalConfig.embed_with_title: bool` requires (a) double-indexed storage OR (b) flag-conditional code path at query time. Both add complexity without clear benefit since the project has consistently shipped/reverted whole interventions (v0.1.23 REVERT precedent; v0.1.25/v0.1.29 CONFIRM shipped without flags). If v0.1.30 ships, baseline can still be reconstructed via `mv` from the snapshot.

## Expected outcome (paid validation will measure)

Predictions (cohort-specific):

- **doc-mode citation_recall**: v0.1.28 baseline 0.33 → target ≥0.38 (≥+0.05 lift). Mechanism: descriptive-doc-segment vectors now match the title-augmented corpus vectors better, surfacing the correct obligation-article more reliably (especially for the doc-006/008/009 cohort that v0.1.28 query-side title-prepend couldn't reach alone).
- **doc-mode citation_precision**: 0.15 baseline → maintain or slight lift (could regress if title-augmented embedding surfaces MORE articles per segment dilutes precision; would warrant looking at config tuning).
- **chat-mode verdict_match**: v0.1.29 baseline 0.76 → target maintain ≥0.71 (no regression >0.05). Chat queries already include article names + topics so the title-augmented corpus side may have less impact here than for doc descriptive segments.
- **chat-mode citation_recall**: v0.1.29 baseline 0.81 → maintain ≥0.76.

Honest framing: if doc-mode citation_recall lift is small (e.g., +0.03) but chat-mode stable, ship + document marginal nature. If doc-mode citation_recall drops OR chat-mode regresses, REVERT.

## References

- ADR-0004 (H2): BGE-M3 + reranker + LanceDB stack.
- ADR-0019 (v0.1.14): segmenter detects Spanish numbered headings (supplies titles to v0.1.28).
- ADR-0033 (v0.1.28): doc_analyst v1.6 Finding-based refusal + title-prepend QUERY-side (the v0.1.30 mirror's antecedent).
- v0.1.28 paid measurement: doc-mode N=10 main at `evals/reports/v0.1.27/v0.1.28-doc-prod-main.md`.
- v0.1.29 paid measurement: chat-mode N=25 main at `evals/reports/v0.1.29/v0.1.29-prod-main.md` (chat baseline pre-v0.1.30).
- Snapshot index: `corpus/indexes/regulaitor.lance.pre-v0.1.30/` (1569 rows; preserved for atomic revert).
- Future commits referenced from this ADR: T1+T2 (helper + 1-line edit + 5 tests; same commit `0afe9d1`), T3 rebuild $0 (re-embed 1569 chunks via `python -m scripts.rag_build --corpus all --lang all --force-rebuild`), T4 ADR-0035 (this commit), T5 paid probe (~€0.65 actual / €0.40 expected; over by €0.25 due to higher doc-mode cost), T6 REVERT decision after probe (T7 main SKIPPED per §REVERT empirical refutation pattern; see below), T-revert (code + index atomic restoration; this commit), T-final squash (`c398c85`; populated at T-final).

---

## §REVERT (appended 2026-05-28) — empirical refutation of prospective design

**Status**: ACCEPTED at T0-T4 (helper + 1-line + tests + ADR + rebuild SHIPPED on branch); **REVERTED at T6** per probe empirical refutation (T7 main SKIPPED per the conservative §REVERT pattern when probe evidence is structurally clear).

ADR-0035 prospective design (D1-D5 + Alternatives A-D) **retained verbatim above as scientific record** (precedent: ADR-0030 §REVERT v0.1.23). The hypothesis was reasonable, the implementation was correct, the §6 invariant held throughout — but the **paid probe measurement refuted the SHIP criterion**.

### §REVERT — T5 probe empirical evidence (€0.65 sunk; budget-conscious decision to skip T7 main)

**T5 paid probe** ran 3 doc cases (doc-001..003) + 3 chat cases (chat-001..003) under v0.1.30 production state (title-augmented re-embedded index + v1.6 doc + v1.5 chat + Auditor v0.1.29). Reports at `evals/reports/v0.1.30/probe.md`.

**Doc-mode citation_recall = 0.33 mean** (target was ≥0.38; equals v0.1.28 baseline; **FAILS SHIP criterion D5 "≥+0.05 lift"**).

**Doc-mode citation_precision = 0.00 mean across 3 cases** (vs v0.1.28 baseline probe 0.50/0/0 = 0.17). **REGRESSION**.

**Per-case over-citation expansion (canonical mechanism evidence)**:

| Case | v0.1.28 probe citas | v0.1.30 probe citas | Expansion | precision delta |
|---|---|---|---|---|
| doc-001 | 2 (`['2.1','6.2']`) | 12 (`['1','112.1','26.11','26.7','26.9','3.1','43.3','6.3','74.12','79.6','80','9.5']`) | **6x** | 0.50 → 0.00 ❌ |
| doc-002 | 2 (`['2.1','5.1']`) | 7 (`['1','10.2','10.5','113.1','113.3','113.6','50.5']`) | **3.5x** | 0/0 → 0/0 flat |
| doc-003 | 1 (`['2.1']`) | 19 (`['12.2','13.1','14.3','14.4','17.1','18.1','26.11','26.2','26.5','6.1','6.5','73.1','73.2','73.6','9.1','9.2','9.5','9.6','9.8']`) | **19x** | 0/0 → 0/0 flat but 19 emitted vs 1 |

**Median expansion = 5x**. Chat-mode on the overlapping 3 cases (chat-001..003) is essentially unchanged (3/3 verdict_match preserved; per-case citation lists nearly identical to v0.1.29 baseline; chat-002 actually slightly improved).

### Mechanism attribution (§22.22 honest)

**The intervention worked AS DESIGNED at the embedding level** (title prefix changes vectors; cosine sim 0.97 vs pre-v0.1.30 snapshot on ai_act.1.en confirms meaningful vector shift). But the **downstream consequence was unfavorable**: title-augmented embeddings surface significantly more topic-related corpus articles per doc segment → v1.6 doc_analyst emits Findings citing all the surfaced articles → precision tanks because the gold-specific articles still don't dominate the surfaced set + the over-emission dilutes the signal.

**This is the same mechanism as ADR-0033 §22.22 #5 T4-extra α+β REVERT** (v0.1.28): "T4-extra α+β: top_k=15 + max_chunks_per_norma=5. Caused context dilution; citation_precision 0.17 → 0.00. REVERTED." The breadth dilution at the retrieval-config layer (v0.1.28 T4-extra) and at the embedding-vector layer (v0.1.30) produce the same over-citation failure mode. The mechanism is **structural to BGE-M3 + v1.6 doc_analyst** combination, not stochastic to the specific intervention.

### Decision — REVERT per ADR-0035 D5 + cost discipline

**T7 paid main (~€1.40) SKIPPED**. With N=3 probe showing structurally clear regression matching a prior REVERT mechanism + clear theoretical attribution, spending €1.40 to "confirm REVERT" would be wasteful (~12% of remaining $9.20 budget; same outcome with high confidence). Atomic revert via snapshot mv-back + manifest git-checkout + code restoration costs $0 and is byte-equivalent to pre-v0.1.30 state.

### Atomic revert applied

1. **Index revert**: `mv corpus/indexes/regulaitor.lance.pre-v0.1.30/ corpus/indexes/regulaitor.lance/` (atomic; pre-v0.1.30 snapshot becomes live; the v0.1.30 title-augmented index discarded after cosine-sim verification it was meaningfully different).
2. **Manifests revert**: `git checkout HEAD -- corpus/manifests/` (restores pre-v0.1.30 `embedded_at` timestamps in ai_act.json / gdpr.json / nis2.json / dora.json).
3. **Code revert** (in this commit): `src/regulaitor/rag/build.py` restored to main state (remove `_text_to_embed` helper + restore `embeddings.embed([ch.text for ch in chunks])` line + remove `Chunk` import); `tests/unit/rag/test_build_title_augmented.py` removed (5 tests).
4. **Verification**: live index cosine sim 0.97 (NOT 1.0) vs the discarded v0.1.30 index → confirms revert is real (different vectors); pytest 999/0/1 (back to v0.1.29 baseline); `git diff main -- src/regulaitor/rag/build.py` empty (byte-equivalent restoration).

### §6 invariant — HELD throughout

`citation/validator.py` + `citation/schemas.py` + `agents/auditor.py` + `agents/analyst.py` + `prompts/` + `rag/chunking.py` + `rag/retrieval.py` + `rag/schemas.py` + `rag/store.py` + `evals/` pipeline + gold set ALL BYTE-UNCHANGED across both T1+T2 (activation) and T-revert (restoration). The only files modified at activation were `src/regulaitor/rag/build.py` (helper + import + 1 line) + `tests/unit/rag/test_build_title_augmented.py` (NEW). Both reverted cleanly. 0 fabrications detected at T5 probe (per-citation reasons all valid `text_not_in_apartado` or `article_not_found` patterns). redteam-smoke 0.92 carry preserved by construction (retrieval-layer index change does not affect deterministic adversarial sanitizer/injection patterns; verified by `redteam-smoke` not re-run since the change didn't touch sanitizer/injection code paths).

### Lessons learned — carry-forwards

1. **Over-citation pattern is structural to BGE-M3 + v1.6 doc_analyst combo** when retrieval breadth expands (whether via top_k, max_chunks_per_norma, OR vector-similarity broadening from title-augmented embeddings). Future doc-mode retrieval improvements should target QUERY-SIDE precision (HyDE per Alternative A; hybrid BM25 per Alternative B) OR a different prompt strategy that suppresses citation-of-non-gold articles, NOT corpus-side breadth expansion.

2. **The descriptive-doc-segment → obligation-corpus-article semantic gap is fundamental** at the embedding level and CANNOT be closed by title prefix alone — HyDE-style query reformulation (LLM drafts a hypothetical regulatory answer → embed THAT) is more theoretically grounded. Carried as HX post-deploy work; real traffic will inform whether the gap matters in production.

3. **v0.1.28 T4-bis title-prepend QUERY-side STAYS** (proven helpful at v0.1.28 main; citation_recall 0 → 0.33). The v0.1.30 REVERT does NOT revert v0.1.28's query-side prepend; only the corpus-side mirror was reverted.

4. **Doc gold set N=10 too small for high-confidence retrieval-engineering decisions** — even if a probe shows lift on 3 cases, main N=10 noise floor is ~20% per v0.1.23 §REVERT. HX retrieval work needs N≥30 doc cases OR real production traffic, neither available pre-H17.

5. **Methodology vindication**: v0.1.30 is the **2nd REVERT outcome** in the §22.22 lineage (after v0.1.23). The methodology contribution — diagnose → intervene → measure → refute → revert → document — applies across both retrieval (v0.1.30) and Auditor (v0.1.23) layers. The §6 invariant held throughout both.

### Cost summary

- Total v0.1.30 paid: **€0.65** (T5 probe; T7 main skipped per §REVERT decision)
- Sunk vs budget: 6.5% of €10 remaining (vs alternative €2.05 = ~20% if main proceeded)
- Saved by skip: ~€1.40 + ~1h wall-clock + closure complexity

### Plan progress

**12 consecutive milestones with §22.22 honest framing pattern** (v0.1.19 / v0.1.20 / v0.1.21 / v0.1.21.2 / v0.1.22 / v0.1.22.1 / v0.1.23 [REVERT] / v0.1.24 / v0.1.24.1 / v0.1.25 [CONFIRM partial] / v0.1.29 [CONFIRM all-blocked] / v0.1.30 [REVERT title-augmented]). v0.1.30 is the **2nd REVERT outcome** in the lineage; meta-validates the diagnose-intervene-measure-refute-revert-document science cycle as **applicable across retrieval-layer interventions (v0.1.30) and Auditor-layer interventions (v0.1.23)**, not just one layer. The §6 invariant held throughout both REVERTs.

The methodology continues to be the contribution.
