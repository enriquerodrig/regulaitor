"""v0.1.9 — xcorpus-002 retrieval diagnostic regression pin (slow, $0 local CPU).

Pins the 3 findings of `scripts/diagnose_xcorpus_002.py` (documented in
`docs/xcorpus_002_investigation.md`) so future changes to the retrieval stack
(BGE-M3, reranker, `_apply_purity_gate`, RetrievalConfig defaults) fail this
test loudly if the diagnostic narrative would no longer hold.

The v0.1.9 conclusion was: **root cause = reranker scoring on this query**
(not the purity gate, not dense-retrieval depth). Therefore:

  - Call 1 (defaults purity=0.6): top-5 reranked is dominated by NIS2 art 23
    paragraphs; purity gate collapses to NIS2; NIS2 art 35 and GDPR art 33 are
    NOT surfaced.
  - Call 2 (purity=0.5): identical emitted output to Call 1 — because top-5
    was already pure NIS2 art 23 before the gate, so changing the gate
    threshold cannot recover the missing articles.
  - Call 3 (dense pool 200, no rerank, no gate): all 3 expected articles
    (NIS2 23, NIS2 35, GDPR 33) ARE present in the candidate pool — the
    dense retriever is finding them; the reranker is enterring them.

If any of these invariants flip, the v0.1.9 conclusion needs to be revisited
and the investigation doc re-run.

Marked ``@pytest.mark.slow``: BGE-M3 + reranker cold-load + LanceDB query
takes ~30-60s on CPU. Excluded from the standard ``pytest -m "not slow"``
gate; run explicitly: ``uv run pytest tests/integration/test_xcorpus_002_diagnostic.py -m slow``.

No LLM, $0 — local CPU only.
"""

from __future__ import annotations

import pytest

from regulaitor.corpus import loader
from regulaitor.rag import embeddings, reranker, retrieval, store
from regulaitor.rag.build import INDEX_PATH

pytestmark = pytest.mark.slow

QUERY = (
    "Nuestra organización es operador de infraestructura digital sujeta a "
    "NIS2 y hemos sufrido un incidente que implica fuga de datos personales. "
    "¿Debemos notificarlo solo al CSIRT según NIS2 o también a la autoridad "
    "de protección de datos según el RGPD?"
)


@pytest.fixture(scope="module", autouse=True)
def _warm() -> None:  # type: ignore[return]
    loader.reset()
    loader.warmup()
    reranker.warmup()
    yield  # type: ignore[misc]
    loader.reset()


def _emitted_pairs(chunks: list) -> set[tuple[str, str]]:
    return {(c.norma, c.articulo) for c in chunks}


def test_call1_defaults_collapses_to_nis2_and_misses_35_and_33() -> None:
    """v0.1.9 Call 1: defaults (purity_threshold=0.6) → only NIS2 art 23 surfaces;
    NIS2 art 35 and GDPR art 33 are NOT in the emitted top-5.

    If this fails: the purity gate or reranker behaviour changed; investigate
    whether the v0.1.9 conclusion (reranker-layer root cause) still holds."""
    cfg = retrieval.RetrievalConfig()  # all defaults: purity=0.6, top_k=5, pre_rerank=50
    chunks, resolved = retrieval.run_auto(QUERY, "es", cfg)
    emitted = _emitted_pairs(chunks)

    assert list(resolved) == ["nis2"], (
        f"purity gate did not collapse to NIS2 alone (got resolved_normas={resolved}). "
        "v0.1.9 baseline was NIS2-only collapse — narrative needs re-check."
    )
    assert (
        "nis2",
        "23",
    ) in emitted, f"NIS2 art 23 not in emitted ({emitted}); v0.1.9 baseline had 5x NIS2 23."
    assert ("nis2", "35") not in emitted, (
        "NIS2 art 35 unexpectedly surfaced in Call 1 (defaults). "
        "Reranker improved or purity gate changed — re-investigate."
    )
    assert ("gdpr", "33") not in emitted, (
        "GDPR art 33 unexpectedly surfaced in Call 1 (defaults). "
        "Reranker improved or purity gate changed — re-investigate."
    )


def test_call2_lower_purity_threshold_does_not_change_emitted_set() -> None:
    """v0.1.9 Call 2: purity_threshold=0.5 produces the SAME emitted set as
    Call 1 — the purity gate cannot be the fix because top-5 is already
    pure NIS2 art 23 chunks BEFORE the gate even applies.

    If this fails: lowering threshold now produces different output, which
    would mean the reranker scoring shifted and the v0.1.9 conclusion needs
    a paid re-baseline."""
    cfg_default = retrieval.RetrievalConfig()  # purity=0.6
    cfg_lower = retrieval.RetrievalConfig(purity_threshold=0.5)
    chunks_default, _ = retrieval.run_auto(QUERY, "es", cfg_default)
    chunks_lower, _ = retrieval.run_auto(QUERY, "es", cfg_lower)

    assert _emitted_pairs(chunks_default) == _emitted_pairs(chunks_lower), (
        "Lowering purity_threshold from 0.6 to 0.5 changed the emitted set — "
        "v0.1.9 baseline showed identical output. The purity gate now matters "
        "for this query; conclusion (reranker is root cause) may have changed."
    )


def test_call3_dense_pool_contains_all_three_expected_articles() -> None:
    """v0.1.9 Call 3: at pre_rerank=200, the raw dense pool (no rerank, no
    gate) contains ALL 3 expected articles: NIS2 23, NIS2 35, GDPR 33.

    This is the discriminator that locked in the v0.1.9 conclusion: the dense
    retriever IS finding the expected articles; the reranker is the bottleneck.

    If this fails (an expected article goes missing from the dense pool): the
    dense retriever or the corpus index changed, and v0.1.9's
    'reranker-layer root cause' becomes 'dense-retrieval-layer root cause'."""
    [qvec] = embeddings.embed([QUERY])
    table = store.connect(INDEX_PATH)
    cands = list(table.search(qvec).where("language = 'es'").limit(200).to_list())
    pool_pairs = {(c["norma"], c["articulo"]) for c in cands}

    assert ("nis2", "23") in pool_pairs, (
        "NIS2 art 23 missing from dense pool at pre_rerank=200; "
        "v0.1.9 baseline had it. Dense retrieval regressed."
    )
    assert ("nis2", "35") in pool_pairs, (
        "NIS2 art 35 missing from dense pool at pre_rerank=200; "
        "v0.1.9 baseline had it. Dense retrieval regressed."
    )
    assert ("gdpr", "33") in pool_pairs, (
        "GDPR art 33 missing from dense pool at pre_rerank=200; "
        "v0.1.9 baseline had it. Dense retrieval regressed."
    )
