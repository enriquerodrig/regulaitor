"""H8 — Integration smoke test for the eval harness with cache pre-populated.

Does NOT call Anthropic. Pre-populates the cache with canned judge responses
and stubs the production graph calls so the entire pipeline (load -> run ->
metrics -> report) is exercised end-to-end without LLM cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from evals import cache, harness


@pytest.fixture
def populated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Populate the cache with judge responses keyed by all expected criteria queries."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(cache, "_CACHE_DIR", cache_dir)
    return cache_dir


def _stub_chat_state(case_id: str = "x") -> Any:
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        AuditResult,
        AuditVerdict,
        Citation,
        Finding,
    )
    from regulaitor.orchestration.state import ChatState

    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    finding = Finding(text="hallazgo", citations=[cit], severity="medium")
    answer = Answer(query="q", language="es", text="respuesta", findings=[finding])
    audit = AuditResult(
        citation=cit,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    audited = AuditedAnswer(
        answer=answer,
        verdict=AuditVerdict.PASS,
        audit_results=[audit],
        reason=None,
    )
    return ChatState(
        case_id=case_id,
        query="q",
        corpus="ai_act",
        language="es",
        answer=answer,
        audited_answer=audited,
    )


def test_smoke_subset_with_canned_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, populated_cache: Path
) -> None:
    # Write a 1-case gold set
    gold_path = tmp_path / "gold_set.jsonl"
    gold_path.write_text(
        json.dumps(
            {
                "id": "chat-001",
                "tipo": "chat",
                "entrada": "test query",
                "corpus_esperado": "ai_act",
                "articulos_esperados": ["6.1"],
                "severidad_esperada": "medium",
                "criterios_evaluacion": ["criterion_one"],
                "salida_esperada": None,
                "requiere_revision_humana": False,
                "expected_verdict": "pass",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Stub backend chat run
    monkeypatch.setattr(harness, "run_chat", lambda **kw: _stub_chat_state(kw.get("case_id", "x")))

    # Stub Ragas: avoid live Ragas call by patching _ragas_metrics_chat
    from evals import metrics as metrics_mod

    monkeypatch.setattr(
        metrics_mod,
        "_ragas_metrics_chat",
        lambda **kw: {
            "faithfulness": 0.9,
            "answer_relevancy": 0.9,
            "context_precision": 0.8,
            "context_recall": 0.78,
        },
    )

    # Pre-populate judge cache for the criterion call
    judge_response = json.dumps(
        {"scores": [{"criterion": "criterion_one", "passed": True, "reason": "ok"}]}
    )
    # Build the same key the harness will compute
    from evals.judge import _load_judge_prompt

    system_prompt = _load_judge_prompt()
    user_payload = json.dumps(
        {
            "query": "test query",
            "actual_answer": "respuesta",
            "expected_answer": None,
            "cited_articles": ["6.1"],
            "expected_articles": ["6.1"],
            "criteria": ["criterion_one"],
        },
        ensure_ascii=False,
        indent=2,
    )
    prompt_text = f"{system_prompt}\n---\n{user_payload}"
    key = cache.cache_key(model="claude-haiku-4-5-20251001", prompt=prompt_text, temperature=0.0)
    (populated_cache / f"{key}.json").write_text(
        json.dumps(
            {
                "request": {
                    "model": "claude-haiku-4-5-20251001",
                    "system": system_prompt,
                    "user": user_payload,
                    "temperature": 0.0,
                },
                "response": judge_response,
                "timestamp": "2026-05-10T00:00:00Z",
                "tokens_in": 200,
                "tokens_out": 50,
                "cost_eur": 0.0003,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Patch report path to tmp
    report_path = tmp_path / "latest.md"
    monkeypatch.setattr(harness, "_REPORT_PATH", report_path)

    # Run cache-only mode — should succeed because we populated the judge cache
    harness.main(gold_set_path=gold_path, subset=1, cache_only=True)

    # Verify report generated
    assert report_path.exists()
    md = report_path.read_text(encoding="utf-8")
    assert "RegulAItor — Evaluation Report" in md
    assert "chat-001" in md
