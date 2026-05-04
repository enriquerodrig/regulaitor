"""Chunker: ParsedArticle -> list[Chunk].

Hybrid strategy decided in the H1 spec §5: chunk = whole article if article
text is <= THRESHOLD_TOKENS BGE-M3 tokens; otherwise split by apartado.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from regulaitor.corpus.formex_parser import ParsedArticle
from regulaitor.corpus.schemas import Language, Norma, SourceFormat
from regulaitor.rag import embeddings
from regulaitor.rag.schemas import Chunk

logger = logging.getLogger("regulaitor.rag.chunking")

THRESHOLD_TOKENS = 1000


def _normalize(text: str) -> str:
    """Lowercase + strip diacritics + collapse whitespace.

    Used to populate `Chunk.text_normalized` for the H3 citation_validator's
    exact-match path.
    """
    s = unicodedata.normalize("NFD", text.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def chunk_article(
    article: ParsedArticle,
    *,
    norma: Norma,
    language: Language,
    celex: str,
    version: str,
    source_format: SourceFormat,
    source_url: str,
    hash: str,
) -> list[Chunk]:
    """Convert a ParsedArticle into one or more Chunk records.

    If the article's full text fits within THRESHOLD_TOKENS (or the article has
    no paragraphs to split by), produces a single chunk. Otherwise produces one
    chunk per `apartado`.
    """
    article_id_base = f"{norma}.{article.articulo}"
    full_text = article.text
    full_tokens = embeddings.token_count(full_text)

    if full_tokens <= THRESHOLD_TOKENS or not article.paragraphs:
        if full_tokens > THRESHOLD_TOKENS:
            logger.warning(
                "article %s/%s/%s exceeds threshold (%d tokens) but has no "
                "paragraphs; emitting a single oversized chunk",
                norma,
                language,
                article.articulo,
                full_tokens,
            )
        chunk_id = f"{article_id_base}.{language}"
        return [
            Chunk(
                chunk_id=chunk_id,
                article_id=article_id_base,
                norma=norma,
                articulo=article.articulo,
                apartado=None,
                language=language,
                text=full_text,
                text_normalized=_normalize(full_text),
                token_count=full_tokens,
                celex=celex,
                version=version,
                source_format=source_format,
                source_url=source_url,
                hash=hash,
            )
        ]

    out: list[Chunk] = []
    for p in article.paragraphs:
        article_id = f"{article_id_base}.{p.apartado}"
        chunk_id = f"{article_id}.{language}"
        out.append(
            Chunk(
                chunk_id=chunk_id,
                article_id=article_id,
                norma=norma,
                articulo=article.articulo,
                apartado=p.apartado,
                language=language,
                text=p.text,
                text_normalized=_normalize(p.text),
                token_count=embeddings.token_count(p.text),
                celex=celex,
                version=version,
                source_format=source_format,
                source_url=source_url,
                hash=hash,
            )
        )
    return out
