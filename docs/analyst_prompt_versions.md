# Analyst prompt version timeline

Status of each `agents/prompts/analyst/` + `agents/prompts/document_analyst/` version
as of 2026-05-28 (Stage 3 pre-H16 polish). Prompts are loaded via
`agents/analyst.py` env seam (`REGULAITOR_ANALYST_PROMPT_VERSION`) with
role-aware defaults; env-unset = production.

## chat role (`agents/prompts/analyst/`)

| Version | First shipped | Status (2026-05-28) | Retain reason | Removal earliest |
|---|---|---|---|---|
| `v1.0` | H4 (2026-05-05) | **OPT-IN** (production default until v0.1.21) | TFM defense: original H4 baseline; regression A/B; cited by ADR-0006 / ADR-0010 / ADR-0026 | post-H17 (TFM defense closes; safe to delete once memoria + slide deck + video demo committed) |
| `v1.1` | H15 (2026-05-19) | OPT-IN | H15 intermediate iteration (Intervention A; loaded by `test_analyst_v1_1_loads.py`); ADR-0016 references it as the calibration probe | post-H17 |
| `v1.2` | H15 (2026-05-19) | OPT-IN | H15 candidate frozen for A/B; cited by ADR-0016 + H15 paid run reports; `test_analyst_v1_2_loads.py` pins frontmatter | post-H17 |
| `v1.3` | v0.1.15 (2026-05-21) | OPT-IN | Gap-analysis chat mode (Hard rule 8 NL auto-detection); ADR-0020; `test_analyst_v1_3_loads.py` | post-H17 |
| `v1.4` | v0.1.17.1 (2026-05-22) | OPT-IN | Force-Finding-emission (Hard rule 9); ADR-0023; production default v0.1.20-v0.1.21 (then flipped to v1.5 per ADR-0027 final review C4) | post-H17 |
| `v1.5` | v0.1.21 (2026-05-24) | **PRODUCTION DEFAULT** for chat | Finding-based refusal with corpus-grounded citation; ships the §6-safe refusal pattern compatible with Tier 2 Capa A+B+C (ADR-0027 C4); 1004+ tests gate on it | active |

## document_analyst role (`agents/prompts/document_analyst/`)

| Version | First shipped | Status (2026-05-28) | Retain reason | Removal earliest |
|---|---|---|---|---|
| `v1.0` | H5 (2026-05-07) | OPT-IN (production default until v0.1.28) | Original H5 baseline; regression A/B; ADR-0007; default for doc role before v0.1.28 found the placeholder citation bug (ADR-0033) | post-H17 |
| `v1.6` | v0.1.28 (2026-05-27) | **PRODUCTION DEFAULT** for document_analyst | Finding-based refusal (Hard rule 4 inviolable placeholder forbid + Rule 2 cite scope article when context insufficient); FOURTH-layer §6 architecture (ADR-0033); paid v0.1.28 measurement eliminated placeholder bug | active |

## Why keep dormant versions

Each retained version has at least one of:

1. **Regression A/B test** — env-seam allows quick re-evaluation if a future intervention regresses (e.g. v0.1.23 REVERT could have been compared against v1.4 baseline via env if needed).
2. **TFM defense memory** — the methodology contribution (§22.22 lineage) refers to prompt evolution; deleting an intermediate prompt would orphan its ADR + decisions_log §X reference.
3. **Frontmatter pinning tests** — `tests/unit/test_analyst_v1_*.py` (+ doc equivalents) load each version's prompt file; deleting the file would break tests.

## Disk cost

Each prompt file is ~10-20 KB (markdown). 8 retained prompts total ≈ 100 KB. Negligible compared to LanceDB index (~50 MB) + corpus (~50 MB).

## Removal protocol (post-H17)

Once H17 TFM cierre académico is tagged (`v1.0.0`):

1. Determine the "memoria-final canonical version" (likely v1.5 chat + v1.6 doc).
2. Mark v1.0-v1.4 chat + v1.0 doc as ARCHIVE-only (move under `docs/milestones/prompt_versions/`).
3. Remove corresponding `test_analyst_v1_X_loads.py` files.
4. Update ADR references to point at the archive path.
5. New tag `v1.0.1-cleanup` or fold into post-H17 hygiene.

**NOT pre-H17**: removal before H17 would destroy the TFM defense evidence chain.

## See also

- `agents/analyst.py` — env seam + role-aware default ternary (line ~125).
- ADR-0026 (v0.1.20 paid validation A/B; v1.0 vs v1.4 flip decision).
- ADR-0027 final review C4 (v1.4 → v1.5 production flip; Capa A+B+C compatibility).
- ADR-0033 (v0.1.28 doc role v1.0 → v1.6 flip; placeholder bug elimination).
- `tests/unit/test_analyst_v1_*.py` — frontmatter regression pins.
