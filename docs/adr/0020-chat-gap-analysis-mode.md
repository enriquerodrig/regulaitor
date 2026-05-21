# ADR 0020 — Chat gap-analysis mode via Analyst prompt v1.3 (NL auto-detect) (v0.1.15)

- **Status:** Accepted — 2026-05-21 — squash `<squash-sha>`, tag `v0.1.15-gap-analysis-chat`
- **Deciders:** Project owner.
- **Companion ADRs:** 0006 (H4 chat E2E — the Analyst chain this extends), 0016 (H15 Auditor calibration — the prompt-versioning seam `REGULAITOR_ANALYST_PROMPT_VERSION` reused here), 0019 (v0.1.14 segmenter heading regex — sibling decimal-milestone discipline pattern).

## Context

v0.1.14 closed the H15 "0 segments" deferral and brought doc-mode evaluation back to measurable. The remaining production-UX gap from the user's TFM dual-target (LinkedIn publish + AI industry presencial session) is a **chat gap-analysis surface**: real industry users do not ask "¿qué dice el AI Act sobre alto riesgo?" — they ask "tengo X, ¿qué me falta?". Without this surface, the chat path can only answer information questions; the user cannot get a structured list of what their declared compliance state is missing.

The boundary contract recorded at v0.1.14 close (user-approved insertion 2026-05-21) is:

- **Use case**: NL chat input "AI Act alto riesgo me aplica, tengo implementado X y Y, ¿qué me falta?" → system returns structured gap list with citations from corpus.
- **Architecture**: extends Analyst prompt v1.2 → v1.3 with gap-analysis-mode instructions + few-shot examples.
- **§6 invariant compatibility**: each claim about "what the law requires" cited from corpus; user's declared state is INPUT (not a claim that needs corpus backing); the gap IS the difference (reasoning, not a normative claim); Auditor still validates per-citation.
- **Ceremony**: medium (~1-2 días, $0).
- **Backward-compat**: Analyst v1.2 stays available via env override; production default decides at v0.1.20 paid validation.

The brainstorming session (committed `a899b15` spec) resolved 5 design questions:

1. **Trigger**: NL auto-detect inside the prompt (no API surface change). Rule 8 of v1.3 detects gap pattern from query content.
2. **Output shape**: reuse the existing `Finding{text, citations[], severity}` schema (zero schema change).
3. **Few-shots**: 1 Q&A (preserved from v1.2) + 2 NEW gap-analysis (precise + vague-real). Total prompt cost ~$0.001 incremental per /ask call.
4. **Gold count**: 10 (5 `industry-g*` precise + 5 `industry-gv*` vague-real).
5. **Production default**: stays v1.0 (matches boundary contract); v1.3 opt-in via env override; v0.1.20 paid bundle decides the production-default flip.

## Decision

Ship the chat gap-analysis surface as a **prompt-only extension**:

1. **NEW** `src/regulaitor/agents/prompts/analyst/system.v1.3.md`:
   - Hard rules 1-7 + Output format + Output contract + Example 1 (Q&A) **byte-identical** to v1.2.
   - **NEW** Hard Rule 8: NL gap-analysis detection. Trigger requires BOTH (a) a declaration of user's state ("tengo", "hemos implementado", "I have", "we've implemented", …) AND (b) a gap-seeking question ("¿qué me falta?", "¿estoy cumpliendo?", "what's missing?", …). When only one is present OR query is a pure information request, regular Q&A mode applies. Ambiguous → Q&A (safer default).
   - **NEW** "Output contract — gap-analysis branch" subsection: each gap = one `Finding` with `text="Falta: [obligación]..."` + citation to the requiring article + severity per scale (`high` blocks hard obligation, `medium` documentation/process gap, `low` procedural detail, `info` positive coverage). Declared state goes in top-level `Answer.text` (INPUT, not citation-worthy).
   - **NEW** Example 2 (precise gap-analysis) + Example 3 (vague-real gap-analysis).
   - Frontmatter `version: 1.3` + changelog entry.

2. **NO API change**: `AskRequest{query, corpus, language, council}` unchanged.

3. **NO schema change**: `Answer`, `Finding`, `Citation`, `AuditedAnswer`, `CitationDTO`, `FindingDTO` — all byte-unchanged. Gap-analysis Findings use the same shape Q&A Findings use.

4. **NO backend change**: §6 Auditor + citation-validator byte-unchanged; H1-H5 + H7 read-only.

5. **Production default stays v1.0** via the env seam from ADR-0016 (`REGULAITOR_ANALYST_PROMPT_VERSION`). v1.3 is opt-in: `REGULAITOR_ANALYST_PROMPT_VERSION=v1.3` activates gap-analysis. v1.0/v1.1/v1.2/v1.3 all coexist on disk; env override picks which loads.

6. **Gold extension**: +10 chat cases (5 `industry-g{1..5}` precise + 5 `industry-gv{1..5}` vague-real, all `corpus_esperado="auto"`). Empirical measurement of v1.3 vs v1.0 deferred to v0.1.20 paid bundle (single bundled validation of all maximalist-plan optimizations).

7. **2 NEW unit test files** ($0): structural prompt fidelity (`test_analyst_v1_3_loads.py`) + gold case schema (`tests/unit/evals/test_industry_gap_cases_load.py`).

## Consequences

**Positive:**

- **Production-UX gap closed for TFM industry session**: users can ask "tengo X, ¿qué me falta?" and get a structured gap list. The demo unlocks with one .env line; no code redeploy needed.
- **§6 invariant trivially preserved**: gap-analysis Findings reuse the standard Finding schema; Auditor validates every citation per existing rules. A gap-analysis Finding with a hallucinated article is rejected identically to a Q&A Finding with a hallucinated article. The "no citation, no answer" guarantee holds by construction.
- **Backward-compat by construction**: production default v1.0 unchanged; the env-unset behavior is byte-identical to v0.1.14. v1.3 also preserves the v1.2 Q&A example verbatim (regression-zero anchor: when v1.3 IS loaded, the regular Q&A path still works the same).
- **Surgical change**: zero API surface, zero schema, zero backend, zero Streamlit. 1 new prompt file + 1 gold append + 2 unit test files + ADR + memoria doc. The smallest possible delta to ship the capability.
- **Cross-corpus by design**: all 10 gold cases use `corpus_esperado="auto"`, exercising the H15.1 + v0.1.10–v0.1.12 cross-corpus retrieval optimizations on real gap-analysis traffic when v0.1.20 measurement runs.

**Negative / accepted (documented honestly per §22.22):**

- **No paid empirical measurement in v0.1.15**: the capability ships without an A/B vs v1.0 baseline. Following the §22.22 pattern from H15/H15.1/v0.1.10–v0.1.13, the empirical question ("does v1.3 produce useful gaps without regressing Q&A?") is deferred to the v0.1.20 paid bundle. v0.1.15's contribution IS the capability + the gold extension + the schema-zero-change design; the quality measurement is bundled with all other optimizations into a single paid run.
- **NL detection lives in the prompt, not in code**: Rule 8 detection is a prompt instruction, not a deterministic dispatcher. The model may occasionally trigger on borderline queries that the design intends as Q&A, or fail to trigger on borderline queries that are genuine gap-analysis. The "ambiguous → Q&A" default biases toward false-negative rather than false-positive (safer because the existing Q&A behavior is well-understood). v0.1.20 measurement will surface any production-relevant detection drift.
- **Few-shot tokens add ~$0.001/call to all /ask invocations under v1.3**: the gap-analysis examples are loaded into the system prompt unconditionally when v1.3 is active. Negligible at expected production volume but documented.
- **Production-default flip deferred to v0.1.20**: the env-override demo path is robust for TFM industry session, but a production rollout where every user gets v1.3 by default requires the paid bundle measurement first. If v0.1.20 shows v1.3 regresses Q&A unacceptably, the production default stays v1.0 and v1.3 remains a power-user opt-in (still defensible for the TFM since the capability is there and measurable).

## Alternatives considered

- **Explicit `mode` parameter on `/ask`** (`AskRequest.mode: "qa" | "gap_analysis"`) — rejected. Cleaner contract and easier gold-testing, but assumes the client KNOWS gap-analysis is what they want. Production target users (per v0.1.13 vague-real rationale) won't always know; they'll just type natural language. Adding a `mode` field also breaks the spec's "zero API surface change" discipline.
- **Separate `POST /gap-analysis` endpoint with structured input** (`{applicable_articles: [...], declared_controls: [...]}`) — rejected. Strongest contract but assumes the user already knows which articles apply (defeats the production-UX requirement to handle vague users). Could coexist with NL auto-detect for power users but adds API surface YAGNI for v0.1.15.
- **New `GapFinding` subtype** (`requires_text`, `requires_citation`, `declared_state`, `gap_summary` fields) — rejected. Cleaner semantics but ripples through Pydantic schemas, Auditor (must know how to validate per-variant), DTO converters, Streamlit renderer, gold case schema. Breaks backend-read-only discipline and forces §6 re-test. The Finding-reuse design preserves §6 by construction.
- **Make v1.3 the production default in v0.1.15** — rejected. Trades honesty for convenience. Gap-analysis quality is untested end-to-end; the additional gap few-shots could subtly affect Q&A on edge cases (regression untested). §22.22 framing applies: ship the capability, defer the production-default flip until measured. The env-override path is robust for the TFM demo use case.

## References

- Boundary contract: memory `v0.1.14_closed_v0.1.15_starting.md` §"Boundary contract for v0.1.15" (user-approved 2026-05-21).
- Brainstorming spec: `docs/superpowers/specs/2026-05-21-v0.1.15-gap-analysis-chat-mode-design.md` (commit `a899b15`).
- Source of NL detection design: `system.v1.3.md` Hard Rule 8.
- New unit tests: `tests/unit/test_analyst_v1_3_loads.py` (prompt fidelity) + `tests/unit/evals/test_industry_gap_cases_load.py` (gold cases).
- v0.1.13 sister: `docs/industry_gold_extension.md` (precise + vague-real split rationale).
- §6 invariant lineage: ADR-0006 (H4 chat E2E), CLAUDE.md §6 ("no citation, no answer").
- Prompt-versioning seam: ADR-0016 (H15 Auditor calibration env override `REGULAITOR_ANALYST_PROMPT_VERSION`).
- Future paid validation: v0.1.20 paid bundle (all maximalist-plan optimizations measured together against production baseline).
