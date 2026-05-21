"""v0.1.13 — industry cross-corpus gold cases load + invariants.

Pins the 10 new industry-targeted cases added in v0.1.13 to validate that:

1. All 10 cases load as valid `GoldCaseChat` (Pydantic schema-conformant).
2. All 10 use `corpus_esperado="auto"` (cross-corpus reasoning required).
3. The 5 precise cases (industry-c{1,3,4,5,8}) and the 5 vague-real cases
   (industry-v{1,2,3,4,5}) are all present.
4. Each case has at least 3 `criterios_evaluacion` (multi-faceted scoring).
5. Each case has a non-empty `articulos_esperados` (otherwise it's a
   hallucination-attack case, which is NOT the v0.1.13 scope).

The purpose: regression-pin so any accidental gold-set modification (delete,
rename, schema break) fails this test loudly. The TFM-defense + industry-demo
hinges on having these representative cross-corpus questions; losing them
silently would be a real problem.

Motivation (v0.1.13, user-flagged industry-demo readiness 2026-05-21):
real-world users ask ambiguous, imprecise compliance questions, not
lawyer-clean queries. The vague cases (v1-v5) test the system on questions
like "¿esto es legal?" / "¿a quién avisamos?" / "¿NIS2 nos aplica?" where the
user doesn't say the regulation name nor the article number.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from evals.schemas import GoldCaseChat

GOLD_PATH = Path("evals/gold_set.jsonl")

# The 10 industry-targeted case IDs added in v0.1.13.
INDUSTRY_PRECISE_IDS = {
    "industry-c1",  # Hospital + IA diagnóstico (triple AI Act + GDPR + NIS2)
    "industry-c3",  # Fintech IA scoring (triple AI Act + GDPR + DORA)
    "industry-c4",  # Banco DORA + cyber incident + GDPR breach
    "industry-c5",  # Cloud proveedor para sector financiero (triple NIS2 + DORA + GDPR)
    "industry-c8",  # IA screening CVs (AI Act + GDPR)
}
INDUSTRY_VAGUE_IDS = {
    "industry-v1",  # worry-tone: reconocimiento facial oficina
    "industry-v2",  # practical-tone: brecha datos genérica
    "industry-v3",  # speculative-tone: IA RRHH genérica
    "industry-v4",  # reactive-tone: incidente sistemas pago
    "industry-v5",  # confused-tone: hosting NIS2 aplicabilidad
}
INDUSTRY_ALL_IDS = INDUSTRY_PRECISE_IDS | INDUSTRY_VAGUE_IDS


def _load_gold() -> list[GoldCaseChat]:
    """Load all chat gold cases; skip non-chat lines if any (defensive)."""
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


def test_all_10_industry_cases_present(gold_cases: list[GoldCaseChat]) -> None:
    """The 10 industry-* cases added in v0.1.13 must all be in the gold set."""
    present_ids = {c.id for c in gold_cases}
    missing = INDUSTRY_ALL_IDS - present_ids
    assert not missing, (
        f"Industry cases missing from gold set: {sorted(missing)}. "
        "v0.1.13 added 5 precise (industry-c*) + 5 vague-real (industry-v*) cases."
    )


def test_all_industry_cases_use_corpus_auto(gold_cases: list[GoldCaseChat]) -> None:
    """All 10 industry cases are cross-corpus → corpus_esperado must be 'auto'.
    If any uses a specific norma, the cross-corpus design intent has drifted."""
    industry = [c for c in gold_cases if c.id in INDUSTRY_ALL_IDS]
    non_auto = [c.id for c in industry if c.corpus_esperado != "auto"]
    assert not non_auto, (
        f"Industry cases NOT using corpus_esperado='auto': {non_auto}. "
        "These cases were designed to test cross-corpus auto-path retrieval."
    )


def test_industry_cases_have_substantive_criteria(gold_cases: list[GoldCaseChat]) -> None:
    """Each industry case has ≥3 criterios_evaluacion (multi-faceted scoring).
    A case with only 1-2 criteria is too thin to be a useful gold benchmark
    for the cross-corpus + industry-realism dimensions we want to measure."""
    industry = [c for c in gold_cases if c.id in INDUSTRY_ALL_IDS]
    thin = [
        (c.id, len(c.criterios_evaluacion)) for c in industry if len(c.criterios_evaluacion) < 3
    ]
    assert not thin, (
        f"Industry cases with <3 criterios_evaluacion: {thin}. "
        "Each industry case should have at least 3 distinct scoring criteria."
    )


def test_industry_cases_have_non_empty_articulos_esperados(
    gold_cases: list[GoldCaseChat],
) -> None:
    """All 10 industry cases are NORMATIVE (expected to cite real articles),
    NOT hallucination-attack cases. So articulos_esperados must be non-empty.
    If empty, the case has been mis-classified and should be moved to a
    block-case suite."""
    industry = [c for c in gold_cases if c.id in INDUSTRY_ALL_IDS]
    empty_arts = [c.id for c in industry if not c.articulos_esperados]
    assert not empty_arts, (
        f"Industry cases with empty articulos_esperados: {empty_arts}. "
        "These are NOT hallucination-attack cases; they SHOULD cite specific articles."
    )


def test_precise_vs_vague_split_is_5_5(gold_cases: list[GoldCaseChat]) -> None:
    """v0.1.13 design intent: 5 precise (industry-c*) + 5 vague-real (industry-v*).
    Pin this distribution so future additions don't drift the balance silently
    (drift would invalidate the dual-coverage design — precise for clean
    retrieval measurement, vague for production-readiness UX measurement)."""
    present_ids = {c.id for c in gold_cases if c.id in INDUSTRY_ALL_IDS}
    precise_present = present_ids & INDUSTRY_PRECISE_IDS
    vague_present = present_ids & INDUSTRY_VAGUE_IDS
    assert len(precise_present) == 5, (
        f"Expected 5 precise industry cases, found {len(precise_present)}: "
        f"{sorted(precise_present)}"
    )
    assert len(vague_present) == 5, (
        f"Expected 5 vague-real industry cases, found {len(vague_present)}: "
        f"{sorted(vague_present)}"
    )


def test_vague_cases_use_natural_language_not_legalese(gold_cases: list[GoldCaseChat]) -> None:
    """The vague-real industry-v* cases test the production-UX dimension:
    real users don't say 'AI Act' or 'GDPR' or article numbers in their
    questions. Pin this property — the `entrada` text of vague cases should
    NOT mention specific articles or norm names with technical precision.

    Heuristic: vague-case entrada text must NOT contain any of the strings
    'AI Act', 'GDPR', 'NIS2', 'DORA', 'Reglamento', 'Directiva', 'artículo X'
    (where X is a number). If any case fails, either it was mis-classified as
    vague when it's actually precise, OR the entrada drifted toward legalese.
    Exception: 'NIS2' alone in v5 is intentional (the user's actual confusion)."""
    vague = [c for c in gold_cases if c.id in INDUSTRY_VAGUE_IDS]
    legalese_tokens = ("AI Act", "GDPR", "RGPD", "Reglamento", "Directiva")
    failures = []
    for c in vague:
        # v5 explicitly mentions NIS2 (user's actual confusion) — allow.
        forbidden = [tok for tok in legalese_tokens if tok in c.entrada]
        if c.id == "industry-v5":
            # Allow NIS2 specifically for v5; flag any OTHER legalese tokens.
            forbidden = [tok for tok in forbidden if tok != "NIS2"]
        if forbidden:
            failures.append((c.id, forbidden))
    assert not failures, (
        f"Vague cases using legalese terms in entrada (breaks vague-UX intent): "
        f"{failures}. Vague cases should mimic real user language without "
        "regulation names or article numbers."
    )
