# ADR 0022 — No-Answer residual diagnostic ($0 cache-mining classifier) (v0.1.17)

- **Status:** Accepted — 2026-05-22 — squash `e5dbedd`, tag `v0.1.17-no-answer-diagnosis`
- **Deciders:** Project owner.
- **Companion ADRs:** 0010 (H8 evaluation harness — the existing diagnostic baseline classifier `scripts/diagnose_baseline.py` this extends; D7 cache-stores-judge-only is the mining substrate), 0016 (H15 Auditor calibration — Intervention B "hardened output contract" v1.1+v1.2 whose effectiveness this measures), 0020 (v0.1.15 chat gap-analysis — §22.22 capability-shipped + measurement-deferred pattern carried), 0021 (v0.1.16 dual-layer thresholds + judge family — measurement-architecture lineage; same Haiku 4.5 judge powers the cache being mined).

## Context

The H15 Auditor calibration study (ADR-0016, `docs/auditor_calibration.md`) documented that ~23% of the H10 30-case baseline failed with `no_answer` (the Analyst emitted no usable Answer → `audited_answer` is None → auto-RHR). H15 Intervention B (the "hardened output contract" in prompt v1.1+v1.2+v1.3) was designed to reduce this by forcing the model to ALWAYS emit a well-formed `emit_answer` tool call — including structured refusals with `findings: []` when the corpus doesn't support an answer. The H15 v1.2 holdout still shows 2/14 residual (dora-001, dora-004) per `docs/auditor_calibration.md:541`.

But the existing classifier (`scripts/diagnose_baseline.py`) labels `no_answer` coarsely: it just looks at `emitted == []` in the report. It does NOT distinguish three very different mechanisms:

- **Case A (refusal)**: Analyst correctly emitted Answer with `findings=[]` and refusal text — the v1.1/v1.2/v1.3 Output contract firing AS DESIGNED. The fix is upstream (retrieval missed the right chunks, OR the gold case has wrong ground truth).
- **Case B (analyst_raise)**: Analyst's 2-attempt retry-on-findings-missing (`analyst.py:97-175`, H8 addition) exhausted; raised RuntimeError; harness `_error_chat_state` sentinel substituted with empty findings + errors[] populated. The fix is Analyst-side (prompt v1.4 tightening OR additional retry strategies).
- **Case C (transport_error)**: Non-Anthropic exception (ConnectionError, TimeoutError, etc.) caught by `evals/harness.py::run_chat_case` → `_error_chat_state` substitution. The fix is harness-side (retry-on-transport-error hook).

The intervention shape depends entirely on which dominates the residual. Shipping a fix-first prompt v1.4 without diagnosing risks fix-the-wrong-thing (e.g. if Case A dominates, v1.4 changes nothing — the residual IS the contract working correctly).

The judge cache (`evals/cache/*.json`, 381 entries) contains the full Analyst Answer text per cached judge prompt (the judge's input includes `actual_answer` per the H8 prompt format). So we can mine the cache at $0 to extract the Analyst's actual emission per no_answer case and classify it.

## Decision

### D1 — Approach = diagnostic-first (intervention deferred)

v0.1.17 ships only the diagnostic. The intervention (if any) becomes a clearly-scoped follow-up microhito decided at v0.1.17 closure based on the actual class distribution:

- Refusal-dominant (>50%): no intervention warranted; the system is working as designed; carry to v0.1.18 (citation granularity confound — eval-instrument fix) or HX (retriever re-tuning / gold review).
- Analyst-raise-dominant (>30%): ship v0.1.17.1 = Analyst prompt v1.4 + optional harness retry-on-RuntimeError hook.
- Transport-error-dominant (>30%): ship v0.1.17.1 = harness retry-on-transport-error hook (no prompt change).
- Other-dominant (>30%): ship v0.1.17.1 = expand REFUSAL_PHRASES seed list + re-run diagnostic.
- Mixed: address the dominant class first; document the others as carry-forward.

### D2 — Data sources = 3 canonical reports + 381-file judge cache

Mine `evals/reports/latest.md` (H10 frozen @ `0cc9534`, 30 chat baseline, v1.0 prompt, ~7 no_answer per `scripts/diagnose_baseline` headline), `evals/reports/h15/candidate-v1.2.md` (H15 v1.2 30-case A/B, same gold set), and `evals/reports/h15/holdout-v1.2-chat.md` (H15 v1.2 14-case cross-corpus holdout, 2 residual). For each no_answer case, scan `evals/cache/*.json` for matching judge prompts; the cached `request.user` is a JSON string with `{query, actual_answer, expected_answer, cited_articles, expected_articles, criteria}` — exact-match on `query` (= gold case `entrada`) yields the Analyst's full Answer text. Cache absence is a meaningful signal (judge wasn't called because Analyst raised pre-judge), classified as `analyst_raise` with documented ambiguity.

### D3 — Taxonomy = 4-bucket classifier (refusal / analyst_raise / transport_error / other)

Algorithm (verbatim from spec §2 D3):

1. Locate cache entry by exact-match on `request.user.query == gold_case.entrada`. Use first matching entry.
2. If no cache entry matched → `analyst_raise` (most likely: Analyst raised before judge was called).
3. If cache entry found, inspect `actual_answer`:
   - Empty string OR `"(backend error)"` sentinel → `transport_error`.
   - Contains any phrase from `REFUSAL_PHRASES` seed list (case-insensitive substring) → `refusal`.
   - Non-empty + no refusal phrase → `other` (needs manual review).

Seed list `REFUSAL_PHRASES`: 16 Spanish phrases + 6 English phrases (22 total) — explicitly non-exhaustive. False negatives classify as `other` and flag follow-up "expand seed list" sub-recommendation.

### D4 — Output = per-case classification table + aggregate counts + conditional intervention recommendation

`docs/no_answer_residual_diagnosis.md` is PRODUCED BY THE SCRIPT (not hand-written) and contains: Dataset / Aggregate counts / Per-report breakdown / Per-case classification table / Trajectory analysis (H10 v1.0 → H15 v1.2 class shift = evidence of Intervention B effectiveness) / Recommended intervention (5 conditional branches per D1) / §22.22 honest caveats. The file is committed as the v0.1.17 closure artifact and doubles as memoria-ready WHAT/WHY/HOW/IMPACT.

## Consequences

**Positive:**

- **$0 evidence-driven intervention decision**: cache-mining + seed-list classification avoids paid LLM probe; fix-the-right-thing risk reduced.
- **Taxonomy reusable**: the 4-bucket schema + `NoAnswerDiagnosis` dataclass can be re-run against future eval reports (e.g. v0.1.20 paid bundle) to track no_answer trajectory across milestones.
- **Surgical change**: 1 new script + 1 new test file + 2 new docs (ADR + diagnostic output). Backend H1-H5/H7 + Auditor + citation-validator + Pydantic schemas + DTOs + eval-internals (judge/cache/harness/metrics/schemas/report) + Analyst prompts v1.0-v1.3 + gold set ALL BYTE-UNCHANGED. Verified by 5 git-diff HARD checks at T5.
- **10 new $0 unit tests** pin classifier behavior + seed list + extractor + parser.
- **ADR-0010 D8 firm**: no backend modification. v0.1.17 stays purely in `scripts/` and `docs/`.

**Negative / accepted (documented honestly per §22.22):**

- **Cache-mining is heuristic**: exact-match on `query` requires that the gold `entrada` appears verbatim in the judge prompt's `query` field. If H4 reformulated the query before passing to Analyst, the match would fail and the case would mis-classify as `analyst_raise`. Documented in the diagnostic's caveats section.
- **REFUSAL_PHRASES seed list is human-curated and non-exhaustive**: 22 phrases (16 ES + 6 EN). False negatives classify as `other`; if `other` count is high, the seed list needs expansion (potential v0.1.17.1 sub-recommendation).
- **Cache absence ambiguity**: `analyst_raise` and `transport_error` are indistinguishable when no cache entry exists (the cache stores judge prompts; if no judge was called, no entry exists regardless of WHY). Conservative default: classify as `analyst_raise` (Analyst pre-judge raise is more common than backend transport error per H8 lineage); the diagnostic's caveats document this.
- **No paid LLM run in v0.1.17**: the diagnostic produces classified evidence at $0 but does NOT measure the post-intervention residual rate — that's v0.1.20 paid bundle territory. v0.1.17's contribution is the composition of the pre-intervention residual.
- **Intervention deferred to follow-up**: v0.1.17 ships data + recommendation, not a fix. The actual fix is v0.1.17.1 (if warranted by data) or absorbed into v0.1.18. Honest §22.22 framing — fix waits for measurement.

## Alternatives considered

- **Fix-first prompt v1.4 (skip diagnostic)** — rejected. Risk of fix-the-wrong-thing: if Case A (refusal) dominates, v1.4 changes nothing because the Output contract is already firing correctly. Diagnostic at $0 is cheap insurance against wasted scope.
- **Fix-first harness retry-on-empty-findings hook (skip diagnostic)** — rejected, same reasoning. If Case A dominates, harness retry on a correctly-emitted refusal is wasted call + adds latency.
- **Diagnostic + speculative intervention in single v0.1.17** — rejected. Combines disciplines but if Case A dominates, the speculative fix is wasted scope. The cleaner pattern is diagnostic-first, then targeted intervention as v0.1.17.1.
- **Re-run no_answer cases via paid Sonnet probe (~$0.14 for 7 H10 cases)** — rejected for v0.1.17. Cache-mining covers it at $0. The paid probe option stays viable for v0.1.20 if the cache-mining yields too many `other` (ambiguous) classifications.
- **Modify `scripts/diagnose_baseline.py` in place** — rejected. The baseline classifier is the canonical H15 calibration evidence (reproducible deterministic; committed; cited in `docs/auditor_calibration.md`). Adding sub-case classification couples two distinct concerns. The new `scripts/diagnose_no_answer.py` is a SEPARATE script that extends, not modifies, the existing one. Backward-compat preserved.

## References

- Spec: `docs/superpowers/specs/2026-05-21-v0.1.17-no-answer-residual-design.md` (commit `7994ca1`).
- Source data: `evals/reports/latest.md` (H10 @ `0cc9534`), `evals/reports/h15/candidate-v1.2.md`, `evals/reports/h15/holdout-v1.2-chat.md`.
- Existing baseline classifier: `scripts/diagnose_baseline.py` (H15 addition; reproducible deterministic).
- Cache substrate: `evals/cache/*.json` (381 entries; gitignored; regenerable via `make eval`).
- §22.22 honest-framing precedent: H15 / H15.1 / v0.1.10 / v0.1.11 / v0.1.12 / v0.1.13 / v0.1.14 / v0.1.15 / v0.1.16 all shipped under capability-shipped + measurement-deferred pattern.
- §6 invariant lineage: `CLAUDE.md` §6 + ADR-0006 (H4 chat E2E). Auditor + citation-validator BYTE-UNCHANGED in v0.1.17 (no touch).
- ADR-0010 D7 (cache covers judge layer only) — the substrate this mines.
- ADR-0010 D8 (no backend modification) — firm; v0.1.17 ships only `scripts/` + `docs/` additions.
- Diagnostic output (v0.1.17 closure artifact): `docs/no_answer_residual_diagnosis.md` (produced by `python -m scripts.diagnose_no_answer` at T4).
- Future paid validation: v0.1.20 paid bundle.
