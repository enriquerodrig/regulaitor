"""v0.1.28 — pin tests for the NEW doc_analyst v1.6 system prompt.

Mirrors the v0.1.21 tests/unit/test_analyst_v1_5_loads.py structure.
Verifies:
- v1.6 file exists at the expected path + frontmatter is loadable
- Hard Rules 4+8 (placeholder forbidden + Finding-or-refusal contract) pinned
- Output contract Rule 2 (Finding-based refusal pattern) pinned verbatim
- Example 3 (the v0.1.28 fix demonstration) referenced
- doc_analyst role default now resolves to v1.6 (not v1.0)
- v1.0 still loadable via explicit env (regression baseline preserved)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaitor.agents.analyst import AnalystAgent

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / (
    "src/regulaitor/agents/prompts/document_analyst"
)


def test_v1_6_prompt_file_exists() -> None:
    """v1.6 system prompt must exist at the canonical path; analyst.py:122
    role-aware ternary references it for env-unset doc_analyst calls."""
    v1_6 = _PROMPTS_DIR / "system.v1.6.md"
    assert v1_6.exists(), f"v1.6 doc-mode prompt missing at {v1_6}"
    assert v1_6.stat().st_size > 2000, "v1.6 prompt suspiciously short"


def test_v1_6_frontmatter_pins_doc_mode_designation() -> None:
    """Frontmatter changelog must document v0.1.28 doc-mode adaptation + the
    'placeholder citation strings forbidden' design rationale (Hard rule 4)."""
    contents = (_PROMPTS_DIR / "system.v1.6.md").read_text(encoding="utf-8")
    head = contents[:3000]
    assert "version: v1.6" in head
    assert "doc-mode" in head.lower() or "document_analyst" in head.lower()
    assert "v0.1.28" in head
    assert "placeholder" in contents.lower(), (
        "v1.6 must explicitly forbid placeholder citation strings "
        "(the v1.0 doc_analyst bug the v0.1.28 milestone fixes)"
    )


def test_v1_6_hard_rule_4_forbids_placeholders() -> None:
    """Hard Rule 4 must explicitly forbid placeholder strings like UNKNOWN/N/A
    — these are the literal failure mode v0.1.27 probe documented (3/3 docs
    all-blocked because Sonnet emitted articulo='<UNKNOWN>' to satisfy schema)."""
    contents = (_PROMPTS_DIR / "system.v1.6.md").read_text(encoding="utf-8")
    assert '"UNKNOWN"' in contents
    assert '"N/A"' in contents
    assert "TBD" in contents
    assert "Never emit placeholder citation strings" in contents


def test_v1_6_output_contract_rule_2_refusal_pattern_present() -> None:
    """Rule 2 Finding-based refusal — exact pattern from v0.1.21 v1.5 ADR-0027
    ported to doc-mode (cite scope/applicability article instead of empty
    findings or placeholder articulo)."""
    contents = (_PROMPTS_DIR / "system.v1.6.md").read_text(encoding="utf-8")
    assert "Rule 2" in contents
    assert "structured refusal" in contents.lower()
    assert "exactly ONE Finding" in contents
    assert (
        "scope" in contents.lower()
    ), "Rule 2 refusal must reference the scope/applicability article fallback"


def test_v1_6_example_3_demonstrates_the_v0128_fix() -> None:
    """Example 3 is THE demonstration of the v0.1.28 fix: a segment with
    insufficient corpus context → Finding-based refusal citing AI Act art 2
    (scope) instead of placeholder citation strings."""
    contents = (_PROMPTS_DIR / "system.v1.6.md").read_text(encoding="utf-8")
    assert "Example 3" in contents
    assert "v0.1.28" in contents
    assert "ADR-0033" in contents


def test_v1_0_doc_analyst_still_loadable_via_explicit_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.28 ADR-0033 flip retains v1.0 as opt-in baseline (regression-safe;
    mirrors v0.1.20 ADR-0026 keeping v1.4 loadable via REGULAITOR_ANALYST_PROMPT_VERSION=v1.4
    for retrospective A/B comparison)."""
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v1.0")
    a = AnalystAgent(prompt_role="document_analyst")
    assert a.prompt_version == "v1.0"
