from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).parents[3] / "src/regulaitor/agents/prompts/council/judge.v1.0.md"


def test_council_prompt_exists_with_frontmatter():
    text = PROMPT.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "agent: council" in text
    assert "role: council_judge" in text
    assert "version: 1.0" in text
    assert "cast_vote" in text  # references the structured-output tool
    # voting vocabulary present
    for token in ("valid", "invalid", "requires_human_review"):
        assert token in text
