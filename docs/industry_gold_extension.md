# Industry-realistic gold set extension (v0.1.13)

Hand-authored synthesis for the 10 new cross-corpus cases added to `evals/gold_set.jsonl` in v0.1.13 (industry-demo readiness, per user-flagged TFM dual-target: LinkedIn publish + AI industry presencial session).

## WHAT/WHY/HOW/IMPACT (memoria-ready synthesis)

- **WHAT** — extended `evals/gold_set.jsonl` from 44 → 54 chat cases by adding 10 cross-corpus, industry-realistic questions: 5 precise (`industry-c{1,3,4,5,8}`) + 5 vague-real (`industry-v{1-5}`). All 10 use `corpus_esperado="auto"` so they exercise the cross-corpus auto path (purity gate + dedup caps v0.1.10/v0.1.11 + top_k_auto v0.1.12).

- **WHY** — three converging motivations:
  1. **Statistical representativeness**: prior gold set had only 2/44 = 4.5% cross-corpus cases (xcorpus-001/002). For a system whose unique value proposition is cross-corpus reasoning (vs ChatGPT + single-doc RAG), the gold weighting needs to better reflect that strength.
  2. **Production-UX realism** (user-flagged industry demo dimension): real compliance officers ask vague, imprecise questions — they don't say "AI Act art 6" or "GDPR art 22". They say "¿esto es legal?" or "vamos a lanzar IA de RRHH, ¿algún problema?". A gold set with only lawyer-clean queries cannot measure production UX. The 5 vague cases test this directly.
  3. **Industry-demo audience**: AI engineers at a presencial session WILL test the system with adversarial / typical industry scenarios (biometrics, scoring crediticio, healthcare AI, breach response). Pre-loading these as gold cases lets us measure + improve readiness BEFORE the demo.

- **HOW** — 10 cases drafted, user-validated, appended to `evals/gold_set.jsonl` as JSONL lines following the established `GoldCaseChat` schema. Unit tests in `tests/unit/evals/test_industry_gold_cases_load.py` pin: schema validity, `corpus_esperado="auto"`, ≥3 criterios per case, non-empty `articulos_esperados`, exact 5+5 precise-vs-vague split, vague-case `entrada` text avoids legalese (regulation names, article numbers). No backward-compat impact (additive only; no existing cases modified; harness `load_gold_set` reads all lines unchanged).

- **IMPACT** — measurement deferred to the v0.1.20 paid validation bundle (when budget recharges) OR to a dedicated $0 local-CPU diagnostic run with proper time budget (per `feedback_local_cpu_rerank_cost.md` rules). The capability — having industry-realistic cases in the gold set — is the v0.1.13 ship; the empirical "do these 10 cases pass when run through retrieval + Analyst + Auditor?" question is for v0.1.20.

## The 10 cases at a glance

### Precise (5) — lawyer-clean cross-corpus

| ID | Scenario | Cross-corpus reach |
|---|---|---|
| `industry-c1` | Hospital + IA diagnóstico clínico | AI Act + GDPR + (NIS2) — triple |
| `industry-c3` | Fintech + IA scoring crediticio + DORA | AI Act + GDPR + DORA — triple |
| `industry-c4` | Banco DORA + ciberataque + brecha datos | DORA + NIS2 + GDPR — triple |
| `industry-c5` | Cloud crítico (sector financiero) | NIS2 + DORA + GDPR — triple |
| `industry-c8` | IA screening CVs | AI Act + GDPR |

### Vague-real (5) — production-UX representative

| ID | Tone | Real question pattern |
|---|---|---|
| `industry-v1` | worry-tone "¿esto es legal?" | Reconocimiento facial oficina (sin mencionar AI Act / GDPR / biometría) |
| `industry-v2` | practical-tone "¿qué tengo que hacer?" | Brecha datos clientes (sin mencionar GDPR / 72h) |
| `industry-v3` | speculative-tone "¿algún problema?" | IA RRHH para CV screening (sin mencionar high-risk / ADM) |
| `industry-v4` | reactive-tone "¿a quién avisamos?" | Incidente cyber en sistemas pago (sin mencionar DORA / NIS2) |
| `industry-v5` | confused-tone "¿me aplica o no?" | Empresa hosting 30 empleados (umbrales NIS2) |

## How this enables future measurement

Once budget recharges, the v0.1.20 paid validation will include these 10 cases in the bundle A/B. Key questions the measurement will answer:

1. **For precise cases**: does the retrieval (with recommended demo-config `RetrievalConfig(max_chunks_per_norma=2)`) surface the expected articles across multiple normas?
2. **For vague cases**: does the Analyst:
   - Correctly identify the applicable regulations WITHOUT the user mentioning them?
   - Cite articles literally even when the user phrased the question colloquially?
   - Recognize ambiguity and request clarifying information (vs hallucinating an answer)?
3. **Aggregate**: do the H15.1/H15.2/v0.1.8-v0.1.12 optimizations produce a measurable improvement on the cross-corpus dimension when applied to a wider distribution than just xcorpus-001/002?

## Trade-offs accepted (§22.22-honest)

- **Articulos_esperados convention carry-forward**: like xcorpus-001/002, the new cases list article numbers only (e.g. `["19", "23", "33"]` for a triple DORA-NIS2-GDPR case). This continues the citation-granularity confound documented in H14/H15.1 (articulos_esperados is corpus-ambiguous; the `criterios_evaluacion` text disambiguates). Will be addressed in v0.1.18 citation granularity confound microhito. For v0.1.13 we deliberately match the existing convention to keep backward-compat with the eval harness.
- **No paid validation in v0.1.13**: deferred to v0.1.20 bundle per the maximalist plan + cost-estimation discipline (probe + tally + user OK + credit confirmation gate). The cases are ready when budget is.
- **Vague-case `articulos_esperados` are aspirational**: the user didn't mention these articles, so when the Analyst surfaces them it requires both retrieval (which now works with v0.1.11 cap=2 cross-corpus) AND Analyst reasoning to correctly identify the applicable regulation. If v0.1.20 measurement shows vague cases fail systematically while precise pass, that's diagnostic value for a future Analyst-prompt microhito (e.g. v0.1.X "ambiguity-aware prompt revision").

## References

- Implementation: `evals/gold_set.jsonl` (lines 45-54, the 10 new entries)
- Schema: `evals/schemas.py` `GoldCaseChat`
- Pin tests: `tests/unit/evals/test_industry_gold_cases_load.py`
- Recommended demo config: `RetrievalConfig(max_chunks_per_norma=2)` (per v0.1.11 BREAKTHROUGH measurement; opt-in, not production default)
- Previous gold-set context: H14 NIS2/DORA expansion (44 cases prior) + H15.1 (xcorpus-001/002 added)
- Future paid validation: v0.1.20 bundle A/B
