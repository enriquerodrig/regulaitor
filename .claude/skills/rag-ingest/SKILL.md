---
name: rag-ingest
description: Use this skill when adding a new regulatory corpus (NIS2, DORA, or any future norma) following the H1 RegulAItor pattern. Ensures the new corpus integrates with the existing fetch/parse/validate/manifest pipeline without ad-hoc divergence.
version: 1
allowed-tools: Read, Edit, Write, Bash
---

# Skill: rag-ingest

## When to use

A new regulatory corpus is being added to RegulAItor. Examples:
- "Add NIS2 to the corpus."
- "Ingest DORA in Spanish and English."
- "Replace AI Act with the next consolidated version."

Do NOT use this skill for non-regulatory documents (those go through the user document pipeline in src/regulaitor/document/).

## Procedure

1. Read `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` and the latest H1 closure entry in `docs/technical_decisions_log.md`.
2. Confirm the EUR-Lex CELEX, the consolidated date, and the languages to fetch with the owner.
3. Update constants:
   - `src/regulaitor/corpus/ingest.py` `CELEX` and `VERSION` dicts.
   - `src/regulaitor/corpus/validate.py` `EXPECTED_ARTICLE_COUNTS`.
4. Add fixture files in `tests/fixtures/formex/{new_corpus}_{lang}_mini.xml` for ES and EN (5-10 articles, hand-crafted).
5. Add a unit test in `tests/unit/corpus/test_formex_parser.py` parametrising the new fixture.
6. Run `uv run python -m scripts.ingest --corpus {new_corpus}` against EUR-Lex (smoke).
7. Verify article count matches `EXPECTED_ARTICLE_COUNTS`.
8. Commit `corpus/manifests/{new_corpus}.json` plus LFS pointers for `corpus/raw/` and `corpus/processed/`.
9. Update `docs/technical_decisions_log.md` with the new corpus entry (version, languages, smoke run stats).
10. If the new corpus reveals a Formex schema variation the parser doesn't handle, raise a follow-up ADR — do NOT silently extend `formex_parser.py` without recording the decision.

## What this skill does NOT do

- Does not chunk, embed or write to LanceDB. That is H2 territory.
- Does not modify `src/regulaitor/agents/` or `mcp_server/`.
- Does not bypass the propose-and-wait rule for new MCPs (e.g. don't install `playwright` even if EUR-Lex changes scheme).

## Verification

Before merging:
- `uv run pytest --cov-fail-under=90` green.
- Manifest round-trips through `Manifest.model_validate_json`.
- Smoke output recorded in `docs/technical_decisions_log.md`.
