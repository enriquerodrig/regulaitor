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
import tiktoken

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.eurlex import (
    EurLexClient,
    FetchResultModified,
    FetchResultNotModified,
)
from regulaitor.corpus.formex_parser import (
    FormexParser,
    FormexValidationError,
    ParsedArticle,
    ParsedParagraph,
)
from regulaitor.corpus.html_parser import HtmlParser
from regulaitor.corpus.manifest import ManifestDiff
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
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(str(tmp), str(path))


def _expand_targets(
    corpus: Norma | Literal["all"],
    languages: list[Language] | Literal["all"],
) -> tuple[list[Norma], list[Language]]:
    corpora: list[Norma] = list(CELEX.keys()) if corpus == "all" else [corpus]
    langs: list[Language] = ["es", "en"] if languages == "all" else list(languages)
    return corpora, langs


def _build_manifest(
    corpus: Norma,
    source_format: Literal["formex4", "html"],
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
                # Preserve H2 chunks and embedded_at
                languages_dict[lang] = old_lang.model_copy(update={"fetched_at": now})
            else:
                if old_lang is not None or old_entry is None:
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
) -> IngestSummary:
    """Run the ingest pipeline. Returns a summary; raises only on unrecoverable errors."""
    summary = IngestSummary()
    corpora, langs = _expand_targets(corpus, languages)

    formex_parser = FormexParser()
    html_parser = HtmlParser()
    client = EurLexClient()

    try:
        for c in corpora:
            manifest_path = MANIFEST_DIR / f"{c}.json"
            old_manifest = manifest_mod.load(manifest_path)

            articles_per_lang: dict[Language, list[ParsedArticle]] = {}
            http_cache_per_lang: dict[Language, HttpCacheEntry] = {}
            source_url_per_lang: dict[Language, str] = {}
            source_format: Literal["formex4", "html"] = "formex4"
            raw_total_bytes = 0

            for lang in langs:
                old_cache = old_manifest.http_cache.get(lang) if old_manifest else None
                cache = None if force_fetch else old_cache
                fetch_format: Literal["formex4", "html"] = "formex4"

                try:
                    fetch_result = client.fetch_formex(CELEX[c], lang, cache)
                except FormexValidationError:
                    if not allow_html_fallback:
                        raise
                    fetch_result = client.fetch_html(CELEX[c], lang, cache)
                    fetch_format = "html"

                if isinstance(fetch_result, FetchResultNotModified):
                    summary.fetch_skipped += 1
                    if old_manifest is not None:
                        # Reuse old data from processed cache
                        processed_path = PROCESSED_DIR / f"{c}_{lang}.json"
                        if processed_path.exists():
                            articles_per_lang[lang] = _reload_processed(processed_path)
                        http_cache_per_lang[lang] = old_cache or HttpCacheEntry()
                        source_url_per_lang[lang] = ""
                    continue

                assert isinstance(fetch_result, FetchResultModified)
                summary.fetched += 1

                xml_bytes = fetch_result.content
                raw_total_bytes += len(xml_bytes)
                _write_atomic(RAW_DIR / f"{c}_{lang}.xml", xml_bytes)

                parser = formex_parser if fetch_format == "formex4" else html_parser
                try:
                    parsed = parser.parse(xml_bytes)
                except FormexValidationError:
                    if not allow_html_fallback:
                        raise
                    fetch_format = "html"
                    fallback_result = client.fetch_html(CELEX[c], lang, cache)
                    if isinstance(fallback_result, FetchResultNotModified):
                        summary.errors += 1
                        continue
                    assert isinstance(fallback_result, FetchResultModified)
                    parsed = html_parser.parse(fallback_result.content)
                    _write_atomic(RAW_DIR / f"{c}_{lang}.xml", fallback_result.content)

                source_format = fetch_format
                report = validate(c, parsed, strict=True)
                logger.info("validate %s/%s: %d/%d", c, lang, report.found, report.expected)

                articles_per_lang[lang] = parsed
                http_cache_per_lang[lang] = HttpCacheEntry(
                    etag=fetch_result.etag,
                    last_modified=fetch_result.last_modified,
                )
                source_url_per_lang[lang] = fetch_result.source_url

                _write_atomic(
                    PROCESSED_DIR / f"{c}_{lang}.json",
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
            summary.diffs[c] = manifest_mod.diff(old_manifest, new_manifest)

    finally:
        client.close()

    return summary
