# tests/unit/test_analyst_v1_4_loads.py
"""v0.1.17.1 — Analyst prompt v1.4 (force-Finding-emission) load + invariants.

Pins the v1.4 prompt added in v0.1.17.1. Asserts:

1. v1.4 file exists + has Pydantic-style frontmatter (version 1.4 + changelog
   referencing v0.1.17.1 + Hard Rule 9 + force-Finding-emission).
2. Hard rules 1-8 from v1.3 preserved byte-identical in v1.4 (regression
   anchor on gap-analysis chat mode + Q&A + minimal-citation discipline).
3. Hard Rule 9 (force-Finding-emission) present with key anchors:
   'substantive answer', 'INVALID', 'no citation, no answer', 'self-check'.
4. Output contract line 85-86 amendment present:
   'every substantive claim in `text` must map to ≥1 Finding'.
5. Output format section byte-identical to v1.3 (no schema change).
6. Examples 1, 2, 3 from v1.3 preserved byte-identical in v1.4 (regression
   anchor on demonstrated correct behavior on Q&A + 2 gap-analysis paths).
7. Output contract — gap-analysis branch section byte-identical to v1.3
   (regression anchor on v0.1.15 work).
8. All 5 prompt versions (v1.0, v1.1, v1.2, v1.3, v1.4) coexist on disk
   (regression-pin that prior versions stay available for env override;
   production default v1.0 unchanged per ADR-0016 env seam).

The default-when-env-unset regression is already pinned by
`tests/unit/test_analyst_prompt_env_seam.py::test_default_is_v1_0_when_env_unset`
(unchanged in v0.1.17.1).
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS = Path("src/regulaitor/agents/prompts/analyst")
_V10 = _PROMPTS / "system.v1.0.md"
_V11 = _PROMPTS / "system.v1.1.md"
_V12 = _PROMPTS / "system.v1.2.md"
_V13 = _PROMPTS / "system.v1.3.md"
_V14 = _PROMPTS / "system.v1.4.md"

# v1.3 Example 1 (Q&A AI Act high-risk) markers — must appear verbatim in v1.4.
_EX1_START = 'User: "¿Qué dice el AI Act sobre sistemas de alto riesgo?"'
_EX1_END = '     severity: "info"}\n  ]'

# v1.3 Example 2 (gap-analysis precise) markers.
_EX2_START = 'User: "Mi empresa opera un sistema de IA clasificado como alto riesgo'
_EX2_END = '     severity: "medium"}\n  ]'

# v1.3 Example 3 (gap-analysis vague-real) markers.
_EX3_START = 'User: "Creo que tenemos un sistema de IA que podría ser de alto riesgo.'
_EX3_END_HINT = "severity:"  # last line of last finding; we'll extract greedily.


def _extract_block(text: str, start: str, end: str, source: str) -> str:
    """Extract a labeled block; raise AssertionError with diagnostic if missing."""
    try:
        s = text.index(start)
        e = text.index(end, s) + len(end)
        return text[s:e]
    except ValueError as exc:
        raise AssertionError(
            f"Markers not found in {source}. Looking for start={start!r} "
            f"and end={end!r}. Did v1.4 author move/rename the block, or "
            f"did v1.3 drift?"
        ) from exc


def test_v1_4_prompt_loads() -> None:
    """v1.4 prompt file exists + parses frontmatter + body, version 1.4."""
    assert _V14.exists(), f"v1.4 prompt file missing: {_V14}"
    txt = _V14.read_text(encoding="utf-8")
    assert txt.startswith("---"), "missing frontmatter opening"
    assert "version: 1.4" in txt, "frontmatter must declare version: 1.4"
    assert "changelog:" in txt, "frontmatter must include changelog block"


def test_v1_4_preserves_hard_rules_1_through_8_verbatim() -> None:
    """Hard rules 1-8 from v1.3 must appear verbatim in v1.4 (regression
    anchor on gap-analysis chat mode + Q&A + minimal-citation discipline).
    Rule 9 is the ONLY new rule."""
    txt = _V14.read_text(encoding="utf-8")
    rule_anchors = [
        "Every assertion you emit must be supported",  # Rule 1
        "You must cite the EXACT TEXT",  # Rule 2
        "Respond in the same language",  # Rule 3
        "You may not hallucinate articles",  # Rule 4
        "You may not provide definitive legal advice",  # Rule 5
        "Cite the SINGLE most-directly-supporting article",  # Rule 6
        "Always emit your answer via the `emit_answer` tool",  # Rule 7
        "Gap-analysis mode detection",  # Rule 8
    ]
    missing = [r for r in rule_anchors if r not in txt]
    assert not missing, f"v1.4 missing hard-rule anchors from v1.3: {missing}"


def test_v1_4_adds_hard_rule_9() -> None:
    """v1.4 must contain Hard Rule 9 (force-Finding-emission) with the key
    anchors from spec §D3."""
    txt = _V14.read_text(encoding="utf-8").lower()
    # Anchors drawn verbatim from spec §D3 wording.
    assert "substantive answer" in txt, "Rule 9 must use 'substantive answer' framing"
    assert "invalid" in txt, "Rule 9 must declare prose-without-findings INVALID"
    assert (
        "no citation, no answer" in txt
    ), "Rule 9 must reference the §6 'no citation, no answer' invariant"
    assert "self-check" in txt, "Rule 9 must include the self-check instruction"


def test_v1_4_output_contract_amended() -> None:
    """v1.4 must contain the Output contract amendment from spec §D3:
    'every substantive claim in `text` must map to ≥1 Finding'."""
    txt = _V14.read_text(encoding="utf-8")
    # The exact amendment language; use a sub-phrase to allow Unicode ≥ glyph.
    assert (
        "every substantive claim in `text` must map to" in txt and "Finding" in txt
    ), "Output contract amendment from spec §D3 not found"
    assert "INVALID" in txt, "amendment must include INVALID assertion"


def test_v1_4_preserves_output_format_section_verbatim() -> None:
    """The 'Output format (enforced via tool use)' section must appear
    verbatim in v1.4 (no schema change in v0.1.17.1)."""
    fmt_start = "## Output format (enforced via tool use)"
    fmt_end = "## Output contract (always a well-formed Answer)"
    v13_block = _extract_block(_V13.read_text(encoding="utf-8"), fmt_start, fmt_end, "v1.3")
    v14_block = _extract_block(_V14.read_text(encoding="utf-8"), fmt_start, fmt_end, "v1.4")
    assert v14_block == v13_block, (
        "Output format section drifted v1.3 → v1.4; no schema change in "
        "v0.1.17.1. Restore byte-identity."
    )


def test_v1_4_preserves_examples_1_2_3_verbatim() -> None:
    """Examples 1, 2, 3 from v1.3 must appear byte-identical in v1.4
    (regression anchor on demonstrated correct behavior — Q&A path +
    2 gap-analysis paths preserved unchanged)."""
    v13 = _V13.read_text(encoding="utf-8")
    v14 = _V14.read_text(encoding="utf-8")

    # Example 1: Q&A AI Act high-risk.
    assert _extract_block(v14, _EX1_START, _EX1_END, "v1.4") == _extract_block(
        v13, _EX1_START, _EX1_END, "v1.3"
    ), "Example 1 (Q&A) drifted v1.3 → v1.4. Restore byte-identity."

    # Example 2: gap-analysis precise.
    assert _extract_block(v14, _EX2_START, _EX2_END, "v1.4") == _extract_block(
        v13, _EX2_START, _EX2_END, "v1.3"
    ), "Example 2 (gap-analysis precise) drifted v1.3 → v1.4. Restore byte-identity."

    # Example 3: gap-analysis vague-real — extract from start to end of file
    # (Example 3 is the last block in both v1.3 and v1.4).
    ex3_v13 = v13[v13.index(_EX3_START) :].rstrip()
    ex3_v14 = v14[v14.index(_EX3_START) :].rstrip()
    assert ex3_v14 == ex3_v13, (
        "Example 3 (gap-analysis vague-real) drifted v1.3 → v1.4. " "Restore byte-identity."
    )


def test_v1_4_preserves_gap_analysis_branch_verbatim() -> None:
    """The 'Output contract — gap-analysis branch' section must appear
    verbatim in v1.4 (regression anchor on v0.1.15 gap-analysis work)."""
    branch_start = "## Output contract — gap-analysis branch"
    branch_end = "## Examples"
    v13_block = _extract_block(_V13.read_text(encoding="utf-8"), branch_start, branch_end, "v1.3")
    v14_block = _extract_block(_V14.read_text(encoding="utf-8"), branch_start, branch_end, "v1.4")
    assert v14_block == v13_block, (
        "Output contract — gap-analysis branch drifted v1.3 → v1.4. "
        "v0.1.15 regression anchor broken. Restore byte-identity."
    )


def test_v1_4_changelog_documents_v0_1_17_1() -> None:
    """v1.4 frontmatter changelog must include a 2026-05-22 entry referencing
    v0.1.17.1 + Hard Rule 9 + force-Finding-emission."""
    txt = _V14.read_text(encoding="utf-8")
    # Extract frontmatter (between first --- and second ---).
    fm_start = txt.index("---") + 3
    fm_end = txt.index("---", fm_start)
    frontmatter = txt[fm_start:fm_end]
    assert "2026-05-22" in frontmatter, "changelog must document 2026-05-22 (v0.1.17.1 ship date)"
    assert "v0.1.17.1" in frontmatter, "changelog must reference milestone v0.1.17.1"
    assert (
        "Hard Rule 9" in frontmatter or "Rule 9" in frontmatter
    ), "changelog must mention Hard Rule 9"
    assert (
        "force-Finding-emission" in frontmatter or "force-finding-emission" in frontmatter.lower()
    ), "changelog must mention force-Finding-emission as the v1.4 contribution"


def test_all_five_prompt_versions_coexist_on_disk() -> None:
    """v1.0, v1.1, v1.2, v1.3, v1.4 all present (env override stays
    meaningful + production default v1.0 unchanged per ADR-0016 env seam)."""
    for path, expected_version in [
        (_V10, "version: 1.0"),
        (_V11, "version: 1.1"),
        (_V12, "version: 1.2"),
        (_V13, "version: 1.3"),
        (_V14, "version: 1.4"),
    ]:
        assert path.exists(), f"prompt file missing: {path}"
        assert expected_version in path.read_text(
            encoding="utf-8"
        ), f"{path.name} does not declare {expected_version}"
