from __future__ import annotations

from langgraph.graph import END

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditVerdict,
    Citation,
    Finding,
)
from regulaitor.orchestration import graph as g
from regulaitor.orchestration.state import ChatState


def _state(verdict=AuditVerdict.PASS, severity="info", override=None, audited=True):
    s = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    s.council_override = override
    if audited:
        ans = Answer(
            query="q",
            language="es",
            text="t",
            findings=[
                Finding(
                    text="f",
                    citations=[
                        Citation(
                            norma="ai_act",
                            articulo="6",
                            apartado="1",
                            language="es",
                            text="x",
                        )
                    ],
                    severity=severity,
                )
            ],
        )
        s.audited_answer = AuditedAnswer(answer=ans, verdict=verdict, audit_results=[], reason=None)
    return s


def test_auto_trigger_on_rhr():
    s = _state(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW)
    assert g._council_triggered(s) is True
    assert g._council_trigger_reason(s) == "auditor_rhr"


def test_auto_trigger_on_high_severity():
    s = _state(verdict=AuditVerdict.PASS, severity="high")
    assert g._council_triggered(s) is True
    assert g._council_trigger_reason(s) == "high_severity"


def test_no_trigger_on_clean_pass():
    s = _state(verdict=AuditVerdict.PASS, severity="info")
    assert g._council_triggered(s) is False
    assert g._route_after_audit(s) == END


def test_override_true_forces_trigger():
    s = _state(verdict=AuditVerdict.PASS, severity="info", override=True)
    assert g._council_triggered(s) is True
    assert g._council_trigger_reason(s) == "api_override"


def test_override_false_blocks_trigger_even_on_rhr():
    s = _state(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW, override=False)
    assert g._council_triggered(s) is False


def test_no_trigger_without_audited_answer():
    s = _state(audited=False)
    assert g._council_triggered(s) is False
    assert g._route_after_audit(s) == END


def test_route_returns_council_when_triggered():
    s = _state(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW)
    assert g._route_after_audit(s) == "council"


def test_injection_blocked_prevents_council_even_with_override():
    s = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    s.injection_blocked = True
    s.council_override = True
    assert g._council_trigger_reason(s) == "not_triggered"
    assert g._council_triggered(s) is False
