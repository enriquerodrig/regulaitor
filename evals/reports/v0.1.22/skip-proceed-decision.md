# v0.1.22 SKIP/PROCEED Gate Decision

**Date:** 2026-05-25
**Spec ref:** docs/superpowers/specs/2026-05-24-v0.1.22-paid-validation-design.md §D3
**Authoritative:** YES (mandatory pre-flight gate before T3 main run)

## Probe history (3 prior attempts $0 — diagnostics, not data)

Per §22.22 honest framing for ADR-0029 — see preserved evidence files in
`evals/reports/v0.1.22/probe-attempt-{1,2,3}*.md` and corresponding checkpoints
in `evals/checkpoints/*-{ssl-failed,ssl-anthropic-failed,capa-a-schema-bug}.jsonl`:

| Attempt | Issue | Cost |
|---|---|---|
| 1 (truststore absent) | Windows CryptoAPI CRL revocation block on HF + Anthropic SSL | $0 (failed pre-API) |
| 2 (HF_HUB_OFFLINE only) | HF fixed, Anthropic SSL still blocked | $0 (failed pre-API) |
| 3 (truststore.inject + HF_HUB_OFFLINE) | SSL fixed, but Anthropic `400 invalid_request_error: tools.0.custom: For 'object' type, additionalProperties must be explicitly set to false` — v0.1.21 Capa A bug (root-only setter; nested $defs untouched) | $0 (failed pre-tool-use) |
| 4 (above + recursive setter fix) | **All systems functional; first real measurement** | €0.32 spent |

The 3 failed attempts revealed:
- (a) Windows CryptoAPI CRL revocation block prevents Python httpx HTTPS calls — fixed via `truststore.inject_into_ssl()` in `scripts/v0122_run.py` (uses Windows native trust store, same path as Edge/Chrome browser).
- (b) v0.1.21 ships a broken Capa A: `_strip_unsupported_schema_fields` set `additionalProperties: false` on the schema root only; Anthropic strict mode requires it on every object-typed subschema (including `$defs.Finding`, `$defs.Citation`). Production state was 100% RHR for chat requests for ~12 hours post-v0.1.21 merge (broken-fail-safe per §6 invariant — empty answers → RHR → no fabrication). **Fixed in v0.1.22 via recursive walker** (`_set_additional_properties_false_recursive`) in `src/regulaitor/agents/analyst.py`; 3 new regression-guard tests in `tests/unit/agents/test_analyst.py`.

§22.22 spec amendment: v0.1.22 spec said "ZERO backend touch" — reality discovered the Capa A bug DURING probe; fixing it inside v0.1.22 is the §22.22-honest path (vs ship-broken-measurement). src/ scope now = 1 file (`agents/analyst.py`) + 1 script (`scripts/v0122_run.py` for truststore inject). ADR-0029 §22.22 will document this amendment.

## Probe attempt 4 measurements (T1)

| Metric | Value |
|---|---|
| Cases run | 5 (chat-001..005, deterministic H10 subset) |
| Total cost (EUR) | €0.32 |
| Total cost (USD ~) | $0.34 |
| Per-case mean (EUR) | €0.064 |
| Per-case mean (USD ~) | $0.069 |
| Crashes | 0 |
| Per-case latency mean | ~352s (~5.9 min/case; consistent with Capa C 3-attempt retries + Council + Judge) |
| per_citation_audits populated | Verified yes via v0.1.21.1 D2 trail |
| Verdict mix | 3 pass / 2 RHR (vs all-RHR in broken probe attempts) |
| Cache hits/misses | 0/5 (all fresh judge calls; +5 cache entries 501→506) |

**v0.1.20-bar passes on probe (7/7)** — all 7 metrics beat the bar by meaningful margins:
- faithfulness 0.97 (bar 0.65, +0.32)
- answer_relevancy 0.87 (bar 0.55, +0.32)
- context_precision 0.77 (bar 0.55, +0.22)
- citation_precision 0.28 (bar 0.25, +0.03)
- citation_recall 0.70 (bar 0.60, +0.10)
- verdict_match 0.60 (bar 0.35, +0.25)
- severity_match 0.40 (bar 0.35, +0.05)

**Cost-per-chat €0.063 over soft bar €0.05** (+0.013) — Capa C 3-attempt retry inflates per-call cost; documented expectation per ADR-0027 D4. Not a blocker for main run.

NOTE: probe N=5 is insufficient for production-default flip decision per
cost-estimation discipline (memory `feedback_cost_estimation_discipline.md`,
N=5 is the MINIMUM, not statistically robust). Decision is conditional on
T3 main 25 cases consistent with probe pattern.

## Extrapolation

```
total_expected = €0.064 × 30 = €1.92 = ~$2.07 USD
total_high     = total_expected × 1.5 = €2.88 = ~$3.10 USD
ad-hoc safety  = 2 × €0.064 = €0.13 = ~$0.14 USD
T3 total high  = €3.01 = ~$3.24 USD
```

## Budget gate

- User budget remaining (Anthropic console 2026-05-24): **~$13.00 USD**
- v0.1.22 spent so far (probes 1-3 $0 + probe-4 €0.32 + direct test calls ~$0.007): **~$0.35 USD**
- Remaining post-probes: **~$12.65 USD**
- T3 total_high USD: **~$3.24 USD**
- Headroom post-T3 worst case: **~$9.41 USD** (~73% headroom)
- Gate: total_high ≤ budget — **PASS** (well below)

## Decision

**PROCEED to T3 main run (25 H10 cases + 2 ad-hoc safety = 27 paid calls)**

Rationale:
1. Budget headroom comfortable (~73% post-T3 worst case).
2. Probe metrics (7/7 v0.1.20-bar PASS) indicate cumulative package WORKS post-fix.
3. Probe verdict mix (3 pass / 2 RHR) is realistic distribution (not all-fail anymore).
4. Per-citation audit trail populated → T5 mechanism diagnostic enabled.
5. Spec amendment to fix Capa A is justified by §22.22 honest framing + 3 regression-guard tests added.

Carry-forwards documented for ADR-0029 §22.22:
- truststore not yet in pyproject.toml (carry-forward to v0.1.22.1 infra hotfix OR add at H16)
- Capa A bug latent in production v0.1.21-v0.1.21.3 (~12h window) — broken-fail-safe (no §6 violation; all RHR is conservative)
- Cost-per-chat over soft bar (+€0.013/case) due to Capa C retry overhead
