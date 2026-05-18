from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

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


def _citation(text="el artículo dice X"):
    return Citation(norma="ai_act", articulo="6", apartado="1", language="es", text=text)


def _finding(severity="high", cite_text="el artículo dice X"):
    return Finding(text="afirmación", citations=[_citation(cite_text)], severity=severity)


def _audited(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW, severity="high"):
    ans = Answer(query="q", language="es", text="resumen", findings=[_finding(severity)])
    ar = AuditResult(
        citation=ans.findings[0].citations[0],
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
    )
    return AuditedAnswer(answer=ans, verdict=verdict, audit_results=[ar], reason="r")


def _context():
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(UTC),
        embedding_model="bge-m3",
    )


class _FakeResult:
    def __init__(self, vote):
        self.tool_use_input = {"vote": vote, "reason": "porque sí"}
        self.text = ""
        self.model_id = "fake"
        self.cost_eur = 0.0
        self.latency_ms = 1
        self.usage = None


def test_review_unanimous_invalid_diverges_from_pass():
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult("invalid")
        cr = CouncilAgent().review(
            _audited(verdict=AuditVerdict.PASS),
            _context(),
            trigger_reason="high_severity",
        )
    assert len(cr.judges) == 3
    assert all(j.ok for j in cr.judges)
    assert cr.council_verdict == AuditVerdict.BLOCK
    assert cr.agreement == "unanimous"
    assert cr.diverges_from_auditor is True
    assert cr.trigger_reason == "high_severity"


def test_review_one_judge_fails_is_degraded_turn_survives():
    calls = {"n": 0}

    def _side_effect(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("groq 429 free-tier cap")
        return _FakeResult("valid")

    with patch("regulaitor.agents.council.router.complete", side_effect=_side_effect):
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="auditor_rhr")
    assert len(cr.judges) == 3
    failed = [j for j in cr.judges if not j.ok]
    assert len(failed) == 1
    assert failed[0].error_category == "RuntimeError"
    assert cr.agreement == "degraded"


def test_review_all_judges_fail_council_unavailable():
    with patch(
        "regulaitor.agents.council.router.complete",
        side_effect=RuntimeError("down"),
    ):
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="auditor_rhr")
    assert all(not j.ok for j in cr.judges)
    assert cr.council_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert "council_unavailable" in cr.reason


def test_findings_under_review_union_logic():
    # verdict PASS + no high severity + not override => union empty => all findings
    aud = _audited(verdict=AuditVerdict.PASS, severity="low")
    agent = CouncilAgent()
    reviewed = agent._findings_under_review(aud)
    assert len(reviewed) == 1  # falls back to all findings when union empty


def test_review_invalid_vote_degrades_that_judge():
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult("garbage_vote")
        cr = CouncilAgent().review(_audited(), _context(), trigger_reason="auditor_rhr")
    assert all(not j.ok for j in cr.judges)
    assert all(j.error_category == "ValueError" for j in cr.judges)
