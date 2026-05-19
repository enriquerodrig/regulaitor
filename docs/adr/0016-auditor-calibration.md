# ADR 0016 — Auditor Calibration Study (H15)

- **Status:** Accepted — 2026-05-19 — squash `<squash-sha>`, tag `v0.1.5-h15`
- **Deciders:** Project owner.
- **Companion ADRs:** 0010 (evaluation harness — the H8 Ragas + LLM-judge
  harness reused unchanged for the A/B; its same-provider-family judge caveat
  carried), 0013 (router multi-LLM — the `REGULAITOR_ROUTER_MODE` eval-override
  precedent the two H15 backend seams directly mirror), 0014 (Council of Judges
  — the `MonotonicEscalatePolicy` / `_COUNCIL_BINDING` binding seam stays OFF in
  H15 by decision D2).

## Context

CLAUDE.md §16.3 lists H15 as: "Calibración Auditor + A/B testing" — calibrate
the Auditor (RHR threshold, Analyst schema-adherence), activate the
`MonotonicEscalatePolicy` binding seam, measure real per-call cost, and run the
full LLM-judge eval over the expanded 44-case gold set. §17 #2/#3/#6 carries the
advanced citation/severity/block-rate targets; §22.22 demands academic honesty
(never present non-measured as measured, document partial/confounded results
transparently, exact-number discipline).

Entering H15 (main post-H14 `v0.1.4-h14`; squash `d2f2a75`) the frozen pre-H15
system-level signal was `verdict_match ≈ 0.28` (H8/H10 `0cc9534`-run committed
baseline), faithfulness 0.54, citation_precision 0.17–0.18, with the H12/H13
finding that the quality ceiling is **system-level**, not model choice, and the
H13 finding that the Auditor over-fires RHR on ambiguous cases (57% Council
divergence, 30% Analyst `findings=[]` skip rate). The gold set was expanded to
44 chat cases in H14.

**The reframe-forcing fact:** the Auditor (`citation/validator.py` + the
Lenient/Strict aggregation in `agents/auditor.py`) is a **pure-Python
deterministic aggregator with NO numeric thresholds** — no score, no cutoff, no
ROC operating point to sweep. "Calibrate the Auditor threshold" is not
literally possible without dishonesty. H15 was therefore honestly reframed
(same honest-reframe lineage as the closed H10 gate-reframe and H13 Done-when
reframe, §22.22) into a **system-level calibration STUDY**: one scientific
claim — `verdict_match ≈ 0.28` is dominantly Analyst-attributable, correctable
by a minimal single-variable versioned Analyst-prompt change, measured
rigorously against a frozen control with an overfitting guard.

## Decision

Five decisions (brainstorming closed 2026-05-19; full rationale + amendments in
`docs/technical_decisions_log.md §H15`; canonical study write-up in
`docs/auditor_calibration.md`):

### D1 — Option-1 Analyst-focus: no knob added to Auditor/validator

No numeric threshold or tunable knob is introduced into `agents/auditor.py` or
`citation/validator.py`; they remain **byte-identical** to pre-H15 production.
The deterministic invariant §6 ("no citation, no answer") is untouched. The
only component the diagnostic implicates is the **Analyst prompt**, and that is
the only component changed.

### D2 — Interventions: A + B (Analyst prompt-only); C measured-only; D OUT

Core interventions, **Analyst PROMPT-ONLY**: **A** (anti-over-citation: cite
only the article(s) directly supporting the finding) + **B** (anti-no-Answer:
hardened output contract — always a well-formed Answer or a well-formed
structured refusal). **C** (retriever re-tuning) is diagnostic-measure-only,
re-tuning **deferred** (the dominant remaining system-level lever). **D**
(Council binding) is **OUT** — the `MonotonicEscalatePolicy` /
`_COUNCIL_BINDING` seam stays OFF (ADR 0014 lineage). The no-Answer residual
that is not prompt-caused is a separate robustness follow-up, **NOT** an
in-H15 retry (single-variable discipline).

### D3 — Overfitting guard: iterate on 30, holdout 14, doc deferred

Iterate prompt candidates on the 30 original chat cases (chat-001..030).
**HOLDOUT** = the 14 H14 cross-corpus chat cases (nis2-/dora-/xcorpus-),
measured **once**, never iterated. The 10 doc holdout cases are deferred
(segmenter confound — see Consequences).

### D4 — Budget: hard ceiling ~€7.5 (~$8), no paid Groq

Hard budget ceiling ~€7.5 (~$8); no paid Groq tier; harness `--limit N` hard
cap + a `--limit 3` probe before every paid run; ≤3 candidate prompt
iterations.

### D5 — Honest done-when

Done-when = a rigorously documented study + **HARD safety non-regression** +
gate §16.2 green + coverage ≥90%; **NO promised metric number** (improvement
quantified OR a documented system-level ceiling — both defend).

> **Two-stage review caught a milestone-consequential plan-level Critical**
> (recorded per CLAUDE.md §22.1). **C1 (T5 code-quality, Opus, caught BEFORE
> any paid spend):** the original mechanical `safety_ok` rule would have
> auto-rejected the SAFER structured refusal (the deterministic Auditor has no
> `refused` verdict → a clean grounded refusal scores `pass`/RHR, never
> `block`), and `redteam-smoke` is prompt-blind (sanitizer/injection layers
> only — identical for v1.0 and v1.2 by construction). The spec/plan was
> amended to **content-based safety + mandatory controller manual backstop +
> honest rescope**. This is the single most valuable catch of H15 — the
> two-stage review delivering exactly the academic-honesty protection it
> exists for.

## Consequences

**Positive:**

- The honest §16.3 reframe is documented end-to-end: the Auditor has no
  thresholds; H15 is a system-level calibration study with one falsifiable
  claim. Canonical report: `docs/auditor_calibration.md`.
- **Two deliberate ADR-documented backend seams** — the ONLY backend touches,
  minimal enablers, NOT scope creep (spec §3.3 anticipated config/env; both
  mirror the ADR-0013 `REGULAITOR_ROUTER_MODE` eval-override precedent —
  env-gated, production-default byte-identical to pre-H15):
  1. `REGULAITOR_ANALYST_PROMPT_VERSION` env seam in `agents/analyst.py`
     (`__init__` only): selects the Analyst prompt version for eval; production
     default = v1.0 (byte-identical to pre-H15 production). Commit `5445d2a`
     (+ `4d65d82`).
  2. Router process-level real-cost accumulator in `models/router.py`
     (`_record_cost_eur` / `reset_cost_accumulator` /
     `get_accumulated_cost_eur`): closes the H12/H13 estimate-not-measured gap.
     Commit `1726ad0` (+ `358fd4d`).
- **Diagnostic anatomy** (`scripts/diagnose_baseline.py`, $0, frozen): default
  invocation vs the committed frozen baseline `evals/reports/latest.md`
  (run-commit `0cc9534`) → over_citation 12/30 (40%), no_answer 7/30 (23%),
  wrong_article 4/30 (13%), other 7/30 (23%) → **77% (23/30)
  Analyst-attributable**. Corroborating on the clean v1.0 re-baseline
  (`evals/reports/h15/baseline-v1.0.md`) → 9/8/8/5 → 83%. Robust ≈77–83%
  conclusion grounds the single claim.
- **A/B result honest** (30 calibration cases chat-001..030, single variable
  v1.0→v1.2, run commit `74efa27`): faithfulness 0.54→0.75 (+0.21),
  answer_relevancy 0.55→0.70 (+0.15), context_precision 0.44→0.60 (+0.16),
  context_recall 0.30→0.47 (+0.17), citation_precision 0.18→0.30 (+0.12),
  citation_recall 0.46→0.71 (+0.25 — §16.2#5 floor 0.40 **PASS**, did not
  regress, improved), verdict_match 0.17→0.27 (+0.10), severity_match
  0.31→0.42 (+0.11), cost_per_chat €0.062→€0.050, cost_total €1.85→€1.51.
  **Every metric improved; the gain is REAL but MODEST** — the system-level
  ceiling persists exactly as the H12/H13/H14 thesis predicted. The 6
  designated ambiguous-RHR cases (chat-011/012/013/026/027/028) verdicts are
  UNCHANGED v1.0→v1.2 (the +0.10 is NOT from gaming the RHR set); chat-026
  shows an honest per-case citation micro-regression (precision 0.50→0.33,
  recall 1.00→0.50, dropped apartado 33.3 due to Intervention A) — disclosed.
- **Holdout no-collapse** (single measurement, never iterated;
  `evals/reports/h15/holdout-v1.2-chat.md`, run commit `d104211`, 14 H14
  cross-corpus chat, v1.2, €0.78): faithfulness 0.66, answer_relevancy 0.66,
  context_precision 0.62, verdict_match 0.43, severity_match 0.67. v1.2 does
  NOT collapse on held-out cross-corpus data → the improvement is not a 30-case
  overfitting artifact (do **NOT** overclaim 0.43>0.27 as "better
  generalization"; the system-level ceiling persists).
- **Plan-vs-reality v1.1→v1.2 divergence (honest):** the plan said
  "v1.0→v1.1"; the frozen candidate is **v1.2** (v1.1 was an intermediate
  iteration within the ≤3-candidate D4 budget; v1.2 = v1.1 + sharpened
  Hard-rule-6 + dropped an Auditor-mechanics clause). Core A/B and holdout used
  v1.0 vs v1.2.
- **Real measured cost** (router accumulator — closes the H12/H13
  estimate-not-measured gap; itemized): v1.0 probe €0.23, v1.1 probe €0.16,
  v1.2 probe €0.16, v1.0 core €1.85, v1.2 core €1.51, doc probe €0.00
  (segmenter-confound), holdout probe €0.16, holdout full €0.78, + ~€0.20
  partial from a failed holdout attempt #1 (transient external Anthropic 529 in
  the judge layer — not a credit/bug issue; it motivated the T6c bounded-retry
  hardening, commit `d1c4255`). **Total ≈ €5.05 of the ~€7.5 (~$8) ceiling.**
  Cost is now **measured, not estimated**.
- Gate authoritative (controller-verified, H14 precedent): `uv run pytest -m
  "not slow"` → **746 passed, 0 failed, 0 errors, 1 skipped** (the expected
  `test_document_e2e_clean.py` `ANTHROPIC_API_KEY not set` — not a failure).
  **Coverage 93.46% ≥ 90%** ✅. Gate GREEN.

**Negative / accepted (documented honestly, not re-run — §22.22, H1-PDF-pivot /
H12 / H13 / H14 precedent):**

- **HARD safety guard — mechanical `safety_ok=False` BUT content-backstop 6/6
  CONTENT-SAFE → v1.2 NOT reverted.** Per the C1 design the content-based
  determination is authoritative: `deterministic_layer_sanity_ok(0.92)=True`
  (redteam-smoke block_rate 0.92 == frozen §16.2#4, NOT dropped); the coarse
  mechanical rule flags chat-029/030 + nis2-006/dora-006 as non-block+emitted
  (`safety_ok=False`) BUT the C1-mandated content-based controller manual
  inspection found **ALL 6 designated block cases (chat-014/015/029/030
  in-calibration + nis2-006/dora-006 holdout) CONTENT-SAFE** — every one
  refused the malicious premise, fabricated NO non-existent article, granted
  NO fake exemption, and where it cited it cited REAL corpus articles to
  REFUTE the attack. A structured refusal scoring `pass` is the **SAFE
  outcome, not a regression**. → the D5 revert trigger does NOT fire → **v1.2
  stands**.
- **Holdout citation_precision/recall = 0.00 is a measurement-instrument
  granularity CONFOUND**, NOT a v1.2 failure: H8 apartado-level metric vs H14
  article-level `expected_articles` + exact-match. The LLM-judge confirms the
  holdout citations are substantively correct. The holdout instrument was
  deliberately NOT post-hoc edited (§22.22 / D3 — editing it would invalidate
  the single-measurement guarantee). Categorized as **eval-instrument quality,
  NOT system optimization** — lower priority than retriever/segmenter; changing
  the metric/gold convention would require a full A/B re-baseline, so **not
  touched in H15**.
- **Recurring no-op-test Criticals caught by the two-stage review** (T3 env
  seam, T4 cost accumulator, T6a `_isolate_report` crash-safety, T7a parser
  column) — each a test that would pass even if the guarded behaviour
  regressed; each fixed with a genuinely-guarding test. **T6c FIX-NOW**: the
  harness-retry tests patched `tenacity.nap.sleep` (ineffective — bound as
  default arg at import; ran ~41s on real backoff) and didn't assert the
  3-attempt bound → fixed to patch `time.sleep` + assert `calls==3` (commit
  `d104211`). **T9 §2 sourcing correction** (diagnostic headline 12/7/4/7
  reframed as the reproducible default-invocation result, commit `f8e447b`) +
  **T9 code-quality** (§3.2 v1.1→v1.2 probe-rationale clarified, §9 ADR-0016
  forward-reference, commit `beef665`).
- **Deferred follow-ups (named, honest — post-H15 optimization phase):**
  (1) **retriever lever C re-tuning** — the dominant remaining system-level
  lever (diagnostic-measured-only in H15 per D2/D5); (2) **document segmenter**
  — the 1-doc probe emitted 0 segments → doc-mode A/B uncomputable → the 10
  doc holdout cases deferred; (3) **no-Answer-residual robustness follow-up** —
  the not-prompt-caused residual (spec D2; a separate robustness effort, NOT an
  in-H15 retry); (4) **Auditor RHR-aggregation-semantics calibration + the
  `MonotonicEscalatePolicy` / `_COUNCIL_BINDING` seam still OFF** (spec D2
  Council-binding OUT); (5) the **citation-metric granularity confound** —
  eval-instrument quality, not system optimization, requires a full A/B
  re-baseline if the convention changes; (6) **§17 thresholds + the LLM-judge
  same-provider-family limitation** (Haiku judge vs Sonnet prod, ADR-0010
  caveat carried).
- No new skills activated; `cost-accounting` stays H17 (scope kept tight;
  `evals-runner` active since H8 was the canonical procedure followed).

## Alternatives considered

- **Add a numeric RHR threshold/knob to the Auditor (literal §16.3 reading)** —
  rejected: the Auditor is a pure-Python deterministic aggregator with no score
  to threshold; adding one would break the §6 invariant and is not what the
  diagnostic implicates (D1).
- **Multi-variable Analyst+retriever+Council change in one cycle** — rejected:
  destroys single-variable attribution; the diagnostic implicates the Analyst,
  so A+B prompt-only, with C measured-only and D OUT (D2).
- **Iterate on the full 44-case set (no holdout)** — rejected: no overfitting
  guard; D3 holds out the 14 H14 cross-corpus cases, measured once.
- **Run the full §17-threshold LLM-judge eval and gate on absolute targets** —
  rejected: same honest-reframe logic as H10/H13/H14; the system is
  documented-uncalibrated and the §17 advanced targets are not honestly
  attainable in one prompt cycle. Done-when is a rigorous study, not a promised
  number (D5).
- **Mechanical `safety_ok` as the authoritative safety gate** — rejected (the
  C1 catch): it would auto-reject the safer structured refusal and
  redteam-smoke is prompt-blind. Content-based determination + manual backstop
  is authoritative.
- **Post-hoc edit the holdout citation instrument to fix the 0.00 confound** —
  rejected: would invalidate the single-measurement / never-iterate holdout
  guarantee (§22.22 / D3). Documented as an eval-instrument follow-up instead.
- **Activate the Council binding seam in H15** — rejected (spec D2;
  Council-binding OUT). Requires Auditor RHR-semantics calibration +
  Analyst schema-adherence validated first; the `_COUNCIL_BINDING=False` seam
  stays OFF.

## References

- Study report (canonical): `docs/auditor_calibration.md`
- Spec: `docs/superpowers/specs/2026-05-18-h15-auditor-calibration-design.md`
- Plan: `docs/superpowers/plans/2026-05-18-h15-auditor-calibration.md`
- Decisions log `§H15` (D1–D5, honest reframe, the two backend seams,
  v1.1→v1.2 divergence, diagnostic anatomy, A/B table, holdout + confound,
  safety guard, measured cost, two-stage-review-caught defects, follow-ups)
- ADR 0010 (evaluation harness — reused unchanged), ADR 0013 (the env-seam
  precedent the two H15 seams mirror), ADR 0014 (Council binding seam stays
  OFF)
- `scripts/diagnose_baseline.py` (frozen $0 diagnostic),
  `scripts/h15_ab_compare.py` (A/B + C1 content-safety logic, commit `74efa27`)
- `evals/reports/h15/baseline-v1.0.md`, `evals/reports/h15/candidate-v1.2.md`,
  `evals/reports/h15/holdout-v1.2-chat.md`
- `src/regulaitor/agents/analyst.py` (`REGULAITOR_ANALYST_PROMPT_VERSION`
  seam), `src/regulaitor/models/router.py` (cost accumulator),
  `src/regulaitor/agents/prompts/analyst/` (v1.0 frozen production, v1.2
  candidate)
