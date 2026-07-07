"""Test per_citation_audits field propagation (spec D2).

Q1.7: the two compute_chat_metrics tests below were once `slow` because that path
transitively loads ragas / HuggingFace embeddings (network — fails offline/SSL-
degraded CI). They now monkeypatch metrics._ragas_metrics_chat (the only remaining
network dependency; the judge is already mocked), so they run in CI at $0 with no
network — recovering the coverage the @slow exclusion cost. The backward_compat
test is a pure schema unit test (no network).
"""

from unittest.mock import Mock

import pytest
from evals import metrics
from evals.metrics import compute_chat_metrics
from evals.schemas import ChatCaseResult, GoldCaseChat

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)
from regulaitor.orchestration.state import ChatState


def _fake_ragas(**_kwargs: object) -> dict[str, float]:
    """Stub the Ragas adapter so compute_chat_metrics needs no network/LLM."""
    return {
        "faithfulness": 0.9,
        "answer_relevancy": 0.9,
        "context_precision": 0.9,
        "context_recall": 0.9,
    }


def test_chat_case_result_per_citation_audits_populated(monkeypatch: pytest.MonkeyPatch):
    """compute_chat_metrics extracts audit_results and populates per_citation_audits."""
    monkeypatch.setattr(metrics, "_ragas_metrics_chat", _fake_ragas)
    citation = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="test text")
    finding = Finding(text="test finding", citations=[citation], severity="info")
    answer = Answer(query="test", language="es", text="test", findings=[finding])

    audit_result = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )

    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=[audit_result], reason=None
    )

    state = ChatState(
        case_id="eval-chat-001",
        query="test",
        corpus="ai_act",
        language="es",
        context=None,
        audited_answer=audited,
    )

    case = GoldCaseChat(
        id="chat-001",
        tipo="chat",
        entrada="test",
        corpus_esperado="ai_act",
        articulos_esperados=["6"],
        severidad_esperada=None,
        criterios_evaluacion=["criterion"],
        salida_esperada=None,
        requiere_revision_humana=False,
        expected_verdict="pass",
    )

    # Mock judge_call and judge_score_fn
    judge_call = Mock(return_value=("mock_response", 0.01))
    judge_score_fn = Mock(return_value=[])

    result = compute_chat_metrics(
        case,
        state,
        judge_call=judge_call,
        judge_score_fn=judge_score_fn,
        latency_ms=1000,
        cost_eur=0.05,
        cache_hit=False,
    )

    # Verify per_citation_audits field exists and is populated
    assert result.per_citation_audits is not None
    assert len(result.per_citation_audits) == 1
    assert result.per_citation_audits[0]["validated"] is True
    assert result.per_citation_audits[0]["citation"]["articulo"] == "6"

    # Q1.4 full-field schema guard: pin the persisted entry shape so a future
    # AuditResult schema change is caught (the trail is mined by $0 diagnostics —
    # e.g. scripts/v0122_1_verdict_diagnostic.py reads per_citation_audits).
    entry = result.per_citation_audits[0]
    assert set(entry.keys()) == {
        "citation",
        "validated",
        "article_exists",
        "apartado_exists",
        "text_normalized_match",
        "reason",
        "failed_check",
    }
    assert set(entry["citation"].keys()) == {"norma", "articulo", "apartado", "language", "text"}


def test_chat_case_result_per_citation_audits_backward_compat():
    """Existing checkpoint entries (old format) load with per_citation_audits=None."""
    # Load an old-format checkpoint JSON without the per_citation_audits field
    old_checkpoint_json = """
    {
        "case_id": "chat-001",
        "expected_verdict": "pass",
        "actual_verdict": "pass",
        "verdict_match": true,
        "expected_severity": null,
        "actual_severity": null,
        "severity_match": null,
        "citations": {"expected": [], "emitted": [], "precision": 0.0, "recall": 0.0},
        "faithfulness": 0.8,
        "answer_relevancy": 0.9,
        "context_precision": 0.7,
        "context_recall": 0.6,
        "criteria_scores": [],
        "latency_ms": 1000,
        "cost_eur": 0.05,
        "cache_hit": false
    }
    """

    result = ChatCaseResult.model_validate_json(old_checkpoint_json)
    assert result.per_citation_audits is None


def test_chat_case_result_per_citation_audits_round_trip(monkeypatch: pytest.MonkeyPatch):
    """New format with per_citation_audits serializes and deserializes correctly."""
    monkeypatch.setattr(metrics, "_ragas_metrics_chat", _fake_ragas)
    citation = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="test text")
    finding = Finding(text="test finding", citations=[citation], severity="info")
    answer = Answer(query="test", language="es", text="test", findings=[finding])

    audit_result = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )

    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=[audit_result], reason=None
    )

    state = ChatState(
        case_id="eval-chat-001",
        query="test",
        corpus="ai_act",
        language="es",
        context=None,
        audited_answer=audited,
    )

    case = GoldCaseChat(
        id="chat-001",
        tipo="chat",
        entrada="test",
        corpus_esperado="ai_act",
        articulos_esperados=["6"],
        severidad_esperada=None,
        criterios_evaluacion=["criterion"],
        salida_esperada=None,
        requiere_revision_humana=False,
        expected_verdict="pass",
    )

    judge_call = Mock(return_value=("mock_response", 0.01))
    judge_score_fn = Mock(return_value=[])

    result1 = compute_chat_metrics(
        case,
        state,
        judge_call=judge_call,
        judge_score_fn=judge_score_fn,
        latency_ms=1000,
        cost_eur=0.05,
        cache_hit=False,
    )

    # Serialize and deserialize
    json_str = result1.model_dump_json()
    result2 = ChatCaseResult.model_validate_json(json_str)

    # Verify round-trip integrity
    assert result2.per_citation_audits is not None
    assert len(result2.per_citation_audits) == len(result1.per_citation_audits)
    assert (
        result2.per_citation_audits[0]["validated"] == result1.per_citation_audits[0]["validated"]
    )
