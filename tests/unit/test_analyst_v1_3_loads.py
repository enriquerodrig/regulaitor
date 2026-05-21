# tests/unit/test_analyst_v1_3_loads.py
"""v0.1.15 — Analyst prompt v1.3 (gap-analysis chat mode) load + invariants.

Pins the v1.3 prompt added in v0.1.15. Asserts:

1. v1.3 file exists + has Pydantic-style frontmatter (version 1.3 + changelog).
2. AnalystAgent loads v1.3 when explicitly requested.
3. v1.3 contains the Hard Rule 8 (gap-analysis NL detection) anchor.
4. v1.3 contains the gap-analysis output contract anchor.
5. v1.3 preserves the v1.2 Example 1 (Q&A) BYTE-IDENTICAL (regression-zero
   anchor on the regular Q&A path — even when v1.3 is loaded, the same
   Q&A example must yield the same Q&A behavior).
6. v1.3 preserves the v1.2 Hard rules 1-7 anchor text (substring presence
   for each — Hard rule 8 is the only NEW rule).
7. All 4 prompt versions (v1.0, v1.1, v1.2, v1.3) coexist on disk
   (regression-pin that prior versions stay available for env override).

The default-when-env-unset regression is already pinned by
`tests/unit/test_analyst_prompt_env_seam.py::test_default_is_v1_0_when_env_unset`
(unchanged in v0.1.15).
"""

from __future__ import annotations

from pathlib import Path

from regulaitor.agents.analyst import AnalystAgent

_PROMPTS = Path("src/regulaitor/agents/prompts/analyst")
_V10 = _PROMPTS / "system.v1.0.md"
_V11 = _PROMPTS / "system.v1.1.md"
_V12 = _PROMPTS / "system.v1.2.md"
_V13 = _PROMPTS / "system.v1.3.md"

# v1.2 Example 1 starts with this user query and ends with the closing of the
# findings list. Both must appear verbatim in v1.3.
_EX1_START = 'User: "¿Qué dice el AI Act sobre sistemas de alto riesgo?"'
_EX1_END = '     severity: "info"}\n  ]'


def _example_1_block(text: str, source: str = "prompt text") -> str:
    """Extract Example 1 (Q&A AI Act high-risk) block from a v1.x prompt.

    Raises AssertionError (not ValueError) when markers aren't found, so test
    output makes it obvious WHICH file drifted and WHICH markers were expected.
    """
    try:
        start = text.index(_EX1_START)
        end = text.index(_EX1_END, start) + len(_EX1_END)
        return text[start:end]
    except ValueError as e:
        raise AssertionError(
            f"Example 1 markers not found in {source}. "
            f"Looking for start={_EX1_START!r} and end={_EX1_END!r}. "
            f"Did v1.3 author move/rename Example 1, or did v1.2 drift?"
        ) from e


def test_v1_3_loads_and_has_frontmatter() -> None:
    """v1.3 prompt file exists + has Pydantic-style frontmatter."""
    txt = _V13.read_text(encoding="utf-8")
    assert txt.startswith("---"), "missing frontmatter opening"
    assert "version: 1.3" in txt, "frontmatter must declare version: 1.3"
    assert "changelog:" in txt, "frontmatter must include changelog block"


def test_agent_loads_v1_3() -> None:
    """AnalystAgent loads v1.3 when explicitly requested via prompt_version arg."""
    a = AnalystAgent(prompt_version="v1.3")
    assert a.prompt_version == "v1.3"
    assert len(a._system_prompt) > 500, "v1.3 system prompt is too short to be valid"


def test_v1_3_contains_rule_8_gap_analysis_detection() -> None:
    """v1.3 must contain Hard Rule 8 (NL gap-analysis detection)."""
    txt = _V13.read_text(encoding="utf-8")
    # Anchor strings drawn from the spec §4 NL detection design.
    assert "Gap-analysis mode detection" in txt, "missing Hard Rule 8 header anchor"
    # The trigger pattern requires BOTH a declaration AND a gap-seeking question.
    assert "declaration" in txt.lower(), "Rule 8 must describe state declaration"
    assert (
        "gap-seeking" in txt.lower() or "gap question" in txt.lower()
    ), "Rule 8 must describe the gap-seeking question half of the trigger"
    # Ambiguous → Q&A (safer default).
    assert "ambiguous" in txt.lower(), "Rule 8 must specify ambiguous → Q&A default"


def test_v1_3_contains_gap_analysis_output_contract() -> None:
    """v1.3 must contain the gap-analysis output contract subsection."""
    txt = _V13.read_text(encoding="utf-8")
    # The output contract subsection introduces gap-analysis Finding shape.
    assert (
        "gap-analysis branch" in txt.lower() or "gap-analysis mode" in txt.lower()
    ), "must contain gap-analysis output contract section header"
    # The severity scale for gap-analysis findings (high/medium/low/info).
    assert "high" in txt and "medium" in txt and "low" in txt and "info" in txt
    # Declared state = INPUT (not citation-worthy).
    assert (
        "INPUT" in txt or "input, not" in txt.lower()
    ), "must clarify declared state is INPUT not normative claim"


def test_v1_3_preserves_v1_2_example_1_q_and_a_verbatim() -> None:
    """The Q&A Example 1 from v1.2 must appear BYTE-IDENTICAL in v1.3.
    This is the regression-zero anchor: even when v1.3 is loaded, the same
    Q&A example yields the same behavior (no prompt drift on the Q&A path)."""
    v12 = _V12.read_text(encoding="utf-8")
    v13 = _V13.read_text(encoding="utf-8")
    assert _example_1_block(v13, "v1.3") == _example_1_block(v12, "v1.2"), (
        "Example 1 (Q&A) drifted from v1.2 → v1.3; the regression-zero anchor "
        "on the regular Q&A path is broken. Restore byte-identity."
    )


def test_v1_3_preserves_v1_2_hard_rules_1_through_7() -> None:
    """v1.3 must preserve the anchor text of all 7 Hard rules from v1.2.
    Rule 8 is the ONLY new rule. If any of these anchors is missing, the
    Hard rules block has drifted."""
    txt = _V13.read_text(encoding="utf-8")
    rule_anchors = [
        "Every assertion you emit must be supported",  # Rule 1
        "You must cite the EXACT TEXT",  # Rule 2
        "Respond in the same language",  # Rule 3
        "You may not hallucinate articles",  # Rule 4
        "You may not provide definitive legal advice",  # Rule 5
        "Cite the SINGLE most-directly-supporting article",  # Rule 6
        "Always emit your answer via the `emit_answer` tool",  # Rule 7
    ]
    missing = [r for r in rule_anchors if r not in txt]
    assert not missing, f"v1.3 missing hard-rule anchors from v1.2: {missing}"


def test_all_four_prompt_versions_coexist_on_disk() -> None:
    """v1.0, v1.1, v1.2, v1.3 all present (env override stays meaningful)."""
    for path, expected_version in [
        (_V10, "version: 1.0"),
        (_V11, "version: 1.1"),
        (_V12, "version: 1.2"),
        (_V13, "version: 1.3"),
    ]:
        assert path.exists(), f"prompt file missing: {path}"
        assert expected_version in path.read_text(
            encoding="utf-8"
        ), f"{path.name} does not declare {expected_version}"
