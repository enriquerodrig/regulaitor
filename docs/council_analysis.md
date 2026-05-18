# RegulAItor — Council of Judges Divergence Study (H13)

**Date:** 2026-05-18 · **Run:** `scripts/council_eval.py` over the 30 chat gold cases, `council_override=True` forced on every case.
**Council:** 3 judges via the H12 router — `judge`=Claude Haiku 4.5 (Anthropic) · `evaluation`=GPT-4o (OpenAI) · `cost`=Llama-3.3-70b (Groq) — aggregated by `AdvisoryMajorityPolicy`.
**Verdict authority:** **advisory only** — the Council never changes the deterministic mechanical-Auditor verdict (H13 decision D1). "No citation, no answer" stays 100% deterministic.

> ⚠️ **Read this before citing any number.** This is an **advisory divergence/evidence study, NOT an improvement claim.** The Council does not change the verdict by construction (D1), so it *cannot* and does *not* "improve faithfulness/block-rate" — claiming so would violate CLAUDE.md §13/§22.22. The honest "Done when" of H13 is *this study itself* (decisions §H13, mirroring the H10 gate-reframe). Three material limitations — read §Caveats:
> 1. **9/30 (30%) cases skipped** — the uncalibrated Analyst omitted the required `findings` field even after the H8 retry; those cases produced no auditable answer to compare. The divergence numbers are over the **21 summarized** cases, not 30.
> 2. **Groq/Llama judge contaminated on ~6 cases** — Groq's free-tier 100k-TPD cap 429'd the `cost` judge; the H12 controlled fallback substituted GPT-4o-mini, so those panels were Haiku+GPT-4o+GPT-4o-mini (2 OpenAI models, not 3 independent providers). The exact H12 **I-2** risk, recurred.
> 3. **Cost is NOT per-run-measured** — same pipeline gap as H12 (nothing aggregates `CompletionResult.cost_eur`); spend ≈ **~$1.2–1.5** is an approximation, not measured.

## Method

- `scripts/council_eval.py` runs each of the 30 chat gold cases through the **unchanged** chat graph with `council_override=True` (forces the advisory Council on every case so it can be measured; the Analyst stays Sonnet 4.6, no Ragas/judge re-score — only the Council layer is added over the existing pipeline output).
- Per case the Council asks 3 judges to vote `valid|invalid|requires_human_review` on whether the finding citations *support* the assertion (CLAUDE.md §6.4 — the semantic-support check the mechanical Auditor structurally cannot do). `AdvisoryMajorityPolicy` aggregates: ≥2 agree → that verdict; else `requires_human_review`.
- A case is **skipped** (counted, disclosed) when the Analyst raises (no `findings` after retry) or the Council is unavailable — it contributes no row. `n_auto_triggered` is **0 by construction** here because every case is forced via `api_override` (organic RHR/high-severity trigger frequency lives in production observability T10, not this forced study).

## Results (real, measured this run — `evals/reports/latest.council.md`)

| Metric | Value |
|---|---|
| Gold chat cases selected | 30 |
| **Summarized** (Analyst produced an auditable answer) | **21** |
| **Skipped** (Analyst `findings`-omission / council-unavailable) | **9 (30%)** — chat-003/006/008/009/019/022/024/025/028 |
| **Council diverged from mechanical Auditor** | **12 / 21 ≈ 57%** |
| Auditor=`pass` but Council flagged (would escalate) | **1** (chat-11: `pass` → `requires_human_review`) |
| Auto-triggered subset (RHR/high-severity) | 0 (by construction — forced override) |

Per-case (the 21 summarized; full table in `evals/reports/latest.council.md`): the single largest divergence pattern is Auditor=`requires_human_review` → Council=`pass` (**7 of the 12 diverged cases** — rows 4, 6, 9, 12, 16, 18, 21) — the LLM panel is **systematically more lenient** than the mechanical Lenient-strict aggregation on ambiguous cases — plus a few Auditor=`block`/`requires_human_review` → Council=`block` agreements/escalations and the single Auditor=`pass` → Council=`requires_human_review` escalation (chat-11).

## Reading

The decisive finding is the **~57% divergence** between an independent 3-judge LLM panel and the deterministic mechanical Auditor on the summarized cases. The divergence is **directional**: on ambiguous cases the mechanical Lenient-strict Auditor lands on `requires_human_review` while the LLM panel mostly votes `pass` (more lenient), and in exactly **one** case the panel is *stricter* than a mechanical `pass` (chat-11, the §6.4 semantic-support catch the advisory Council was designed to surface). This is precisely the **calibration signal H15 needs**: the deterministic gate and an LLM panel disagree on a majority of ambiguous cases, and the disagreement is mostly the Auditor being conservatively over-cautious (`requires_human_review`) where judges see support. It does **not** demonstrate the Council is "right" or an improvement (advisory, uncalibrated judges — the H12 finding that LLM quality is uniformly low/uncalibrated still holds). It characterizes *where* the mechanical Auditor and LLM judgment part ways, feeding the H15 Auditor-calibration plan and the H15 promotion seam (`MonotonicEscalatePolicy`, built+tested, wired OFF).

## Caveats (honest accounting)

1. **30% Analyst skip rate (the dominant limitation).** 9/30 chat cases produced no auditable answer because Sonnet omitted the required `findings` field even after the built-in H8 one-retry — a documented H11 observation, now quantified as *frequent* (not rare). The 21-case divergence sample is therefore selection-affected (only cases where the Analyst was schema-compliant). This is itself a first-class H15 calibration lever (Analyst prompt v1.1 + schema-adherence — decisions §H10/§H13).
2. **Groq/Llama judge contamination (H12 I-2, recurred — empirical).** Groq free tier = 100k TPD on `llama-3.3-70b-versatile`; it 429'd ~6 times. The H12 controlled one-hop fallback fired (`fallback_triggered=true primary_mode=cost`) → GPT-4o-mini answered in the Llama slot → those ~6 panels were Haiku + GPT-4o + GPT-4o-mini (two OpenAI models), **not 3 independent providers**. The `council_verdict` for those cases is over a less-independent panel. Documented, **not re-run for prettier numbers** (§22.22; the H11/H12 contamination-honesty precedent). A clean re-run needs a paid Groq tier (operational lesson, same as H12 cost_analysis.md).
3. **No per-run-measured cost.** Same pipeline gap as H12 — nothing aggregates the real per-call `CompletionResult.cost_eur`. Spend ≈ ~$1.2–1.5 (Anthropic Sonnet Analyst + Haiku judge, OpenAI GPT-4o judge + GPT-4o-mini fallback, Groq free) is an honest approximation, not measured. Per-call cost capture remains the documented H15 follow-up.
4. **Advisory by construction.** The Council changed **no** verdict. Reproducibility of the deterministic `verdict` (gate §16.2) is intact; `council_*` is explicitly declared non-deterministic advisory evidence. Promotion to a binding monotonic gate is the H15 seam (`_COUNCIL_BINDING=False`, `MonotonicEscalatePolicy` implemented + unit-tested but wired OFF).
5. **n_auto_triggered = 0 by construction.** This forced study cannot measure organic trigger frequency; that is observable in production observability (T10), not here.

## Operational lessons (for any future clean re-run, e.g. post-H15)

- The Analyst's ~30% `findings`-omission rate must drop (H15 prompt calibration) before a divergence study is representative — otherwise ~1/3 of the gold set is silently excluded.
- A 30-case forced Council run exhausts the Groq free 100k-TPD cap (~6 fallbacks) — needs a **paid Groq tier** for an uncontaminated 3-provider panel (same lesson as H12 cost_analysis.md §Operational lessons).
- Capture real per-call cost (`CompletionResult.cost_eur` aggregation) instead of approximating — the standing H15 follow-up first raised in H12.

## References

- Decisions log §H13 (D1–D7, the honest "Done when" reframe, the 3 T13 paid-path defects surfaced by this gated run, this run + its caveats) and §H10 (H15 Auditor-calibration plan).
- ADR 0014 (Council of Judges architecture). Spec: `docs/superpowers/specs/2026-05-17-h13-council-of-judges-design.md`; Plan: `docs/superpowers/plans/2026-05-17-h13-council-of-judges.md`.
- Raw report: `evals/reports/latest.council.md` (tracked as TFM evidence — the `!evals/reports/latest.council.md` .gitignore exception, mirroring the H12 arm reports). Honest-documentation precedent: `docs/cost_analysis.md` (H12 I-2 / contamination pattern).
