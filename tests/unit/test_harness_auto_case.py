# tests/unit/test_harness_auto_case.py
from __future__ import annotations

from evals.schemas import GoldCaseChat


def test_goldcasechat_accepts_auto_corpus() -> None:
    gc = GoldCaseChat.model_validate(
        {
            "id": "xcorpus-001",
            "tipo": "chat",
            "entrada": "q",
            "corpus_esperado": "auto",
            "articulos_esperados": ["1", "47"],
            "severidad_esperada": "high",
            "criterios_evaluacion": ["c"],
            "salida_esperada": None,
            "requiere_revision_humana": True,
            "expected_verdict": "requires_human_review",
        }
    )
    assert gc.corpus_esperado == "auto"
