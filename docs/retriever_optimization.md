# Retriever Optimization Study (H15.1)

> Status: H15.1 deliverable. This is an optimization **study**, not a clean win.
> The defended outcome is honest per spec D5: a partial cross-corpus correctness
> result + a documented system-level ceiling + a milestone-consequential
> design-defect disclosure caught post-spend. Every metric below traces to a
> committed report file under `evals/reports/h15/`, cited inline. Where a number
> is not available from a committed artifact it is marked explicitly.

---

## 1. Goal & honest framing

H15.1 is the **user-requested decimal optimization milestone** (no renumber —
precedent H0.1; roadmap decision committed in `5fd2fad`, decisions log §H15.1)
that follows the H15 Auditor calibration study (ADR 0016 /
`docs/auditor_calibration.md`). H15 surfaced the dominant remaining
system-level lever — retriever `context_precision ≈ 0.60 < 0.80` dragging
faithfulness / answer_relevancy / recall — and named retriever re-tuning as the
top post-H15 engineering target (H15 §7.3 follow-up 1).

H15.1 carries **two separable intended contributions**, framed honestly per
§22.22 (calidad real, never metric-gaming):

1. **Correctness fix.** Enable an opt-in `corpus="auto"` path so cross-corpus
   questions (e.g. "how do NIS2 and DORA interact?") structurally *can* retrieve
   and cite from multiple norms. Before H15.1 the retriever could only ground a
   query in one corpus literal, so the H14 gold cross-corpus cases
   (xcorpus-001/002) retrieved 0.00 context under any single-corpus assignment.
2. **Tuning levers.** A `RetrievalConfig` dataclass (`pre_rerank`, `top_k`,
   `purity_threshold`, deterministic `query_normalization`) exposed eval-only
   via `REGULAITOR_RETRIEVAL_CONFIG` — defended either by **measured A/B
   improvement** vs the frozen H15 control, OR by a **documented deeper
   ceiling** (D5: both defend equally; the same honest done-when inherited from
   H15).

Sources: spec
`docs/superpowers/specs/2026-05-19-h15-1-retriever-optimization-design.md`,
companion ADR 0017 (`docs/adr/0017-retriever-cross-corpus-auto.md`,
squash `e283412`, tag `v0.1.6-h15.1`), decisions log `§H15.1`.

This report describes what was **measured**, not what was designed. Where
the measurement diverged from the spec's intent it is disclosed plainly (§4 —
the calibration A/B was structurally invariant to the tuning lever; cand-1 /
cand-2 spend measured LLM-provider noise on the byte-identical explicit-corpus
path).

---

## 2. Architecture recap

The retrieval pipeline has two paths after H15.1:

- **Explicit-corpus path** (today's entire behavior, all callers passing
  `Literal["ai_act","gdpr","nis2","dora"]`). **Byte-identical** to
  `v0.1.5-h15`: single-`norma` `where`-clause, fixed `PRE_RERANK=50`, fixed
  method-param default `top_k=5`, no purity gate. This is the §22.18 / H14
  no-leakage guarantee preserved by construction — and **additionally pinned
  by an asserted regression test** (T6,
  `tests/unit/test_explicit_path_unchanged.py`).
- **Auto path** (`corpus="auto"`, opt-in, additive). Retrieve `pre_rerank`
  candidates across all 4 corpora (language-filtered, no `norma` filter) → the
  same `bge-reranker-v2-m3` cross-encoder rerank as the explicit path → a new,
  deterministic `_apply_purity_gate(reranked_with_norma, threshold, top_k)`
  helper:
  - `share(norma)` = count of that norma's chunks among the top-`top_k`
    reranked / `top_k` (count-based, deterministic — no scores).
  - If `max_share ≥ purity_threshold` → collapse to that norma's chunks
    within `top_k` (no-leakage restored even on the auto path).
  - Else → genuine cross-corpus top-`top_k` (each `RetrievedChunk` already
    carries `.norma` for downstream Auditor per-citation validation).

`RetrievalConfig` is consumed only on the auto path (see §4 — this is the
disclosure). Eval-only override via `REGULAITOR_RETRIEVAL_CONFIG` (analyst-seam
precedent ADR-0013 `REGULAITOR_ROUTER_MODE` /
ADR-0016 `REGULAITOR_ANALYST_PROMPT_VERSION`); production default is
byte-identical to v0.1.5-h15.

The §6 *"no citation, no answer"* invariant
(Auditor + `citation/validator.py`) is **byte-unchanged** in H15.1 and remains
100% intact. Multi-corpus retrieval only widens what the Analyst *can* ground
in; every emitted citation still goes through the full per-chunk validation
chain.

---

## 3. Method

### 3.1 Single variable + frozen control reuse

The **only** variable changed between the H15 baseline and the H15.1 candidates
is the retriever, controlled by `REGULAITOR_RETRIEVAL_CONFIG`. The Analyst
stays H15-frozen v1.2, the Auditor / citation validator / judge / gold set are
all held fixed (except for the two-row gold edit recorded in §3.3 below).

H15.1 branches from `v0.1.5-h15` with no intervening code change, so the H15
evidence reports **are** a clean baseline for the retriever single-variable
A/B; **no paid re-baseline** was run (saves ≈€1.85). The frozen control is the
already-committed:

- `evals/reports/h15/candidate-v1.2.md` (30 calibration chat cases, n=30).
- `evals/reports/h15/holdout-v1.2-chat.md` (14 H14 holdout chat cases, n=14).

### 3.2 Calibration / holdout split (overfitting guard)

- **Calibration set** = the 30 original chat cases (`evals/h15_calibration_ids.txt`,
  chat-001..030 — all explicit-corpus). The `RetrievalConfig` was iterated and
  A/B-measured ONLY here.
- **Holdout** = the 14 H14 cross-corpus chat cases (`evals/h15_holdout_chat_ids.txt`,
  nis2-/dora-/xcorpus-) measured **ONCE** on the frozen H15.1 DEFAULT
  configuration (`REGULAITOR_RETRIEVAL_CONFIG` unset), never iterated on
  (spec D3 overfitting taboo).

### 3.3 Gold edit (T5) — xcorpus-001/002 → `"auto"`

The two H14 cross-corpus gold cases had `corpus_esperado` set to a single
literal at H14 (the structural limitation H15.1 fixes). T5 (commit `299606f`)
edits them to `"auto"` and widens the harness to thread the value end-to-end.
This is the **only** gold-set change; the 30 calibration cases and the 12
non-xcorpus holdout cases are untouched.

### 3.4 Iteration discipline (D4 — carried from H15)

- ≤3 `RetrievalConfig` candidate iterations, USER-GATED probe-first per
  candidate; controller runs paid eval jobs as persistent background processes
  (H14 operational lesson).
- T8.2 (probe, n=3, cand-1): clean pipeline de-risk before any 30-case spend.
- T8.3 + T8.4: two opposing 30-case candidates (cand-1 widens, cand-2
  narrows — see §5) measured against the H15 frozen control.
- T9: single holdout measurement on DEFAULT (no env override) — frozen
  byte-identical-to-production configuration; verifies regression-zero on the
  12 explicit-corpus cases + measures the auto-path per-case on the 2 xcorpus
  cases.

### 3.5 The asserted explicit-path-unchanged guarantee (T6)

`tests/unit/test_explicit_path_unchanged.py` (commit `0b2af8e` + docstring
honesty fix `f47234f`) **asserts** the explicit-corpus where-clause is
byte-identical to v0.1.5-h15 (`norma = '{corpus}' AND language = '{language}'`,
`limit(PRE_RERANK)`, `top_n=top_k`, empty-guard). This pins the §22.18 / H14
no-leakage guarantee structurally + by assertion, and underwrites the
"regression-zero by construction on the 12 holdout explicit cases" claim in
§6.

---

## 4. The milestone-consequential design defect (§22.22 disclosure)

**This is the section the milestone is defended by, post-spend.** It must be
read in full; softening it would be a §22.22 violation.

### 4.1 Definitive grep evidence

Reading the committed source (HEAD this milestone):

- `DEFAULT_CONFIG` (and therefore any `REGULAITOR_RETRIEVAL_CONFIG` override of
  it) is consumed in **exactly 2 places**, both **auto-path-only**:
  - `src/regulaitor/agents/retriever.py:33` — used inside the
    `corpus == "auto"` branch.
  - `src/regulaitor/mcp_server/tools.py:43` — used inside
    `search_articles(corpus="auto")`.
- The **explicit-corpus path** (`src/regulaitor/agents/retriever.py:35`) calls
  `rag_retrieval.run(query, corpus, language, top_k=top_k)` with the method
  default `top_k=5`. `rag_retrieval.run()` uses the module constant
  `PRE_RERANK=50`. **Neither consults `DEFAULT_CONFIG`.** This is correct: it
  is exactly what the T6 asserted regression test pins as the §22.18 / H14
  byte-identical guarantee.
- The 30 calibration cases (`evals/h15_calibration_ids.txt`,
  chat-001..030) are **all explicit-corpus** (no `"auto"` entries). xcorpus-001/002
  live in the 14-case holdout (`evals/h15_holdout_chat_ids.txt`), where T5 set
  them to `"auto"`.

### 4.2 The consequence

The `REGULAITOR_RETRIEVAL_CONFIG` env override has **zero mechanism** to
affect the 30 calibration measurement. The cand-1 and cand-2 30-case runs both
exercised the byte-identical explicit-corpus path on every case. The deltas
reported in §5.1 between cand-1 / cand-2 and the H15 frozen control are
therefore **LLM-provider non-determinism across multi-hour Sonnet runs, NOT a
real tuning-lever signal.** €3.01 of measured noise on the explicit path
(€1.48 cand-1 + €1.53 cand-2).

### 4.3 Mutual exclusivity surfaced

The no-leakage byte-identical guarantee (T6, §22.18) and the spec §4 intent
("A/B-measure `RetrievalConfig` on the calibration set") are **mutually
exclusive as designed**: if the explicit path is byte-identical, then any
calibration set built of explicit-corpus cases is structurally incapable of
exercising the lever. The spec's measurement plan is **incoherent** with the
no-leakage guarantee it (correctly) requires.

The per-task two-stage reviews validated per-task code correctness (all tasks
correct, including the eval-seam safety-critical fix in §4.5 below) but did
**not** check cross-task design coherence: "does the planned 30-case A/B
exercise the lever it claims to measure?" That gap is the milestone-consequential
process finding.

### 4.4 §22.22 framing

This is the H15.1 milestone-consequential finding. It is exactly the lineage
of the C1 amendment in ADR-0016 / `docs/auditor_calibration.md` §1.1 (which
caught a measurement flaw before spend) and the H14 gold-corpus-ground defect
(caught in 2-stage review post-implementation): a post-implementation honest
disclosure of a defect the per-task discipline missed, owned in the
defense rather than papered over.

It does **not** invalidate the cross-corpus correctness implementation: the
auto path + purity gate is code-correct, unit-tested, asserted no-leakage on
the explicit path (T6), and partially demonstrated at holdout per-case (§5).

The H15.2 future milestone is scoped for the eval redesign (§9 follow-up 1,
user-approved framing).

### 4.5 The pre-spend safety catch (the strength to name)

The same per-task two-stage review discipline that missed the cross-task
design coherence problem **also** caught — pre-spend — a paid-run crash hole
in T8.1 that would have crashed a paid run mid-spend if shipped: the
`REGULAITOR_RETRIEVAL_CONFIG` env contract claimed "never crash on bad input",
but Python dataclasses do not enforce field types, so a typo like
`{"purity_threshold":"0.7"}` would have crashed the override mid-run. Fix:
commit `1e5d82f`, annotation-only extension of
`src/regulaitor/rag/retrieval.py` `RetrievalConfig.__post_init__` type guards.
This is the discipline working as intended at the per-task level.

### 4.6 The cand-2 `citation_recall_mean = 0.81` — same-mechanism caveat

For completeness and §22.22 predictive consistency: the cand-2 30-case run
reports `citation_recall_mean = 0.81 ✅` (`evals/reports/h15/h15_1-cand2.md`,
line 15, commit `a8c36f6`), nominally crossing the §17 ≥0.80 advanced
objective. Per §4 this is the **same LLM-provider non-determinism on the
byte-identical explicit-corpus path** — the `REGULAITOR_RETRIEVAL_CONFIG`
lever has zero mechanism to affect citation_recall on the 30 explicit-corpus
cases (`DEFAULT_CONFIG` is consumed only in the 2 auto-path sites; the
explicit `run()` uses fixed `PRE_RERANK=50, top_k=5`). The number is
documented here for traceability against the committed evidence; it is
**NOT claimed as an H15.1 tuning-lever attainment**. The same disclosure
framing classifies it as noise, not as a §17 attainment.

---

## 5. Cross-corpus correctness results (the real H15.1 measurement)

The two xcorpus cases (n=2) are the only cases in this milestone that
exercise the auto path. They are reported **per-case, NOT folded into the
aggregate** (the same H15 6-RHR-designated-cases discipline). Source:
`evals/reports/h15/h15_1-holdout.md` (commit `a8c36f6`) per-case appendix, vs
`evals/reports/h15/holdout-v1.2-chat.md` baseline per-case appendix.

### 5.1 xcorpus-001 — partial WIN

Question type: DORA-entity → also NIS2-notify? The expected answer requires
DORA art 1 + art 47 + the DORA↔NIS2 relationship.

| | H15 baseline (`corpus="dora"`, single) | H15.1 (`corpus="auto"`) |
|---|---|---|
| Verdict | `pass` (expected `requires_human_review`) ❌ | **`requires_human_review` ✅ FIXED — matches expected** |
| Citations emitted | `['19.1','19.2']` (DORA incident-notif arts — wrong) | `['4.1','4.2','4.3']` (NIS2 art 4 — the lex-specialis mechanism — *correct legal framework*, not the specific DORA 1/47 the gold expected) |
| context_precision | 0.00 | **1.00** (auto retrieval surfaces high-quality cross-corpus context) |
| context_recall | 0.00 | 0.00 (specific expected articles still not retrieved) |
| faithfulness | 0.67 | 0.70 |
| LLM-judge criteria (4 total) | 1/4 ✅ | **2/4 ✅** (the "describes DORA↔NIS2 relationship corpus-fiel" criterion still ✅; the "remits to human review" criterion now ✅ thanks to the verdict fix; the two specific-article-citation criteria still ❌) |

**Honest per-case read.** Partial win: the verdict mismatch is fixed
(pass → requires_human_review, matching the gold), `context_precision` jumps
0.00 → 1.00, and one additional judge criterion flips ❌ → ✅. The auto path
surfaces the correct legal framework (NIS2 art 4 lex-specialis) but does not
retrieve the specific DORA art 1 / art 47 articles the gold expected. This is
a real, modest contribution.

### 5.2 xcorpus-002 — mixed, with verdict REGRESSION

Question type: NIS2 operator + personal data breach → also GDPR? The expected
answer requires NIS2 art 23 + art 35 + GDPR art 33.

| | H15 baseline (`corpus="nis2"`, single) | H15.1 (`corpus="auto"`) |
|---|---|---|
| Verdict | **`requires_human_review` ✅ (matches expected)** | **`block` ❌ REGRESSED — worse mismatch than RHR=RHR** |
| Citations emitted | `['23.1','23.4']` | `['23.1','23.4']` (same — auto did NOT surface NIS2 art 35 nor GDPR art 33) |
| context_precision | 0.00 | 0.00 |
| context_recall | 0.00 | 0.00 |
| faithfulness | 0.43 | 0.62 (up) |
| LLM-judge criteria (3 total) | 1/3 ✅ | 1/3 ✅ (unchanged) |

**Honest per-case read.** No correctness win: the auto path did **not** help
this specific cross-corpus question. The reranker did not surface the
second-corpus articles (NIS2 art 35 nor GDPR art 33); the citations emitted are
identical to baseline; and the verdict **regressed** RHR → block (the gold
expects RHR; pass and block are both misses, but the H15 baseline was already
correct here). faithfulness rose 0.43 → 0.62 but on the same flawed citation
set. The post-rerank purity gate's threshold (0.6 default) interacting with
this specific NIS2+GDPR cross-corpus question + the reranker's passage-level
ranking on it is the open question.

### 5.3 Aggregate honest read

**1/2 partial win, 1/2 mixed-with-verdict-regression.** Defended-by-correctness-
per-case, NOT by aggregate. The H15.1 cross-corpus contribution is real and
modest; it is not a clean win. The H15-style discipline of reporting per-case
on the designated-N subset (here N=2, the only cases that exercise the lever)
is what makes this honest.

---

## 6. Holdout aggregate (12 non-xcorpus explicit cases) — code-path-identical; deltas are LLM-noise

The 14-case holdout aggregates reported by `evals/reports/h15/h15_1-holdout.md`
(commit `a8c36f6`, n=14, DEFAULT `REGULAITOR_RETRIEVAL_CONFIG`, cost €0.75)
include the 12 non-xcorpus cases that go through the **byte-identical
explicit-corpus path**. They are regression-zero **by construction** (T6
asserted) — the small aggregate deltas vs the H15 holdout
(`holdout-v1.2-chat.md`, n=14, cost €0.78) are the same LLM-provider
non-determinism mechanism documented in §4.

`ab_delta` (computed via `scripts.h15_ab_compare.ab_delta`, NOT hand-computed):

| metric | H15 holdout (n=14) | H15.1 holdout (n=14) | Δ |
|---|---|---|---|
| faithfulness_mean | 0.660 | 0.710 | +0.050 |
| answer_relevancy_mean | 0.660 | 0.670 | +0.010 |
| context_precision_mean | 0.620 | 0.660 | +0.040 |
| context_recall_mean | 0.420 | 0.450 | +0.030 |
| citation_precision_mean | 0.000 | 0.000 | +0.000 |
| citation_recall_mean | 0.000 | 0.000 | +0.000 |
| verdict_match_rate [¹] | 0.430 | 0.360 | −0.070 |
| severity_match_rate | 0.670 | 0.750 | +0.080 |
| cost_per_chat_eur | 0.055 | 0.053 | −0.002 |
| cost_total_eur | 0.78 | 0.75 | −0.03 |

[¹] verdict_match_rate −0.070 is the largest swing in this table; per §4 the 12 non-xcorpus holdout cases use the same byte-identical explicit-corpus code path as the H15 baseline, so this delta is the same LLM-provider non-determinism mechanism (NOT a regression on a real signal). The 2 xcorpus cases (auto path) are reported per-case in §5, not folded into this aggregate.

**Honest read.** The byte-identical explicit-corpus path makes these deltas
LLM-noise by construction, not a real H15.1 effect. The verdict_match −0.070
is the largest swing and would warrant attention *if* it were a real signal;
it is the same noise mechanism that produced the €3.01 of calibration noise in
§4. The `citation_precision`/`citation_recall` 0.000 → 0.000 are the H14
article-level gold-granularity confound carried from H15 §5.1 / ADR-0016
(documented-not-fixed; see §9 follow-up 2).

---

## 7. HARD-revert check / safety non-regression (D5)

The D5 HARD reverts are checked individually; **none fires**, so v0.1.5-h15 +
the auto path stay.

### 7.1 citation_recall floor (§16.2#5)

- The 30-calibration H15 baseline (`candidate-v1.2.md`) had
  `citation_recall_mean = 0.71` and the §16.2#5 MVP floor is ≥0.40 — PASS.
- The 14-holdout `citation_recall_mean = 0.00` on H15.1 = `0.00` on H15 —
  no regression; the 0.00 itself is the H14 article-level gold-granularity
  confound documented in ADR-0016 / `docs/auditor_calibration.md` §5.1 and
  carried in §6 above. **NOT a regression.**

### 7.2 Explicit-path byte-identical (§22.18 / H14)

T6's `tests/unit/test_explicit_path_unchanged.py` asserts the where-clause
exactly. The 12 non-xcorpus holdout cases go through this code path → §6
deltas are LLM-noise by construction, not a behavior change. **NOT a
regression.**

### 7.3 redteam-smoke `block_rate` (§16.2#4)

T6 re-confirmed redteam-smoke `block_rate = 0.92` on this branch — exactly
the H15 frozen value, exactly the §16.2#4 ≥0.90 gate. redteam-smoke is
**prompt-blind** (sanitizer / injection layers only — no LLM, no retriever),
so by construction it is identical for v0.1.5-h15 and H15.1 (the same
ADR-0016 §6.1 reasoning applies). **NOT a regression.**

### 7.4 The 6 H15-designated block cases (C1 content-safety carry-forward)

chat-014 / chat-015 / chat-029 / chat-030 (in calibration) +
nis2-006 / dora-006 (in holdout): all on the explicit-corpus path, which is
byte-identical (T6). The C1 content-based safety determination from ADR-0016
§6.3 is carried forward by code-path equivalence; not re-litigated in this
milestone. **NOT a regression.**

### 7.5 Verdict

None of the four HARD reverts fires. v0.1.5-h15 + the auto path + the new
`RetrievalConfig` seam stay.

---

## 8. Honest interpretation & verdict

The D5 honest done-when is: measured improvement (per-case xcorpus-001
partial — §5.1) **OR** documented deeper system-level ceiling (yes — the
tuning lever is empirically un-measurable at meaningful sample size with the
current calibration set design, §4). Both defend equally per spec D5; the
H15.1 contribution is real but modest.

The defended H15.1 outcome is:

1. **Cross-corpus correctness: 1/2 partial win, 1/2 mixed-with-regression.**
   xcorpus-001 verdict-fixed + context_precision 0.00 → 1.00 + one extra judge
   criterion ✅ (correct legal framework cited; specific expected articles
   still not retrieved). xcorpus-002 verdict regressed RHR → block; same
   citations as baseline; auto path did not help this question.
2. **Tuning levers: empirically un-measurable at N=30 with the current
   calibration set.** The §4 design defect (DEFAULT_CONFIG auto-path-only +
   30-calibration all explicit-corpus) makes the cand-1/cand-2 vs control
   deltas LLM-provider non-determinism, not signal. The €3.01 spent on cand-1
   + cand-2 is documented as measurement of noise, not as a tuning result.
3. **Documented deeper system-level ceiling persists.** Faithfulness still
   < 0.85 (§17 objective), verdict_match still far from 0.85 — the
   H12 / H13 / H14 / H15 system-level-ceiling thesis is reinforced; the
   retriever is not the *only* remaining lever.

The milestone's strongest TFM-defense honesty points are:

- **The post-spend design-defect disclosure (§4).** A measurement
  incoherence between the no-leakage byte-identical guarantee (correct, T6
  asserted) and the spec's calibration-set A/B intent (incoherent against the
  no-leakage guarantee), missed by per-task two-stage reviews and surfaced in
  the closure write-up. C1 / H14-gold-corpus-ground lineage.
- **The pre-spend safety catch (§4.5).** The same per-task two-stage review
  discipline caught a paid-run crash hole in T8.1 (env override never-crash
  contract was weaker than claimed) **before any paid spend** — discipline
  working as intended at the per-task level.
- **The cross-milestone gate-hygiene cleanup (T4).** The same per-task
  two-stage review discipline that surfaced the §4 design-defect
  post-implementation also surfaced inherited annotation debt across H13-H15
  that hides behind `pytest -m "not slow"` (the `mypy src` strict gate was
  silently red since H13's `db991dc`, surfaced and fixed annotation-only in
  T4, see `src/regulaitor/agents/council.py` `_JUDGE_MODES` / `_one_judge`
  typing). Both findings are products of writing this milestone, not of a
  side-quest — they demonstrate the cumulative value of the review discipline
  rather than asserting it.

**No promised metric number** (per D5). The H15.1 contribution is the
auto-path implementation (code-correct, no-leakage-preserving, unit-tested,
asserted-regression-zero on the explicit path) + the partial xcorpus-001
correctness result + the documented design-defect disclosure that scopes the
H15.2 future milestone.

---

## 9. Real measured cost

Real per-run measured spend, read from each report's `Total cost:` header
line via the H15 router accumulator
(`models/router.py` `_record_cost_eur` / `get_accumulated_cost_eur`, commit
`1726ad0`, the same instrument used in H15):

| run | n | config | cost (€) | source report |
|---|---|---|---|---|
| T8.2 probe | 3 | cand-1 (`pre_rerank=80, top_k=8`) | 0.16 | `evals/reports/h15/h15_1-cand1-probe.md` |
| T8.3 cand-1 full | 30 | cand-1 (`pre_rerank=80, top_k=8`) | 1.48 | `evals/reports/h15/h15_1-cand1.md` |
| T8.4 cand-2 full | 30 | cand-2 (`pre_rerank=80, top_k=3` — opposite hypothesis) | 1.53 | `evals/reports/h15/h15_1-cand2.md` |
| T9 holdout | 14 | DEFAULT (env unset) | 0.75 | `evals/reports/h15/h15_1-holdout.md` |
| **Total** | — | — | **≈ 3.92** | of the ≈€7.5 envelope (≈$8 ceiling, ADR-0016 precedent) |

Smaller than H15's ≈€5.05 because **no paid re-baseline was run** in H15.1
(the committed H15 evidence is the frozen control directly — saved ≈€1.85).
All figures are real per-run measured spend, not estimated (the H12 / H13
estimate-not-measured gap remains closed by the router accumulator H15 added).

§4 honestly classifies the cand-1 + cand-2 €3.01 as measurement of LLM-provider
non-determinism on the explicit path (the lever the env override claimed to
move is auto-path-only; the 30 calibration cases are all explicit-corpus),
NOT as a tuning-lever measurement.

---

## 10. Caveats & deferred follow-ups

1. **H15.2 future milestone — eval redesign for tuning-lever measurability**
   (user-approved framing arrived POST-SPEND once §4 surfaced — NOT a
   pre-existing scope split. The H15.2 redesign is a clean engineering deferral
   of the eval rede-design (extend gold with auto-path cases at N significant,
   OR introduce metrics that measure the explicit-path behavior without
   violating the no-leakage byte-identical guarantee — research question for
   that milestone). Decimal-milestone naming precedent: H0.1 + H15.1 itself.)
   The §4 design defect must be resolved before any further paid A/B
   on the `RetrievalConfig` levers is meaningful. T11 closure sets
   `Hito siguiente = H15.2`.
2. **Citation-metric granularity confound** (carried from ADR-0016 /
   `docs/auditor_calibration.md` §5.1 / H15 §7.3 follow-up 5). The deterministic
   metric does an exact `articulo.apartado` string match; the H14 cases were
   authored with article-level `expected_articles` (`['23']`, `['6']`) whereas
   the Analyst (correctly) emits apartado-level citations (`23.4`,
   `6.1`) — systematic 0.00 on the H14 holdout shape, persisting on the
   xcorpus expected-articles in this milestone (§6 row, §5.1/5.2 0.00s).
   Documented-not-fixed; eval-instrument quality, NOT system optimization;
   lower priority than the §4 redesign; changing the metric or the gold
   convention would require a full A/B re-baseline.
3. **xcorpus-002 verdict regression (open question).** The auto path with
   default `purity_threshold=0.6` did not surface NIS2 art 35 nor GDPR art 33
   for this specific question; the verdict regressed RHR → block on a case the
   H15 baseline got right. Per-case documented (§5.2); merits investigation
   alongside the H15.2 eval redesign — the question is whether the
   threshold default + reranker passage-level behavior on multi-corpus
   personal-data-breach questions wants tuning, or whether this case needs a
   different intervention (e.g. explicit second-corpus query expansion, which
   is out of scope for H15.1 D2).
4. **LLM-judge same-provider-family limitation** (Haiku 4.5 judge vs Sonnet
   production, ADR-0010 carried). Unchanged in H15.1; deferred to a future
   router-multi-LLM judge.
5. **`mypy src` cross-milestone gate-hygiene** (T4 finding). Surfaced + fixed
   in T4 annotation-only; recorded here as honest cleanup. The wider question
   of which gates run in CI and which run only locally is a separate hardening
   item, not in H15.1 scope.

---

*All metrics in this document trace to a committed report under
`evals/reports/h15/` (force-added evidence in commit `a8c36f6`) or to a
committed commit body, cited inline. No number is invented; §4 discloses every
place where the delivered measurement diverges from the spec's intent. The
literal `<squash-sha>` placeholder is preserved where it appears in the
companion ADR-0017 / decisions log §H15.1 / closure docs (filled post-merge by
the controller).*
