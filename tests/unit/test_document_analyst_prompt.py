"""Tests for AnalystAgent prompt_role parameter (H5)."""

from __future__ import annotations

import pytest

from regulaitor.agents.analyst import PROMPTS_DIR, AnalystAgent


def test_default_role_is_analyst_backcompat(monkeypatch):
    # Existing H4 prompt should still load with no prompt_role argument.
    # v0.1.20 flipped env-unset default for the chat `analyst` role v1.0 -> v1.4
    # per ADR-0026; v0.1.21 final-review C4 further flipped chat default
    # v1.4 -> v1.5 (v1.5 ships Finding-based refusal compatible with Tier 2
    # Capa A+B hard constraints on findings non-empty; see ADR-0027
    # "Implementation note (post-final-review)"). `document_analyst` role
    # still defaults to v1.0 (no v1.5 for doc-mode; doc-mode A/B + refusal
    # coherence carried forward).
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    a = AnalystAgent()
    assert a.prompt_role == "analyst"
    assert a.prompt_version == "v1.5"


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
    # v0.1.28 ADR-0033 flipped env-unset doc default v1.0 → v1.6 (Finding-based
    # refusal pattern). v1.0 still loadable via explicit env (see
    # test_v1_0_doc_analyst_still_loadable_via_explicit_env in
    # test_analyst_v1_6_doc_loads.py).
    a = AnalystAgent(prompt_role="document_analyst")
    expected = PROMPTS_DIR.parent / "document_analyst" / "system.v1.6.md"
    assert expected.exists()
    assert a._system_prompt == expected.read_text(encoding="utf-8")


def test_invalid_prompt_version_still_rejected():
    with pytest.raises(ValueError, match="prompt_version"):
        AnalystAgent(prompt_role="document_analyst", prompt_version="bad")
