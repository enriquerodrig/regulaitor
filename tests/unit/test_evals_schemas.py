"""Unit tests for evals.schemas — Pydantic v2 validation."""

from __future__ import annotations

import pytest
from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    EvalRunMeta,
    GoldCaseChat,
    GoldCaseDoc,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# GoldCaseChat
# ---------------------------------------------------------------------------


def _chat_payload() -> dict:
    return {
        "id": "chat-001",
        "tipo": "chat",
        "entrada": "¿Qué dice el AI Act sobre sistemas de alto riesgo?",
        "corpus_esperado": "ai_act",
        "articulos_esperados": ["6.1", "9.2"],
        "severidad_esperada": "medium",
        "criterios_evaluacion": ["Cita art. 6.1", "No afirma X sin evidencia"],
        "salida_esperada": "El AI Act regula sistemas de alto riesgo en art. 6 y 9...",
        "requiere_revision_humana": False,
        "expected_verdict": "pass",
    }


def test_gold_case_chat_valid_minimal() -> None:
    case = GoldCaseChat.model_validate(_chat_payload())
    assert case.id == "chat-001"
    assert case.tipo == "chat"
    assert case.expected_verdict == "pass"


def test_gold_case_chat_rejects_extra_field() -> None:
    payload = _chat_payload() | {"unknown": "x"}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_rejects_oversize_entrada() -> None:
    payload = _chat_payload() | {"entrada": "x" * 2001}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_rejects_unknown_corpus() -> None:
    payload = _chat_payload() | {"corpus_esperado": "nis2"}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_severidad_optional() -> None:
    payload = _chat_payload() | {"severidad_esperada": None}
    case = GoldCaseChat.model_validate(payload)
    assert case.severidad_esperada is None


def test_gold_case_chat_criterios_min_length_one() -> None:
    payload = _chat_payload() | {"criterios_evaluacion": []}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_frozen() -> None:
    case = GoldCaseChat.model_validate(_chat_payload())
    with pytest.raises(ValidationError):
        case.entrada = "nuevo texto"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GoldCaseDoc
# ---------------------------------------------------------------------------


def _doc_payload() -> dict:
    return {
        "id": "doc-001",
        "tipo": "document",
        "pdf_path": "case_001_ai_act_policy.pdf",
        "corpus_esperado": ["ai_act"],
        "expected_findings_articulos": ["6.1"],
        "expected_document_verdict": "requires_human_review",
        "expected_n_segments": 5,
        "n_segments_tolerance": 2,
        "criterios_evaluacion": ["Detecta sistema alto riesgo no clasificado"],
    }


def test_gold_case_doc_valid_minimal() -> None:
    case = GoldCaseDoc.model_validate(_doc_payload())
    assert case.id == "doc-001"
    assert case.expected_n_segments == 5


def test_gold_case_doc_rejects_zero_n_segments() -> None:
    payload = _doc_payload() | {"expected_n_segments": 0}
    with pytest.raises(ValidationError):
        GoldCaseDoc.model_validate(payload)


def test_gold_case_doc_corpus_min_length_one() -> None:
    payload = _doc_payload() | {"corpus_esperado": []}
    with pytest.raises(ValidationError):
        GoldCaseDoc.model_validate(payload)


# ---------------------------------------------------------------------------
# CitationMetrics
# ---------------------------------------------------------------------------


def test_citation_metrics_clamps_precision_recall() -> None:
    cm = CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0)
    assert cm.precision == 1.0
    with pytest.raises(ValidationError):
        CitationMetrics(emitted=[], expected=[], precision=1.5, recall=1.0)


# ---------------------------------------------------------------------------
# ChatCaseResult / DocCaseResult / AggregateMetrics
# ---------------------------------------------------------------------------


def test_chat_case_result_full_shape() -> None:
    cm = CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0)
    result = ChatCaseResult(
        case_id="chat-001",
        expected_verdict="pass",
        actual_verdict="pass",
        verdict_match=True,
        expected_severity="medium",
        actual_severity="medium",
        severity_match=True,
        citations=cm,
        faithfulness=0.9,
        answer_relevancy=0.85,
        context_precision=0.8,
        context_recall=0.78,
        criteria_scores=[
            CriteriaScore(criterion="Cita art. 6.1", passed=True, reason="literal match")
        ],
        latency_ms=4200,
        cost_eur=0.04,
        cache_hit=False,
    )
    assert result.case_id == "chat-001"
    assert result.criteria_scores[0].passed is True


def test_aggregate_metrics_validation() -> None:
    agg = AggregateMetrics(
        n_chat_cases=30,
        n_doc_cases=10,
        faithfulness_mean=0.87,
        answer_relevancy_mean=0.91,
        context_precision_mean=0.78,
        context_recall_mean=0.82,
        citation_precision_mean=0.93,
        citation_recall_mean=0.79,
        verdict_match_rate=0.90,
        severity_match_rate=0.83,
        latency_p95_ms=8420,
        cost_per_chat_eur=0.041,
        cost_per_doc_eur=0.487,
        cost_total_eur=6.83,
        cache_hit_rate=0.05,
    )
    assert agg.cost_total_eur == 6.83


def test_aggregate_metrics_rate_clamped_to_unit() -> None:
    with pytest.raises(ValidationError):
        AggregateMetrics(
            n_chat_cases=30,
            n_doc_cases=10,
            faithfulness_mean=1.5,  # invalid
            answer_relevancy_mean=0.91,
            context_precision_mean=0.78,
            context_recall_mean=0.82,
            citation_precision_mean=0.93,
            citation_recall_mean=0.79,
            verdict_match_rate=0.90,
            severity_match_rate=0.83,
            latency_p95_ms=8420,
            cost_per_chat_eur=0.041,
            cost_per_doc_eur=0.487,
            cost_total_eur=6.83,
            cache_hit_rate=0.05,
        )


def test_eval_run_meta_shape() -> None:
    meta = EvalRunMeta(
        run_date="2026-05-10T18:00:00+00:00",
        commit_sha="abcd123",
        production_model="claude-sonnet-4-6",
        judge_model="claude-haiku-4-5-20251001",
        temperature=0.0,
        subset=None,
        cache_only=False,
    )
    assert meta.commit_sha == "abcd123"
    assert meta.subset is None
