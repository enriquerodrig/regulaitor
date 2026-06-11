"""Single source of truth for per-norma corpus configuration (ADR-0037).

Adding a corpus to the system used to mean editing ~15 hardcoded enumeration
sites (the closed-`Norma`-Literal cost noted in ADR-0036). This registry holds
every per-norma datum once; the ingest maps, validation counts, CLI/API/UI
choice lists, and corpus-chip styling all DERIVE from it. The static `Norma` and
`CorpusSelector` Literals (`schemas.py`) stay manual (mypy/Pydantic need a
compile-time type), but `tests/unit/corpus/test_registry_consistency.py` asserts
the two Literals and the registry keys never desync — so a new corpus is exactly
three edits in two files (the `Norma` + `CorpusSelector` Literals in `schemas.py`
+ one entry here) and nothing can be silently missed.

The ingest inputs (`celex`, `version`, `expected_articles`) CANNOT derive from
the manifests — they are needed BEFORE the manifest exists (the manifest is the
*output* of ingest). The display fields (`label`, `color`) are human-curated.
Hence a declared registry rather than a manifest-derived one.
"""

from __future__ import annotations

from dataclasses import dataclass

from regulaitor.corpus.schemas import Norma


@dataclass(frozen=True)
class CorpusSpec:
    """Everything the system needs to know about one corpus, in one place."""

    celex: str  # EUR-Lex CELEX (ingest input — fetch/pin before manifest exists)
    version: str  # consolidation / OJ-publication date YYYY-MM-DD
    expected_articles: int  # article-count invariant checked at ingest validation
    label: str  # human-readable UI chip label
    color: str  # UI chip accent colour (hex)


# The ONE place per-norma data lives. Keys MUST match the `Norma` Literal
# (enforced by test_registry_consistency).
CORPUS_REGISTRY: dict[Norma, CorpusSpec] = {
    "ai_act": CorpusSpec("32024R1689", "2024-07-12", 113, "AI Act", "#1E40AF"),
    "gdpr": CorpusSpec("02016R0679-20160504", "2016-05-04", 99, "GDPR", "#047857"),
    "nis2": CorpusSpec("32022L2555", "2022-12-27", 46, "NIS2", "#6D28D9"),
    "dora": CorpusSpec("32022R2554", "2022-12-27", 64, "DORA", "#B45309"),
    "dora_rts_incident": CorpusSpec("32025R0301", "2025-02-20", 7, "DORA RTS Plazos", "#0F766E"),
    "dora_rts_class": CorpusSpec("32024R1772", "2024-06-25", 13, "DORA RTS Clasif.", "#A21CAF"),
    # Fase 6 — AML/MiCA financial-crime + crypto corpus.
    "amlr": CorpusSpec("32024R1624", "2024-06-19", 90, "AMLR", "#9F1239"),  # rose-800
    "mica": CorpusSpec("32023R1114", "2023-06-09", 149, "MiCA", "#0E7490"),  # cyan-700
    "tfr": CorpusSpec("32023R1113", "2023-06-09", 40, "TFR", "#4D7C0F"),  # lime-700
}

# Canonical ordered tuple of all normas — the basis every other enumeration
# (CLI choices, API guard, UI lists, ingest/validate maps) derives from.
ALL_NORMAS: tuple[Norma, ...] = tuple(CORPUS_REGISTRY)
