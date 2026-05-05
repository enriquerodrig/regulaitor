---
name: prompt-versioning
description: Use this skill when adding, modifying, or rolling back agent prompts in src/regulaitor/agents/prompts/ to keep the project's prompt history reproducible and auditable. Activates from H4 onwards (Analyst, Auditor, Council).
version: 0.1.0
---

# Prompt versioning skill

## Why

Reproducibility (CLAUDE.md §10.6): every Analyst/Auditor/Council prompt must
carry a version + changelog so a TFM reviewer can trace which prompt produced
which gold-set result.

## When to use

Activate this skill the moment you create a new prompt file, modify an existing
one, or revert a prompt. Do NOT activate it for incidental README updates that
mention prompts but do not change them.

## Procedure

1. **Path convention.** Prompts live in
   `src/regulaitor/agents/prompts/<agent>/<role>.v<MAJOR>.<MINOR>.md`.
   Examples: `analyst/system.v1.0.md`, `auditor/decide.v2.1.md`.
2. **Header block.** Every prompt file starts with this YAML frontmatter:
   ```yaml
   ---
   agent: <retriever|analyst|auditor|council>
   role: <system|user-template|few-shot>
   version: <MAJOR>.<MINOR>
   created: <YYYY-MM-DD>
   author: <github username>
   model_compatibility: [<llm-id-1>, <llm-id-2>]
   changelog:
     - <YYYY-MM-DD>: <one-line summary>
   ---
   ```
3. **Versioning rules.**
   - **MAJOR bump:** breaking change to expected agent behaviour (different
     output schema, removal of an instruction the system relies on, change in
     refusal policy).
   - **MINOR bump:** non-breaking refinement (better few-shot example, more
     concrete instruction, accent/typo fix).
   - **No silent edits.** Even a typo fix is a MINOR bump.
4. **Forbidden in prompts.**
   - Hardcoded model names (use `models/router.py` to bind).
   - Hardcoded user data or PII.
   - Anything that bypasses the Auditor.
5. **When changing a prompt.**
   - Copy the previous file with the new version number.
   - Edit and update the changelog.
   - Run `make eval` against the gold set; record the new metrics in
     `evals/reports/<YYYY-MM-DD>-prompt-vN.M.md`.
   - Commit: `feat(prompts/<agent>): bump <role> v<old>->v<new> — <reason>`.
6. **Rolling back.**
   - Move the failing prompt to `.archive/` with a comment in the changelog.
   - Switch the active version reference in `models/config.py`.

## What this skill does NOT cover

- Embedding model versioning — that lives in `corpus/manifests/*.json` per
  LanguageEntry and is governed by ADR 0004.
- Changes to non-prompt agent code — those follow normal commit conventions.
