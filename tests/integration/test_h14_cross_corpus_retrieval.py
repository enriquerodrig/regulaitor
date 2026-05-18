"""$0 deterministic cross-corpus retrieval verification (H14, §16.3-reframe D3).

Tests that NIS2 and DORA chunks are retrievable from the live LanceDB index and
that AI Act retrieval is regression-zero after the 4-corpus expansion.

Deliberately $0 — no Analyst / Auditor / LLM calls; only local BGE-M3 + reranker.

Design decisions
----------------
* Uses the real `retrieval.run` (BGE-M3 embed + LanceDB query + reranker) against
  the live ``corpus/indexes/regulaitor.lance`` index built in Tasks 1-6 of H14.
* Corpus-scoping assertions: chunks returned for a corpus-scoped query must ALL
  carry ``norma == corpus``. ``retrieval.run`` injects a WHERE clause, so a
  scoping failure would be a structural regression, not a quality signal.
* Recall-style article assertions: query text is taken verbatim from the gold set
  (``evals/gold_set.jsonl`` nis2-001, dora-001) and the expected article ids are
  verified against ``corpus/processed/{nis2,dora}_es.json`` before being asserted:
    - NIS2 "a qué entidades se aplica" → art. "2"  (verified: art.2 text = scope)
    - DORA "gestión del riesgo de las TIC marco"  → art. "6"  (verified: art.6 text
      = "marco de gestión del riesgo relacionado con las TIC")
  Both surface at top-1 with scores >0.88 / >0.99 (empirically confirmed probe,
  2026-05-18). If future calibration changes retrieval order so the expected article
  drops out of top-5, the comment below explains why — do NOT weaken to a tautology;
  treat as an H15 calibration concern and annotate explicitly.
* Marked ``@pytest.mark.slow`` (loads BGE-M3 + bge-reranker-v2-m3; ~30-90 s wall).

No LLM, no network beyond model-weight cache. ``--env-file .env`` is for invocation
parity with the CI environment only; nothing paid runs in this module.
"""

from __future__ import annotations

import pytest

from regulaitor.corpus import loader
from regulaitor.rag import reranker, retrieval

pytestmark = pytest.mark.slow

# ---------------------------------------------------------------------------
# Module-scoped warm-up: pay the BGE-M3 + reranker cold-start cost once.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _warm() -> None:  # type: ignore[return]
    loader.reset()
    loader.warmup()
    reranker.warmup()
    yield  # type: ignore[misc]
    loader.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _retrieve(corpus: str, query: str, top_k: int = 5) -> list:
    """Call retrieval.run with Norma/Language literals; return list[RetrievedChunk]."""
    return retrieval.run(query=query, corpus=corpus, language="es", top_k=top_k)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NIS2 tests
# ---------------------------------------------------------------------------


def test_nis2_query_returns_nonempty_chunks() -> None:
    """NIS2 scope query must return at least one chunk."""
    chunks = _retrieve("nis2", "¿A qué entidades se aplica la Directiva NIS2?")
    assert chunks, "no chunks retrieved for nis2 scope query — index may be missing or corrupt"


def test_nis2_chunks_are_from_nis2_corpus() -> None:
    """All chunks returned for a NIS2-scoped query must have norma='nis2'.

    retrieval.run injects WHERE norma='nis2' into LanceDB; if any chunk leaks a
    different norma the scoping logic is broken (structural regression, not quality).
    """
    chunks = _retrieve("nis2", "¿A qué entidades se aplica la Directiva NIS2?")
    assert chunks, "pre-condition: non-empty"
    leaking = [c for c in chunks if c.norma != "nis2"]
    assert not leaking, (
        f"corpus leakage: expected norma='nis2' for all chunks, "
        f"got {[(c.norma, c.articulo) for c in leaking]}"
    )


def test_nis2_scope_query_retrieves_article_2() -> None:
    """NIS2 scope/applicability query must retrieve article '2' in top-5.

    Verified against corpus/processed/nis2_es.json (2026-05-18):
      art.2 text = "La presente Directiva se aplicará a las entidades públicas o
      privadas de alguno de los tipos mencionados en los anexos I o II..."
    Gold set nis2-001 articulos_esperados = ['2', '3'].
    Empirical probe: art.2 is top-1 with score 0.886.

    If this assertion fails after a re-ingest or embedding model upgrade, check
    whether art.2 was re-chunked; do NOT weaken to assert-non-empty — instead
    annotate as an H15 calibration concern with evidence.
    """
    chunks = _retrieve("nis2", "¿A qué entidades se aplica la Directiva NIS2?")
    retrieved_articles = {c.articulo for c in chunks}
    assert "2" in retrieved_articles, (
        f"NIS2 scope query did not retrieve article '2' in top-5. "
        f"Got articles: {retrieved_articles}. "
        f"H15 calibration concern if this regresses after re-ingest."
    )


# ---------------------------------------------------------------------------
# DORA tests
# ---------------------------------------------------------------------------


def test_dora_query_returns_nonempty_chunks() -> None:
    """DORA ICT risk management query must return at least one chunk."""
    chunks = _retrieve("dora", "¿Qué exige DORA sobre gestión del riesgo de las TIC?")
    assert chunks, "no chunks retrieved for dora ICT risk query — index may be missing or corrupt"


def test_dora_chunks_are_from_dora_corpus() -> None:
    """All chunks returned for a DORA-scoped query must have norma='dora'.

    Same structural invariant as the NIS2 scoping test.
    """
    chunks = _retrieve("dora", "¿Qué exige DORA sobre gestión del riesgo de las TIC?")
    assert chunks, "pre-condition: non-empty"
    leaking = [c for c in chunks if c.norma != "dora"]
    assert not leaking, (
        f"corpus leakage: expected norma='dora' for all chunks, "
        f"got {[(c.norma, c.articulo) for c in leaking]}"
    )


def test_dora_ict_risk_query_retrieves_article_6() -> None:
    """DORA ICT risk framework query must retrieve article '6' in top-5.

    Verified against corpus/processed/dora_es.json (2026-05-18):
      art.6 text = "Las entidades financieras contarán con un marco de gestión del
      riesgo relacionado con las TIC sólido, completo y bien documentado..."
    Gold set dora-001 articulos_esperados = ['6'].
    Empirical probe: art.6 is top-1 with score 0.999.

    If this assertion fails after a re-ingest or embedding model upgrade, check
    whether art.6 was re-chunked; do NOT weaken to assert-non-empty — instead
    annotate as an H15 calibration concern with evidence.
    """
    chunks = _retrieve("dora", "¿Qué exige DORA sobre gestión del riesgo de las TIC?")
    retrieved_articles = {c.articulo for c in chunks}
    assert "6" in retrieved_articles, (
        f"DORA ICT risk query did not retrieve article '6' in top-5. "
        f"Got articles: {retrieved_articles}. "
        f"H15 calibration concern if this regresses after re-ingest."
    )


# ---------------------------------------------------------------------------
# AI Act regression-zero test
# ---------------------------------------------------------------------------


def test_aiact_retrieval_unaffected_by_corpus_expansion() -> None:
    """AI Act retrieval must still work after adding NIS2 + DORA to the index.

    Regression-zero: proves that the 4-corpus index expansion (H14 Tasks 1-6)
    did not corrupt or pollute AI Act retrieval.
    Empirical probe (2026-05-18): top-5 for 'sistemas de IA de alto riesgo' are
    all norma='ai_act' (articles 6, 9, 16).
    """
    chunks = _retrieve("ai_act", "sistemas de IA de alto riesgo")
    assert chunks, "ai_act retrieval regressed: no chunks returned after H14 corpus expansion"
    leaking = [c for c in chunks if c.norma != "ai_act"]
    assert not leaking, (
        f"ai_act regression: norma leakage detected after H14 expansion. "
        f"Leaked chunks: {[(c.norma, c.articulo) for c in leaking]}"
    )


# ---------------------------------------------------------------------------
# Loader smoke: all 4 corpora load cleanly (Step 3 of the H14 Task 7 plan)
# ---------------------------------------------------------------------------


def test_all_four_corpora_load_without_error() -> None:
    """warmup() loads all 4 corpora without KeyError or integrity failure.

    Confirms that the manifests, processed JSON, and SHA256 hashes are all
    consistent for ai_act, gdpr, nis2, dora.
    """
    # warmup() already called by the module-scoped _warm fixture; get_manifest
    # raises KeyError if a corpus was not loaded.
    for corpus in loader.CORPORA_WITH_MANIFESTS:
        manifest = loader.get_manifest(corpus)
        assert manifest.corpus == corpus, f"manifest.corpus mismatch for {corpus}"
        assert len(manifest.articles) > 0, f"no articles in manifest for {corpus}"
