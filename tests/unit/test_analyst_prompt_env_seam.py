# tests/unit/test_analyst_prompt_env_seam.py
from __future__ import annotations

import pytest

from regulaitor.agents.analyst import AnalystAgent


def test_default_is_v1_5_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # v0.1.20 flipped env-unset default v1.0 -> v1.4 per ADR-0026.
    # v0.1.21 further flipped v1.4 -> v1.5 per ADR-0027 final-review C4
    # (v1.4's `findings: []` refusal pattern is incompatible with v0.1.21
    # Tier 2 Capa A+B hard constraints; v1.5 ships Finding-based refusal).
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    a = AnalystAgent()
    assert a.prompt_version == "v1.5"


def test_env_consult_wired__absent_version_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove the env seam is genuinely wired: a valid-format but ABSENT version
    set via env must make the constructor raise FileNotFoundError whose message
    contains that version. Fails immediately if the env-consult block is
    removed/skipped (the v1.0 fallback exists and would NOT raise). No v1.1
    file required. Without this, a silent env-consult regression would make the
    H15 A/B run v1.0-vs-v1.0 and invalidate the study with no failing test.
    """
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v2.7")
    with pytest.raises(FileNotFoundError, match="v2.7"):
        AnalystAgent()


def test_explicit_arg_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v9.9")
    a = AnalystAgent(prompt_version="v1.0")
    assert a.prompt_version == "v1.0"  # explicit arg wins, env ignored


def test_invalid_env_falls_back_to_v1_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "not-a-version")
    a = AnalystAgent()
    assert a.prompt_version == "v1.0"  # invalid env ignored with WARNING, never crashes


def test_document_analyst_role_defaults_to_v1_0_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.20 / ADR-0026 role-aware default: the FLIP only applies to the
    chat `analyst` role; `document_analyst` still defaults to v1.0 because
    v1.4 was authored for chat role only (doc-mode A/B carried forward as
    future work). Regression-pin so a future "uniform default" refactor
    doesn't silently break doc-mode by trying to load a non-existent
    document_analyst/system.v1.4.md."""
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    a = AnalystAgent(prompt_role="document_analyst")
    assert a.prompt_role == "document_analyst"
    assert a.prompt_version == "v1.0"
