# ADR 0023 — No-Answer residual fix (TWO-part + 5-bucket extension) (v0.1.17.1)

- **Status:** Accepted — 2026-05-22 — squash `98f3768`, tag `v0.1.17.1-no-answer-fix`
- **Deciders:** Project owner.
- **Companion ADRs:** 0016 (H15 Auditor calibration — REGULAITOR_ANALYST_PROMPT_VERSION env seam this extends with v1.4; production default stays v1.0 per the boundary contract carried since v0.1.15), 0020 (v0.1.15 chat gap-analysis — Analyst prompt v1.3 this builds on; v1.4 preserves gap-analysis chat mode byte-identical), 0021 (v0.1.16 dual-layer thresholds + judge family — same v0.1.20 acceptance ritual will measure v1.4 against the v0.1.20-bar), 0022 (v0.1.17 no-Answer residual diagnostic — the evidence-driving the v0.1.17.1 intervention; D1's "other-dominant → v0.1.17.1 expand REFUSAL_PHRASES + re-run" branch fires, plus the 5th-mechanism finding redirects v1.4's wording).

## Context

The v0.1.17 cache-mining diagnostic (ADR-0022, `docs/no_answer_residual_diagnosis.md`) classified **12 no_answer cases** across 3 reports (H10 baseline, H15 v1.2 candidate, H15 v1.2 holdout) into the 4-bucket taxonomy:

- refusal: 0/12 (0%)
- analyst_raise: 0/12 (0%)
- transport_error: 2/12 (17%)
- **other: 10/12 (83%)** — dominant

Per ADR-0022 D1's conditional intervention rules: other-dominant → v0.1.17.1 expand REFUSAL_PHRASES seed + re-run.

But the diagnostic-first design paid off in a deeper way: inspecting the 10 `other` cases per-case (beyond mechanical classifier output) reveals a **5th mechanism the 4-bucket taxonomy didn't anticipate**:

- **8 of 10 `other` cases are prose-without-findings**: the Analyst emits substantive prose answers in the `text` field (real RGPD / AI Act / DORA content) but fails to structure them as `Finding` objects with citations. Examples: chat-003 "El AI Act impone a los proveedores…", chat-019 "Según el RGPD, el tratamiento de categorías especiales…", dora-001 "El Reglamento DORA impone a las entidades financieras…".
- **2 of 10 `other` cases are redteam-block refusals with phrasings outside the 22-entry seed list**: chat-014 "Esta solicitud no puede ser atendida…", chat-015 "Esta consulta no puede ser atendida…". The Analyst correctly refused; the diagnostic missed the refusal because the seed didn't cover the "atendida" phrasing.

A fix-first prompt v1.4 (skipping the v0.1.17 diagnostic) would have addressed only the refusal-phrasing aspect (2/12 = 17%, secondary), not the dominant prose-without-findings pattern (8/12 = 67%). The diagnostic exposed the 5th mechanism, which redirects the intervention.

## Decision

### D1 — Approach = intervention + observability extension (no measurement in v0.1.17.1)

Ship the intervention (v1.4 prompt + seed expansion) AND the diagnostic observability extension (5th bucket). DO NOT measure v1.4 effectiveness with a paid LLM run in v0.1.17.1. Empirical A/B v1.0 vs v1.4 on the 30-case cohort goes into the **v0.1.20 paid bundle** (alongside all maximalist-plan optimizations, per the bundled-validation discipline established v0.1.8).

Rationale: $0 budget remaining; v0.1.20 bundled measurement amortizes paid run across multiple capabilities (v1.4 + v0.1.10/v0.1.11/v0.1.12 retrieval levers + v0.1.13/v0.1.15 gold extensions + v0.1.14 segmenter); v1.4 production-default flip happens in the v0.1.20 acceptance ritual against the v0.1.20-bar (ADR-0021) — NOT in v0.1.17.1.

### D2 — REFUSAL_PHRASES expansion = 3 phrases, evidence-driven only

Add to `REFUSAL_PHRASES_ES` in `scripts/diagnose_no_answer.py`:

1. `"esta solicitud no puede ser atendida"` — verbatim from chat-014.
2. `"esta consulta no puede ser atendida"` — verbatim from chat-015.
3. `"no se puede atender"` — catch-all for the "atender" pattern (covers nearby phrasings the model variants might emit, e.g. "esta petición no se puede atender").

Counts: 16 → 19 ES, 6 → 6 EN, total 22 → **25**. Length-sort behavior in `_find_refusal_phrase` (added v0.1.17) preserved.

NOT speculative catch-all expansion: only the evidence-driven 3 phrases. If v0.1.17.1's re-run still shows residual `other` cases with new refusal phrasings, those carry to a future v0.1.17.2 (or get absorbed into the v0.1.20 acceptance narrative).

### D3 — Analyst prompt v1.4 = v1.3 + Hard Rule 9 + Output contract amendment

NEW file: `src/regulaitor/agents/prompts/analyst/system.v1.4.md`. Built on top of v1.3 (preserves gap-analysis chat mode from v0.1.15). Production default stays **v1.0** (boundary contract carried verbatim: env-unset = v0.1.17 byte-identical); v1.4 opt-in via `REGULAITOR_ANALYST_PROMPT_VERSION=v1.4` for v0.1.20 paid bundle measurement.

Hard Rule 9 (verbatim):

> 9. A substantive answer in `text` without `findings` is INVALID. If your `text` field contains any substantive claim about what the law requires, permits, prohibits, or how a corpus article applies — even one sentence beyond pure acknowledgement — you MUST emit at least one `Finding` with ≥1 citation grounding that claim. Emitting prose into `text` while leaving `findings: []` violates §6 ("no citation, no answer") and the Auditor will auto-reject the answer. Before returning, perform a self-check: "Did I make any normative or factual claim about the corpus in `text`? If yes, is each such claim represented by ≥1 Finding with a literal citation?" If a claim is not represented, either (i) add a Finding for it, or (ii) remove the claim from `text` and emit a structured refusal instead (Output contract Rule 2). There is no third option.

Output contract amendment on the context-supports-answer branch: "Per Hard rule 9, every substantive claim in `text` must map to ≥1 Finding — empty `findings` with non-empty substantive `text` is INVALID".

Design notes:

- **"Substantive" not "any"** — `text` like "Has declarado: X, Y" (gap-analysis acknowledgement) or "El AI Act no contiene disposiciones aplicables a tu consulta" (refusal) is NOT a normative claim about the corpus — those legitimately stay without Findings.
- **Self-check instruction** — forces the model to reason about its own output before tool emission, mirroring v1.2 Hard Rule 6's single-most-directly-supporting-article self-check that worked.
- **No JUNK-Finding risk** — self-check explicitly offers "remove the claim from `text` and emit a refusal" as alternative; gives the model an out instead of fabricating empty Findings to satisfy a quota.
- **Hard rules 1-8 + Output format + Output contract — gap-analysis branch + Examples 1-3 byte-identical to v1.3** (regression-zero on gap-analysis chat mode + Q&A path; verified by 4 byte-equal tests in `tests/unit/test_analyst_v1_4_loads.py`).

### D4 — Classifier 5th bucket = `prose_without_findings` with 100-char heuristic

Extend `classify_no_answer_case` in `scripts/diagnose_no_answer.py`: between the existing refusal-phrase step and the `other` fallback, add a `prose_without_findings` step that triggers when `actual_answer` is non-empty + has no refusal phrase + `len(actual_answer.strip()) > 100`. Cases ≤ 100 chars without refusal phrase stay `other` (conservative — short edge cases remain visible for manual review).

Why 100 chars: all 8 observed prose-without-findings cases from v0.1.17 diagnostic are ≥ 200 chars (substantive paragraphs starting with "El AI Act impone…", "Según el RGPD…", "El Reglamento DORA impone…"). A 100-char ceiling on `other` keeps the bucket for genuine edge cases without over-classifying short refusal variants.

`_recommend_intervention` gains a 5th branch for prose_without_findings-dominant (>50%) labeling the dominant class + referencing v1.4 + force-Finding-emission as the v0.1.17.1 intervention shape.

§22.22 honest caveat carried in the produced markdown: "The 100-char threshold is a heuristic motivated by the v0.1.17 observation that all 8 prose-without-findings cases exceeded 200 chars. Future diagnostic runs may surface short substantive prose cases that the threshold misses — these stay in `other` and remain visible for manual review."

### D5 — Diagnostic re-run = committed artifact in v0.1.17.1 closure

After (a)+(c) are in place, controller-runs `python -m scripts.diagnose_no_answer` against the same cache snapshot used in v0.1.17. Updated `docs/no_answer_residual_diagnosis.md` committed as v0.1.17.1 closure artifact. Expected reclassification (honest, not promised):

- `refusal`: 0 → ≥2 (chat-014/015 reclassify from `other`).
- `prose_without_findings`: 0 → ≥6 (the 8 substantive-prose cases minus the 2 redteam-block phrasings now in refusal; conservative because the 100-char threshold may classify some short substantive cases back to `other`).
- `other`: 10 → ≤2 (residual ambiguous cases requiring manual review).
- `transport_error`: 2 → 2 (unchanged).
- `analyst_raise`: 0 → 0 (unchanged).

The v1.4 prompt's effectiveness is NOT measured here (deferred to v0.1.20 per D1) — the re-run validates that (a) and (c) work as designed.

## Consequences

**Positive:**

- **Evidence-driven intervention**: v1.4 + seed expansion target actual dominant patterns from v0.1.17 (not speculative).
- **§6 invariant strengthened**: Hard Rule 9 makes the "no citation, no answer" invariant explicit at the prompt level, not just enforced downstream by the Auditor.
- **Boundary contract preserved**: production default stays v1.0; v1.4 is opt-in via env. Zero risk to current production behavior.
- **5-bucket taxonomy reusable**: future diagnostic re-runs (v0.1.20, post-TFM) directly count the 5th mechanism instead of inferring from `other`.
- **$0 milestone**: cache-mining re-run + unit tests; no paid LLM.

**Negative / accepted (per §22.22):**

- **No empirical validation in v0.1.17.1**: v1.4's effectiveness is NOT measured here. v0.1.20 paid bundle measures it.
- **100-char heuristic threshold**: short substantive prose cases (rare but possible) stay in `other` and require manual review.
- **3-phrase seed expansion is non-exhaustive**: future drift handled at v0.1.17.2 or v0.1.20 acceptance narrative.
- **No JUNK-Finding empirical risk assessment**: Hard Rule 9 explicitly guards against JUNK Findings via self-check + "remove the claim" out, but the actual model behavior under v1.4 is unmeasured until v0.1.20.
- **Cross-prompt regression risk at v1.4**: Hard Rule 9 + Output contract amendment interact with v1.3's gap-analysis Hard Rule 8 in ways unmeasured here. The "preserves gap-analysis branch byte-identical" test pins the prompt structure, but model behavior under v1.4 on gap-analysis cases is not validated until v0.1.20. The T4 code-quality review flagged Example 3's "Importante: confirmar la clasificación alto riesgo bajo art. 6" as a borderline "substantive claim" that could trigger a JUNK-Finding emission under strict Rule 9 reading — empirical question for v0.1.20 measurement (would warrant a v1.5 carve-out sentence on the gap-analysis orientation prose if the failure mode materializes).

## Alternatives considered

- **Fix-first prompt v1.4 (skip v0.1.17 diagnostic entirely)** — already rejected in ADR-0022 D1 alternatives. The diagnostic-first design paid off here: v0.1.17 exposed the prose-without-findings 5th mechanism, which redirects v1.4's wording from "expand structured-refusal contract" (the speculative target) to "force Finding emission on substantive prose" (the evidence-driven target).
- **Speculative seed expansion (10-20 new REFUSAL_PHRASES)** — rejected. Only the 3 evidence-driven phrases are added. Prophylactic expansion risks false-positives (legitimate prose accidentally containing common phrases).
- **6-bucket taxonomy** — rejected as premature. 5-bucket addresses the observed 5th mechanism; a 6th bucket waits for evidence of a 6th mechanism in v0.1.20 paid run.
- **Ship (a) and (c) only, defer (b) v1.4 prompt to v0.1.17.2** — rejected. The v1.4 prompt is the intervention closest to the dominant pattern; deferring it would leave v0.1.17.1 as a pure observability update with no actual fix. The bundling of (a)+(b)+(c) in one milestone is appropriate because they all address the same evidence and don't require paid measurement to ship.
- **Promote v1.4 to production default in v0.1.17.1** — rejected. Production-default flip is governed by v0.1.20-bar measurement (ADR-0021); flipping without measurement would violate §22.22.
- **Stricter Hard Rule 9 wording ("MUST emit ≥1 Finding for any non-empty `text`")** — rejected. Too strict: would force JUNK Findings on legitimate acknowledgements and refusals.
- **Softer Hard Rule 9 wording ("should emit Findings when appropriate")** — rejected. Too soft: empirical evidence from v0.1.17 shows the current "If the context supports an answer: emit findings" permission framing already fails. The intervention needs absolute language with self-check enforcement.

## References

- Spec: `docs/superpowers/specs/2026-05-22-v0.1.17.1-no-answer-fix-design.md` (commit `2c7ddba`).
- Plan: `docs/superpowers/plans/2026-05-22-v0.1.17.1-no-answer-fix.md` (commit `27d2235`).
- ADR-0022 (v0.1.17 no-Answer residual diagnostic — the evidence).
- ADR-0021 (v0.1.16 dual-layer thresholds — v0.1.20-bar measurement venue).
- ADR-0020 (v0.1.15 chat gap-analysis — v1.3 base preserved by v1.4).
- ADR-0016 (H15 Auditor calibration — REGULAITOR_ANALYST_PROMPT_VERSION env seam).
- Updated diagnostic output (v0.1.17.1 closure artifact): `docs/no_answer_residual_diagnosis.md` (regenerated by T6 controller-run).
- New Analyst prompt: `src/regulaitor/agents/prompts/analyst/system.v1.4.md` (T4 commit `24d067b`).
- Future paid validation: v0.1.20 paid bundle.
