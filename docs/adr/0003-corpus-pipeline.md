# ADR 0003 — Corpus pipeline architecture

- **Status:** Accepted
- **Date:** 2026-05-04 (H1 closure)
- **Deciders:** Project owner.
- **Supersedes:** none. **Refines:** open questions §12 of the H1 spec.

## Context

H1 needs to land the AI Act and GDPR corpora into the repository in a form that downstream RAG (H2), the citation validator (H3) and the agents (H4+) can consume without re-implementing source parsing. The ingest must be reproducible bit-for-bit on a clean clone, idempotent on re-runs, and bilingual (Spanish + English). Without this foundation, every later "no citation, no answer" claim collapses.

The H1 design spec (`docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md`) committed at the start of H1 was implementation-agnostic about which fetch source to use; it pinned the modules and the manifest contract. Two open questions were deliberately deferred to implementation: (a) the exact EUR-Lex URL pattern that returns Formex 4 XML, and (b) the reliability of EUR-Lex `If-Modified-Since`. This ADR records the architecture that emerged after both questions were answered by smoke-running against the live service.

## Decision

### Module layout

Six modules under `src/regulaitor/corpus/`, each with one clear responsibility:

| Module | Responsibility | Public surface |
|---|---|---|
| `schemas.py` | Pydantic v2 contract for manifest, articles, language entries. | `Manifest`, `ArticleEntry`, `LanguageEntry`, `HttpCacheEntry`, `Stats`, `Norma`, `Language`, `SourceFormat` |
| `manifest.py` | Atomic load / save / per-article diff over the manifest file. | `load`, `save_atomic`, `diff`, `ManifestDiff` |
| `eurlex.py` | HTTP client with allowlist, conditional requests, retry. | `EurLexClient`, `FetchResult*`, `EurLexAllowlistError` |
| `formex_parser.py` | Formex 4 XML parser (lxml, XPath). | `FormexParser`, `FormexValidationError`, `ParsedArticle`, `ParsedParagraph` |
| `html_parser.py` | EUR-Lex HTML fallback parser (BeautifulSoup). | `HtmlParser`, `HtmlParseError` |
| `pdf_parser.py` | EUR-Lex consolidated PDF parser (pdfplumber + regex). | `PdfParser`, `PdfParseError` |
| `validate.py` | Per-corpus invariants (article count, no duplicates, no empty). | `validate`, `ValidationReport`, `ValidationFailure`, `EXPECTED_ARTICLE_COUNTS` |
| `ingest.py` | Orchestrator wiring all the above. | `run`, `IngestSummary` |

The CLI entry point is `python -m scripts.ingest`. Manifests live as plain JSON in `corpus/manifests/`. Raw downloads and parsed outputs live in `corpus/raw/` and `corpus/processed/`, both tracked via Git-LFS.

### Three source formats, one parser interface

All three parsers expose `parse(bytes) -> list[ParsedArticle]`. The orchestrator selects the parser via a dict dispatch keyed on `fetch_format ∈ {"formex4", "html", "pdf"}`. The Pydantic `SourceFormat` literal carries the same values, ensuring compile-time consistency.

This deviates from the original spec, which scoped H1 to Formex 4 + HTML only and reserved PDF for H5 (user documents). The reason for adopting PDF in H1 is operational, not architectural — see "Pivot to PDF" below.

### Idempotency

Two layers of caching:

1. **HTTP layer** (`eurlex.py`): `If-Modified-Since` + `If-None-Match` headers from the previous fetch's manifest entry. A 304 short-circuits to `FetchResultNotModified` and the orchestrator reuses the cached `corpus/processed/` data.
2. **Article layer** (`ingest._build_manifest`): SHA256 hash per `(article, language)`. When the new hash matches the manifest's stored hash, the previous `LanguageEntry` is preserved verbatim — including the `chunks` list and `embedded_at` timestamp that H2 will populate. This keeps re-runs cheap when only one article in the corpus has changed: H2 re-embeds only the changed article, not the whole corpus.

Local-only mode (`--use-local-only`) skips layer 1 entirely; layer 2 still applies, so re-running ingest after editing a local file only re-processes the touched articles.

### Validation as the safety net

After parsing, `validate.py` enforces:
- Article count matches `EXPECTED_ARTICLE_COUNTS[corpus]` (113 for AI Act, 99 for GDPR; pinned per Reglamento (UE) 2024/1689 and Reglamento (UE) 2016/679).
- No duplicate article numbers.
- No empty article bodies.

`strict=True` raises `ValidationFailure` and the orchestrator aborts the manifest write atomically — the previous valid manifest stays intact. This guarantees H2 always sees either a fully valid manifest or no new manifest at all.

### Atomicity

All disk writes — raw, processed, manifest — go through `_write_atomic`/`save_atomic` which writes to `<path>.tmp` and `os.replace()`s into place. No partial writes can corrupt H2's view.

## Pivot to PDF (operational reality vs design intent)

The spec assumed Formex 4 XML would be directly addressable by CELEX over EUR-Lex's `legal-content/{LANG}/TXT/?uri=CELEX:{celex}` endpoint with `Accept: application/xml`. The H1 smoke run revealed this is not true:

- **Formex endpoint returns HTTP 200 with empty body** (0 bytes) when content negotiation doesn't yield a Formex resource for the requested CELEX. This is an EUR-Lex frontend behaviour, not a routing error.
- **HTML endpoint returns HTTP 202 with a CloudFront WAF challenge page** (~2 KB of JavaScript that solves a bot puzzle and redirects to the real content). Without a JS engine, every non-browser client gets the challenge.

Four options were evaluated:
1. Cellar / Publications Office RDF (parse RDF, follow manifestation URIs). Robust but adds `rdflib` and a 2-3h research detour.
2. Beat the WAF with browser headers / cookies. Tested with full Chrome User-Agent and `Accept-Language` — still gets 202 challenge.
3. Playwright headless browser. Fragile, contradicts ADR 0002's "no `playwright` MCP in H1".
4. **Pragmatic snapshot: download PDFs manually once, commit to LFS, ingest from local file.**

Option 4 was chosen. The operator downloaded 4 PDFs (AI Act ES + EN, GDPR ES + EN) from the EUR-Lex frontend in a real browser (which solves the WAF challenge) and placed them in `corpus/raw/`. The orchestrator's new `--use-local-only` mode reads from disk without touching HTTP. The PDFs are tracked in Git-LFS as the reproducible source snapshot.

### Why this is acceptable for H1

- **Honest narrative**: "EUR-Lex blocked our automated API access; we pivoted to a versioned local snapshot" is more defensible academically than "we beat the WAF" or "we faked it with mocks".
- **Architectural strength**: the pipeline now supports three source formats. Extending to NIS2/DORA in H14 may use any of them depending on what's available.
- **No infrastructure debt**: `pdfplumber` was already pinned in CLAUDE.md §10.2 for H5 (user documents); we just brought the dependency forward by 4 hitos.
- **HTTP path preserved**: `eurlex.py` still works against any future endpoint that doesn't require browser automation. When H14 ships, we re-evaluate (Cellar API may have improved, EUR-Lex may have relaxed the WAF, or we adopt option 1).

### Why PDF parsing is not as fragile as it sounds for this corpus

EU consolidated regulation PDFs share a strict typographical convention:
- Article headers occupy their own line as `Article N` / `Artículo N` (no trailing punctuation).
- ToC entries are visually distinguished by trailing dot leaders and page numbers (`Article 1 — Subject matter ............ 12`), so a strict `^\s*(?:Article|Artículo)\s+\d+\s*$` regex excludes them naturally.
- Annex back-references appear inline (`...in accordance with Article 49(1)`), so they don't match the line-anchored regex.

The one corner case observed (AI Act EN has "Article 49" appearing twice as a header — once as the body article, once inside an Annex VIII reference table) is handled by **keep-first-by-offset** deduplication: the body article precedes the annex in document order, so keep-first picks the right one.

Smoke run confirmed all four PDFs produce exactly the expected article counts (113 + 99) without any per-document tuning.

## Alternatives considered

- **Single-file ingest script.** Rejected: mixes HTTP, parsing, validation; hard to test in isolation; H2 cannot reuse the parsers cleanly.
- **DVC instead of Git-LFS.** Rejected: <1 GB total expected for AI Act + GDPR + NIS2 + DORA combined. DVC adds external infrastructure that doesn't earn its keep at this scale.
- **Akoma Ntoso XML over Formex 4.** Rejected at H1 brainstorming: GDPR consolidated isn't fully published in Akoma Ntoso; running two structured-XML parsers is more complex than Formex + HTML fallback. After the WAF reality check, both were moot.
- **Per-chunk hashes in manifest** (instead of per-article). Rejected: chunks live in H2; tying H1 manifest to chunk identity creates false coupling. Hashing per article and letting H2 derive chunk identity from article text keeps the boundary clean.
- **HttpUrl for `source_url` field.** Rejected during Task 1 review: URLs are constructed internally and exact-match is required for HTTP cache headers (decisions log entry "source_url se modela como str").
- **Retry on HTTP 5xx in `EurLexClient`.** Rejected during Task 7 review: 5xx from EUR-Lex usually means structural outage; retry storms are antisocial. Orchestrator-level retry via `make ingest` cron is the right boundary.

## Consequences

### Positive

- Each module is independently testable; per-module coverage ≥85% achievable without integration shortcuts. H1 closes at 91% global coverage on `src/regulaitor/corpus/`.
- Re-runs are cheap: HTTP 304 short-circuits download (when HTTP path is alive), per-article hash short-circuits embedding cost in H2.
- Three source formats (Formex / HTML / PDF) give us optionality for H14 (NIS2 + DORA) and resilience against EUR-Lex publishing-format changes.
- Adding NIS2 / DORA in H14 means updating constants (`CELEX`, `VERSION`, `EXPECTED_ARTICLE_COUNTS`) and adding fixtures — no architecture change.
- The `rag-ingest` skill (`.claude/skills/rag-ingest/SKILL.md`) codifies the procedure for adding a new corpus.

### Negative

- HTML and PDF parsers are heuristic — EUR-Lex template changes will require manual updates. Mitigation: keep parsers small (each ≤120 lines), document the calibration corpora in module docstrings, record any update in `docs/technical_decisions_log.md`.
- `tiktoken` (`cl100k_base`) is used as a token-count proxy. BGE-M3 uses an XLM-RoBERTa tokenizer, so the chunking threshold check in H2 will need to switch tokenizers. The `1000-token` threshold is generous enough that the proxy is acceptable here.
- The `--use-local-only` mode bypasses the HTTP cache layer, so re-runs always re-extract text from PDFs (slow: ~115 seconds for the four files combined). Acceptable since `make ingest` runs on consolidation refresh, not per request.
- The H1 manifests currently carry `source_format: "pdf"`. When the HTTP path is rehabilitated in H14, we will re-ingest and the value will switch to `formex4` or `html`. The `version` field captures the consolidation date so the H1 PDF snapshot remains identifiable.

## References

- `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` — H1 design spec.
- `docs/superpowers/plans/2026-04-30-h1-corpus-ingest.md` — H1 implementation plan.
- `docs/technical_decisions_log.md` H1 section, especially the closure entry "Pivote a PDF tras WAF de EUR-Lex".
- `docs/adr/0001-project-scope.md` — parent ADR.
- `docs/adr/0002-skills-mcps-roadmap.md` — companion ADR; H1 closure note added.
- `corpus/manifests/ai_act.json`, `corpus/manifests/gdpr.json` — concrete output.
