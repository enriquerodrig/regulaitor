# tests/unit/test_analyst_v1_2_loads.py
from __future__ import annotations

from pathlib import Path

from regulaitor.agents.analyst import AnalystAgent

_V12 = Path("src/regulaitor/agents/prompts/analyst/system.v1.2.md")


def test_v1_2_loads_and_has_frontmatter() -> None:
    txt = _V12.read_text(encoding="utf-8")
    assert txt.startswith("---")
    assert "version: 1.2" in txt
    assert "changelog:" in txt


def test_agent_loads_v1_2() -> None:
    a = AnalystAgent(prompt_version="v1.2")
    assert a.prompt_version == "v1.2"
    assert len(a._system_prompt) > 500


def test_v1_2_sharpens_minimal_citation_and_drops_auditor_mechanics() -> None:
    import re

    txt = _V12.read_text(encoding="utf-8")
    # Sharpened minimality wording present:
    assert "SINGLE most-directly-supporting" in txt
    # I2 fix: the v1.1 teaching-to-the-grader clause is GONE:
    assert "blocked or flagged for human review" not in txt
    # Anti-overfit, correctly scoped to the AUTHORED Hard rule 6 block only.
    # (The inherited "## Examples" block's generic `art. 6.1`, byte-identical
    # since v1.0 and pre-probe, is legitimately exempt — it is NOT overfitting
    # and must stay byte-identical for single-variable validity.)
    m = re.search(r"^6\. \*\*Cite the SINGLE.*?(?=^7\. \*\*Always emit)", txt, re.S | re.M)
    assert m is not None, "authored Hard rule 6 block not found"
    rule6 = m.group(0)
    assert not re.search(r"\b\d+\.\d+\b", rule6), f"rule 6 leaks a real article id: {rule6!r}"
    assert "[X]" in rule6 and "X, Y, Z" in rule6  # abstract placeholders only


def test_v1_0_and_v1_1_preserved() -> None:
    v10 = Path("src/regulaitor/agents/prompts/analyst/system.v1.0.md").read_text(encoding="utf-8")
    v11 = Path("src/regulaitor/agents/prompts/analyst/system.v1.1.md").read_text(encoding="utf-8")
    assert "version: 1.0" in v10
    assert "version: 1.1" in v11
