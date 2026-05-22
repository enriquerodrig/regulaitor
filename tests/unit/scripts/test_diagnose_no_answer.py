"""v0.1.17 + v0.1.17.1 — No-Answer residual classifier ($0 cache-mining diagnostic).

v0.1.17 pins the original 4-bucket taxonomy from spec §2 D3:
- refusal: actual_answer contains a REFUSAL_PHRASES seed phrase.
- analyst_raise: no cache entry matched for the case's query.
- transport_error: actual_answer is empty OR "(backend error)" sentinel.
- other: actual_answer is non-empty + no refusal phrase (needs manual review).

v0.1.17.1 extends to 5 buckets (per-case inspection of v0.1.17's `other` cases
surfaced a 5th mechanism: prose_without_findings — Analyst emits substantive
prose into `text` without structured Findings) + expands REFUSAL_PHRASES seed
22 → 25 (3 ES `atendida` phrases observed in chat-014/015 redteam-block cases):
- prose_without_findings (NEW): actual_answer > 100 chars + no refusal phrase.

Plus the cache-mining helpers (query→actual_answer extractor) and the
markdown report parser (per-case appendix → ReportCase).

Sources of truth:
- docs/superpowers/specs/2026-05-21-v0.1.17-no-answer-residual-design.md
- docs/superpowers/specs/2026-05-22-v0.1.17.1-no-answer-fix-design.md
"""

from __future__ import annotations

import json

from scripts.diagnose_no_answer import (
    REFUSAL_PHRASES,
    REFUSAL_PHRASES_EN,
    REFUSAL_PHRASES_ES,
    CacheEntry,
    ReportCase,
    classify_no_answer_case,
    find_actual_answer_in_cache,
    parse_no_answer_cases_from_report,
)

# --- Synthetic fixtures ---------------------------------------------------


def _make_cache_entry(query: str, actual_answer: str) -> CacheEntry:
    """Build a CacheEntry shaped like the real evals/cache/*.json files.

    Real cache files have request.user as a JSON STRING (not a parsed object).
    The extractor parses it. We mirror that shape here.
    """
    user_payload = json.dumps(
        {
            "query": query,
            "actual_answer": actual_answer,
            "expected_answer": "...",
            "cited_articles": [],
            "expected_articles": [],
            "criteria": ["criterion 1"],
        }
    )
    return CacheEntry(
        path="<synthetic>",
        request_user_json=user_payload,
    )


def _make_report_case(
    case_id: str = "chat-008",
    expected_articles: list[str] | None = None,
    expected_verdict: str = "pass",
    query: str = "¿Qué dice el AI Act sobre supervisión humana?",
) -> ReportCase:
    return ReportCase(
        report_file="latest.md",
        case_id=case_id,
        expected_articles=expected_articles or ["14.1", "14.2"],
        expected_verdict=expected_verdict,
        actual_verdict="requires_human_review",
        query=query,
    )


# --- Refusal-phrase classification ---------------------------------------


def test_classify_refusal_via_phrase_match() -> None:
    """Each phrase in REFUSAL_PHRASES seed list, when present in actual_answer,
    returns 'refusal'."""
    case = _make_report_case()
    for phrase in REFUSAL_PHRASES:
        answer = f"Lo siento, {phrase} para esta consulta concreta."
        cache_entries = [_make_cache_entry(case.query, answer)]
        result = classify_no_answer_case(case, cache_entries)
        assert (
            result.classification == "refusal"
        ), f"Phrase {phrase!r} should yield 'refusal'; got {result.classification!r}"
        assert result.matched_phrase is not None
        assert phrase.lower() in result.matched_phrase.lower()


def test_classify_refusal_phrase_match_is_case_insensitive() -> None:
    """Refusal phrases match case-insensitively."""
    case = _make_report_case()
    answer = "EL CORPUS NO RESPALDA esta afirmación."  # uppercase
    cache_entries = [_make_cache_entry(case.query, answer)]
    result = classify_no_answer_case(case, cache_entries)
    assert result.classification == "refusal"


# --- Transport / sentinel classification ---------------------------------


def test_classify_transport_error_on_sentinel_string() -> None:
    """actual_answer == '(backend error)' → 'transport_error'."""
    case = _make_report_case()
    cache_entries = [_make_cache_entry(case.query, "(backend error)")]
    result = classify_no_answer_case(case, cache_entries)
    assert result.classification == "transport_error"


def test_classify_transport_error_on_empty_string() -> None:
    """actual_answer == '' → 'transport_error'."""
    case = _make_report_case()
    cache_entries = [_make_cache_entry(case.query, "")]
    result = classify_no_answer_case(case, cache_entries)
    assert result.classification == "transport_error"


# --- Analyst raise (no cache entry) classification -----------------------


def test_classify_analyst_raise_when_no_cache_entry() -> None:
    """No matching cache entry → 'analyst_raise' (most likely: Analyst raised
    before judge was called; no actual_answer ever cached)."""
    case = _make_report_case(query="¿Pregunta sin entrada en cache?")
    # Cache has entries for OTHER queries, not this one.
    cache_entries = [
        _make_cache_entry("Otra pregunta", "Respuesta cualquiera"),
        _make_cache_entry("Una más", "Texto"),
    ]
    result = classify_no_answer_case(case, cache_entries)
    assert result.classification == "analyst_raise"
    assert result.matched_phrase is None
    assert result.actual_answer_snippet == "(not in cache)"


# --- Other (non-refusal prose) classification ----------------------------


def test_classify_prose_just_above_100_char_threshold() -> None:
    """v0.1.17.1: short-but-over-threshold non-refusal prose (113 chars,
    just above the 100-char heuristic) → 'prose_without_findings'.

    This pairs with `test_classify_other_when_short_non_refusal` (≤100
    chars boundary) and `test_classify_prose_without_findings_when_long_substantive`
    (>200 chars typical) to fully pin the boundary behavior:
        ≤100 chars                  → other
        >100 chars (just above)     → prose_without_findings  ← this test
        >200 chars (typical)        → prose_without_findings
    """
    case = _make_report_case()
    # Real-shaped prose that does NOT contain any refusal phrase.
    # This text is 113 chars, just above the 100-char threshold.
    answer = (
        "El artículo 12 del AI Act regula los registros automáticos de "
        "eventos durante el funcionamiento del sistema."
    )
    cache_entries = [_make_cache_entry(case.query, answer)]
    result = classify_no_answer_case(case, cache_entries)
    assert result.classification == "prose_without_findings"
    assert result.matched_phrase is None
    assert result.classifier_confidence == "medium"


# --- actual_answer extractor ---------------------------------------------


def test_extract_actual_answer_from_cache_request() -> None:
    """find_actual_answer_in_cache(query, cache_entries) returns the
    actual_answer field of the matching entry's parsed request.user JSON.

    Cache files store request.user as a JSON STRING (not parsed). The
    extractor handles that.
    """
    target_query = "¿Cuál es el plazo de notificación de incidentes?"
    target_answer = "El plazo es de 72 horas según RGPD art 33."
    cache_entries = [
        _make_cache_entry("Otra pregunta", "Otra respuesta"),
        _make_cache_entry(target_query, target_answer),
        _make_cache_entry("Pregunta extra", "Respuesta extra"),
    ]
    result = find_actual_answer_in_cache(target_query, cache_entries)
    assert result == target_answer


def test_extract_actual_answer_returns_none_when_no_match() -> None:
    """find_actual_answer_in_cache returns None when no cache entry matches
    the target query."""
    cache_entries = [_make_cache_entry("Pregunta 1", "Respuesta 1")]
    result = find_actual_answer_in_cache("Pregunta no existente", cache_entries)
    assert result is None


# --- Report parser -------------------------------------------------------


def test_parse_no_answer_cases_from_report() -> None:
    """Given a synthetic per-case markdown block with emitted=[] +
    requires_human_review, parse_no_answer_cases_from_report yields a
    ReportCase entry."""
    md = """
# Some Report

## Aggregate metrics

| metric | value |
|---|---|

## Per-case appendix — chat (2 cases)

### chat-008

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['14.1', '14.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00
  context_recall=0.00

### chat-009

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`info` ✅
- **Citations**: emitted=['5.1'] expected=['5.1'] precision=1.00 recall=1.00
- **RAG metrics**: faithfulness=0.80 answer_relevancy=0.85 context_precision=1.00
  context_recall=1.00
"""
    cases = parse_no_answer_cases_from_report(md, report_file="synthetic.md")
    # Only chat-008 is a no_answer case (emitted=[] + verdict mismatch).
    # chat-009 has emitted=['5.1'] and verdict match → NOT no_answer.
    assert len(cases) == 1
    assert cases[0].case_id == "chat-008"
    assert cases[0].actual_verdict == "requires_human_review"
    assert cases[0].expected_verdict == "pass"
    assert cases[0].expected_articles == ["14.1", "14.2"]


def test_parse_handles_cross_corpus_case_ids() -> None:
    """The parser must recognize non-chat case IDs (dora-001, nis2-XXX,
    industry-c1, etc.) since holdout reports include H14 cross-corpus cases."""
    md = """
### dora-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['17', '19'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00
  context_recall=0.00
"""
    cases = parse_no_answer_cases_from_report(md, report_file="holdout-v1.2-chat.md")
    assert len(cases) == 1
    assert cases[0].case_id == "dora-001"


# --- Seed-list regression anchor -----------------------------------------


def test_refusal_phrases_seed_list_pinned() -> None:
    """The REFUSAL_PHRASES seed list has exactly 19 Spanish + 6 English
    entries (v0.1.17.1: +3 ES for "atendida" patterns observed in
    chat-014/015). Pin to catch accidental drift (seed expansion must be
    intentional + accompanied by a follow-up plan)."""
    assert (
        len(REFUSAL_PHRASES_ES) == 19
    ), f"REFUSAL_PHRASES_ES drift: expected 19, got {len(REFUSAL_PHRASES_ES)}"
    assert (
        len(REFUSAL_PHRASES_EN) == 6
    ), f"REFUSAL_PHRASES_EN drift: expected 6, got {len(REFUSAL_PHRASES_EN)}"
    # Pin a few specific phrases as canary entries (catches reordering /
    # accidental edits).
    assert "no encuentro" in REFUSAL_PHRASES_ES
    assert "el corpus no respalda" in REFUSAL_PHRASES_ES
    assert "fuera del ámbito del corpus" in REFUSAL_PHRASES_ES
    assert "i cannot provide" in REFUSAL_PHRASES_EN
    assert "the corpus does not support" in REFUSAL_PHRASES_EN
    # v0.1.17.1 additions (evidence-driven, observed in chat-014/015
    # redteam-block cases that the 22-entry seed missed).
    assert "esta solicitud no puede ser atendida" in REFUSAL_PHRASES_ES
    assert "esta consulta no puede ser atendida" in REFUSAL_PHRASES_ES
    assert "no se puede atender" in REFUSAL_PHRASES_ES
    # Total = 25.
    assert len(REFUSAL_PHRASES) == 25


# --- v0.1.17.1: 5th bucket (prose_without_findings) + new refusal phrases ---


def test_classify_prose_without_findings_when_long_substantive() -> None:
    """v0.1.17.1: cache entry present + non-empty + no refusal phrase +
    actual_answer > 100 chars → 'prose_without_findings' (the 5th bucket
    surfaced by v0.1.17 per-case inspection of `other`).

    Uses a real-shaped sample from v0.1.17 docs/no_answer_residual_diagnosis.md
    per-case table (chat-003-style prose answer)."""
    case = _make_report_case()
    # Real-shaped prose answer > 100 chars (substantive AI Act content).
    answer = (
        "El AI Act impone a los proveedores de sistemas de IA de alto riesgo "
        "un conjunto de obligaciones de gestión de riesgos, supervisión humana "
        "y registro automático de eventos durante el funcionamiento del sistema."
    )
    assert len(answer) > 100, "fixture sanity: prose sample must exceed 100 chars"
    cache_entries = [_make_cache_entry(case.query, answer)]
    result = classify_no_answer_case(case, cache_entries)
    assert (
        result.classification == "prose_without_findings"
    ), f"expected 'prose_without_findings', got {result.classification!r}"
    assert result.matched_phrase is None


def test_classify_other_when_short_non_refusal() -> None:
    """v0.1.17.1 boundary test: cache entry present + non-empty + no refusal
    phrase + actual_answer ≤ 100 chars → stays 'other' (the 5th-bucket rule
    applies only to LONG substantive prose; short edge cases stay in `other`
    for manual review per spec D4 conservative-heuristic rationale)."""
    case = _make_report_case()
    answer = "El artículo 12 regula los registros."  # 38 chars, < 100
    assert len(answer) <= 100, "fixture sanity: short sample must be ≤ 100 chars"
    cache_entries = [_make_cache_entry(case.query, answer)]
    result = classify_no_answer_case(case, cache_entries)
    assert (
        result.classification == "other"
    ), f"expected 'other' for short non-refusal, got {result.classification!r}"
    assert result.matched_phrase is None


def test_classify_refusal_with_new_atendida_phrases() -> None:
    """v0.1.17.1: cache entry present + actual_answer contains
    'esta solicitud no puede ser atendida' (or sibling phrase) → 'refusal'.

    Regression anchor that chat-014/015-style redteam-block refusals (which
    classified as `other` in v0.1.17 because the seed missed the phrase) now
    correctly classify as `refusal`."""
    case = _make_report_case()
    answer = (
        "Esta solicitud no puede ser atendida porque implica inventar "
        "contenido normativo no presente en el corpus."
    )
    cache_entries = [_make_cache_entry(case.query, answer)]
    result = classify_no_answer_case(case, cache_entries)
    assert result.classification == "refusal", f"expected 'refusal', got {result.classification!r}"
    assert result.matched_phrase is not None
    assert "atendida" in result.matched_phrase.lower()


def test_recommend_intervention_handles_prose_without_findings_dominant() -> None:
    """v0.1.17.1: when prose_without_findings dominates (> 50%), the
    recommendation must reference prose_without_findings-dominant + v1.4 +
    force-Finding-emission (the v0.1.17.1 intervention itself)."""
    from scripts.diagnose_no_answer import _recommend_intervention

    counts = {
        "refusal": 2,
        "analyst_raise": 0,
        "transport_error": 0,
        "prose_without_findings": 8,
        "other": 0,
    }
    text = _recommend_intervention(counts)
    assert (
        "prose_without_findings-dominant" in text.lower()
    ), "recommendation must label the dominant class"
    assert "v1.4" in text, "recommendation must reference prompt v1.4"
    assert (
        "force-finding-emission" in text.lower() or "force-finding" in text.lower()
    ), "recommendation must mention force-Finding-emission as the intervention shape"
