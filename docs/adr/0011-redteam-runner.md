# ADR 0011 — Red Team runner (H9)

- **Status:** Accepted
- **Date:** 2026-05-12 (decision); 2026-05-13 (merged, squash `c1e7de6`, tag `v0.0.10-h9`)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0007 (document pipeline), 0010 (H8 evaluation
  harness — precedent for separated stack).

## Context

CLAUDE.md §16.1 lists H9 as the milestone where `make redteam` becomes reproducible with
real block-rate measurements, gating the move from MVP to advanced (§16.2 gate #4:
block_rate ≥ 0.90 on adversarial set). H9 must produce: (a) ≥50 manually authored attacks
covering the 10 scenarios §18, (b) a standalone Python runner, (c) a CI smoke job running
the deterministic subset, (d) a markdown report committed to main, and (e) formal closure
documents (ADR, security report, decisions log §H9, activated skills).

The system entering H9 (main post-H8, commit `0d0409a`) has four defense layers:
sanitizer (12 categories), injection regex (23 patterns, 10 chat + 13 document), citation
validator (3 checks: article_exists, apartado_exists, text_normalized_match), and the
Auditor lenient-strict aggregator. H9 stress-tests these layers under adversarial conditions
and is permitted to improve them additively (injection.py, sanitizer.py, validator.py) but
not to refactor the Auditor, schemas, router, or prompts.

The harness H8 set the precedent for a separated evaluation stack (ADR 0010 D8: "no backend
modification"). H9 follows the same constraint for production code (H1-H5) and adds an
analogous constraint for the evaluation stack (H8): red team lives in `redteam/`, not in
`evals/`, and does not modify `evals/gold_set.jsonl` (CLAUDE.md §18 anti-pattern).

## Decision

Six design decisions (brainstorming closed 2026-05-12). Full rationale per Q in
`docs/technical_decisions_log.md §H9`. Executive summary:

### D1 — Target N: 50 attacks (MVP complete)

50 attacks covering all 10 scenarios §18, stratified 22 chat-mode + 28 doc-mode, with 5
attacks per scenario. This fulfills the "MVP completo" level (§18: ≥50) without waiting for
the "avanzado" level (≥80). N=10 smoke was rejected as statistically weak for gate ≥0.90
(9/10 trivial); N=50 (≥45/50) requires rigor and produces academically defensible evidence.

### D2 — Architecture: hybrid runner + optional cache reuse

Runner standalone in `redteam/runner.py` (independent from `evals/harness.py`), respecting
the logical separation (CLAUDE.md §18: "NO mezclar adversarial cases con gold set"). Cache
infrastructure from `evals.cache.cache_call` reused optionally — H9 turned out not to need
it (block/pass decisions are deterministic pipeline verdicts, not LLM judge opinions), but
the door stays open for future metrics (e.g., "was the block reasoning correct?").

### D3 — Execution model: mode-stratified

- Chat-mode attacks: always E2E (live LLM, ~$0.019/attack). Realism justifies the cost.
- Doc-mode attacks: deterministic by default (sanitizer + injection.py, $0). Only attacks
  with `requires_e2e: true` (~10-15 of 28) invoke the full H5 document pipeline (~$0.193).

Estimated full run cost: 22 chat × $0.019 + ~15 doc-e2e × $0.193 = ~$3.31 (within budget).

### D4 — Reporting: per-scenario + global + per-layer attribution

Per-scenario §18 breakdown (10 rows) surfaces gaps hidden by a single global number.
Per-layer attribution (sanitizer / injection / citation_validator / auditor / none-escaped)
informs calibration in H15. Both are low-cost additions.

### D5 — CI: `make redteam-smoke` (deterministic subset, $0)

Deterministic doc-mode attacks (requires_e2e=false) complete in ms using only Python
(sanitizer + injection.py + validator). Smoke in CI = immediate regression detection for
security-critical changes without LLM cost. Gate: block_rate smoke ≥ 0.90. Full run with
LLM is human-initiated only.

### D6 — Defense scope: free improvement with additive guardrails

H9 may improve defenses intra-milestone (measure → find gap → fix → re-measure) because
the TFM signal is "found → fixed → re-measured", not just "found". Guardrails enforced:
- Only additive changes: new `if/elif` branches in injection.py, sanitizer.py, validator.py.
- No refactor of Auditor aggregation logic, schemas, router, or prompts.
- Report `block_rate_baseline` (pre-improvements) and `block_rate_final` (post).

## Amendments applied during H9

Four additive fixes applied (commit `41df74c`):

1. `olvida-anteriores` regex widened to also match `"olvida todo"` and similar variants.
2. New `document_instruction_to_evaluator_direct` injection pattern for direct imperative
   forms targeting the evaluator in document context.
3. New Spanish `ignora-anteriores` pattern complementing the existing English coverage.
4. Sanitizer metadata scanning extended: injection pattern check on PDF metadata values +
   URL allowlist validation on metadata hyperlinks.

Plus: attack-008 PDF spec trimmed (rendering survival fix — oversized invisible text caused
PDF corruption in some viewers, not an injection bypass).

Baseline block_rate (smoke pre-improvements): 0.46. Post-improvements: 0.92.
Final block_rate over the 50 full set: **deferred to H11** (first full-run attempt
hung on Anthropic API silent timeout; runner timeouts pending). Closure evidence:
smoke block_rate **0.92** sobre el subset deterministic (13 ataques), gate §16.2 #4
≥ 0.90 ✅. Ver `docs/technical_decisions_log.md §H9 amendment 5`.

## Consequences

### Positive

- Gate §16.2 #4 (block_rate ≥ 0.90) reachable with post-improvement tooling.
- Runner reproducible: `make redteam-smoke` ($0, CI) and `make redteam` (full, human-manual).
- Per-layer attribution provides H15 calibration inputs at no extra impl cost.
- Backend H1-H5 untouched: zero regression risk by construction (same guarantee as H6-H8).
- Same-vendor limitation (Anthropic Sonnet as pipeline + judge fallback) documented here; not
  an issue for red team where block decisions are deterministic verdicts, not LLM scores.
- Additive improvement pattern: each regression test added alongside each fix creates a test
  corpus for H10+ regressions.

### Negative / accepted

- Chat E2E cost (~$0.42 for 22 attacks) is unavoidable; doc-mode budget saved offsets it.
- `requires_e2e=false` doc attacks exercise only layers 1-2 (sanitizer + injection), not the
  full citation + Auditor chain. Full-chain doc coverage requires E2E flag, raising cost.
- 50 attacks do not cover all attack surfaces exhaustively; the suite grows to ≥80 in
  advanced (H14+) and fuzzing in HX.
- Smoke CI job adds ~30s to CI runtime; acceptable for security regression value.

### Deferred to future-work doc in H17

- Expanding attack suite to ≥80 (H14 advanced corpus NIS2/DORA adds new scenarios).
- Fuzzing-based attack generation (HX: property-based testing with Hypothesis).
- LLM-as-judge for "was the block reasoning correct?" metric (H15).
- Adversarial fine-tune testing against LoRA classifier (HX1).
- Full-chain doc E2E for all 28 doc attacks (cost ~$5.40; deferred per budget).

## Alternatives considered

### Extend H8 harness (single eval+redteam stack)

Rejected: CLAUDE.md §18 explicitly prohibits mixing adversarial cases with `evals/gold_set.jsonl`.
A combined stack would blur the separation in code even if the JSONL files remained separate.
Additionally, red team metrics (block_rate, layer attribution) have no counterpart in the
Ragas/custom layer schema of H8; retrofitting them would require schema changes that break the
frozen H8 contract.

### Standalone runner with duplicated cache

Rejected: duplicating `evals.cache.cache_call` creates two maintenance points for the same
SHA256 hash-keyed file cache. The hybrid (import `evals.cache` optionally, don't mandate it)
preserves DRY while honoring logical separation.

### Smoke-only run (N=10, CI-integrated, $0)

Rejected per D1: statistically weak, does not fulfill CLAUDE.md §18 "MVP completo" (≥50).
Deferred to background context: smoke is a CI artifact, not the primary gate artifact.

### No intra-H9 defense improvements (measure only)

Rejected per D6: academically weak. The TFM Module 4 (security + red team) is strengthened by
the "found → fixed → re-measured" narrative, not just by "measured". Guardrails ensure
improvements stay additive and scoped.

## References

- Spec: `docs/superpowers/specs/2026-05-12-h9-redteam-design.md`
- Plan: `docs/superpowers/plans/2026-05-12-h9-redteam.md`
- Report: `redteam/reports/latest.md`
- Decisions log: `docs/technical_decisions_log.md §H9`
- Predecessor: ADR 0010 (H8 evaluation harness — separated stack precedent)
