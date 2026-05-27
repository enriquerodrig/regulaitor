# ADR-0033 — doc_analyst v1.6 Finding-based refusal + role-default flip v1.0→v1.6

- **Status:** Accepted — 2026-05-27 — squash `d02336a`, tag `v0.1.28-doc-analyst-v1-6`
- **Milestone:** v0.1.28 (doc-mode quality fix; mirror of v0.1.21 chat lineage ported to doc role)
- **Spec/plan:** inline (no separate spec; pattern fully derived from ADR-0026 + ADR-0027 + ADR-0032 chat-role precedent)
- **Companion ADRs:** [0026](0026-v0120-paid-validation.md) (chat role v1.0→v1.4 first flip), [0027](0027-v0121-auditor-quorum-hard-constraints.md) (Tier 2 Capa A+B+C + chat v1.5 Finding-based refusal C4), [0029](0029-v0122-paid-validation.md) (Capa A nested-schema recursive walker fix), [0032](0032-auditor-partial-routing.md) (Auditor THREE-layer architecture)

## Context

**The v0.1.27 finding.** The v0.1.27 doc-mode paid measurement (3-doc probe, €0.16) revealed that the `doc_analyst` role with v1.0 prompt + v0.1.21 Tier 2 Capa A+B+C constraints produces a structural failure mode at scale:

- v1.0 doc_analyst prompt explicitly states (line 47-48): "An empty Findings list is a valid output when the segment contains no analyzable compliance content."
- v0.1.21 Tier 2 Capa B (ADR-0027 D2) added `Field(min_length=1)` to `Answer.findings` → empty findings is REJECTED at the Pydantic schema layer.
- v0.1.21 Tier 2 Capa C (ADR-0027 D4) added a 3-attempt retry loop with failure-specific feedback when validation fails.
- Sonnet 4.6 fallback behavior: when retried with feedback "your findings array is empty, must have ≥1 Finding", it emits a placeholder Finding with `articulo="<UNKNOWN>"`, `articulo="N/A"`, or `articulo="UNKNOWN"` to satisfy the `articulo: str` schema (which has no enum constraint).
- The Auditor's `citation_validator` rejects these placeholder citations (article doesn't exist in corpus) → all per-citation results invalid → all-blocked Finding routing → BLOCK verdict.
- Result on v0.1.27 probe doc-001..003: **3/3 docs BLOCK** (expected: 1 RHR + 2 PASS). verdict_match 0/3. citation_precision/recall 0/0. faithfulness 0.14-0.21. severity: none emitted. cited_articles all placeholder junk strings.

**The chat-mode equivalent fix.** The chat `analyst` role hit a similar but earlier wall:
- v0.1.17 diagnostic ADR-0022: identified the no-Answer residual as 5-mechanism (refusal / analyst_raise / transport_error / prose_without_findings / other).
- v0.1.17.1 ADR-0023: shipped v1.4 prompt (force-Finding-emission Hard Rule 9) + REFUSAL_PHRASES classifier extension.
- v0.1.20 ADR-0026: paid A/B v1.0 vs v1.4 → flip chat default v1.0→v1.4.
- v0.1.21 ADR-0027: Tier 2 Capa A+B+C hard constraints + final-review C4 caught the chat v1.4 vs Capa A+B incompatibility → shipped v1.5 Finding-based refusal pattern + flip chat default v1.4→v1.5.

**The fix never propagated to doc role.** The v1.5 prompt at `prompts/analyst/system.v1.5.md` is chat-only (the prompts directory is partitioned by role: `prompts/analyst/` vs `prompts/document_analyst/`). The `doc_analyst` role stayed on v1.0 — including the now-broken "empty findings is valid" pattern — through v0.1.21, v0.1.22, v0.1.25. The v0.1.27 probe was the first paid measurement of doc-mode under the Tier 2 Capa A+B+C constraints, and surfaced the structural failure.

## Decision

### D1 — Author v1.6 doc_analyst as faithful upgrade of v1.0 doc + chat v1.5 Finding-based refusal port

Create `src/regulaitor/agents/prompts/document_analyst/system.v1.6.md` that:
- **Preserves verbatim** the v1.0 doc_analyst anti-injection inviolable rules (data-not-instructions; adversarial-segment defense; H5 SSDLC framing per ADR-0007).
- **Preserves verbatim** the v1.0 doc_analyst §6 inviolable rule ("no citation, no answer" at per-Finding level: ≥1 citation + literal text + norma+articulo+apartado fields populated).
- **Replaces** v1.0's "An empty Findings list is a valid output" pattern with the chat v1.5 Finding-based refusal pattern (Output shape Rule 2): emit EXACTLY ONE Finding with text=refusal + citations=[REAL retrieved corpus chunk; typically the scope/applicability article of the most-relevant corpus] + severity=high.
- **Adds** Hard rule 4 inviolable: "Never emit placeholder citation strings like 'UNKNOWN', 'N/A', 'TBD', 'PLACEHOLDER', '<UNKNOWN>'". This is THE explicit fix for the v0.1.27-discovered failure mode.
- **Adapts** the 3 chat v1.5 examples to doc-mode context (segment analysis, not query Q&A): Example 1 = substantive Finding for non-compliance gap; Example 2 = positive coverage info Finding; Example 3 = THE Rule 2 refusal pattern demonstrating the v0.1.28 fix.

### D2 — Flip env-unset doc_analyst default v1.0 → v1.6

Modify `src/regulaitor/agents/analyst.py:122` role-aware ternary:
- Before: `default_version = "v1.5" if prompt_role == "analyst" else "v1.0"`
- After:  `default_version = "v1.5" if prompt_role == "analyst" else "v1.6"`

Mirrors the v0.1.20 ADR-0026 chat v1.0→v1.4 flip pattern and the v0.1.21 ADR-0027 final-review C4 chat v1.4→v1.5 flip pattern. Same single-line edit at the same line. Same regression-safe fallback (invalid env still returns v1.0). Same opt-in via `REGULAITOR_ANALYST_PROMPT_VERSION=v1.0` to retain a baseline-comparable code path for retrospective A/B.

### D3 — Validate via paid A/B vs cached v0.1.27 v1.0 baseline

The v0.1.27 probe paid €0.16 and produced doc-001..003 v1.0 baseline results (3/3 BLOCK, all-placeholder citations). Those reports serve as the **cached v1.0 baseline** for v0.1.28 — no re-payment of the v1.0 baseline is needed.

The v0.1.28 paid validation runs v1.6 on the same 10 doc cases (3 probe + 7 main):
- T5 probe doc-001..003 v1.6 (~€0.16): per-case verdict_match vs gold + per-case comparison vs cached v1.0 (PASS/RHR/BLOCK transition matrix + citation_precision/recall delta + faithfulness delta).
- T6 SKIP/PROCEED gate based on T5 results.
- T6 main doc-004..010 v1.6 (~€0.37): full 10-doc coverage + cost_per_doc retention check.

Expected outcome predictions (per chat v0.1.20 ADR-0026 + v0.1.21 ADR-0027 precedent of +9.4pp verdict_match on flip + Finding-based refusal):
- verdict_match 0/3 (v1.0 cached) → ~5-7/10 (v1.6 measured) on the 10-doc cohort.
- citation_precision/recall 0/0 → >0 (any positive value is structural win; mechanism placeholder bug fixed).
- faithfulness 0.14-0.21 (v1.0) → ~0.50-0.70 (v1.6); v1.6 cites real corpus articles, not `<UNKNOWN>` placeholders.
- cost_per_doc unchanged or slightly lower (v1.6 acerta first attempt; less Capa C retry overhead).

The §22.22 honest framing: any positive shift on these metrics confirms the fix; the absolute values matter less than the directional confirmation that the placeholder-citation bug is eliminated.

### D4 — §6 invariant interpretive evolution: prompt-level explicit forbid + Auditor-byte-unchanged

§6 evolved at v0.1.24 (ADR-0031) from "byte-unchanged" to "byte-equivalent semantics + additive observability"; evolved again at v0.1.25 (ADR-0032) to "THREE-layer Auditor architecture (validator + Finding-Lenient byte-unchanged + aggregation policy modified)". v0.1.28 adds a fourth layer of clarification: **prompt-level explicit forbid of placeholder citation strings**.

Statement at v0.1.28:
- **Layer (a) per-citation validator**: `citation/validator.py` + `citation/schemas.py` BYTE-UNCHANGED (the validator still rejects `articulo="<UNKNOWN>"` as it always has, on the grounds that no such article exists in any corpus).
- **Layer (b) Finding-Lenient aggregation**: `auditor.py::audit_answer` lines 47-119 BYTE-UNCHANGED.
- **Layer (c) Turn-level aggregation policy**: BYTE-UNCHANGED at v0.1.28 (v0.1.25 D2 partial-routing softening preserved).
- **Layer (d) prompt-level explicit forbid (NEW at v0.1.28)**: v1.6 doc_analyst Hard rule 4 explicitly forbids the model from emitting placeholder citation strings. This is BEHAVIORAL ENFORCEMENT at the model-side, complementing the existing layer-(a) validator-side enforcement. The two layers are defense-in-depth: layer (d) reduces the placeholder-bug rate via prompt discipline; layer (a) catches any remaining instances and rejects them per §6 invariant.

The §6 invariant "no citation, no answer" is preserved unchanged in semantic. v0.1.28 strengthens its enforcement at the model output layer in addition to the validator layer, narrowing the gap between "what the model emits" and "what the validator accepts".

### D5 — No spec/plan document

This ADR is the formal documentation; the design pattern is FULLY DERIVED from established precedent (ADR-0026 + ADR-0027 + ADR-0032 for the flip mechanics; v1.5 chat prompt for the refusal pattern; v1.0 doc_analyst for the anti-injection rules to preserve). No design judgment unique to v0.1.28 — just a faithful port of the chat lineage to doc role. Per project pattern, light-ceremony mini-milestones (v0.1.21.1, v0.1.21.2, v0.1.24, v0.1.24.1, v0.1.26) carry no separate spec/plan when the design is derivative; v0.1.28 follows this pattern.

## Alternatives considered

### Alternative A: Add Capa A `enum` constraint to `Citation.articulo` to reject placeholder strings at schema layer

**Rejected.** The corpus contains thousands of valid `articulo` values across 4 corpora; encoding them as a Pydantic enum is fragile (changes per corpus expansion + per-version) and shifts the §6 invariant enforcement from layer (a) validator (which has the corpus loaded) to layer (b) schema (which doesn't). Maintains separation of concerns: schemas validate STRUCTURE; validator validates EXISTENCE.

### Alternative B: Reject placeholder strings in `citation/validator.py` with a specific error code

**Rejected.** The validator ALREADY rejects placeholder strings (they fail `article_exists` check because no article named `<UNKNOWN>` exists in any corpus manifest). Adding a SPECIFIC error code "placeholder_citation_detected" would be observability-only, not behaviorally different. The fix needs to be UPSTREAM (model output) to prevent the symptom in the first place; downstream blocking is already in place.

### Alternative C: Doc-mode-specific prompt v1.6 OR uniform v1.5 across both roles

**Rejected uniform v1.5.** The chat v1.5 prompt has Hard Rule 8 (gap-analysis NL detection) which is irrelevant for doc-mode (each segment IS the analyzed content, not a user query with "I have X / what's missing" structure). It also has chat-Q&A-specific examples. Using v1.5 as-is for doc role would emit Q&A-style answers that misalign with the doc-mode SegmentResult shape downstream consumers expect.

**Chosen doc-specific v1.6.** Drops Hard Rule 8 (gap-analysis NL detection); rewrites examples for segment analysis; preserves anti-injection inviolable rules from v1.0 doc_analyst that the chat v1.5 doesn't have (chat doesn't process untrusted document segments, so the data-not-instructions inviolable rule isn't applicable to chat). The result is a true doc-mode adaptation of v1.5's Finding-based refusal pattern, not a copy-paste.

### Alternative D: Defer doc-mode fix to HX post-TFM and ship v0.1.28 as v1.0-doc-mode-known-bug "TFM-defendible-as-honest-gap"

**Rejected.** The bug structurally breaks doc-mode for non-trivial documents (any segment with insufficient retrieval context returns BLOCK with placeholder citations — i.e., almost every document in production will hit this on at least one segment). Shipping v0.1.28 as a documented bug would weaken the H16 deploy and create an immediate post-deploy issue for any real user uploading a document. The fix is small (1 new prompt + 1-line analyst.py edit + 6 tests) and the paid validation is cheap (~€0.53 total).

## §22.22 disclosures (5)

1. **The v0.1.27 probe (€0.16) is reused as the v1.0 baseline for v0.1.28 paid validation** — no re-payment of v1.0 baseline. This is honest cost-discipline: the v0.1.27 measurement-only milestone produced authoritative v1.0 baseline data as a side-effect of its primary cost/segmenter measurement objective.

2. **v1.6 is UNTESTED empirically pre-paid.** The Rule 2 refusal pattern is validated empirically in chat at v0.1.21 + v0.1.22 (chat-014/015/029/030 hard safety floor PASS). Doc-mode is a different code path (document_graph.run_document vs orchestration.graph.run); even though the prompt-level pattern is structurally identical, paid validation T5+T6 is the only authoritative empirical confirmation.

3. **The expected outcome predictions are extrapolations from chat lineage**, not measurements. Chat v0.1.20 flip showed +9.4pp verdict_match for v1.4 vs v1.0; v0.1.21 final-review C4 v1.4→v1.5 was structural fix not measured directly. Doc-mode flip prediction (0/3 → 5-7/10) is the analog projection; the actual lift may differ.

4. **Capa A nested-schema recursive walker (ADR-0029)** applies to doc-mode as well. No additional walker change needed at v0.1.28 (the v0.1.22 fix to `_set_additional_properties_false_recursive` covers all schemas including Finding+Citation). v0.1.28 doc-mode now FIRST exercises this walker under doc workload — paid validation will confirm.

5. **doc-mode performance/latency is NOT measured pre-flip.** v0.1.27 probe measured cost (€0.053/doc) and segmenter (3/3 exact). v0.1.28 will measure verdict_match + citation_precision/recall + faithfulness under v1.6 but does NOT re-measure cost (assumed unchanged or slightly improved per ADR-0027 D4 retry-reduction logic; if cost rises unexpectedly, T7 diagnostic will flag).

## Consequences

### Positive

- doc-mode `BLOCK`-by-default failure pattern eliminated structurally.
- §6 invariant enforcement strengthened with prompt-level defense in addition to validator-level catch.
- Chat + doc roles now have COHERENT refusal semantics (both use Finding-based refusal citing real corpus articles).
- v0.1.27 probe data reused without waste — €0.16 sunk cost produces v1.0 baseline + the v0.1.28 trigger evidence in one shot.
- TFM defense narrative: v0.1.27 → v0.1.28 sequence is the textbook "diagnose-first" methodology continuing to be the contribution.

### Negative / risks

- v1.6 doc_analyst is UNVALIDATED pre-paid (mitigated by T5 probe + cached v1.0 baseline comparison).
- Adds a 6th prompt file to maintain (analyst v1.0-v1.5 + document_analyst v1.0+v1.6). EOL policy carry to H17 (document v1.1-v1.4 NEVER existed; doc_analyst lineage is v1.0 → v1.6, skip versions for parity with chat).
- §6 "interpretive evolution" prose now spans 4 layers (validator + Finding-Lenient + aggregation policy + prompt-level forbid). TFM defense narrative must reconcile across ADR-0024 + ADR-0031 + ADR-0032 + ADR-0033 — the spine doc (decisions_log) handles this with chronological framing.

### Neutral

- doc-mode A/B paid cost ~€0.53 total = modest milestone cost; budget post-v0.1.28 ~$10.95 USD remaining → suficiente for H16 deploy + emergencies.
- Tests +6 net (988 baseline + 6 = 994/0/1).
- src/ scope = 1 file modified (agents/analyst.py 1-line ternary) + 1 prompt file added (prompts/document_analyst/system.v1.6.md).
- No new infrastructure; no breaking change for any consumer.

## References

- ADR-0026 (v0.1.20): paid A/B v1.0 vs v1.4 chat flip — establishes flip-after-paid-A/B pattern.
- ADR-0027 (v0.1.21): Tier 2 Capa A+B+C + final-review C4 v1.5 chat Finding-based refusal — establishes the refusal pattern this ADR ports to doc.
- ADR-0029 (v0.1.22): Capa A nested-schema recursive walker — orthogonal Capa A fix that doc-mode now exercises.
- ADR-0032 (v0.1.25): Auditor THREE-layer architecture — provides the §6 interpretive frame this ADR extends.
- v0.1.27 closure (`evals/reports/v0.1.27/doc-probe.md` + commit `b3273a3`): the trigger evidence.
- Future commits referenced from this ADR: T1+T2 (`4fa96a5`), T3 ADR-0033 (this commit), T4 pre-paid gate (TBD), T5 paid probe (TBD), T6 paid main (TBD), T7 diagnostic (TBD), T8 closure docs (TBD), T-final squash (`d02336a`; populated at T-final).
