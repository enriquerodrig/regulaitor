"""v0.1.15 — industry gap-analysis gold cases load + invariants.

Pins the 10 NEW industry-targeted gap-analysis cases added in v0.1.15:

1. All 10 cases load as valid `GoldCaseChat` (Pydantic schema-conformant).
2. All 10 use `corpus_esperado="auto"` (gap-analysis is typically cross-corpus).
3. All 10 have `expected_verdict="pass"` (gap answers are normal pass verdicts;
   they only block if Auditor catches a bad citation).
4. The 5 precise cases (industry-g{1..5}) and the 5 vague-real cases
   (industry-gv{1..5}) are all present.
5. Each case has ≥3 `criterios_evaluacion` (multi-faceted scoring including
   per-gap coverage AND NOT-emitted constraints for declared controls).
6. Each case has ≥1 `articulos_esperados` (the gap articles — obligations
   the user did NOT declare).
7. Vague-real (`gv*`) cases have `entrada` WITHOUT article-number references
   (production-UX requirement; the v0.1.13 vague-no-legalese pin extended
   to gap-analysis).

Motivation: real industry users will ask "tengo X, ¿qué me falta?" without
naming every article. The vague split tests production-UX; the precise split
tests cleaner retrieval measurement. Measurement deferred to v0.1.20 paid
bundle; this test file pins the gold-set additions structurally so that
accidental deletion/rename/schema break fails loudly NOW.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from evals.schemas import GoldCaseChat

GOLD_PATH = Path("evals/gold_set.jsonl")

INDUSTRY_GAP_PRECISE_IDS = {
    "industry-g1",
    "industry-g2",
    "industry-g3",
    "industry-g4",
    "industry-g5",
}
INDUSTRY_GAP_VAGUE_IDS = {
    "industry-gv1",
    "industry-gv2",
    "industry-gv3",
    "industry-gv4",
    "industry-gv5",
}
INDUSTRY_GAP_ALL_IDS = INDUSTRY_GAP_PRECISE_IDS | INDUSTRY_GAP_VAGUE_IDS

# Article-number reference regex (Spanish + English compact + "art." abbrev).
# Used to enforce vague-no-legalese on `gv*` cases.
_ARTICLE_NUM_RE = re.compile(
    r"\bart(?:[íi]culo|\.?)\s*\d+",
    re.IGNORECASE,
)


def _load_gold() -> list[GoldCaseChat]:
    """Load all chat gold cases (defensive against blank lines)."""
    cases: list[GoldCaseChat] = []
    with GOLD_PATH.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            cases.append(GoldCaseChat.model_validate_json(stripped))
    return cases


@pytest.fixture(scope="module")
def gold_cases() -> list[GoldCaseChat]:
    return _load_gold()


def test_all_10_industry_gap_cases_present(gold_cases: list[GoldCaseChat]) -> None:
    """All 10 industry-g{1..5} + industry-gv{1..5} cases must be in the gold set."""
    present_ids = {c.id for c in gold_cases}
    missing = INDUSTRY_GAP_ALL_IDS - present_ids
    assert not missing, (
        f"Industry gap-analysis cases missing: {sorted(missing)}. "
        "v0.1.15 added 5 precise (industry-g*) + 5 vague-real (industry-gv*) cases."
    )


def test_precise_vs_vague_gap_split_is_5_5(gold_cases: list[GoldCaseChat]) -> None:
    """v0.1.15 design intent: 5 precise + 5 vague-real gap-analysis cases."""
    present_ids = {c.id for c in gold_cases if c.id in INDUSTRY_GAP_ALL_IDS}
    precise_present = present_ids & INDUSTRY_GAP_PRECISE_IDS
    vague_present = present_ids & INDUSTRY_GAP_VAGUE_IDS
    assert len(precise_present) == 5, (
        f"Expected 5 precise gap cases, found {len(precise_present)}: " f"{sorted(precise_present)}"
    )
    assert len(vague_present) == 5, (
        f"Expected 5 vague-real gap cases, found {len(vague_present)}: " f"{sorted(vague_present)}"
    )


def test_all_gap_cases_use_corpus_auto(gold_cases: list[GoldCaseChat]) -> None:
    """Gap-analysis is typically cross-corpus → corpus_esperado must be 'auto'."""
    gaps = [c for c in gold_cases if c.id in INDUSTRY_GAP_ALL_IDS]
    non_auto = [c.id for c in gaps if c.corpus_esperado != "auto"]
    assert not non_auto, f"Gap-analysis cases NOT using corpus_esperado='auto': {non_auto}."


def test_all_gap_cases_expected_verdict_pass(gold_cases: list[GoldCaseChat]) -> None:
    """Gap answers are normal pass verdicts (only block on bad citation)."""
    gaps = [c for c in gold_cases if c.id in INDUSTRY_GAP_ALL_IDS]
    non_pass = [(c.id, c.expected_verdict) for c in gaps if c.expected_verdict != "pass"]
    assert not non_pass, f"Gap-analysis cases with expected_verdict != 'pass': {non_pass}."


def test_gap_cases_have_at_least_one_articulo_esperado(
    gold_cases: list[GoldCaseChat],
) -> None:
    """Gap cases must list the expected gap articles (what user did NOT declare)."""
    gaps = [c for c in gold_cases if c.id in INDUSTRY_GAP_ALL_IDS]
    empty_arts = [c.id for c in gaps if not c.articulos_esperados]
    assert not empty_arts, (
        f"Gap-analysis cases with empty articulos_esperados: {empty_arts}. "
        "Each gap case must list which articles the system should emit as gaps."
    )


def test_gap_cases_have_substantive_criteria(gold_cases: list[GoldCaseChat]) -> None:
    """Each gap case has ≥3 criterios_evaluacion: per-gap coverage AND
    NOT-emitted constraints for declared controls (otherwise the judge cannot
    verify that the system honored the user's declared state)."""
    gaps = [c for c in gold_cases if c.id in INDUSTRY_GAP_ALL_IDS]
    thin = [(c.id, len(c.criterios_evaluacion)) for c in gaps if len(c.criterios_evaluacion) < 3]
    assert not thin, (
        f"Gap cases with <3 criterios_evaluacion: {thin}. "
        "Each gap case should have ≥3 distinct scoring criteria."
    )


def test_vague_gap_cases_have_no_article_number_references(
    gold_cases: list[GoldCaseChat],
) -> None:
    """Vague-real `gv*` cases mirror production-UX: users don't quote article
    numbers. Pin: `entrada` must NOT contain 'art X', 'artículo X' (number).
    Extension of the v0.1.13 vague-no-legalese pin to gap-analysis."""
    vague = [c for c in gold_cases if c.id in INDUSTRY_GAP_VAGUE_IDS]
    failures = []
    for c in vague:
        if _ARTICLE_NUM_RE.search(c.entrada):
            failures.append((c.id, c.entrada))
    assert not failures, (
        f"Vague gap cases with article-number references in `entrada` "
        f"(breaks vague-UX intent): {failures}. Vague gap cases should mimic "
        "real user language without article numbers."
    )
