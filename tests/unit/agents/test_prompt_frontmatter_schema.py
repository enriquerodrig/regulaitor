"""Frontmatter schema test for all Analyst + doc_analyst + Auditor + Council
system prompts (deep-review I9 fix).

Asserts every `system.v*.md` under `src/regulaitor/agents/prompts/**/` has
the minimum frontmatter contract per SKILL.md prompt-versioning:
  - opens with `---` fence
  - has `agent:` field (matches parent dir name)
  - has `version:` field (any string; format consistency v1.6 vs 1.5 is HX)
  - has `changelog:` block

Catches regressions like v0.1.28 doc_analyst v1.6 missing standard fields.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_PROMPTS_ROOT = Path("src/regulaitor/agents/prompts")


def _all_prompt_files() -> list[Path]:
    return sorted(_PROMPTS_ROOT.glob("**/system.v*.md"))


def test_at_least_one_prompt_found() -> None:
    """Sanity: the prompts tree exists and has system prompts."""
    files = _all_prompt_files()
    assert files, f"No system.v*.md found under {_PROMPTS_ROOT}"


@pytest.mark.parametrize("prompt_path", _all_prompt_files(), ids=lambda p: str(p))
def test_prompt_frontmatter_minimum_contract(prompt_path: Path) -> None:
    """Every prompt has agent + version + changelog frontmatter fields."""
    text = prompt_path.read_text(encoding="utf-8")

    # Frontmatter starts with --- on first line
    assert text.startswith("---\n"), f"{prompt_path}: missing opening --- fence"

    # Extract frontmatter block (between first two --- fences)
    end_fence = text.find("\n---\n", 4)
    assert end_fence > 0, f"{prompt_path}: missing closing --- fence"
    frontmatter = text[4:end_fence]

    # Required fields per SKILL.md prompt-versioning contract
    expected_agent = prompt_path.parent.name
    assert f"agent: {expected_agent}" in frontmatter, (
        f"{prompt_path}: frontmatter missing `agent: {expected_agent}` field "
        f"(prompts dir name must match the agent field per SKILL.md)"
    )
    assert "version:" in frontmatter, f"{prompt_path}: frontmatter missing `version:` field"
    assert "changelog:" in frontmatter, f"{prompt_path}: frontmatter missing `changelog:` block"
