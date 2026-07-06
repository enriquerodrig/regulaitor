"""Citation validator — 3 strict checks: article exists, apartado exists, text match.

Reuses _normalize from rag/chunking so the citation-vs-corpus comparison uses
the same canonical form the chunker uses (decisions log 2026-05-05 entry
"Citation validator: matching normalizado exacto").
"""

from __future__ import annotations

from typing import Protocol, cast

from regulaitor.citation.schemas import AuditResult, Citation
from regulaitor.corpus import loader as default_loader
from regulaitor.rag.chunking import _normalize

# sec6-01 (pre-pilot audit; ADR-0043): minimum normalized length for a citation's
# text to carry evidentiary weight. Check 3 is a substring test, so without a floor
# a trivial token (e.g. "el") is a substring of nearly every article and validates
# with zero evidence. Calibrated from real data ($0): across 429 validated citations
# from paid runs the shortest was 53 chars, and the shortest citable corpus segment
# is 42 chars (4820 segments, none < 30) — so 20 sits safely below BOTH, rejecting
# trivial/short-phrase citations with zero false-positives on the observed cohort.
# §6-safe: a STRICT-tightening (can only make MORE citations invalid, never fewer);
# article/apartado fabrication stays blocked upstream at Checks 1/2.
_MIN_CITATION_CHARS = 20


class LoaderProtocol(Protocol):
    """Structural typing for the corpus loader surface used by the validator.

    The real implementation is :mod:`regulaitor.corpus.loader`; tests inject a
    fake that satisfies these four methods. Using ``Protocol`` (instead of duck
    typing on ``hasattr``) keeps the validator from silently bypassing the
    ``_CORPUS`` integrity gate if ``ArticleEntry`` ever grows a ``.text``
    attribute.
    """

    def get_article(self, norma: str, articulo: str, language: str) -> object: ...

    def get_paragraph(self, norma: str, articulo: str, apartado: str, language: str) -> str: ...

    def get_article_text(self, norma: str, articulo: str, language: str) -> str: ...

    def list_apartados(self, norma: str, articulo: str, language: str) -> list[str]: ...


def validate(citation: Citation, *, loader: LoaderProtocol | None = None) -> AuditResult:
    """Run 3 strict checks on `citation`. Fail-fast at first failing check.

    The `loader` argument is for test injection; defaults to the corpus.loader
    singleton.
    """
    # The corpus.loader module exposes the four functions LoaderProtocol
    # requires; cast bridges the Module type to the Protocol type for mypy.
    ld: LoaderProtocol = loader if loader is not None else cast(LoaderProtocol, default_loader)

    # Check 1: article_exists
    try:
        ld.get_article(citation.norma, citation.articulo, citation.language)
    except KeyError:
        return AuditResult(
            citation=citation,
            validated=False,
            article_exists=False,
            apartado_exists=None if citation.apartado is None else False,
            text_normalized_match=False,
            reason=(
                f"article_not_found: {citation.norma} has no articulo "
                f"{citation.articulo} in language {citation.language}"
            ),
            failed_check=1,
        )

    # Check 2: apartado_exists (only when apartado is given)
    target_text: str
    apartado_exists: bool | None
    if citation.apartado is not None:
        try:
            target_text = ld.get_paragraph(
                citation.norma, citation.articulo, citation.apartado, citation.language
            )
            apartado_exists = True
        except KeyError:
            valid_apartados = ld.list_apartados(
                citation.norma, citation.articulo, citation.language
            )
            return AuditResult(
                citation=citation,
                validated=False,
                article_exists=True,
                apartado_exists=False,
                text_normalized_match=False,
                reason=(
                    f"apartado_not_found: {citation.norma} art. "
                    f"{citation.articulo} {citation.language} has no apartado "
                    f"{citation.apartado}. Valid apartados: {valid_apartados}."
                ),
                failed_check=2,
            )
    else:
        target_text = ld.get_article_text(citation.norma, citation.articulo, citation.language)
        apartado_exists = None

    # Check 3: text_normalized_match
    citation_norm = _normalize(citation.text)
    target_norm = _normalize(target_text)
    # v0.1.32-post §6 defense-in-depth: schema Citation rejects whitespace-only
    # text, but if a future caller bypasses the schema (e.g. test injection,
    # downstream mutation, deserialization edge case) and citation_norm collapses
    # to empty, "" in target_norm is unconditionally True → §6 bypass. Reject here.
    #
    # sec6-01b (mutation-audit follow-up to ADR-0043): failed_check=4, NOT 3. An
    # empty citation is the EXTREME non-citation — by the same rationale the floor
    # below uses (a non-citation is not a paraphrase), it must route strict. Emitting
    # 3 (paraphrase) would let the Auditor's _all_blocked_findings_paraphrase_only
    # soften an empty "citation" to PASS. 4 makes its `!= 3` guard route BLOCK/RHR.
    # Byte-consistent with the floor (both are non-citations); auditor.py stays
    # byte-unchanged. Strict-tightening (monotone: only routes MORE strictly).
    #
    # REACHABLE via the normal prod path (§6 review): a Citation.text of bare
    # combining marks (U+0301) or variation selectors (U+FE0F) — Unicode category Mn
    # — passes the schema's whitespace-only field_validator (str.strip() keeps Mn),
    # but _normalize (NFD-decompose + drop Mn) collapses it to "". So this is a real
    # bypass sec6-01b closes, not only defense-in-depth. (Standard whitespace and
    # zero-width chars do NOT reach here — the schema rejects the former; the latter
    # survive _normalize with len>=1 and hit the floor, also failed_check=4.)
    if len(citation_norm) == 0:
        scope = "apartado" if citation.apartado is not None else "article"
        return AuditResult(
            citation=citation,
            validated=False,
            article_exists=True,
            apartado_exists=apartado_exists,
            text_normalized_match=False,
            reason=(
                f"empty_citation_text_after_normalization: {citation.norma} art. "
                f"{citation.articulo}{('.' + citation.apartado) if citation.apartado else ''} "
                f"{citation.language}; cited text is empty after Unicode normalization "
                f"(input was whitespace-only or zero-width sequence)."
            ),
            failed_check=4,
        )
    # sec6-01 (ADR-0043): reject a too-short citation BEFORE the substring test, so a
    # trivial token can no longer ride the `in` operator to a spurious pass. See the
    # _MIN_CITATION_CHARS calibration note above.
    #
    # failed_check=4 (NOT 3): a too-short citation is a NON-citation, not a paraphrase.
    # The Auditor's paraphrase-routing helper (_all_blocked_findings_paraphrase_only)
    # softens to PASS only when every invalid citation has failed_check==3; emitting 4
    # makes its `!= 3` guard route a too-short-only Finding to BLOCK/RHR instead — so
    # the floor actually closes the gap at the TURN level, not just the validator
    # layer. auditor.py stays byte-unchanged (its existing guard handles 4).
    if len(citation_norm) < _MIN_CITATION_CHARS:
        scope = "apartado" if citation.apartado is not None else "article"
        return AuditResult(
            citation=citation,
            validated=False,
            article_exists=True,
            apartado_exists=apartado_exists,
            text_normalized_match=False,
            reason=(
                f"citation_text_too_short: {citation.norma} art. {citation.articulo}"
                f"{('.' + citation.apartado) if citation.apartado else ''} "
                f"{citation.language}; cited text is {len(citation_norm)} normalized "
                f"chars (minimum {_MIN_CITATION_CHARS}) — too short to carry evidence "
                f"in a substring match against the {scope}."
            ),
            failed_check=4,
        )
    text_match = citation_norm in target_norm

    if not text_match:
        scope = "apartado" if citation.apartado is not None else "article"
        return AuditResult(
            citation=citation,
            validated=False,
            article_exists=True,
            apartado_exists=apartado_exists,
            text_normalized_match=False,
            reason=(
                f"text_not_in_{scope}: {citation.norma} art. {citation.articulo}"
                f"{('.' + citation.apartado) if citation.apartado else ''} "
                f"{citation.language}; cited text not found after normalization "
                f"({len(citation_norm)} chars vs {len(target_norm)} chars {scope})."
            ),
            failed_check=3,
        )

    return AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=apartado_exists,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
