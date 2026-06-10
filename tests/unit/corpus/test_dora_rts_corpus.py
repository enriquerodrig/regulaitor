"""Fase 3 — DORA Level-2 RTS corpus: norma registration + §6 validator path.

Pins that the two new normas (dora_rts_incident = 32025R0301, dora_rts_class =
32024R1772) are registered, loadable, and validate citations through the SAME
byte-unchanged citation/validator.py path (real snippet passes, fabrication
fails). Uses committed manifests; no LanceDB / BGE-M3 needed (loader reads the
manifest text, the validator reads the loader)."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import validate
from regulaitor.corpus import loader
from regulaitor.corpus.loader import CORPORA_WITH_MANIFESTS


@pytest.fixture(scope="module", autouse=True)
def _warmup():
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def test_rts_normas_registered() -> None:
    assert "dora_rts_incident" in CORPORA_WITH_MANIFESTS
    assert "dora_rts_class" in CORPORA_WITH_MANIFESTS


def test_incident_rts_article5_loadable() -> None:
    """Art 5 of the incident RTS carries the reporting time limits."""
    text = loader.get_paragraph("dora_rts_incident", "5", "1", "es")
    assert len(text) > 100
    # spelled-out timelines are present in the authentic legal text
    assert "horas" in text and "mes" in text


def test_classification_rts_loadable() -> None:
    text = loader.get_paragraph("dora_rts_class", "1", "1", "es")
    assert len(text) > 50


def test_section6_validates_real_snippet_and_blocks_fabrication() -> None:
    """The §6 invariant holds against the NEW corpus: a verbatim snippet
    validates; a fabricated timeline does not (validator byte-unchanged)."""
    real = loader.get_paragraph("dora_rts_incident", "5", "1", "es")
    snippet = real[20:120]
    ok = validate(
        Citation(
            norma="dora_rts_incident",
            articulo="5",
            apartado="1",
            language="es",
            text=snippet,
        )
    )
    assert ok.validated is True
    assert ok.failed_check is None

    fabricated = validate(
        Citation(
            norma="dora_rts_incident",
            articulo="5",
            apartado="1",
            language="es",
            text="las entidades disponen de noventa dias habiles para notificar",
        )
    )
    assert fabricated.validated is False
    assert fabricated.failed_check == 3
