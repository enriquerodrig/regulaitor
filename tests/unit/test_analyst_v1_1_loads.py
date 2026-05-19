# tests/unit/test_analyst_v1_1_loads.py
from __future__ import annotations

from pathlib import Path

from regulaitor.agents.analyst import AnalystAgent

_V11 = Path("src/regulaitor/agents/prompts/analyst/system.v1.1.md")


def test_v1_1_file_exists_with_frontmatter() -> None:
    txt = _V11.read_text(encoding="utf-8")
    assert txt.startswith("---")
    assert "version: 1.1" in txt
    assert "changelog:" in txt
    assert "minimal" in txt.lower() or "only the article" in txt.lower()


def test_agent_loads_v1_1() -> None:
    a = AnalystAgent(prompt_version="v1.1")
    assert a.prompt_version == "v1.1"
    assert len(a._system_prompt) > 500


def test_v1_0_preserved_unchanged() -> None:
    v10 = Path("src/regulaitor/agents/prompts/analyst/system.v1.0.md").read_text(encoding="utf-8")
    assert "version: 1.0" in v10
