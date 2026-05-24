# ADR 0028 — Tier 2 retrieval defaults flip + chat refusal mock (v0.1.21.2)

- **Status:** Accepted — 2026-05-24 — squash `6552d1c`, tag `v0.1.21.2-tier2-flips`
- **Deciders:** Project owner.
- **Companion ADRs:** 0017 (H15.1 retriever optimization — original per-norma cap motivation; v0.1.11 BREAKTHROUGH 1/3 → 2/3 cross-corpus demonstration), 0018 (H15.2 eval rede-design — top_k_auto wiring algorithmically verified through the `RetrievalConfig` per-call resolution path), 0026 (v0.1.20 paid validation framework — the venue where the cumulative effect of v0.1.21.2 retrieval defaults will be measured), 0027 (v0.1.21 Tier 1 quorum + Tier 2 Capa A+B+C + v1.5 prompt — production state into which v0.1.21.2 lands).

## Context

Two retrieval capabilities have been **opt-in since their shipment** without paid validation pre-flip:

- `RetrievalConfig.max_chunks_per_norma` (v0.1.11, squash `107479d`): mechanically demonstrated cross-corpus 1/3 → 2/3 expected-article surfacing on xcorpus-002 diagnostic (boundary math: cap=2 forces sub-purity-threshold share which routes through the multi-corpus branch; cap=3 stays boundary-inclusive and still collapses). Previously default `None` (no cap = v0.1.10 behaviour).
- `RetrievalConfig.top_k_auto` (v0.1.12, squash `64c6eac`): wiring algorithmically verified via 9 unit tests with mocked rerank. Empirical xcorpus-002 measurement was deferred per the §v0.1.12 local-CPU rerank time-budget realization. Applies only to `corpus="auto"` queries (subset of production traffic). Previously default `None` (use `cfg.top_k` for auto = v0.1.11 behaviour).

**§6 invariant interpretive distinction** (carried verbatim from ADR-0024 / 0025 / 0026 / 0027): the production-side citation VALIDATION (`src/regulaitor/citation/validator.py`) is **byte-unchanged**. v0.1.21.2 modifies retrieval-config defaults — upstream of the validator, downstream of the corpus. The Auditor aggregation (`agents/auditor.py`, post-v0.1.21 Tier 1 quorum) and the Pydantic schema (`citation/schemas.py`, post-v0.1.21 Capa B `min_length=1`) are byte-unchanged. The "no citation, no answer" guarantee continues to operate entirely on the validator + Auditor layers.

**v0.1.21 final-review I5 caveat** motivates D3: the deterministic redteam-smoke gate (block_rate 0.92 carry since v0.1.14) filters its corpus to doc-mode cases only. Chat-mode adversarial behavior under the post-v0.1.21 production stack (v1.5 Analyst prompt + Capa A strict-mode + Capa B Pydantic min_length=1 + Capa C aggressive retry) was **unmeasured**. This was acknowledged at v0.1.21 closure as a follow-up; v0.1.21.2 closes it at $0 via mock-based e2e tests.

**v0.1.22 paid run** (CONDITIONAL, ~€4-6 30-case A/B) is the venue where the cumulative effect of (v0.1.21 Tier 1 quorum + Tier 2 Capa A+B+C + v1.5 + v0.1.21.2 retrieval defaults) is measured against the v0.1.20-bar metrics (ADR-0021). The v0.1.21.2 flips themselves are NOT measured in isolation.

## Decision

### D1 — Flip `max_chunks_per_norma=2` to production default

Modify `src/regulaitor/rag/retrieval.py:63`:

```python
# BEFORE (v0.1.11):
max_chunks_per_norma: int | None = None  # None == no cap == v0.1.10 behaviour

# AFTER (v0.1.21.2):
max_chunks_per_norma: int | None = 2  # default cap=2 per v0.1.11 BREAKTHROUGH cross-corpus 1/3->2/3; opt-out via RetrievalConfig(max_chunks_per_norma=None) restores v0.1.10 behaviour
```

**Rationale**: v0.1.11 mechanically demonstrated the BREAKTHROUGH on cross-corpus retrieval. The "future product foundation" preference (per project memory) argues for production having the best-evidence configuration as default rather than requiring callers to discover the opt-in.

**Backward-compat**: pre-existing callers that explicitly construct `RetrievalConfig(max_chunks_per_norma=None)` opt back into v0.1.10 behaviour. Callers constructing `RetrievalConfig()` with no args now get `cap=2` (previously `None`); this is intentional.

### D2 — Flip `top_k_auto=12` to production default

Modify `src/regulaitor/rag/retrieval.py:64`:

```python
# BEFORE (v0.1.12):
top_k_auto: int | None = None  # None == use cfg.top_k for auto == v0.1.11 behaviour

# AFTER (v0.1.21.2):
top_k_auto: int | None = 12  # v0.1.21.2; default top_k for auto-corpus queries; opt-out via RetrievalConfig(top_k_auto=None) restores cfg.top_k usage
```

**Rationale**: v0.1.12 spec'd 12 as the default (twice the default `top_k=5` with purity-gate margin); no paid measurement determined an empirically optimal value, so 12 stands as the spec'd default. The field applies only to `corpus="auto"` queries per the v0.1.12 wiring (explicit-corpus paths ignore it; T6 byte-identical guarantee preserved per ADR-0018).

**Backward-compat**: only `corpus="auto"` queries are affected. Explicit-corpus production traffic (the majority) is byte-unchanged.

### D3 — Chat refusal mock e2e tests

NEW `tests/unit/redteam/test_chat_refusal_mock.py` (6 tests) covering adversarial chat-mode scenarios. The chat pipeline (Retriever + Analyst + Auditor) is mocked end-to-end with fabricated Sonnet responses; verifies the v1.5 Finding-based refusal flow + Capa A+B+C handling are correctly integrated.

Scenarios covered: ask-to-fabricate-citation, ask-for-definitive-legal-advice, prompt-injection variants, ask-about-nonexistent-article, edge-case mock returning empty findings (Capa B rejects → Capa C retry → eventual valid or `RuntimeError`).

All mocks; $0; no API calls. Closes the v0.1.21 final-review I5 caveat at zero cost; surfaces interaction bugs before the v0.1.22 paid run.

## Results

**T1-T4 shipped** (all three items implemented + unit-tested):

- T1 `7130235` TDD red — new tests (~13 new across 4 files: 7 retrieval defaults + 6 chat refusal mock).
- T2 `20d0fa8` GREEN D1 — flipped `max_chunks_per_norma=2` + 2 pre-existing test sites updated.
- T3 `8723537` GREEN D2 — flipped `top_k_auto=12` + 2 pre-existing test sites updated.
- T4 `f88c608` GREEN D3 — chat refusal mock e2e tests verified.
- cleanup `eb954e8` — black/ruff formatting normalization on T1-T4 test files.
- T5 (this ADR) — ADR-0028 written.
- T6 — closure docs (decisions_log §v0.1.21.2 + evidence_matrix + CLAUDE.md §16.3 + §27).
- T-final — squash + tag ceremony populates Status-line squash-sha.

**Gate authoritative**: `uv run pytest -m "not slow"` → **968 passed / 0 failed / 1 skipped** (was 955 baseline at v0.1.21.1 close; +13 net from T1 new tests).

**mypy strict**: **71 source files Success UNCHANGED** (1 src/ file modified: `rag/retrieval.py` 2 lines; no new `.py` under `src/`).

**5 HARD git-diff invariants empty**:

- `src/regulaitor/citation/validator.py` byte-unchanged
- `src/regulaitor/citation/schemas.py` byte-unchanged (v0.1.21 Capa B `min_length=1` carried)
- `src/regulaitor/agents/auditor.py` byte-unchanged (v0.1.21 Tier 1 quorum carried)
- `src/regulaitor/agents/council.py` byte-unchanged (v0.1.19 binding ON carried)
- `src/regulaitor/agents/prompts/analyst/` byte-unchanged (v1.0-v1.5 carried)
- `evals/gold_set.jsonl` byte-unchanged

**redteam-smoke**: 0.92 carry (= v0.1.14-v0.1.21.1 frozen; retrieval-config defaults do NOT affect the deterministic smoke cases, which exercise doc-mode sanitizer + Analyst refusal paths; the doc-mode filter on smoke is precisely the gap that D3 closes for chat-mode at $0).

**§22.22 honest framing (the headline payload)**: NO paid validation pre-flip. The mechanical evidence (v0.1.11 BREAKTHROUGH for D1, v0.1.12 wiring verification for D2) is the basis for the flips; the v0.1.22 paid run (CONDITIONAL) measures the cumulative package (Tier 1 quorum + Capa A+B+C + v1.5 + retrieval defaults) rather than isolating each flip's contribution.

## Consequences

**Positive:**

- Production gets the best-evidence default retrieval config without callers needing to know about the opt-in (per the "future product foundation" preference). The v0.1.11 BREAKTHROUGH is now the default rather than a discoverable knob.
- Cross-corpus queries (the v0.1.13 industry cohort + the v0.1.15 gap-analysis cohort + the H14 cross-corpus xcorpus-* gold cases) are the primary expected beneficiary of D1; the cross-corpus retrieval pattern of 1/3 → 2/3 expected-article surfacing per the v0.1.11 mechanical evidence should now occur on every production cross-corpus query.
- `auto`-path queries get the spec'd `top_k=12` rather than falling back to `cfg.top_k=5`; D2 grants more candidates pre-purity-gate, which interacts coherently with D1's per-norma cap.
- v0.1.21 final-review I5 caveat is closed via chat refusal mock e2e coverage. The v1.5 Finding-based refusal interaction with Capa A+B+C is now tested explicitly rather than implicitly assumed safe.
- Backward-compat is preserved: explicit `RetrievalConfig(max_chunks_per_norma=None, top_k_auto=None)` restores pre-v0.1.21.2 behaviour for any caller that needs it (regression-zero opt-out path).

**Negative / accepted (per §22.22 honest framing):**

- **H10 cohort impact UNKNOWN pre-flip**: H10 is NOT cross-corpus dominant (single-corpus explicit-corpus cases), so the D1 BREAKTHROUGH evidence does not directly extrapolate. The H10 cohort defines the v0.1.20-bar metrics (ADR-0021); the bar-impact direction (positive / neutral / regression) is unmeasured until v0.1.22.
- **`top_k_auto=12` value not empirically optimal**: 12 is the v0.1.12 spec'd default. Future tuning milestone if v0.1.22 evidence shows opportunity (e.g. =8 less noise, =15 better recall). Carry to potential v0.1.23 / post-H17 polish.
- **v0.1.22 paid run measures cumulative package, NOT isolated impact per flip**: the v0.1.21.2 retrieval defaults land alongside the v0.1.21 Tier 1 quorum + Capa A+B+C + v1.5 prompt. Disentangling individual contributions would require additional A/B arms (out of scope per budget). The cumulative measurement is the intended granularity.
- **4th consecutive milestone with §22.22 framing on capability ships without paid pre-validation**: v0.1.19 (Council binding ON) / v0.1.20 (paid A/B caught role-aware default flip defect at gate) / v0.1.21 (Tier 1 + Capa A+B+C + v1.5 ships untested empirically) / v0.1.21.2 (retrieval defaults ship without paid pre-flip). The cross-milestone pattern is: per-task reviews validate per-task correctness; cumulative empirical validation lives at the paid-milestone cadence rather than the capability-milestone cadence. Documented; v0.1.22 (CONDITIONAL) is the empirical reckoning point.
- **D3 mocks may diverge from real Sonnet behaviour**: the chat refusal mock e2e tests fabricate Sonnet responses to exercise the v1.5 + Capa A+B+C flow. Real adversarial behavior (Sonnet's actual refusal phrasings under jailbreak attempts) is not measured here; that lives at v0.1.22 or a future redteam-paid milestone.

## Alternatives considered

1. **Paid probe N=5 before flipping** (~€0.50). Rejected: breaks the $0 mini-milestone discipline established in the maximalist plan + post-v0.1.8 cost-estimation hygiene. v0.1.22 already measures the package; an isolated probe adds wall-clock + budget without changing the flip/defer decision.
2. **Flip only per-norma cap (D1) without `top_k_auto` (D2)**. Rejected: bundled coherently as Tier 2 per user authorization; D1 + D2 interact (more candidates pre-purity-gate makes the per-norma cap more effective at diversifying the multi-corpus pool); v0.1.12 wiring evidence is mechanically sound on its own (algorithmically verified by 9 unit tests).
3. **`top_k_auto=8` or `=15` instead of `=12`**. Rejected: v0.1.12 spec'd 12 as the default; arbitrary deviation without empirical basis is just YAGNI. Future tuning milestone if v0.1.22 evidence shows opportunity.
4. **Also flip `max_chunks_per_article` to a default cap**. Rejected: v0.1.10 measurement deemed per-article cap marginal at the time (article-level dedup did NOT fix xcorpus-002; that was D1's contribution at NORMA level). Out-of-scope for v0.1.21.2; potential carry if H17 follow-ups identify article-level over-clustering in production traces.
5. **Real adversarial chat redteam (paid)** for D3 instead of mocks. Rejected: mocks suffice to close the I5 interaction-correctness caveat at $0; real adversarial measurement lives at v0.1.22 or a future redteam-paid milestone with proper budget allocation. The mocks catch interaction bugs (e.g. v1.5 refusal format vs Capa A strict mode); they do NOT measure Sonnet's real-world refusal robustness, which is a separate question.

## References

- **Spec**: `docs/superpowers/specs/2026-05-24-v0.1.21.2-tier2-flips-design.md` @ commit `78c95ce`.
- **Plan**: `docs/superpowers/plans/2026-05-24-v0.1.21.2-tier2-flips.md` @ commit `d50450e`.
- **T1-T4 commits**: `7130235` (TDD red) → `20d0fa8` (T2 D1 flip) → `8723537` (T3 D2 flip) → `f88c608` (T4 D3 chat refusal mock) → `eb954e8` (linter cleanup).
- **Companion ADRs**: 0017 (H15.1 retriever optimization), 0018 (H15.2 wiring), 0026 (v0.1.20 paid framework), 0027 (v0.1.21 Tier 1 + Capa A+B+C + v1.5).
- **v0.1.21 final review I5 caveat** (motivates D3): doc-mode-filtered smoke gate left chat refusal under v1.5+Capa A+B unmeasured. Referenced in `docs/technical_decisions_log.md` §v0.1.21 + ADR-0027 implementation note.
- **Source code touched by v0.1.21.2**:
  - `src/regulaitor/rag/retrieval.py` (2-line default flip: D1 + D2).
- **Test additions**:
  - `tests/unit/rag/test_retrieval_defaults_v0121_2.py` (7 tests — D1 + D2 default assertions + opt-out anchors).
  - `tests/unit/redteam/test_chat_refusal_mock.py` (6 tests — D3 chat refusal mock e2e).
- **Future**: v0.1.22 CONDITIONAL paid 30-case A/B measures the cumulative v0.1.21 + v0.1.21.1 + v0.1.21.2 package; OR direct path to H16 (HF Spaces deploy) → H17 (TFM closure).
