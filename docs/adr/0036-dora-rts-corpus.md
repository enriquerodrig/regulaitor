# ADR 0036 — DORA Level-2 RTS Corpus Expansion (Fase 3, HX)

- **Status:** Accepted
- **Date:** 2026-06-10 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0003 (corpus pipeline — live-fetch→local pivot lineage this continues),
  0004 (RAG architecture — corpus-agnostic chunking/embedding; reused unchanged),
  0015 (NIS2+DORA corpus expansion — the direct "add-a-norma" precedent).

## Context

HX founder constraint #2 ("expand the regulatory corpus, ranked by buyer willingness-to-pay").
Fase 3 was scoped as "DORA RTS + consolidated versions of the 4 corpora". A `$0` scoping pass
(workflow `wf_2341813a-aee`, 11 agents, research→adversarial-verify, 5/5 CELEX verified
high-confidence; `docs/_handoff/fase3_scoping.md`) reframed the scope:

**The "consolidated versions of the 4" is a verified no-op.** No operatively-different consolidated
text exists to re-ingest: AI Act (`32024R1689`) has no consolidated version (no amending act in
force); GDPR is **already** ingested as the consolidated `02016R0679-20160504`; NIS2's consolidated
snapshot carries the base-act date `20221227` (only corrigenda, no operative amendment); DORA
(`32022R2554`) has no consolidated version (no amending act). EUR-Lex only mints a `0YYYY...-YYYYMMDD`
consolidated text when an **amending act** modifies the base; corrigenda and Level-2 RTS/ITS do not.
Therefore the regression risk of re-ingesting consolidated text (gold-set citation drift against the
text-match validator) **evaporates** — there is nothing to replace.

The genuinely valuable, low-risk deliverable is the **DORA Level-2 RTS** that makes the incident-
reporting timelines citable. dora-003 (existing gold) already passes by design — it expects the
system to say the 4h/24h/72h timelines are **not** in DORA and are delegated to RTS (DORA art 20).
Adding the RTS is therefore a **new capability** (citing the concrete timelines), not a fix to
dora-003, which is left byte-unchanged.

## Decision

### D1 — Two new normas, separate from the DORA base act

The two RTS are distinct legal acts with their own CELEX and their own article numbering (both start
at Article 1; both have an Article 5), so they cannot share the `dora` base-act norma without
ambiguous `(norma, articulo)` citations. They are added as two normas:

- **`dora_rts_incident`** — Commission Delegated Regulation (EU) 2025/301 (CELEX `32025R0301`,
  OJ 2025-02-20, **7 articles** ES+EN). Article 5 carries the time limits: initial notification
  ≤4h from classification as major (and ≤24h from awareness); intermediate report ≤72h from the
  initial; final report ≤1 month after the (latest updated) intermediate.
- **`dora_rts_class`** — Commission Delegated Regulation (EU) 2024/1772 (CELEX `32024R1772`,
  OJ 2024-06-25, **13 articles** ES+EN). Criteria + materiality thresholds for classifying an ICT
  incident as "major" (the prerequisite that starts the 4h clock).

The companion ITS (Implementing Reg (EU) 2025/302, `32025R0302` — templates/forms only, no
timelines) was deliberately **excluded** (no citable substantive obligations; user decision).

Adding two normas touched the same family of hardcoded enumeration sites H14 mapped (the closed
`Norma = Literal[...]` model): the two type Literals, `ALL_NORMAS`, `CORPORA_WITH_MANIFESTS`,
`EXPECTED_ARTICLE_COUNTS`, the `CELEX`/`VERSION` ingest maps, the **three** CLI `--corpus` gates
(`scripts/ingest.py`, `scripts/rag_build.py`, `scripts/analyze.py`), the API `AskRequest.corpus`
Literal + `routes_analyze` guard, the two UI `_CORPUS_CHOICES` + the `_NORMA_STYLE` chip map, and
`GoldCaseDoc.corpus_esperado`. **The closed-Literal model costs ~15 sites per norma; constraint #2
will keep hitting this** — a registry derived from manifests is a worthwhile future refactor,
deliberately NOT done here (mirror H14 for regression-zero). To reduce the miss-risk, the two sites
the Fase 3 adversarial review caught (`scripts/analyze.py` `_VALID_CORPUS` and
`GoldCaseDoc.corpus_esperado`) were rewired to derive from the canonical `ALL_NORMAS` / `Norma`
rather than re-list the members (review findings NEC-1 / NEC-2).

### D2 — Source / format: HTML via Playwright WAF bypass + new 2025 OJ format

EUR-Lex's CloudFront WAF (ADR-0003/0015 lineage) returns HTTP 202 challenge to programmatic fetch
of **both** the PDF and the HTML endpoints; only full browser *navigation* passes. Unlike H14 (which
captured PDFs), the 2025/2024 acts' PDF-generation endpoint stayed WAF-challenged on every
programmatic attempt, so the **rendered HTML** (`div#docHtml`) was captured via Playwright navigation
+ same-origin DOM read and saved to `corpus/raw/{norma}_{lang}.html` (verbatim document content).
`source_format = html` for these normas (the existing 4 stay PDF; the Manifest records format
per-norma).

The 2025+ EUR-Lex **Official Journal** template renamed the article CSS classes (`sti-art`→`oj-sti-art`,
`normal`→`oj-normal`); `div#art_N` ids are unchanged. `corpus/html_parser.py` gained a **minimal
additive** update recognising both vocabularies (the parser's own docstring invites template-change
updates). This benefits all future EU corpus (every new EU act uses this format). The article
designation (`oj-ti-art`) is intentionally not body text — the article number comes from the id.

### D3 — Article-level citation granularity (accepted limitation)

The HTML parser collapses each article to one paragraph (`apartado="1"`). The RTS is therefore citable
at **article level** (e.g. `dora_rts_incident` art 5 = all timelines), not apartado level. This is
adequate for the incident-reporting use case (the whole of Art 5 is the timelines unit) and documented
as a limitation; apartado-level extraction for the OJ format is a future refinement.

### D4 — §6 invariant byte-unchanged; existing 4 normas regression-zero

`citation/validator.py` and `agents/auditor.py` are **byte-unchanged**. The new corpus is validated
by exactly the same `(norma, articulo, apartado, text-normalized-match)` path: verified that a
verbatim Art 5 snippet validates (`validated=True`) and a fabricated timeline does not
(`validated=False, failed_check=3`). The existing 4 corpora (1569 LanceDB rows) are untouched; the
40 new RTS chunks are additive. `$0` (local BGE-M3 embed, `HF_HUB_OFFLINE=1` for the Windows CRL SSL
bug per ADR-0029).

### D5 — Gold case `dora-rts-001`; dora-003 unchanged

One new chat gold case (`dora-rts-001`, `corpus_esperado="dora_rts_incident"`, `articulos_esperados=["5"]`,
the timelines question) demonstrates the new capability. dora-003 (DORA base-act framing) stays valid
and byte-unchanged. Retrieval grounding confirmed: the timelines query surfaces Art 5 as the top
result (score 0.996).

## Consequences

- The system can now cite the concrete DORA incident-reporting timelines (a real compliance buyer
  need) with a validated corpus citation — the "no citation, no answer" invariant holds for the RTS.
- `html_parser` now handles the 2024+ OJ format → future EU corpus expansion is cheaper.
- The closed-`Norma`-Literal scaling cost is documented as a future-refactor watch-item.

## §22.22 disclosures

1. **Scope reframe (headline):** "consolidated re-ingest of the 4" was a verified no-op; Fase 3
   collapsed to the RTS ingest. Honest reframe presented to and approved by the owner before any work.
2. **HTML not PDF:** the 2025 OJ PDF endpoint stayed WAF-challenged on programmatic fetch; HTML was
   captured instead. The raw file is the verbatim `div#docHtml` content (provenance: CELEX + source_url
   in the manifest; per-article hash over the legal text).
3. **Article-level granularity** (D3): apartado-level citations are not available for the RTS under the
   HTML parser.
4. **Empirical Analyst behavior NOT measured here ($0 milestone):** that the Analyst actually emits a
   correct, validated Art 5 citation for `dora-rts-001` is a paid-LLM measurement, deferred to the next
   paid eval bundle. Retrieval + validator + schema are verified; the model-side answer is not.
5. **AI Act watch-item:** when the Digital Omnibus amending Regulation is published (~July 2026),
   EUR-Lex will mint `02024R1689-<date>` with changed high-risk timelines — a future corpus refresh.

## Alternatives considered

- **Re-ingest consolidated versions of the 4** — rejected: verified no-op (no operatively-different text)
  with non-zero regression risk for nil benefit.
- **One `dora_rts` norma for both acts** — rejected: article-number collision (both start at Art 1)
  makes `(norma, articulo)` citations ambiguous.
- **Synthesize parser-compatible HTML browser-side (no parser change)** — rejected in favour of saving
  verbatim HTML + a small, reusable parser update (more defensible provenance; benefits future corpus).
- **Registry-derived norma set (kill the closed Literal)** — deferred to a future refactor; out of
  Fase 3 scope (mirror H14 for regression-zero).
