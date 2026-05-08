"""Tests for AnalystAgent prompt_role parameter (H5)."""

from __future__ import annotations

import pytest

from regulaitor.agents.analyst import PROMPTS_DIR, AnalystAgent


def test_default_role_is_analyst_backcompat(monkeypatch):
    # Existing H4 prompt should still load with no prompt_role argument.
    a = AnalystAgent()
    assert a.prompt_role == "analyst"
    assert a.prompt_version == "v1.0"


def test_document_analyst_role_loads_v1():
    # Requires Task 10 to have created the prompt file.
    a = AnalystAgent(prompt_role="document_analyst")
    assert a.prompt_role == "document_analyst"
    prompt_lower = a._system_prompt.lower()
    assert "datos a analizar" in prompt_lower or "data to analyze" in prompt_lower


def test_invalid_role_rejected():
    with pytest.raises(ValueError, match="prompt_role"):
        AnalystAgent(prompt_role="rogue_role")  # type: ignore[arg-type]


def test_path_traversal_via_role_rejected():
    with pytest.raises(ValueError, match="prompt_role"):
        AnalystAgent(prompt_role="../../etc")  # type: ignore[arg-type]


def test_resolved_path_inside_prompts_dir():
    a = AnalystAgent(prompt_role="document_analyst")
    expected = PROMPTS_DIR.parent / "document_analyst" / "system.v1.0.md"
    assert expected.exists()
    assert a._system_prompt == expected.read_text(encoding="utf-8")


def test_invalid_prompt_version_still_rejected():
    with pytest.raises(ValueError, match="prompt_version"):
        AnalystAgent(prompt_role="document_analyst", prompt_version="bad")
