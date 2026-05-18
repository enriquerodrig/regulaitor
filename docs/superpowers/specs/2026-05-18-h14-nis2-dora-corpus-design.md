# H14 — NIS2 + DORA corpus expansion · Design Spec

**Date:** 2026-05-18 (brainstorming closed). **Milestone:** H14 (advanced track; H13 closed `v0.1.3-h13`).

**Goal:** Land the **NIS2** (Directive (EU) 2022/2555, CELEX 32022L2555) and **DORA** (Regulation (EU) 2022/2554, CELEX 32022R2554) corpora (ES+EN, latest consolidated, **PDF** — mirroring the ADR-0003 path the existing two corpora use), make them retrievable end-to-end alongside AI Act + RGPD, add gold-set cases (incl. cross-corpus), and verify it **$0-deterministically** — with AI Act + RGPD strictly **regression-zero** (§22.18) and an honest documented per-corpus partial if a corpus's PDF intractably resists the parser.

---

## 1. Context (current state)

- The H1 corpus pipeline (`src/regulaitor/corpus/{ingest,parse,validate,loader}.py`, `_targets.py`) is **already 4-corpus-ready by design**: `Norma = Literal["ai_act","gdpr","nis2","dora"]` (corpus/schemas.py:14), `ALL_NORMAS = ("ai_act","gdpr","nis2","dora")` (_targets.py:12), `Manifest` is corpus-agnostic, and `ingest.py:281-282` already filters "to only corpora that have CELEX/VERSION pinned (H1 + H14)" — the comment anticipates H14.
- The existing AI Act + RGPD are **PDF** (ADR 0003 pivoted H1 from HTML/Formex to consolidated PDF). `corpus/raw/{ai_act,gdpr}_{es,en}.pdf` (Git-LFS), `corpus/manifests/{ai_act,gdpr}.json`, `corpus/processed/`. `SourceFormat = Literal["formex4","html","pdf"]`. `CELEX: dict[Norma,str]` at `ingest.py:55` (`ai_act:"32024R1689"`, gdpr next).
- **Real blast radius — exactly the hardcoded 2-value spots** (everything else uses the already-4-value `Norma`): `api/schemas.py:43` (`AskRequest.corpus: Literal["ai_act","gdpr"]`), `api/routes_analyze.py:67` (`c in ("ai_act","gdpr")` guard), `corpus/loader.py:31` (`CORPORA_WITH_MANIFESTS: tuple[Norma,...] = ("ai_act","gdpr")` — the warmup gate, the reason only 2 load today), `ui_streamlit/tab_ask.py:20` + `tab_analyze.py:25` (`_CORPUS_CHOICES = ["ai_act","gdpr"]`), and `evals/schemas.py` `GoldCaseChat.corpus_esperado: Literal["ai_act","gdpr"]`.
- The `rag-ingest` skill (`.claude/skills/rag-ingest/SKILL.md`, active since H1) is the canonical add-a-corpus procedure (confirm CELEX/version/langs with owner → `CELEX`/`VERSION` + `EXPECTED_ARTICLE_COUNTS` → fixtures + parser test → smoke `scripts.ingest --corpus X` → verify counts → commit manifest + LFS → decisions log; **step 10: a parser-schema variation → follow-up ADR, never silently extend the parser**). **Known doc tension:** the SKILL.md procedure references Formex fixtures/`test_formex_parser.py`, but the corpora are PDF (ADR 0003) — H14 follows the **actual proven PDF parse path** AI Act/RGPD use, not the stale-looking Formex steps; if the SKILL.md is stale vs ADR 0003 that is a documented skill-doc follow-up.
- Chunking/embedding (`rag/{chunking,embeddings,store,build}.py`, BGE-M3 + bge-reranker-v2-m3) is **corpus-agnostic** — operates on the Manifest/processed JSON regardless of corpus; H14 reuses it unchanged (no chunking redesign).
- State: H13 closed (`v0.1.3-h13`, squash `db991dc`, post-merge `c25e0d2`). Advanced gate §16.2 met. System documented-**uncalibrated** (H10/H12/H13: faithfulness 0.54, verdict_match 0.17–0.28) — the §17 ≥0.85 thresholds are the H15 calibration job, not H14's.

## 2. Decisions (brainstorming, user-approved 2026-05-18)

- **D1 — Source/format.** NIS2 = CELEX **32022L2555**, DORA = CELEX **32022R2554**; **ES + EN**, latest **consolidated**; **obtained directly from EUR-Lex via `curl`** (allowlisted host `eur-lex.europa.eu`, the `/TXT/PDF/?uri=CELEX:<celex>` endpoint, smoke-verified live), placed as local **Git-LFS** files in `corpus/raw/`, and parsed via the same proven **local** PDF path AI Act/RGPD use (mirror ADR 0003 — the automated httpx client only fetches formex/html; the consolidated PDF is a deliberate local-file step, exactly as the existing `corpus/raw/*.pdf` were provided; lowest parser-divergence risk).
- **D2 — Scope = best-effort + honest documented per-corpus partial.** Attempt both via the PDF path. If a corpus's PDF intractably resists the parser within a reasonable time-box (the operative-plan H14 ~3-day threshold / a bounded number of parser iterations): ship it **partial** — that corpus deferred (NOT added to `CORPORA_WITH_MANIFESTS`/gold/index), documented honestly (decisions §H14 + a follow-up ADR per rag-ingest step 10, §22.22, the H1-PDF-pivot / H13-30%-skip precedent) — rather than (i) burning days, (ii) silently hacking the PDF parser, or (iii) blocking the milestone. AI Act + RGPD stay **regression-zero** (§22.18) regardless. The other corpus + AI Act/RGPD still ship.
- **D3 — Success = gold cases + $0 deterministic verification; LLM-judge eval + §17 thresholds deferred to H15 (honest §16.3 reframe).** The system is documented-uncalibrated, so "la evaluación pasa los umbrales" cannot mean the §17 advanced targets without dishonesty (§13/§22.22). Honest reframe (mirrors the H10 gate-reframe / H13 Done-when reframe, recorded decisions §H14): H14 success = (a) `make ingest` loads the 4 corpora; (b) ≥5 NIS2 + ≥5 DORA chat gold cases + cross-corpus cases authored; (c) a **$0** test proves the new gold cases retrieve the correct NIS2/DORA articles (citation-recall-style — the §16.2 #5 safety-relevant signal, **no LLM-judge cost**); (d) AI Act/RGPD regression-zero. The full LLM-judge metric eval over the expanded gold set + the §17 thresholds are **explicitly deferred to H15** (the calibration cycle, where the ~$10 budget is planned and where thresholds belong). **H14 is entirely $0** (no paid LLM run: EUR-Lex fetch is network/$0, the LanceDB rebuild is local BGE-M3/$0).
- **D4 — Architecture = Approach 1.** Two independent corpus **vertical slices** (NIS2, DORA), each following the `rag-ingest` procedure, then one shared **integration step** (widen the 6 hardcoded 2-value spots — §1 — to the canonical 4-value `Norma` + rebuild the LanceDB index over the 4 corpora + author gold cases + $0 cross-corpus verification + closure). Best isolation; the D2 honest-partial falls out for free (a resisting corpus is simply not landed; the rest proceeds); backend H1–H3/agents/Auditor untouched (only corpus-ingest constants + input-validation literals + gold set + LanceDB rebuild).

## 3. Architecture & components

**Per-corpus slice (×NIS2, ×DORA) — the `rag-ingest` procedure:**
- `src/regulaitor/corpus/ingest.py`: add to `CELEX` (`"nis2": "32022L2555"`, `"dora": "32022R2554"`) and `VERSION` (the consolidated date string, pinned at implementation from the fetched consolidated PDF).
- `src/regulaitor/corpus/validate.py`: add `EXPECTED_ARTICLE_COUNTS` entries (NIS2 ~46 articles; DORA ~64 — exact counts pinned at implementation from the consolidated PDF; the validator enforces coverage + hash uniqueness).
- Obtain the consolidated **PDF** ES+EN by `curl` from EUR-Lex `https://eur-lex.europa.eu/legal-content/{ES|EN}/TXT/PDF/?uri=CELEX:<celex>` (allowlisted host; **smoke-verify each URL returns a real consolidated PDF, not an error/redirect page, before relying on it** — the ADR-0003 H1 live-fetch lesson) → place at `corpus/raw/{nis2,dora}_{es,en}.pdf` (Git-LFS, mirroring AI Act/RGPD) → parse via the proven local PDF path (`pdf_parser.py`, the `_resolve_local_source` flow) → `corpus/processed/{nis2,dora}_{es,en}.json` + `corpus/manifests/{nis2,dora}.json` (`Manifest`, already corpus-agnostic). The automated httpx client (`eurlex.py`, formex/html only) is **not** used for PDF.
- A parser unit test per corpus with a small hand-crafted fixture, mirroring the **actual** existing per-corpus parser test pattern (verify whether it is the Formex fixture form the SKILL.md describes or the PDF reality — follow the proven pattern; flag SKILL.md staleness as a doc follow-up if they diverge).
- Parser-variation handling (rag-ingest step 10 + D2): if NIS2 (Directive structure) / DORA breaks the PDF parser → raise a follow-up ADR; a scoped low-risk parser adaptation is allowed ONLY within the time-box, else declare that corpus deferred-documented. **Never silently hack the parser.** AI Act/RGPD parse path byte-unchanged.

**Shared integration step (after the slices land):**
- Widen the hardcoded 2-value spots to the canonical 4-value `Norma` (additive; ai_act/gdpr behaviour byte-identical, §22.18): `api/schemas.py` `AskRequest.corpus`, `api/routes_analyze.py` corpus guard, `ui_streamlit/tab_{ask,analyze}.py` `_CORPUS_CHOICES`, `evals/schemas.py` `GoldCaseChat.corpus_esperado`. `corpus/loader.py` `CORPORA_WITH_MANIFESTS` is widened **only to corpora whose manifest actually exists** (the honest-partial gate — a deferred corpus is NOT added here). Prefer deriving from `Norma`/`ALL_NORMAS` where it cleanly removes the 2-value anomaly; widen document-mode and chat-mode consistently (special-casing chat-only is more work, not less).
- **LanceDB rebuild:** run the existing H2 `rag/build` (`make rag-build`) over the (≤)4 landed corpora — `chunking.py`/`embeddings.py`(BGE-M3)/`store.py` are corpus-agnostic; no chunking redesign. The index then carries all landed corpora's chunks → cross-corpus retrieval works.
- **Gold set:** author ≥5 NIS2 + ≥5 DORA chat cases + a few cross-corpus cases (expected articles spanning ≥2 corpora) in `evals/gold_set.jsonl`, using the existing `GoldCaseChat` shape (`id/tipo/entrada/corpus_esperado/articulos_esperados/severidad_esperada/criterios_evaluacion/salida_esperada/requiere_revision_humana/expected_verdict`).
- **$0 deterministic verification:** a test that `make ingest` / `corpus_loader.warmup()` loads the 4 (or landed) corpora; a $0 retrieval test that each new gold case retrieves its expected NIS2/DORA articles (citation-recall-style — no LLM); a cross-corpus query returns the correct corpus's articles (no corpus leakage); the existing AI Act/RGPD corpus/retrieval/agent/api tests stay green (regression-zero).

## 4. Data flow

`fetch(CELEX, lang)` → consolidated PDF in `corpus/raw/` → `parse` → `corpus/processed/<corpus>_<lang>.json` → `validate` (vs `EXPECTED_ARTICLE_COUNTS`, hash-unique) → `Manifest` → `rag/build` chunk+embed (BGE-M3) into LanceDB across landed corpora → Retriever queries any landed corpus → chat/document graph **unchanged** (corpus-agnostic once `Norma` is widened). No LLM anywhere in the H14 path ($0).

## 5. Error handling / invariants / honest-partial

- **§22.18 regression-zero (hard):** AI Act + RGPD manifests / processed / LanceDB chunks / existing tests are byte-identical. The slices only ADD `nis2`/`dora`; the integration only WIDENS literals additively. A full AI-Act+RGPD regression run is part of the gate.
- **Honest-partial is per-corpus and native to Approach 1.** A corpus that intractably resists the PDF parser within the time-box is simply not landed (no manifest → not in `CORPORA_WITH_MANIFESTS` → not indexed → not in the gold set); recorded transparently in decisions §H14 + a follow-up ADR (rag-ingest step 10). No fabricated coverage, no silent parser hack (§22.22).
- EUR-Lex fetch errors / consolidated-PDF-URL drift: surface loudly with the actionable CELEX/URL (the ADR-0003 lesson: smoke-confirm the live fetch path early in each slice before parser work). Allowlist (`eur-lex.europa.eu`) already governs fetch (§13/§18.6).
- No new MCP (a JS-rendered EUR-Lex change does NOT authorise installing playwright without the propose-and-wait rule — rag-ingest "what this skill does NOT do").

## 6. Testing

- Per-corpus parser unit test (fixture-based, mirroring the proven existing corpus parser test).
- `Manifest.model_validate_json` round-trips for each new manifest.
- Widened-literal changes: existing api/contract, evals-schema, and Streamlit tests stay green AND the 4-value `Norma` is accepted (a `nis2`/`dora` request validates).
- $0 cross-corpus retrieval test (new gold cases find the correct articles; no corpus leakage) + AI Act/RGPD retrieval/agent regression-zero.
- `make ingest` smoke (loads the landed corpora).
- Full `python -m pytest -q` gate green, coverage ≥90% (no override; no paid path involved).

## 7. Gate / definition of done (operative plan §16.3, §25, §24 Módulo 3; honest §16.3 reframe per D3)

1. NIS2 and DORA landed (CELEX/VERSION/EXPECTED_ARTICLE_COUNTS pinned, PDF fetched, parsed, validated, manifests committed + Git-LFS raw/processed) — OR a corpus honestly declared deferred-partial per D2 with the documented rationale + follow-up ADR.
2. The 6 hardcoded 2-value spots (§1) widened to the canonical 4-value `Norma`; `CORPORA_WITH_MANIFESTS` widened only to landed corpora; AI Act/RGPD byte-identical (§22.18, regression run green).
3. LanceDB rebuilt over the landed corpora; cross-corpus retrieval works.
4. Gold set: ≥5 NIS2 + ≥5 DORA chat cases + cross-corpus cases (for each landed corpus); the $0 deterministic retrieval verification passes; LLM-judge metric eval + §17 thresholds **explicitly deferred to H15** (documented reframe, NOT a fabricated pass).
5. Full test gate ≥90% green; `make ingest` loads the landed corpora.
6. ADR 0015 + decisions §H14 (incl. the honest §16.3 reframe + any partial + the SKILL.md-vs-PDF note) + evidence_matrix + CLAUDE.md §27 (→ Hito siguiente H15) + memory roll-forward.
7. Tag `v0.1.4-h14`. **H14 spends $0** (no paid LLM run).

## 8. Non-goals (YAGNI)

No chunking/embedding redesign (corpus-agnostic, reuse H2); no LLM-judge metric eval in H14 (H15); no §17-threshold gating in H14; no agent/Auditor/graph logic change (corpus-agnostic once `Norma` widened); no document-mode special-casing (widen literals consistently for both modes); no new MCP; no calibration (H15); no new skill (`rag-ingest` already active since H1).

## 9. Risks

- **NIS2(Directive)/DORA(Regulation) PDF structure differs from AI Act/RGPD (central risk).** The consolidated-PDF layout (article numbering, annexes, recitals) may not match the proven parser. Mitigation: D2 best-effort + honest documented per-corpus partial; scoped parser adaptation only within the time-box; follow-up ADR (rag-ingest step 10); never silent-hack.
- **`rag-ingest` SKILL.md appears Formex-centric vs the ADR-0003 PDF reality.** Follow the actual proven PDF path; flag SKILL.md staleness as a doc follow-up (do not blindly follow stale steps).
- **EUR-Lex consolidated-PDF availability / URL pattern for these CELEX.** Smoke-confirm the live fetch path early in each slice (the ADR-0003 H1 lesson) before investing in parser work.
- **Git-LFS for new `corpus/raw/`+`corpus/processed/`.** Mirror exactly how AI Act/RGPD handle LFS pointers (rag-ingest step 8).

## 10. Boundary contract H14 inherits

Backend H1–H3 (rag chunking/embeddings/store, citation validator), Analyst, Auditor, the chat/document graphs are **read-only / regression-zero**; H14 touches only: corpus-ingest constants (`ingest.py`/`validate.py`), the 6 input-validation literals (additive widening, §1), the gold set, and the LanceDB rebuild (existing H2 machinery). AI Act + RGPD must stay stable (§22.18 — if NIS2/DORA exceed the time-box, declare partial/future, do not destabilise the working corpora). `.env` PROHIBITED as `.env.example` (single `.env`; not relevant here — no new keys). gitleaks CI-enforced; local commits `SKIP=gitleaks` (never `--no-verify`). Decisions log = TFM backbone (§11.b/§21.12); post-merge pattern: `docs(h14): populate post-merge SHA` direct on main + annotated tag (H10–H13 precedent). Honest metrics §22.22 (no fabricated thresholds; partial/contaminated → document transparent, never re-run/hack for prettier numbers — H1-PDF-pivot/H12/H13 precedent). subagent-driven-development 2-stage + final whole-branch review.

## 11. References

- CLAUDE.md §7 (corpus; §7.2 NIS2/DORA), §16.3 H14, §22.18 (AI Act/RGPD stable before NIS2/DORA), §24 Módulo 3, §16.2 #5 (recall-based safety gate, the $0 verification basis).
- ADR 0003 (corpus pipeline architecture / H1 PDF pivot). Spec: `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md`. Skill: `.claude/skills/rag-ingest/SKILL.md`.
- Decisions log §H1 (corpus pipeline + PDF pivot), §H10 (gate-reframe precedent), §H13 (honest Done-when reframe precedent, §22.22). Operative plan H14 (the ~3-day partial-threshold decisión-previa).
