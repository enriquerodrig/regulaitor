"""P4.1: the Council skips a judge whose provider key is absent (sovereign profile).

Under the sovereign deploy profile the US judge providers (Anthropic/OpenAI/Groq)
have no key, so each judge must be skipped WITHOUT a doomed router.complete call.
A skipped judge is a not-ok vote, so the degrade-safe aggregation is preserved
(the Auditor's mechanical verdict stands). See docs/sovereign_deploy.md §4 G2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from regulaitor.agents.council import CouncilAgent
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Context,
    Finding,
)
from regulaitor.models import router


def _audited() -> AuditedAnswer:
    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="el art dice X")
    ans = Answer(
        query="q",
        language="es",
        text="resumen",
        findings=[Finding(text="afirmación", citations=[cit], severity="high")],
    )
    ar = AuditResult(
        citation=cit,
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
    )
    return AuditedAnswer(
        answer=ans, verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW, audit_results=[ar], reason="r"
    )


def _context() -> Context:
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(UTC),
        embedding_model="bge-m3",
    )


class _FakeResult:
    def __init__(self, vote: str = "invalid") -> None:
        self.tool_use_input = {"vote": vote, "reason": "r"}
        self.text = ""
        self.model_id = "fake"
        self.cost_eur = 0.0
        self.latency_ms = 1
        self.usage = None


def _no_us_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_all_judges_skipped_when_us_keys_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_us_keys(monkeypatch)
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult()
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="high_severity")
    m.assert_not_called()  # zero doomed calls — the whole point of the guard
    assert len(cr.judges) == 3
    assert all(not j.ok for j in cr.judges)
    assert all(j.error_category == "provider_key_absent" for j in cr.judges)
    assert cr.agreement == "degraded"


def test_turn_survives_all_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Advisory: an all-skipped Council still returns a review (never crashes)."""
    _no_us_keys(monkeypatch)
    with patch("regulaitor.agents.council.router.complete"):
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="auditor_rhr")
    assert cr.triggered is True
    assert cr.council_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW  # degraded → conservative


def test_judges_run_when_keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult()
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="high_severity")
    assert m.call_count == 3  # every judge ran
    assert all(j.ok for j in cr.judges)


def test_global_override_selfhost_runs_judges_without_us_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sovereign config (b): REGULAITOR_ROUTER_MODE=self_hosted routes every judge
    to the self-host provider, so with US keys absent but the self-host key set the
    judges RUN (on Mistral) instead of being skipped — the guard is override-aware."""
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "self_hosted")
    monkeypatch.setenv("REGULAITOR_SELFHOST_API_KEY", "sk-mistral")
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult()
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="high_severity")
    m.assert_called()  # not skipped — effective provider is selfhost (key present)
    assert m.call_count == 3
    assert all(j.ok for j in cr.judges)


def test_global_override_missing_selfhost_key_skips_with_selfhost_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config (b) misconfigured: override to self_hosted but SELFHOST key missing →
    judges skip, and the vote is labelled with the EFFECTIVE provider (selfhost) so
    the operator sees the actually-missing key, not the nominal US judge (F4)."""
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "REGULAITOR_SELFHOST_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "self_hosted")
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult()
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="high_severity")
    m.assert_not_called()
    assert all(not j.ok for j in cr.judges)
    assert all(j.provider == router.PROVIDER_SELFHOST for j in cr.judges)  # effective, not nominal
