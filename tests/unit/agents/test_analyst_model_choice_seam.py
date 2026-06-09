"""Unit tests for the Analyst-scoped model_choice seam (probe R1).

REGULAITOR_ANALYST_MODEL_CHOICE overrides ONLY the Analyst's router mode (the
judge/Council stay constant), so an A/B can swap the Analyst's model without the
global REGULAITOR_ROUTER_MODE that would also swap the judge. Mirrors the
existing REGULAITOR_ANALYST_PROMPT_VERSION seam.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from regulaitor.agents.analyst import AnalystAgent, _analyst_model_choice
from regulaitor.citation.schemas import Context
from regulaitor.models import router


def _ctx() -> Context:
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3",
    )


def test_model_choice_defaults_to_default_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("REGULAITOR_ANALYST_MODEL_CHOICE", raising=False)
    assert _analyst_model_choice() == "default"


def test_model_choice_reads_valid_env(monkeypatch) -> None:
    monkeypatch.setenv("REGULAITOR_ANALYST_MODEL_CHOICE", "self_hosted")
    assert _analyst_model_choice() == "self_hosted"


def test_model_choice_invalid_env_falls_back_to_default_with_warning(monkeypatch, caplog) -> None:
    monkeypatch.setenv("REGULAITOR_ANALYST_MODEL_CHOICE", "bogus-mode")
    with caplog.at_level(logging.WARNING, logger="regulaitor.agents.analyst"):
        assert _analyst_model_choice() == "default"
    assert "REGULAITOR_ANALYST_MODEL_CHOICE" in caplog.text


def test_analyze_passes_resolved_model_choice_to_router(monkeypatch) -> None:
    """analyze() forwards the env-resolved model_choice to router.complete."""
    monkeypatch.setenv("REGULAITOR_ANALYST_MODEL_CHOICE", "self_hosted")
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    captured: dict = {}

    def _fake_complete(**kwargs):
        captured["model_choice"] = kwargs["model_choice"]
        # Stop after capturing; analyze() does not catch RuntimeError here.
        raise RuntimeError("stop-after-capture")

    monkeypatch.setattr(router, "complete", _fake_complete)
    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="stop-after-capture"):
        agent.analyze("q", _ctx())
    assert captured["model_choice"] == "self_hosted"


def test_analyze_uses_default_when_env_unset(monkeypatch) -> None:
    """Regression-zero: env unset => Analyst routes 'default' (Sonnet), unchanged."""
    monkeypatch.delenv("REGULAITOR_ANALYST_MODEL_CHOICE", raising=False)
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    captured: dict = {}

    def _fake_complete(**kwargs):
        captured["model_choice"] = kwargs["model_choice"]
        raise RuntimeError("stop-after-capture")

    monkeypatch.setattr(router, "complete", _fake_complete)
    agent = AnalystAgent()
    with pytest.raises(RuntimeError, match="stop-after-capture"):
        agent.analyze("q", _ctx())
    assert captured["model_choice"] == "default"
