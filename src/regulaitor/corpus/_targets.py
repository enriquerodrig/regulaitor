"""Shared expansion of corpus and language wildcards.

Lifted from corpus/ingest._expand_targets in H2 to be reusable by rag/build.py.
"""

from __future__ import annotations

from typing import Literal

from regulaitor.corpus.registry import ALL_NORMAS  # single source of truth (ADR-0037)
from regulaitor.corpus.schemas import Language, Norma

__all__ = ["ALL_NORMAS", "ALL_LANGUAGES", "expand_targets"]

ALL_LANGUAGES: tuple[Language, ...] = ("es", "en")


def expand_targets(
    corpus: Norma | Literal["all"],
    languages: list[Language] | Literal["all"],
) -> tuple[list[Norma], list[Language]]:
    """Expand "all" wildcards into concrete lists.

    For corpus: "all" -> all four corpora; specific -> [specific].
    For languages: "all" -> ["es", "en"]; list -> list as-is.
    """
    corpora: list[Norma] = list(ALL_NORMAS) if corpus == "all" else [corpus]
    langs: list[Language] = list(ALL_LANGUAGES) if languages == "all" else list(languages)
    return corpora, langs
