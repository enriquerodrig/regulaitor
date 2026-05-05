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
            )
    else:
        target_text = ld.get_article_text(citation.norma, citation.articulo, citation.language)
        apartado_exists = None

    # Check 3: text_normalized_match
    citation_norm = _normalize(citation.text)
    target_norm = _normalize(target_text)
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
        )

    return AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=apartado_exists,
        text_normalized_match=True,
        reason=None,
    )
