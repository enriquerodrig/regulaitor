from __future__ import annotations

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote
from regulaitor.orchestration import graph as g
from regulaitor.orchestration.state import ChatState


def test_trace_record_includes_council_summary():
    s = ChatState(case_id="c", query="secret query text", corpus="ai_act", language="es")
    s.council_review = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="m",
                provider="p",
                vote=AuditVerdict.BLOCK,
                reason="r",
                ok=True,
                error_category=None,
            )
        ],
        council_verdict=AuditVerdict.BLOCK,
        agreement="degraded",
        diverges_from_auditor=True,
        reason="x",
    )
    rec = g._trace_record(s, 100)
    assert rec["council_triggered"] is True
    assert rec["council_verdict"] == "block"
    assert rec["council_diverges"] is True
    assert rec["n_judges_ok"] == 1
    # SSDLC: no raw query text anywhere in the record
    assert "secret query text" not in str(rec)


def test_trace_record_council_absent_when_no_review():
    s = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    rec = g._trace_record(s, 10)
    assert rec["council_triggered"] is False
    assert rec["council_verdict"] is None
