"""H14 — Task 4: verify that all 9 hardcoded ai_act/gdpr spots accept the
full 4-value Norma (ai_act, gdpr, nis2, dora) and that the loader gate
equals exactly the landed manifests on disk.

RED before Step 3 widening, GREEN after.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_ask_request_accepts_nis2_dora() -> None:
    """AskRequest.corpus must accept all 4 Norma values."""
    from regulaitor.api.schemas import AskRequest

    for c in ("ai_act", "gdpr", "nis2", "dora"):
        req = AskRequest(query="q", corpus=c, language="es")
        assert req.corpus == c


def test_ask_request_rejects_unknown_corpus() -> None:
    """AskRequest.corpus must still reject invalid values (regression guard)."""
    from regulaitor.api.schemas import AskRequest

    with pytest.raises(ValidationError):
        AskRequest(query="q", corpus="unknown_norma", language="es")


def test_goldcasechat_accepts_nis2() -> None:
    """GoldCaseChat.corpus_esperado must accept 'nis2'."""
    from evals.schemas import GoldCaseChat

    gc = GoldCaseChat(
        id="nis2-001",
        tipo="chat",
        entrada="q",
        corpus_esperado="nis2",
        articulos_esperados=["1"],
        severidad_esperada=None,
        criterios_evaluacion=["c"],
        salida_esperada=None,
        requiere_revision_humana=False,
        expected_verdict="pass",
    )
    assert gc.corpus_esperado == "nis2"


def test_goldcasechat_accepts_dora() -> None:
    """GoldCaseChat.corpus_esperado must accept 'dora'."""
    from evals.schemas import GoldCaseChat

    gc = GoldCaseChat(
        id="dora-001",
        tipo="chat",
        entrada="q",
        corpus_esperado="dora",
        articulos_esperados=["2"],
        severidad_esperada=None,
        criterios_evaluacion=["c"],
        salida_esperada=None,
        requiere_revision_humana=False,
        expected_verdict="pass",
    )
    assert gc.corpus_esperado == "dora"


def test_goldcasedoc_corpus_esperado_accepts_nis2_dora() -> None:
    """GoldCaseDoc.corpus_esperado list must accept nis2 and dora entries."""
    from evals.schemas import GoldCaseDoc

    gc = GoldCaseDoc(
        id="doc-nis2-001",
        tipo="document",
        pdf_path="redteam/documents/fake.pdf",
        corpus_esperado=["nis2", "dora"],
        expected_findings_articulos=["1"],
        expected_document_verdict="pass",
        expected_n_segments=1,
        criterios_evaluacion=["c"],
    )
    assert "nis2" in gc.corpus_esperado
    assert "dora" in gc.corpus_esperado


def test_loader_gate_only_landed_corpora() -> None:
    """CORPORA_WITH_MANIFESTS must equal exactly the set of manifest files on disk."""
    from pathlib import Path

    from regulaitor.corpus.loader import CORPORA_WITH_MANIFESTS

    landed = {p.stem for p in Path("corpus/manifests").glob("*.json")}
    assert set(CORPORA_WITH_MANIFESTS) == landed, (
        f"CORPORA_WITH_MANIFESTS={set(CORPORA_WITH_MANIFESTS)} != " f"landed manifests={landed}"
    )
