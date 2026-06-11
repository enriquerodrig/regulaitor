"""ADR-0037: the CORPUS_REGISTRY is the single source of truth for per-norma
data. These tests make a desync impossible (the static Norma Literal must match
the registry keys) and pin that every derived enumeration equals the values it
replaced (regression-zero)."""

from __future__ import annotations

from typing import get_args

from regulaitor.corpus.registry import ALL_NORMAS, CORPUS_REGISTRY
from regulaitor.corpus.schemas import CorpusSelector, Norma


def test_norma_literal_matches_registry_keys() -> None:
    """A new corpus is exactly: the Norma + CorpusSelector Literals + one
    registry entry. If they desync (a forgotten edit), this fails — nothing
    is silently missed."""
    assert set(get_args(Norma)) == set(CORPUS_REGISTRY)


def test_corpus_selector_is_normas_plus_auto() -> None:
    assert set(get_args(CorpusSelector)) == set(get_args(Norma)) | {"auto"}


def test_all_normas_is_registry_keys_in_order() -> None:
    assert tuple(CORPUS_REGISTRY) == ALL_NORMAS


# --- regression: derived values must equal the previously-hardcoded ones ---


def test_celex_values_unchanged() -> None:
    expected = {
        "ai_act": "32024R1689",
        "gdpr": "02016R0679-20160504",
        "nis2": "32022L2555",
        "dora": "32022R2554",
        "dora_rts_incident": "32025R0301",
        "dora_rts_class": "32024R1772",
        "amlr": "32024R1624",
        "mica": "32023R1114",
        "tfr": "32023R1113",
    }
    assert {n: s.celex for n, s in CORPUS_REGISTRY.items()} == expected


def test_version_values_unchanged() -> None:
    expected = {
        "ai_act": "2024-07-12",
        "gdpr": "2016-05-04",
        "nis2": "2022-12-27",
        "dora": "2022-12-27",
        "dora_rts_incident": "2025-02-20",
        "dora_rts_class": "2024-06-25",
        "amlr": "2024-06-19",
        "mica": "2023-06-09",
        "tfr": "2023-06-09",
    }
    assert {n: s.version for n, s in CORPUS_REGISTRY.items()} == expected


def test_expected_article_counts_unchanged() -> None:
    expected = {
        "ai_act": 113,
        "gdpr": 99,
        "nis2": 46,
        "dora": 64,
        "dora_rts_incident": 7,
        "dora_rts_class": 13,
        "amlr": 90,
        "mica": 149,
        "tfr": 40,
    }
    assert {n: s.expected_articles for n, s in CORPUS_REGISTRY.items()} == expected


def test_norma_style_unchanged() -> None:
    expected = {
        "ai_act": ("AI Act", "#1E40AF"),
        "gdpr": ("GDPR", "#047857"),
        "nis2": ("NIS2", "#6D28D9"),
        "dora": ("DORA", "#B45309"),
        "dora_rts_incident": ("DORA RTS Plazos", "#0F766E"),
        "dora_rts_class": ("DORA RTS Clasif.", "#A21CAF"),
        "amlr": ("AMLR", "#9F1239"),
        "mica": ("MiCA", "#0E7490"),
        "tfr": ("TFR", "#4D7C0F"),
    }
    assert {n: (s.label, s.color) for n, s in CORPUS_REGISTRY.items()} == expected


def test_derived_module_constants_track_the_registry() -> None:
    """CTR-1/CTR-3: the constants other modules expose must DERIVE from the
    registry, not be re-hardcoded. This turns red the moment any consumer stops
    deriving (e.g. a re-hardcoded dict with a typo) — the regression the refactor
    exists to prevent, for ALL six normas (not registry-vs-literals only)."""
    from regulaitor.corpus.ingest import CELEX, VERSION
    from regulaitor.corpus.loader import CORPORA_WITH_MANIFESTS
    from regulaitor.corpus.validate import EXPECTED_ARTICLE_COUNTS
    from regulaitor.ui_streamlit._render import _NORMA_STYLE

    assert {n: s.celex for n, s in CORPUS_REGISTRY.items()} == CELEX
    assert {n: s.version for n, s in CORPUS_REGISTRY.items()} == VERSION
    assert {n: s.expected_articles for n, s in CORPUS_REGISTRY.items()} == EXPECTED_ARTICLE_COUNTS
    assert {n: (s.label, s.color) for n, s in CORPUS_REGISTRY.items()} == _NORMA_STYLE
    # CORPORA_WITH_MANIFESTS is aliased to ALL_NORMAS (ADR-0037, superseding the
    # ADR-0015 D2 seam — see ADR-0037 §22.22).
    assert tuple(CORPORA_WITH_MANIFESTS) == ALL_NORMAS
