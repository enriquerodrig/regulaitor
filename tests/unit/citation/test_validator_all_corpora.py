"""P3.5: the §6 validator rejects fabricated articles for ALL 9 corpora.

The HX corpus expansion added seven norms (NIS2, DORA, two DORA RTS, AMLR,
MiCA, TFR) — and with them a fabrication surface the red team suite did not
cover explicitly (an attack citing a non-existent MiCA article, say). This
test proves the §6 guard is corpus-agnostic: Check 1 (article_exists) is a
key lookup against the on-disk corpus, so a fabricated article of *any*
registered norma is rejected the same way AI Act art. 99999 is.

Runs $0 — no LLM, no LanceDB; only ``loader.warmup()`` (processed JSON on
disk). The chat fabrication attacks (attack-051..059 in ``attacks.jsonl``)
exercise the same surface end-to-end and are verified in the paid full run.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import validate
from regulaitor.corpus import loader
from regulaitor.corpus.registry import ALL_NORMAS


@pytest.fixture(scope="module")
def warm_corpus() -> Iterator[None]:
    """Load the real corpus once, then restore cold state so pytest-randomly
    ordering cannot leak a warmed loader into tests that assume it is cold."""
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


@pytest.mark.parametrize("norma", ALL_NORMAS)
def test_fabricated_article_rejected_for_every_corpus(warm_corpus: None, norma: str) -> None:
    citation = Citation(
        norma=norma,  # type: ignore[arg-type]  # ALL_NORMAS members are Norma
        articulo="99999",  # no corpus has article 99999
        language="es",
        text="texto normativo fabricado que no existe en el corpus oficial",
    )
    result = validate(citation)
    assert result.validated is False
    assert result.article_exists is False
    assert result.failed_check == 1  # article_not_found — the fabrication guard fired
