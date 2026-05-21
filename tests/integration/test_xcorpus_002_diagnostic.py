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


def test_call4_v0_1_10_cap2_diversifies_within_nis2_but_does_not_fix_xcorpus_002() -> None:
    """v0.1.10 Call 4: with `max_chunks_per_article=2` and otherwise defaults,
    the emitted set MUST diversify within NIS2 (no longer 5×nis2.23) but MUST
    STILL miss NIS2 art 35 and GDPR art 33 (purity gate still collapses to NIS2
    because the deduped top-5 is still 5/5 NIS2 in distinct articles).

    This pins the v0.1.10 honest finding: per-article cap works algorithmically
    but does not fix xcorpus-002 alone; the reranker bias is at NORMA level,
    not just ARTICLE level. If this fails (cap now surfaces NIS2 35 or GDPR 33),
    the v0.1.10 conclusion needs revisiting and the next-step candidates (per-norma
    cap, raise top_k, different reranker) may not all be needed."""
    cfg = retrieval.RetrievalConfig(max_chunks_per_article=2)
    chunks, resolved = retrieval.run_auto(QUERY, "es", cfg)
    emitted = _emitted_pairs(chunks)

    # Algorithm-level success: cap recovers article diversity within NIS2.
    distinct_nis2_articles = {a for (n, a) in emitted if n == "nis2"}
    assert len(distinct_nis2_articles) >= 2, (
        f"cap=2 should have produced at least 2 distinct NIS2 articles in top-5, "
        f"but got distinct={distinct_nis2_articles} from emitted={emitted}. "
        "Either the dedup helper regressed, or the reranker output changed."
    )

    # System-level failure preservation: cap alone does NOT recover NIS2 35 / GDPR 33.
    assert list(resolved) == ["nis2"], (
        f"purity gate did not collapse to NIS2 alone with cap=2 (got resolved={resolved}). "
        "v0.1.10 baseline was still NIS2-only collapse — narrative needs re-check."
    )
    assert ("nis2", "35") not in emitted, (
        "NIS2 art 35 unexpectedly surfaced with cap=2 alone. The v0.1.10 honest "
        "finding was that cap=2 algorithm-works but does NOT fix xcorpus-002 — "
        "reranker bias is at norma level, not article level. Re-investigate."
    )
    assert ("gdpr", "33") not in emitted, (
        "GDPR art 33 unexpectedly surfaced with cap=2 alone. Same as above — "
        "v0.1.10 honest finding was that cap=2 does NOT fix xcorpus-002."
    )


def test_call5_v0_1_10_cap2_plus_lower_threshold_produces_identical_set_to_call4() -> None:
    """v0.1.10 Call 5: cap=2 + purity_threshold=0.5 produces the SAME emitted
    set as cap=2 alone (Call 4) — because top-5 deduped is still 5/5 NIS2 in
    distinct articles, so `dominant_norma_share = 1.0 ≥ 0.5` and the gate
    collapses regardless of whether the threshold is 0.6 or 0.5.

    If this fails: lowering the threshold WITH the cap now changes the output,
    which would be unexpected and would re-open the question of whether
    combining cap + lower threshold could fix xcorpus-002 after all."""
    cfg_cap_only = retrieval.RetrievalConfig(max_chunks_per_article=2)
    cfg_combo = retrieval.RetrievalConfig(max_chunks_per_article=2, purity_threshold=0.5)
    chunks_cap_only, _ = retrieval.run_auto(QUERY, "es", cfg_cap_only)
    chunks_combo, _ = retrieval.run_auto(QUERY, "es", cfg_combo)

    assert _emitted_pairs(chunks_cap_only) == _emitted_pairs(chunks_combo), (
        "cap=2 + purity=0.5 changed the emitted set vs cap=2 alone — "
        "v0.1.10 baseline showed identical output because dominant-norma share "
        "was 1.0 in both. The combo now matters; re-investigate fix candidates."
    )


def test_call8_v0_1_11_cap_per_norma_2_breakthrough_surfaces_gdpr_33() -> None:
    """v0.1.11 Call 8: with `max_chunks_per_norma=2` and otherwise defaults,
    the gate is mathematically forced to multi-corpus (max-share 2/5=0.4 < 0.6
    default threshold). MEASURED: emits `nis2.23, nis2.23, dora.19, dora.22,
    gdpr.33` → resolved_normas = [dora, gdpr, nis2] → 2/3 expected articles
    surfaced (NIS2 23 + GDPR 33). NIS2 35 still missed (reranker scores it
    below DORA 19/22 — deeper ceiling carried to v0.1.12).

    This pins the v0.1.11 breakthrough — real measured 1/3 → 2/3 improvement
    over baseline. If this fails (cap=2 no longer surfaces GDPR 33), the
    purity gate / reranker changed and v0.1.11's narrative needs revisit."""
    cfg = retrieval.RetrievalConfig(max_chunks_per_norma=2)
    chunks, resolved = retrieval.run_auto(QUERY, "es", cfg)
    emitted = _emitted_pairs(chunks)

    # Multi-corpus emission (the structural breakthrough): purity gate did NOT
    # collapse to a single norma because max-share = 2/5 = 0.4 < 0.6 threshold.
    assert len(set(resolved)) >= 2, (
        f"purity gate collapsed under cap_per_norma=2 (resolved={resolved}); "
        "the math (2/5=0.4 < 0.6 threshold) should have prevented this. "
        "Either the gate or reranker changed; re-investigate."
    )
    assert "gdpr" in resolved, (
        f"GDPR not in resolved_normas under cap=2 (resolved={resolved}); "
        "v0.1.11 baseline had GDPR 33 surfaced as part of the breakthrough."
    )

    # The 2/3 expected articles surfaced (real measured improvement vs 1/3 baseline).
    assert ("nis2", "23") in emitted, "NIS2 23 missing — was always present in baseline."
    assert ("gdpr", "33") in emitted, (
        "GDPR 33 missing — was the v0.1.11 breakthrough vs the 1/3 baseline. "
        "Re-investigate whether reranker scoring changed for this query."
    )
    # NIS2 35 STILL missing — the deeper ceiling carried to v0.1.12.
    assert ("nis2", "35") not in emitted, (
        "NIS2 35 unexpectedly surfaced under cap=2 alone. The v0.1.11 honest "
        "finding was that NIS2 35 is below DORA 19/22 in the reranker → not in "
        "deduped top-5. If it now surfaces, the reranker improved and the "
        "v0.1.12 candidate (raise top_k 5→12) may not be needed."
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
