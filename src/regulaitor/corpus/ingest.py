"""Corpus ingest orchestrator: fetch -> parse -> validate -> manifest write.

H1 scope: lands raw + processed + manifest (article-level metadata).
H2 will read processed/ to chunk + embed + write LanceDB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus._targets import expand_targets
from regulaitor.corpus.eurlex import (
    EurLexClient,
    FetchResult,
    FetchResultModified,
    FetchResultNotModified,
)
from regulaitor.corpus.formex_parser import (
    FormexParser,
    FormexValidationError,
    ParsedArticle,
    ParsedParagraph,
)
from regulaitor.corpus.html_parser import HtmlParseError, HtmlParser
from regulaitor.corpus.manifest import ManifestDiff
from regulaitor.corpus.pdf_parser import PdfParseError, PdfParser
from regulaitor.corpus.schemas import (
    ArticleEntry,
    HttpCacheEntry,
    Language,
    LanguageEntry,
    Manifest,
    Norma,
    Stats,
)
from regulaitor.corpus.validate import validate

logger = logging.getLogger("regulaitor.corpus.ingest")

CORPUS_ROOT = Path("corpus")
MANIFEST_DIR = CORPUS_ROOT / "manifests"
RAW_DIR = CORPUS_ROOT / "raw"
PROCESSED_DIR = CORPUS_ROOT / "processed"

CELEX: dict[Norma, str] = {
    "ai_act": "32024R1689",
    "gdpr": "02016R0679-20160504",
}

VERSION: dict[Norma, str] = {
    "ai_act": "2024-07-12",
    "gdpr": "2016-05-04",
}


@dataclass
class IngestSummary:
    errors: int = 0
    fetch_skipped: int = 0
    fetched: int = 0
    reprocessed_articles: int = 0
    diffs: dict[Norma, ManifestDiff] = field(default_factory=dict)
    would_write: list[Path] = field(default_factory=list)

    def format_human(self) -> str:
        parts = [
            "Ingest summary:",
            f"  errors:                {self.errors}",
            f"  fetched:               {self.fetched}",
            f"  fetch_skipped (304):   {self.fetch_skipped}",
            f"  reprocessed_articles:  {self.reprocessed_articles}",
        ]
        for corpus, diff in self.diffs.items():
            parts.append(
                f"  {corpus}: +{len(diff.added_articles)} ~{len(diff.changed_articles)} "
                f"-{len(diff.removed_articles)} ={len(diff.unchanged_articles)}"
            )
        if self.would_write:
            parts.append(f"  would_write (dry-run): {[str(p) for p in self.would_write]}")
        return "\n".join(parts)


def _make_test_client(transport: httpx.BaseTransport) -> EurLexClient:
    """Helper used by tests to inject a mock transport.

    Imports EurLexClient directly from its source module to avoid resolving the
    monkeypatched name on `ingest.EurLexClient` (which is the lambda under test).
    """
    from regulaitor.corpus.eurlex import EurLexClient as _RealEurLexClient

    return _RealEurLexClient(transport=transport)


def _sha256_hex(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _token_count(text: str) -> int:
    """Token counter stub. H2 Task 10 will redirect this to rag.embeddings.token_count.
    For now, a whitespace-split proxy keeps tests passing without tiktoken."""
    return len(text.split())


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(str(tmp), str(path))


def _load_local(
    corpus: Norma, lang: Language
) -> tuple[FetchResultModified, Literal["formex4", "html", "pdf"]]:
    """Load a corpus snapshot from local RAW_DIR (no HTTP).

    Used by `--use-local-only` mode (Task 12 pragmatic pivot for EUR-Lex CloudFront WAF).
    Tries `{corpus}_{lang}.xml` (Formex), then `.html`, then `.pdf` — in that order
    of preference (XML is most structured, PDF most fragile).
    """
    xml_path = RAW_DIR / f"{corpus}_{lang}.xml"
    html_path = RAW_DIR / f"{corpus}_{lang}.html"
    pdf_path = RAW_DIR / f"{corpus}_{lang}.pdf"
    fmt: Literal["formex4", "html", "pdf"]
    if xml_path.exists():
        path, fmt = xml_path, "formex4"
    elif html_path.exists():
        path, fmt = html_path, "html"
    elif pdf_path.exists():
        path, fmt = pdf_path, "pdf"
    else:
        raise FileNotFoundError(
            f"--use-local-only requires one of {xml_path}, {html_path}, {pdf_path} to exist"
        )
    return (
        FetchResultModified(
            content=path.read_bytes(),
            etag=None,
            last_modified=None,
            source_url=path.resolve().as_uri(),
            fetched_at=datetime.now(UTC),
        ),
        fmt,
    )


def _build_manifest(
    corpus: Norma,
    source_format: Literal["formex4", "html", "pdf"],
    articles_per_lang: dict[Language, list[ParsedArticle]],
    http_cache: dict[Language, HttpCacheEntry],
    old_manifest: Manifest | None,
    *,
    force_reprocess: bool,
    raw_total_bytes: int,
) -> tuple[Manifest, int]:
    """Merge per-language parsed articles into a Manifest, preserving H2 state."""
    old_index = {a.article_id: a for a in old_manifest.articles} if old_manifest else {}
    all_articulos = sorted(
        {a.articulo for parsed in articles_per_lang.values() for a in parsed},
        key=lambda x: int(x) if x.isdigit() else 10**9,
    )
    now = datetime.now(UTC)
    new_articles: list[ArticleEntry] = []
    reprocessed = 0

    for articulo in all_articulos:
        article_id = f"{corpus}.{articulo}"
        old_entry = old_index.get(article_id)
        languages_dict: dict[Language, LanguageEntry] = {}
        title_es = title_en = None

        for lang, parsed_list in articles_per_lang.items():
            parsed = next((p for p in parsed_list if p.articulo == articulo), None)
            if parsed is None:
                continue

            text_hash = _sha256_hex(parsed.text)
            tokens = _token_count(parsed.text)
            old_lang = old_entry.languages.get(lang) if old_entry else None

            if not force_reprocess and old_lang is not None and old_lang.hash == text_hash:
                # Preserve H2 chunks and embedded_at — article unchanged.
                languages_dict[lang] = old_lang.model_copy(update={"fetched_at": now})
            else:
                # New article, changed article, or force reprocess — invalidate H2 state.
                reprocessed += 1
                languages_dict[lang] = LanguageEntry(
                    hash=text_hash,
                    tokens=tokens,
                    chunks=[],
                    embedded_at=None,
                    fetched_at=now,
                    source_url="",  # filled by caller via backfill
                )
            if lang == "es":
                title_es = parsed.title
            elif lang == "en":
                title_en = parsed.title

        new_articles.append(
            ArticleEntry(
                article_id=article_id,
                articulo=articulo,
                title_es=title_es,
                title_en=title_en,
                languages=languages_dict,
            )
        )

    manifest = Manifest(
        corpus=corpus,
        celex=CELEX[corpus],
        version=VERSION[corpus],
        source_format=source_format,
        fetched_at=now,
        languages=list(articles_per_lang.keys()),
        http_cache=http_cache,
        stats=Stats(
            articles_total=len(new_articles),
            chunks_total=sum(len(le.chunks) for a in new_articles for le in a.languages.values()),
            embedded_total=sum(
                1 for a in new_articles for le in a.languages.values() if le.embedded_at
            ),
            raw_size_bytes=raw_total_bytes,
        ),
        articles=new_articles,
    )
    return manifest, reprocessed


def _reload_processed(path: Path) -> list[ParsedArticle]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ParsedArticle(
            articulo=a["articulo"],
            title=a.get("title"),
            text=a["text"],
            paragraphs=[
                ParsedParagraph(apartado=p["apartado"], text=p["text"])
                for p in a.get("paragraphs", [])
            ],
        )
        for a in data
    ]


def run(
    corpus: Norma | Literal["all"] = "all",
    languages: list[Language] | Literal["all"] = "all",
    *,
    force_fetch: bool = False,
    force_reprocess: bool = False,
    allow_html_fallback: bool = True,
    dry_run: bool = False,
    use_local_only: bool = False,
) -> IngestSummary:
    """Run the ingest pipeline. Returns a summary; raises only on unrecoverable errors.

    When `use_local_only=True`, skips HTTP entirely and reads files from RAW_DIR.
    Used as the H1 pragmatic path because EUR-Lex CloudFront WAF blocks bot fetches
    (see docs/technical_decisions_log.md H1 entry "EUR-Lex WAF — local-only mode").
    """
    summary = IngestSummary()
    corpora, langs = expand_targets(corpus, languages)
    # Filter to only corpora that have CELEX/VERSION pinned (H1 + H14).
    corpora = [c for c in corpora if c in CELEX]

    formex_parser = FormexParser()
    html_parser = HtmlParser()
    pdf_parser = PdfParser()
    parsers: dict[str, FormexParser | HtmlParser | PdfParser] = {
        "formex4": formex_parser,
        "html": html_parser,
        "pdf": pdf_parser,
    }
    client = None if use_local_only else EurLexClient()

    try:
        for c in corpora:
            manifest_path = MANIFEST_DIR / f"{c}.json"
            old_manifest = manifest_mod.load(manifest_path)
            logger.info("manifest %s: %s", c, "loaded" if old_manifest else "not found, creating")

            articles_per_lang: dict[Language, list[ParsedArticle]] = {}
            http_cache_per_lang: dict[Language, HttpCacheEntry] = {}
            source_url_per_lang: dict[Language, str] = {}
            source_format: Literal["formex4", "html", "pdf"] = "formex4"
            raw_total_bytes = 0

            for lang in langs:
                old_cache = old_manifest.http_cache.get(lang) if old_manifest else None
                cache = None if force_fetch else old_cache
                fetch_format: Literal["formex4", "html", "pdf"] = "formex4"

                fetch_result: FetchResult
                if use_local_only:
                    fetch_result, fetch_format = _load_local(c, lang)
                    logger.info(
                        "local %s/%s: %s, %d bytes",
                        c,
                        lang,
                        fetch_format,
                        len(fetch_result.content),
                    )
                else:
                    assert client is not None  # noqa: S101 # nosec B101  # type narrow for mypy
                    try:
                        fetch_result = client.fetch_formex(CELEX[c], lang, cache)
                    except FormexValidationError:
                        if not allow_html_fallback:
                            raise
                        fetch_result = client.fetch_html(CELEX[c], lang, cache)
                        fetch_format = "html"

                if isinstance(fetch_result, FetchResultNotModified):
                    logger.info("fetch %s/%s: 304 Not Modified", c, lang)
                    summary.fetch_skipped += 1
                    if old_manifest is not None:
                        # Reuse old data from processed cache
                        processed_path = PROCESSED_DIR / f"{c}_{lang}.json"
                        if processed_path.exists():
                            articles_per_lang[lang] = _reload_processed(processed_path)
                        http_cache_per_lang[lang] = old_cache or HttpCacheEntry()
                        source_url_per_lang[lang] = ""
                    continue

                assert isinstance(  # noqa: S101 # nosec B101  # type narrow for mypy
                    fetch_result, FetchResultModified
                )
                summary.fetched += 1
                logger.info(
                    "fetch %s/%s: 200 OK, %d bytes, etag=%s",
                    c,
                    lang,
                    len(fetch_result.content),
                    fetch_result.etag,
                )

                xml_bytes = fetch_result.content
                raw_total_bytes += len(xml_bytes)
                if not use_local_only:
                    # In local-only mode, the file is already in RAW_DIR (we just read it).
                    _write_atomic(RAW_DIR / f"{c}_{lang}.xml", xml_bytes)

                parser = parsers[fetch_format]
                try:
                    parsed = parser.parse(xml_bytes)
                except (FormexValidationError, HtmlParseError, PdfParseError) as exc:
                    if not allow_html_fallback:
                        raise
                    if use_local_only:
                        # No HTTP fallback in local-only mode; the local file is the source.
                        logger.error(
                            "%s parse failed for %s/%s in local-only mode: %s",
                            fetch_format,
                            c,
                            lang,
                            exc,
                        )
                        summary.errors += 1
                        continue
                    assert client is not None  # noqa: S101 # nosec B101  # type narrow for mypy
                    logger.warning(
                        "%s parse failed for %s/%s (%s); falling back to HTML",
                        fetch_format,
                        c,
                        lang,
                        exc,
                    )
                    fetch_format = "html"
                    fetch_result = client.fetch_html(CELEX[c], lang, cache)
                    if isinstance(fetch_result, FetchResultNotModified):
                        logger.error(
                            "HTML fallback for %s/%s returned 304 with no cached data; skipping",
                            c,
                            lang,
                        )
                        summary.errors += 1
                        continue
                    assert isinstance(  # noqa: S101 # nosec B101  # type narrow for mypy
                        fetch_result, FetchResultModified
                    )
                    parsed = html_parser.parse(fetch_result.content)
                    _write_atomic(RAW_DIR / f"{c}_{lang}.xml", fetch_result.content)

                source_format = fetch_format
                report = validate(c, parsed, strict=True)
                logger.info("parse %s/%s: %d articles", c, lang, len(parsed))
                logger.info(
                    "validate %s/%s: %d/%d coverage_ok=%s",
                    c,
                    lang,
                    report.found,
                    report.expected,
                    report.coverage_ok,
                )

                articles_per_lang[lang] = parsed
                http_cache_per_lang[lang] = HttpCacheEntry(
                    etag=fetch_result.etag,
                    last_modified=fetch_result.last_modified,
                )
                source_url_per_lang[lang] = fetch_result.source_url

                processed_path_value = PROCESSED_DIR / f"{c}_{lang}.json"
                _write_atomic(
                    processed_path_value,
                    json.dumps(
                        [
                            {
                                "articulo": a.articulo,
                                "title": a.title,
                                "text": a.text,
                                "paragraphs": [
                                    {"apartado": p.apartado, "text": p.text} for p in a.paragraphs
                                ],
                            }
                            for a in parsed
                        ],
                        ensure_ascii=False,
                        indent=2,
                    ).encode("utf-8"),
                )
                logger.info("processed %s/%s: wrote %s", c, lang, processed_path_value)

            if not articles_per_lang:
                # Everything was 304 and we have no old data — nothing to do.
                summary.diffs[c] = ManifestDiff([], [], [], [])
                continue

            new_manifest, reprocessed = _build_manifest(
                corpus=c,
                source_format=source_format,
                articles_per_lang=articles_per_lang,
                http_cache=http_cache_per_lang,
                old_manifest=old_manifest,
                force_reprocess=force_reprocess,
                raw_total_bytes=raw_total_bytes
                or (old_manifest.stats.raw_size_bytes if old_manifest else 0),
            )
            # Backfill source_url on freshly-fetched language entries.
            for article in new_manifest.articles:
                for lang_, le in article.languages.items():
                    if le.source_url == "" and source_url_per_lang.get(lang_):
                        article.languages[lang_] = le.model_copy(
                            update={"source_url": source_url_per_lang[lang_]}
                        )

            summary.reprocessed_articles += reprocessed

            if not dry_run:
                manifest_mod.save_atomic(manifest_path, new_manifest)
                logger.info(
                    "manifest %s: wrote %s with %d articles, %d reprocessed",
                    c,
                    manifest_path,
                    len(new_manifest.articles),
                    reprocessed,
                )
            else:
                summary.would_write.append(manifest_path)
            summary.diffs[c] = manifest_mod.diff(old_manifest, new_manifest)

    finally:
        if client is not None:
            client.close()

    logger.info(
        "ingest summary: errors=%d fetched=%d fetch_skipped=%d reprocessed=%d",
        summary.errors,
        summary.fetched,
        summary.fetch_skipped,
        summary.reprocessed_articles,
    )
    return summary
