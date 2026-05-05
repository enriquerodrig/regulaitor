---
name: citation-validator
description: Use this skill when modifying src/regulaitor/citation/validator.py or its policy. Documents the canonical 3-check validation procedure and the rules for evolving it (e.g. adding a fuzzy-fallback layer in H15).
version: 0.1.0
---

# Citation validator skill

## Why

The validator is the operational core of the "no citation, no answer" rule
(CLAUDE.md §6). Any change here directly affects whether the system can
produce auditable answers. This skill encodes the disciplined evolution path.

## Activation

Activate when:
- Modifying `src/regulaitor/citation/validator.py`.
- Modifying `_normalize` in `src/regulaitor/rag/chunking.py` (validator depends on it).
- Adding a new validation check (e.g. version-consistency, language-consistency).
- Calibrating thresholds in H15.

Do NOT activate for unrelated tests, schema field additions in
`citation/schemas.py`, or refactors that don't change validation semantics.

## Canonical procedure (H3 baseline)

The validator runs 3 strict checks in order, with fail-fast on first failure:

1. `article_exists`: `(norma, articulo)` is in the manifest.
2. `apartado_exists` (if citation has an apartado): the apartado is a known
   paragraph for that article.
3. `text_normalized_match`: `_normalize(citation.text)` is a substring of
   `_normalize(target_text)`, where `target_text` is the apartado paragraph
   when an apartado is given, else the full article text.

`validated` = AND of the checks. `reason` field carries a specific code:
- `article_not_found:`
- `apartado_not_found:`
- `text_not_in_apartado:`
- `text_not_in_article:`

## Adding new checks

When proposing a new check (e.g. `version_consistent`):
1. Open a brainstorming session per `superpowers:brainstorming` skill.
2. Document the threat model the new check closes (concrete attack scenario).
3. Add to `AuditResult` schema as a new boolean field (Pydantic v2 backwards
   compatible).
4. Update validator.py with fail-fast ordering: cheaper checks first, expensive
   last.
5. Update tests in `tests/unit/citation/test_validator.py` with happy + failure
   cases.
6. Update this SKILL.md procedure section.
7. Update `docs/technical_decisions_log.md` with the rationale.

## Adding fuzzy fallback (H15)

When H8/H15 evaluation shows that strict normalized match has too many false
negatives:
1. Run the calibration with the gold set; produce a precision-recall curve.
2. Choose a threshold from the curve and document the choice.
3. Add a fuzzy fallback layer: if strict match fails, run fuzzy match; on
   match, set `validated=False, requires_human_review=True, confidence=<score>`.
   Do NOT silently accept — surface the doubt.
4. Strict match output unchanged; fuzzy is only for diagnostic info.
5. Update tests with adversarial near-paraphrase cases.

## Forbidden changes

- Replacing strict match with fuzzy as the default.
- Accepting citations on string-similarity score above any threshold without
  a human review hook.
- Removing `reason` codes (downstream Auditor logic depends on them).
- Validator that depends on the LLM model that produced the citation
  (validator must be deterministic).
