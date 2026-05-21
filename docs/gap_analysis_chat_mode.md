# Chat gap-analysis mode (v0.1.15)

**Status:** Capability shipped 2026-05-21 (tag `v0.1.15-gap-analysis-chat`). Empirical measurement deferred to v0.1.20 paid bundle. Production default `Analyst v1.0` unchanged; opt-in `v1.3` via `REGULAITOR_ANALYST_PROMPT_VERSION=v1.3`.

**TFM dual-target:** LinkedIn publish + AI industry presencial session require a "tell me what I'm missing" surface beyond Q&A. v0.1.15 closes that surface gap via a prompt-only extension.

---

## WHAT

A chat surface for **gap analysis**: the user describes their current state in natural language (e.g. "Mi empresa opera un sistema de IA clasificado como alto riesgo según AI Act art. 6. Hemos implementado evaluación de impacto y supervisión humana. ¿Qué nos falta?") and receives a structured list of missing obligations, each grounded in a corpus citation.

The surface ships as **Analyst prompt v1.3** — a new version that extends v1.2 with:

- **Hard Rule 8 (NL detection)**: the prompt itself detects whether the query is a gap-analysis request (requires BOTH a declaration like "tengo" / "hemos implementado" / "I have" AND a gap-seeking question like "¿qué me falta?" / "¿estoy cumpliendo?" / "what's missing?"). When ambiguous, defaults to regular Q&A.
- **Gap-analysis output contract**: each gap is one `Finding{text="Falta: [obligación]...", citations[...], severity}` using the SAME schema Q&A uses. The user's declared state is paraphrased in top-level `Answer.text` (INPUT, no citation needed). Severity scale: `high` blocks hard obligation, `medium` documentation/process gap, `low` procedural detail, `info` positive coverage statement.
- **2 new few-shot examples**: one precise (user names article numbers + declares specific controls) + one vague-real (user uses colloquial language, tentative declaration). The original Q&A example (Hard Rule 1-7 anchor case) is preserved byte-identical so the regular Q&A path doesn't regress when v1.3 is loaded.

Plus **10 new gold cases** in `evals/gold_set.jsonl`:

- 5 `industry-g{1..5}` precise (banca + DORA, fintech + GDPR art 22, hospital + GDPR art 9, cloud + DORA art 28/30, AI Act high-risk operator).
- 5 `industry-gv{1..5}` vague-real (no article numbers, colloquial declarations).

All 10 cases use `corpus_esperado="auto"` (gap-analysis is typically cross-corpus).

## WHY

**The production-UX gap.** Pre-v0.1.15 the chat surface answered "¿qué dice X sobre Y?" (information questions) but had no clean way to answer "tengo X, ¿qué me falta?" (gap questions). For the TFM industry session this matters: a compliance officer at a PYME does not want a treatise on the AI Act; they want a structured list of what they're missing given what they've already declared. The information question is the academic Q&A; the gap question is the practical product.

**Why NL auto-detect, not an explicit mode parameter or separate endpoint.** The brainstorming explored three options:

1. NL auto-detect inside the prompt (chosen).
2. Explicit `mode: "qa" | "gap_analysis"` field on `AskRequest`.
3. Separate `POST /gap-analysis` endpoint with structured input `{applicable_articles, declared_controls}`.

Option 2 forces the client to know which mode they want; option 3 assumes the client already knows which articles apply. Both defeat the production-UX requirement to handle the vague users that v0.1.13 explicitly added to the gold set (industry-v* cases). Option 1 keeps the UX zero-friction: the user types natural language; the system decides. The cost is reliability of detection at the prompt level — which Rule 8's "BOTH (a) AND (b) required; ambiguous → Q&A" wording is designed to bias toward false-negative (miss a borderline gap-analysis and treat it as Q&A) over false-positive (treat a borderline Q&A as gap-analysis and produce confusing output).

**Why reuse `Finding` instead of a new `GapFinding` subtype.** The brainstorming considered both. A new subtype with explicit `requires_text/requires_citation/declared_state/gap_summary` fields would carry clearer semantics, but it ripples through Pydantic schemas, Auditor (must validate per-variant), DTO converters, Streamlit renderer, gold case schema. The Finding-reuse design has ONE crucial property: §6 invariant ("no citation, no answer") is preserved by construction. The Auditor doesn't need to be taught about gap-analysis; it sees the same `Finding{text, citations[], severity}` shape it always sees, and validates every citation per its existing rules. A gap-analysis Finding with a hallucinated article is rejected identically to a Q&A Finding with a hallucinated article. This is the right discipline trade: a slightly less expressive schema in exchange for byte-unchanged backend.

**Why production default stays v1.0.** The boundary contract from v0.1.14 close said "production default decides at v0.1.20 paid validation". v0.1.20 is the single bundled paid run that measures ALL maximalist-plan optimizations (per-article cap v0.1.10, per-norma cap v0.1.11, top_k_auto v0.1.12, industry gold v0.1.13, segmenter v0.1.14, gap-analysis v0.1.15) against the production baseline. Flipping the default in v0.1.15 without that measurement would trade honesty for convenience — the gap-analysis few-shots could subtly affect Q&A on edge cases (regression untested). The env-override path (`REGULAITOR_ANALYST_PROMPT_VERSION=v1.3` in `.env`) unlocks the TFM demo capability with zero risk to the production default.

## HOW

**Architecturally** the change is purely additive at the prompt surface:

```
.../analyst/system.v1.0.md   ← production default (env unset)
.../analyst/system.v1.1.md   ← H15 iteration
.../analyst/system.v1.2.md   ← H15 final candidate
.../analyst/system.v1.3.md   ← NEW v0.1.15 (gap-analysis chat mode)
```

`AnalystAgent.__init__()` reads `REGULAITOR_ANALYST_PROMPT_VERSION` env var. Unset → defaults `v1.0` → production behavior byte-identical to v0.1.14. Set to `v1.3` → loads v1.3 → gap-analysis Rule 8 detection active. Set to any other valid version → that version loads. Set to an invalid value → WARNING log + fall back to v1.0 (never crashes).

**At the LLM level**, when v1.3 is active and a query arrives:

1. The Analyst sees the v1.3 system prompt (Hard rules 1-8 + Output format + Output contract + Output contract — gap-analysis branch + 3 Examples).
2. The Analyst sees the retrieved corpus chunks (same retrieval path as Q&A — cross-corpus auto or single-corpus explicit).
3. Rule 8 detection: the Analyst inspects the user's query for (a) a state declaration + (b) a gap-seeking question. Both present → gap-analysis mode. Either missing → Q&A mode (Example 1 path).
4. Output: same `emit_answer` tool call shape (zero schema change). Each Finding either describes a gap ("Falta: [obligación]...") or positive coverage ("El estado declarado cubre las obligaciones aplicables del [artículo]"). Top-level `Answer.text` paraphrases the user's declaration.
5. Auditor downstream validates every citation literally against the corpus (existing logic, byte-unchanged). A hallucinated article is rejected; the §6 guarantee holds.

**At the gold level**, 10 new cases extend the existing 54 chat cases (44 H14 + 10 v0.1.13 industry-c/v). The 5 precise gap cases test cleaner retrieval + reasoning under structured input; the 5 vague-real cases test production-UX detection of gap-analysis intent without article numbers or norm names.

**At the test level**, two new $0 unit test files pin the structural invariants:

- `tests/unit/test_analyst_v1_3_loads.py`: 7 tests asserting v1.3 file exists + frontmatter + Rule 8 anchor + gap-output contract anchor + Example 1 byte-identical to v1.2 + Hard rules 1-7 anchors preserved + all 4 prompt versions coexist on disk.
- `tests/unit/evals/test_industry_gap_cases_load.py`: 7 tests asserting all 10 cases load + 5/5 split + auto corpus + pass verdict + non-empty `articulos_esperados` + ≥3 criterios + vague cases without article numbers.

No LLM call in v0.1.15. Empirical question deferred to v0.1.20.

## IMPACT

**Capability shipped, measurement deferred.** v0.1.15 is the `n`-th milestone in a row to ship under the §22.22 honest framing: the contribution IS the capability + the gold extension + the schema-zero-change design that preserves §6 by construction. The empirical question ("does v1.3 produce useful gaps without regressing Q&A?") is bundled into the v0.1.20 single paid validation run alongside per-article cap (v0.1.10), per-norma cap (v0.1.11), top_k_auto (v0.1.12), industry gold (v0.1.13), and segmenter heading regex (v0.1.14). At v0.1.20 the production default flip decision is made on measured evidence, not on a priori confidence.

**TFM demo readiness.** The industry session can demo the gap-analysis surface from v0.1.15 by setting one .env line. The LinkedIn writeup can describe the surface, the §6 invariant interpretation, and the schema-zero-change design.

**§6 invariant intact, verified by 4 git-diff checks at closure.** `src/regulaitor/agents/auditor.py`, `src/regulaitor/citation/validator.py`, `src/regulaitor/citation/schemas.py`, `src/regulaitor/api/schemas.py` — all empty diffs vs main at the whole-branch review. Backend `rag/`, `document/`, `api/`, `orchestration/` directories — empty diffs. The §6 guarantee is preserved by construction because gap-analysis reuses the Finding schema the Auditor already validates.

**Gate carry-forward.** v0.1.14 baseline 836 tests → v0.1.15 baseline 850 tests (836 + 7 + 7 new $0 unit tests). 0 failures, 1 skipped (carry). mypy strict 71 files exit 0. Redteam-smoke 0.92 (prompt-blind so unaffected; verified at closure).

**$0 milestone.** No paid LLM call in v0.1.15. Single bundled paid validation at v0.1.20 when budget recharges. Following the cost-estimation discipline registered after H15.2 (probe min N=5, ranges with high=expected×1.5, no auth if budget<high-estimate, no paid run without harness checkpoint).

---

## §6 invariant interpretation for gap-analysis (callout)

> **§6 of CLAUDE.md (verbatim):** "Sin cita verificable, no hay respuesta. Toda salida del Analyst-Agent pasa por el Auditor-Agent. El Auditor valida: que la cita existe en el corpus, que el texto citado coincide literal o normalizado, que el artículo y apartado existen, que la cita apoya la afirmación, que la salida no contiene afirmaciones jurídicas no respaldadas."
>
> **How gap-analysis honors §6**:
>
> 1. **What the law requires** is a normative claim. Each gap-analysis `Finding.text` makes one such claim ("X exige Y..."). Each Finding has ≥1 citation; the Auditor validates that citation literally against the corpus. If the citation is fake or doesn't match the literal text of the chunk, the Auditor rejects the Finding. **§6 satisfied per Finding.**
> 2. **What the user declared** is INPUT, not a claim. It lives in top-level `Answer.text` as a paraphrase ("Has declarado: X, Y, Z. Análisis de gaps:"). The paraphrase makes NO assertion about the law; it summarizes what the user said. §6 requires backing for assertions ABOUT the corpus, not for repeating what the user told the system. **§6 not engaged for the declaration paraphrase.**
> 3. **The gap itself is reasoning**, not a claim. The system observes that the user's declared state lacks something the corpus says is required; the GAP is the delta. The reasoning happens in the Finding's `text` ("Falta: X..."), but the claim "X is required" is what's cited; the gap (= "X is required AND user did not declare X") follows from reasoning over INPUT + corpus, not from a separate normative claim. **§6 still satisfied because the only normative claim — that X is required — is cited.**
>
> **Practical consequence**: the existing Auditor + citation-validator code does NOT need to be modified for gap-analysis. It sees the same `Finding{text, citations[], severity}` shape and applies the same validation. A gap-analysis Finding with a hallucinated article is rejected exactly like a Q&A Finding with a hallucinated article. The §6 guarantee is preserved by construction.

---

## References

- Spec: `docs/superpowers/specs/2026-05-21-v0.1.15-gap-analysis-chat-mode-design.md`.
- ADR: `docs/adr/0020-chat-gap-analysis-mode.md`.
- Boundary contract: memory `v0.1.14_closed_v0.1.15_starting.md` §"Boundary contract for v0.1.15".
- Prompt versioning seam: `docs/adr/0016-auditor-calibration.md` (H15 introduced `REGULAITOR_ANALYST_PROMPT_VERSION`).
- §6 invariant lineage: `CLAUDE.md` §6 ("no citation, no answer") + ADR-0006 (H4 chat E2E).
- Sibling v0.1.13 design: `docs/industry_gold_extension.md` (precise + vague-real split rationale extended here to gap-analysis).
- Sibling v0.1.14 closure: `docs/adr/0019-segmenter-numbered-section-heading-detection.md` (decimal-milestone discipline pattern).
- Future paid validation: v0.1.20 paid bundle (single bundled measurement of all maximalist-plan optimizations).
