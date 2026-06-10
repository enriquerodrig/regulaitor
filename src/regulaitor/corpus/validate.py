"""Article-level invariants checked after parsing and before manifest write."""

from __future__ import annotations

from dataclasses import dataclass, field

from regulaitor.corpus.formex_parser import ParsedArticle
from regulaitor.corpus.schemas import Norma

EXPECTED_ARTICLE_COUNTS: dict[Norma, int] = {
    "ai_act": 113,
    "gdpr": 99,
    "nis2": 46,  # pinned from real manifest: corpus/manifests/nis2.json (H14)
    "dora": 64,  # pinned from real manifest: corpus/manifests/dora.json (H14)
    "dora_rts_incident": 7,  # Commission Delegated Reg (EU) 2025/301 (Fase 3)
    "dora_rts_class": 13,  # Commission Delegated Reg (EU) 2024/1772 (Fase 3)
}


@dataclass
class ValidationReport:
    coverage_ok: bool
    expected: int
    found: int
    duplicates: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)


class ValidationFailure(Exception):  # noqa: N818
    """Raised when strict validation finds invariants broken."""

    def __init__(self, report: ValidationReport) -> None:
        super().__init__(self._format(report))
        self.report = report

    @staticmethod
    def _format(r: ValidationReport) -> str:
        return (
            f"validation failed: expected={r.expected} found={r.found} "
            f"missing={r.missing} duplicates={r.duplicates} empty={r.empty}"
        )


def validate(
    corpus: Norma,
    articles: list[ParsedArticle],
    *,
    strict: bool = True,
) -> ValidationReport:
    """Validate a list of parsed articles against expected corpus invariants.

    Args:
        corpus: The corpus identifier (must be a key in EXPECTED_ARTICLE_COUNTS).
        articles: Parsed articles to validate.
        strict: If True, raise ValidationFailure when any invariant is broken.

    Returns:
        A ValidationReport describing coverage, duplicates, missing, and empty articles.

    Raises:
        KeyError: If corpus is not a known key in EXPECTED_ARTICLE_COUNTS.
        ValidationFailure: If strict=True and any invariant is violated.
    """
    expected = EXPECTED_ARTICLE_COUNTS[corpus]
    seen: dict[str, int] = {}
    empty: list[str] = []

    for article in articles:
        seen[article.articulo] = seen.get(article.articulo, 0) + 1
        if not article.text.strip():
            empty.append(article.articulo)

    duplicates = sorted(num for num, count in seen.items() if count > 1)
    found_unique = len(seen)
    expected_set = {str(i) for i in range(1, expected + 1)}
    missing = sorted(expected_set - set(seen.keys()), key=lambda x: int(x))

    report = ValidationReport(
        coverage_ok=(found_unique == expected and not duplicates and not empty),
        expected=expected,
        found=found_unique,
        duplicates=duplicates,
        missing=missing,
        empty=empty,
    )
    if strict and not report.coverage_ok:
        raise ValidationFailure(report)
    return report
