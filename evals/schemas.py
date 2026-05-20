"""H8 — Pydantic v2 schemas for the evaluation harness.

These models define the gold set entries (input), per-case results (output of
metric computation), aggregate metrics (input to the report), and run
metadata (header of the report). All models are frozen and reject extra
fields by construction (extra='forbid') so a typo in the gold set jsonl
fails fast at load time.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from regulaitor.corpus.schemas import CorpusSelector

# ---------------------------------------------------------------------------
# Gold set entries
# ---------------------------------------------------------------------------


class GoldCaseChat(BaseModel):
    """One chat case in evals/gold_set.jsonl."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    tipo: Literal["chat"]
    entrada: str = Field(min_length=1, max_length=2000)
    corpus_esperado: CorpusSelector
    articulos_esperados: list[str]  # empty list valid for block cases (no citation expected)
    severidad_esperada: Literal["info", "low", "medium", "high"] | None
    criterios_evaluacion: list[str] = Field(min_length=1)
    salida_esperada: str | None
    requiere_revision_humana: bool
    expected_verdict: Literal["pass", "block", "requires_human_review"]


class GoldCaseDoc(BaseModel):
    """One document case (manifest paired with a PDF file)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    tipo: Literal["document"]
    pdf_path: str = Field(min_length=1)
    corpus_esperado: list[Literal["ai_act", "gdpr", "nis2", "dora"]] = Field(min_length=1)
    expected_findings_articulos: list[str]
    expected_document_verdict: Literal["pass", "block", "requires_human_review"]
    expected_n_segments: int = Field(ge=1)
    n_segments_tolerance: int = Field(default=2, ge=0)
    criterios_evaluacion: list[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Per-case metric results
# ---------------------------------------------------------------------------


class CitationMetrics(BaseModel):
    """Article-level set comparison: precision = |emitted ∩ expected| / |emitted|."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    expected: list[str]
    emitted: list[str]
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)


class CriteriaScore(BaseModel):
    """Single LLM-judge result for one criterion from criterios_evaluacion."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    criterion: str
    passed: bool
    reason: str | None


class ChatCaseResult(BaseModel):
    """All metrics for one chat case after running graph.run + judge."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    expected_verdict: Literal["pass", "block", "requires_human_review"]
    actual_verdict: Literal["pass", "block", "requires_human_review", "blocked_injection"]
    verdict_match: bool
    expected_severity: Literal["info", "low", "medium", "high"] | None
    actual_severity: Literal["info", "low", "medium", "high"] | None
    severity_match: bool | None
    citations: CitationMetrics
    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: float = Field(ge=0.0, le=1.0)
    criteria_scores: list[CriteriaScore]
    latency_ms: int = Field(ge=0)
    cost_eur: float = Field(ge=0)
    cache_hit: bool


class DocCaseResult(BaseModel):
    """All metrics for one document case after run_document + judge."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    expected_document_verdict: Literal["pass", "block", "requires_human_review"]
    actual_document_verdict: Literal["pass", "block", "requires_human_review"]
    verdict_match: bool
    expected_n_segments: int
    actual_n_segments: int
    n_segments_within_tolerance: bool
    findings_citations: CitationMetrics
    faithfulness: float = Field(ge=0.0, le=1.0)
    criteria_scores: list[CriteriaScore]
    latency_ms_total: int = Field(ge=0)
    cost_eur_total: float = Field(ge=0)
    cache_hit: bool


class AggregateMetrics(BaseModel):
    """Headline numbers across all cases — what the report's top table renders."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    n_chat_cases: int = Field(ge=0)
    n_doc_cases: int = Field(ge=0)
    faithfulness_mean: float = Field(ge=0.0, le=1.0)
    answer_relevancy_mean: float = Field(ge=0.0, le=1.0)
    context_precision_mean: float = Field(ge=0.0, le=1.0)
    context_recall_mean: float = Field(ge=0.0, le=1.0)
    citation_precision_mean: float = Field(ge=0.0, le=1.0)
    citation_recall_mean: float = Field(ge=0.0, le=1.0)
    verdict_match_rate: float = Field(ge=0.0, le=1.0)
    severity_match_rate: float = Field(ge=0.0, le=1.0)
    chat_latency_p95_ms: int = Field(ge=0)
    doc_latency_p95_ms: int = Field(ge=0)
    latency_p95_ms: int = Field(ge=0)  # combined (kept for spec §5.4 compatibility)
    cost_per_chat_eur: float = Field(ge=0)
    cost_per_doc_eur: float = Field(ge=0)
    cost_total_eur: float = Field(ge=0)
    cache_hit_rate: float = Field(ge=0.0, le=1.0)


class EvalRunMeta(BaseModel):
    """Header metadata for the markdown report."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    run_date: str
    commit_sha: str
    production_model: str
    judge_model: str
    temperature: float = Field(ge=0.0, le=2.0)
    subset: int | None
    cache_only: bool
