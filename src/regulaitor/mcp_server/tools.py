"""MCP tool adapters: search_articles, fetch_article, validate_citation.

Per-tool error semantics (decisions log 2026-05-05 entry "Política de errores"):
  - search_articles: empty results -> []. Only raises on infrastructure failure.
  - fetch_article: missing article/apartado -> NotFoundError. Pydantic ValidationError on bad input.
  - validate_citation: any citation problem -> AuditResult(validated=False).
                       Never raises NotFoundError for citation content failures.
"""

from __future__ import annotations

from regulaitor.citation import validator as validator_mod
from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    FetchedArticle,
    RetrievedChunk,
)
from regulaitor.corpus import loader
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.mcp_server.errors import NotFoundError
from regulaitor.rag import retrieval as rag_retrieval


def search_articles(
    query: str,
    corpus: Norma,
    language: Language,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks for `query` filtered by corpus + language."""
    return rag_retrieval.run(query, corpus, language, top_k=top_k)


def fetch_article(
    norma: Norma,
    articulo: str,
    language: Language,
    apartado: str | None = None,
) -> FetchedArticle:
    """Direct lookup of an article or paragraph in the corpus.

    Raises NotFoundError with an actionable message when the resource is absent.

    Note: NotFoundError messages may include hints with valid article IDs (e.g.
    "Valid range: 1-113"). This is acceptable because all current corpora are
    public (EUR-Lex AI Act, GDPR). If private corpora are added in future
    milestones, revisit whether to redact these hints at the MCP boundary.
    """
    try:
        meta = loader.get_manifest_meta(norma)
        if apartado is not None:
            text = loader.get_paragraph(norma, articulo, apartado, language)
        else:
            text = loader.get_article_text(norma, articulo, language)
    except KeyError as e:
        raise NotFoundError(str(e)) from e

    return FetchedArticle(
        norma=norma,
        articulo=articulo,
        apartado=apartado,
        language=language,
        text=text,
        version=meta["version"],
        source_url=meta["source_url"],
    )


def validate_citation(citation: Citation) -> AuditResult:
    """Validate a citation against the corpus. Always returns AuditResult."""
    return validator_mod.validate(citation)
