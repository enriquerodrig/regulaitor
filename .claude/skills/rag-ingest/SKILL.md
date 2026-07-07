---
name: rag-ingest
description: Use this skill when adding a new regulatory corpus (NIS2, DORA, or any future norma) following the H1 RegulAItor pattern. Ensures the new corpus integrates with the existing fetch/parse/validate/manifest pipeline without ad-hoc divergence.
version: 1
allowed-tools: Read, Edit, Write, Bash
---

# Skill: rag-ingest

## When to use

A new regulatory corpus is being added to RegulAItor. The store currently holds 9 corpora (ai_act, gdpr, nis2, dora, dora_rts_incident, dora_rts_class, amlr, mica, tfr); this skill covers adding the next one. Examples:
- "Add the next DORA RTS to the corpus."
- "Ingest a new AML/CFT instrument in Spanish and English."
- "Replace AI Act with the next consolidated version."

Do NOT use this skill for non-regulatory documents (those go through the user document pipeline in src/regulaitor/document/).

## Procedure

1. Read `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` and the latest H1 closure entry in `docs/technical_decisions_log.md`.
2. Confirm the EUR-Lex CELEX, the consolidated date, and the languages to fetch with the owner.
3. Update constants:
   - `src/regulaitor/corpus/ingest.py` `CELEX` and `VERSION` dicts.
   - `src/regulaitor/corpus/validate.py` `EXPECTED_ARTICLE_COUNTS`.
4. Fetch the base-act PDF from EUR-Lex via Playwright headless (the WAF blocks curl/httpx) and stage it under `corpus/raw/` for the LFS snapshot. Add a parser fixture/test alongside the existing `tests/unit/corpus/` suite (PDF path via `pdf_parser.py` is the operational one since the H1 ADR-0003 PDF pivot; the Formex parser and `tests/fixtures/formex/` remain only as a legacy fallback).
5. Add a unit test in `tests/unit/corpus/` covering the new corpus fixture.
6. Run `uv run python -m scripts.ingest --corpus {new_corpus} --use-local-only` against the staged snapshot (smoke).
7. Verify article count matches `EXPECTED_ARTICLE_COUNTS`.
8. Commit `corpus/manifests/{new_corpus}.json` plus LFS pointers for `corpus/raw/` and `corpus/processed/`.
9. Update `docs/technical_decisions_log.md` with the new corpus entry (version, languages, smoke run stats).
10. If the new corpus reveals a PDF layout (or legacy Formex schema) variation the parser doesn't handle, raise a follow-up ADR — do NOT silently extend `pdf_parser.py` / `formex_parser.py` without recording the decision.

## What this skill does NOT do

- Does not chunk, embed or write to LanceDB. That is H2 territory.
- Does not modify `src/regulaitor/agents/` or `mcp_server/`.
- Does not bypass the propose-and-wait rule for new MCPs. Note: since H14, EUR-Lex's CloudFront WAF blocks curl/httpx bot fetches, so the base-act PDF is acquired via Playwright headless (in-browser JS-challenge solve) and then ingested through `--use-local-only` from the LFS snapshot. The `httpx` `EurLexClient` remains as a fallback path but is not the operational one.

## Verification

Before merging:
- `uv run pytest` green (coverage gate is `--cov-fail-under=85` in pyproject addopts).
- Manifest round-trips through `Manifest.model_validate_json`.
- Smoke output recorded in `docs/technical_decisions_log.md`.
