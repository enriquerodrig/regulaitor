"""Fase 6 — AML/MiCA/TFR corpus: norma registration + §6 validator path.

Pins that the three new normas (amlr = 32024R1624, mica = 32023R1114, tfr =
32023R1113) are registered, loadable, and validate citations through the SAME
byte-unchanged citation/validator.py path (real snippet passes, fabrication
fails). Uses committed manifests; no LanceDB / BGE-M3 needed."""

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


def test_aml_mica_normas_registered() -> None:
    for n in ("amlr", "mica", "tfr"):
        assert n in CORPORA_WITH_MANIFESTS


def test_key_articles_loadable() -> None:
    # AMLR Art 20 = customer due diligence; MiCA Art 59 = CASP authorisation;
    # TFR Art 14 = crypto travel-rule information.
    assert "diligencia debida" in loader.get_paragraph("amlr", "20", "1", "es")
    assert len(loader.get_paragraph("mica", "59", "1", "es")) > 80
    assert "criptoactivos" in loader.get_paragraph("tfr", "14", "1", "es")


def test_section6_validates_real_and_blocks_fabrication() -> None:
    """§6 holds against the new corpora: verbatim snippet validates; a fabricated
    obligation does not (validator byte-unchanged)."""
    real = loader.get_paragraph("amlr", "20", "1", "es")
    ok = validate(
        Citation(norma="amlr", articulo="20", apartado="1", language="es", text=real[20:120])
    )
    assert ok.validated is True
    assert ok.failed_check is None

    bad = validate(
        Citation(
            norma="mica",
            articulo="59",
            apartado="1",
            language="es",
            text="los CASP estan exentos de toda autorizacion en la union europea",
        )
    )
    assert bad.validated is False
    assert bad.failed_check == 3
