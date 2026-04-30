# H1 Corpus Ingestion — Design Spec

- **Date:** 2026-04-30
- **Milestone scope:** This document designs the full corpus-to-vector-store pipeline. **H1 implements** fetch / parse / validate / manifest (article-level metadata, no chunks, no embeddings). **H2 implements** chunker, embedder, LanceDB store and extends the manifest with chunks.
- **Approved decisions:** see `docs/technical_decisions_log.md` H1 section.
- **Status:** approved by owner, ready for implementation plan.

---

## 1. Context

RegulAItor needs an authoritative, reproducible representation of two regulatory corpora — AI Act (CELEX `32024R1689`) and GDPR (CELEX `02016R0679-20160504`) — in Spanish and English. Every downstream component (Retriever, Analyst, Auditor) depends on this corpus being:

1. **Faithful to source** — citations must match what EUR-Lex actually publishes, not a paraphrase.
2. **Versioned** — when EUR-Lex publishes a new consolidation, we capture which version we used.
3. **Reproducible** — `make ingest` on a clean clone produces an identical corpus state given the same EUR-Lex contents.
4. **Idempotent** — re-running `make ingest` is cheap when nothing has changed upstream.
5. **Bilingual** — Spanish for UI consistency, English to exploit BGE-M3's cross-lingual alignment.

Without this, every later "no citation, no answer" claim collapses.

The H1 deliverable is the parse → validate → manifest layer. H2 builds on top. The design covers both because the data model needs to be coherent across the boundary.

---

## 2. Scope

### In scope (H1)

- HTTP fetch from EUR-Lex with conditional requests (`If-Modified-Since`, `ETag`).
- Formex 4 XML parser (primary path).
- HTML parser (fallback, only when Formex unavailable for a specific consolidated version).
- Article-level validation (coverage count, unique IDs, hash recomputability).
- Per-corpus manifest with article-level metadata (no `chunks` populated yet).
- CLI `python -m scripts.ingest` with idempotency flags.
- Git-LFS configuration for `corpus/raw/` and `corpus/processed/`.
- Unit + contract + integration tests with stub HTTP fixtures.

### In design only (deferred to H2)

- Chunker (article vs apartado, 1000-token threshold).
- Embedding generation (BGE-M3, 1024-dim).
- LanceDB schema and writes.
- Chunk-level entries in manifest (`chunks: [...]` lists, `embedded_at` timestamps).

### Out of scope

- Reranker (H2).
- Retriever logic, agents (H3+).
- NIS2 / DORA corpora (H14, but the architecture must accept them with zero refactor).
- OCR / PDF parsing for corpus (we use Formex+HTML; PDF extraction is reserved for user-uploaded documents in H5).
- Citation matching policy (H3 decision).
- DVC migration (we picked Git-LFS; revisit only if corpus exceeds 1 GB).

---

## 3. Approved decisions (recap)

| Decision | Choice | Rationale (short) |
|---|---|---|
| Corpus versions | AI Act CELEX `32024R1689`; GDPR CELEX `02016R0679-20160504` (consolidated) | Stable references; consolidated avoids errata reconciliation |
| Languages | Spanish + English | Exploits BGE-M3 cross-lingual alignment; defends multilingual claim |
| Versioning | Git-LFS for raw/processed; git-tracked manifests | <1 GB corpus, no DVC infra needed |
| Source format | Formex 4 (primary), HTML (fallback) | Formal XML schema, robust against EUR-Lex template changes |
| Chunking (H2) | Hybrid: article-level if ≤ 1000 tokens, split by apartado otherwise | Long articles (AI Act art. 6, 9, 14) saturate embedding window |
| Bilingual storage (H2) | One chunk per (article, language) joined by `article_id` | Best use of BGE-M3, supports cross-lingual queries |
| Idempotency | HTTP `If-Modified-Since` + `ETag` for fetch; per-article SHA256 for processing | Saves both bandwidth and embedding cost |
| Manifest layout | One JSON per corpus | Clean diffs, lazy loading |

---

## 4. Architecture

```
                  ┌─────────────────────────────────────┐
                  │   scripts/ingest.py (CLI)           │
                  └──────────────┬──────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
    [H1: fetch]            [H1: parse]           [H1: validate]
  corpus/eurlex.py     corpus/formex_parser.py    corpus/validate.py
   HTTP w/ etag         lxml xpath selectors      schema + coverage
   raw/{c}_{l}.xml      processed/{c}_{l}.json    invariants
          │                      │                      │
          └──────────────────────┴──────────────────────┘
                                 │
                       [H1: manifest writer]
                       corpus/manifest.py
                       corpus/manifests/{c}.json
                                 │
                                 ▼
                   ─── boundary H1 → H2 ───
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
    [H2: chunker]         [H2: embedder]         [H2: store]
   rag/chunking.py       rag/embeddings.py        rag/store.py
   article|apartado       BGE-M3 1024-dim         LanceDB upsert
   tokens<=1000           local FlagEmbedding     by chunk_id
          │                      │                      │
          └──────────────────────┴──────────────────────┘
                                 │
                       [H2: manifest extender]
                       updates `chunks` + `embedded_at`
```

### Boundary contract H1 → H2

After a successful H1 run:
- `corpus/raw/{corpus}_{lang}.xml` exists (Git-LFS).
- `corpus/processed/{corpus}_{lang}.json` exists (Git-LFS).
- `corpus/manifests/{corpus}.json` exists (git-tracked) with `articles[*].languages.{es,en}` populated and `articles[*].languages.{lang}.chunks: []` empty.

H2 reads `processed/` and writes back the populated `chunks` arrays and `embedded_at` timestamps.

---

## 5. Components

All H1 modules live under `src/regulaitor/corpus/`. No module imports from `agents/`, `rag/`, `mcp_server/`, or `api/`.

### 5.1 `corpus/schemas.py`

Pydantic v2 models. Frozen for H1; H2 will extend `LanguageEntry` with `chunks: list[str]` (already present here as empty list).

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

Norma = Literal["ai_act", "gdpr", "nis2", "dora"]
Language = Literal["es", "en"]
SourceFormat = Literal["formex4", "html"]

class HttpCacheEntry(BaseModel):
    etag: str | None = None
    last_modified: str | None = None  # raw HTTP date string

class LanguageEntry(BaseModel):
    hash: str  # "sha256:<hex>"
    tokens: int
    chunks: list[str] = Field(default_factory=list)  # populated by H2
    embedded_at: datetime | None = None  # populated by H2
    fetched_at: datetime
    source_url: HttpUrl

class ArticleEntry(BaseModel):
    article_id: str  # e.g. "ai_act.6"
    articulo: str
    title_es: str | None = None
    title_en: str | None = None
    languages: dict[Language, LanguageEntry]

class Stats(BaseModel):
    articles_total: int
    chunks_total: int = 0  # populated by H2
    embedded_total: int = 0  # populated by H2
    raw_size_bytes: int

class Manifest(BaseModel):
    corpus: Norma
    celex: str
    version: str  # consolidation date as YYYY-MM-DD
    source_format: SourceFormat
    fetched_at: datetime
    languages: list[Language]
    http_cache: dict[Language, HttpCacheEntry]
    stats: Stats
    articles: list[ArticleEntry]
```

### 5.2 `corpus/eurlex.py`

```python
class EurLexClient:
    BASE = "https://eur-lex.europa.eu"
    ALLOWED_HOSTS = {"eur-lex.europa.eu"}

    def __init__(self, timeout: float = 30.0, retries: int = 3) -> None: ...

    def fetch_formex(
        self,
        celex: str,
        language: Language,
        cache: HttpCacheEntry | None = None,
    ) -> FetchResult: ...

    def fetch_html(
        self,
        celex: str,
        language: Language,
        cache: HttpCacheEntry | None = None,
    ) -> FetchResult: ...
```

`FetchResult` is a discriminated union: `FetchResultModified(content: bytes, etag, last_modified, source_url, fetched_at)` or `FetchResultNotModified()`.

URL construction:
- Formex: `https://eur-lex.europa.eu/legal-content/{LANG}/TXT/?uri=CELEX:{celex}` requesting `Accept: application/xml` with the Formex MIME hint, falling back to the Formex-specific endpoint if needed.
- HTML: `https://eur-lex.europa.eu/legal-content/{LANG}/TXT/HTML/?uri=CELEX:{celex}`.

The exact endpoint patterns are pinned in a private constants module and revisited in implementation; the spec only fixes the abstraction.

Allowlist enforcement: `urlparse(url).hostname in ALLOWED_HOSTS`. Anything else raises `EurLexAllowlistError`.

Retries: 3 attempts with 1s/2s/4s backoff on connection errors and 5xx. 4xx is fatal (no retry). 304 short-circuits to `FetchResultNotModified`.

### 5.3 `corpus/formex_parser.py`

```python
class FormexParser:
    def parse(self, xml_bytes: bytes) -> list[ParsedArticle]: ...

@dataclass(frozen=True)
class ParsedArticle:
    articulo: str       # "6"
    title: str | None   # "Reglas de clasificación..."
    text: str           # full text including PARA contents, normalized whitespace
    paragraphs: list[ParsedParagraph]  # for H2 chunker

@dataclass(frozen=True)
class ParsedParagraph:
    apartado: str       # "1", "2a", etc.
    text: str
```

Implementation uses `lxml.etree` with namespace-aware XPath selectors:

```python
ARTICLE_XPATH = ".//ARTICLE"
ARTICLE_NUM_XPATH = "./NO.ARTICLE/text()"
ARTICLE_TITLE_XPATH = "./TI.ART/text()"
PARA_XPATH = "./PARAG"
PARA_NUM_XPATH = "./NO.P/text()"
PARA_TEXT_XPATH = "./TXT//text()"
```

(Exact XPath set is calibrated against real samples during implementation; the parser has unit tests with synthetic XML covering each XPath.)

Raises `FormexValidationError` if any of:
- Root element is not `CONS.ACT` or expected Formex root.
- An ARTICLE has no `NO.ARTICLE`.
- Article text is empty after stripping.

### 5.4 `corpus/html_parser.py`

Same `parse()` signature as `FormexParser`. Returns `list[ParsedArticle]`. Used only when caller passes `--allow-html-fallback` AND Formex fetch returned a 404 or schema-violating response.

Implementation uses BeautifulSoup with brittle CSS selectors known to work for current EUR-Lex template. Documented in module docstring as "best effort, expect breakage on EUR-Lex redesigns; raise an issue and update the parser".

### 5.5 `corpus/validate.py`

```python
EXPECTED_ARTICLE_COUNTS: dict[Norma, int] = {
    "ai_act": 113,
    "gdpr": 99,
}

def validate(
    corpus: Norma,
    articles: list[ParsedArticle],
    *,
    strict: bool = True,
) -> ValidationReport: ...

@dataclass
class ValidationReport:
    coverage_ok: bool
    expected: int
    found: int
    duplicates: list[str]   # article numbers appearing twice
    missing: list[str]      # article numbers expected but absent
    empty: list[str]        # articles with empty text
```

When `strict=True`, `coverage_ok=False` causes ingest to abort. Counts come from EUR-Lex's published structure and are pinned in code; if EUR-Lex restructures (very rare), the constant gets bumped via PR.

### 5.6 `corpus/manifest.py`

```python
def load(path: Path) -> Manifest | None: ...

def save_atomic(path: Path, manifest: Manifest) -> None:
    """Write to <path>.tmp then os.replace to <path>. Never partial."""

def diff(old: Manifest | None, new: Manifest) -> ManifestDiff: ...

@dataclass
class ManifestDiff:
    added_articles: list[str]
    removed_articles: list[str]
    changed_articles: list[str]   # same article_id, different hash
    unchanged_articles: list[str]
```

Diff is logged at INFO and used to decide which downstream artifacts (chunks, embeddings) need invalidation in H2.

### 5.7 `corpus/ingest.py`

The orchestrator. Public function:

```python
def run(
    corpus: Norma | Literal["all"],
    languages: list[Language] | Literal["all"] = "all",
    *,
    force_fetch: bool = False,
    force_reprocess: bool = False,
    allow_html_fallback: bool = True,
    dry_run: bool = False,
) -> IngestSummary: ...
```

Pseudocode:

```python
def run(corpus, languages, ...):
    summary = IngestSummary()
    targets = expand_targets(corpus, languages)

    for c in targets.corpora:
        manifest_path = MANIFEST_DIR / f"{c}.json"
        old_manifest = manifest.load(manifest_path)

        articles_per_lang = {}
        http_cache_per_lang = {}

        for lang in targets.languages_for(c):
            old_cache = old_manifest.http_cache.get(lang) if old_manifest else None
            cache = None if force_fetch else old_cache

            try:
                fetch_result = client.fetch_formex(CELEX[c], lang, cache)
                source_format = "formex4"
            except FormexValidationError:
                if allow_html_fallback:
                    fetch_result = client.fetch_html(CELEX[c], lang, cache)
                    source_format = "html"
                else:
                    raise

            if isinstance(fetch_result, FetchResultNotModified):
                summary.fetch_skipped += 1
                articles_per_lang[lang] = old_articles_for_lang(old_manifest, lang)
                http_cache_per_lang[lang] = old_cache
                continue

            write_atomic(RAW_DIR / f"{c}_{lang}.xml", fetch_result.content)

            parsed = (FormexParser if source_format == "formex4" else HtmlParser)().parse(fetch_result.content)
            report = validate.validate(c, parsed, strict=True)
            if not report.coverage_ok:
                raise ValidationFailure(report)

            articles_per_lang[lang] = parsed
            http_cache_per_lang[lang] = HttpCacheEntry(
                etag=fetch_result.etag, last_modified=fetch_result.last_modified
            )

            write_atomic(
                PROCESSED_DIR / f"{c}_{lang}.json",
                json.dumps([a.model_dump() for a in parsed], indent=2).encode(),
            )

        new_manifest = build_manifest(
            corpus=c,
            celex=CELEX[c],
            version=VERSION[c],
            source_format=source_format,
            articles_per_lang=articles_per_lang,
            http_cache=http_cache_per_lang,
            old_manifest=old_manifest,
            force_reprocess=force_reprocess,
        )

        if dry_run:
            summary.would_write.append(manifest_path)
        else:
            manifest.save_atomic(manifest_path, new_manifest)

        summary.diffs[c] = manifest.diff(old_manifest, new_manifest)

    return summary
```

`build_manifest` merges per-language parsed articles into the unified `articles` list, preserving H2's downstream work when an article hasn't changed:

```python
def build_manifest(corpus, celex, version, source_format,
                   articles_per_lang, http_cache, old_manifest, force_reprocess):
    # 1. Index old manifest by article_id for O(1) lookups
    old_index: dict[str, ArticleEntry] = (
        {a.article_id: a for a in old_manifest.articles} if old_manifest else {}
    )

    # 2. Collect all article numbers across languages (union, not intersection)
    all_articulos = sorted({
        a.articulo for parsed_list in articles_per_lang.values() for a in parsed_list
    }, key=lambda x: int(x) if x.isdigit() else float("inf"))

    new_articles: list[ArticleEntry] = []
    for articulo in all_articulos:
        article_id = f"{corpus}.{articulo}"
        old_entry = old_index.get(article_id)

        languages_dict: dict[Language, LanguageEntry] = {}
        title_es = title_en = None

        for lang, parsed_list in articles_per_lang.items():
            parsed = next((p for p in parsed_list if p.articulo == articulo), None)
            if parsed is None:
                continue  # language gap (rare)

            text_hash = sha256_hex(parsed.text)
            tokens = tiktoken_count(parsed.text)
            old_lang = old_entry.languages.get(lang) if old_entry else None

            if (not force_reprocess
                and old_lang is not None
                and old_lang.hash == text_hash):
                # Preserve H2's chunks and embedded_at — article didn't change
                languages_dict[lang] = old_lang.model_copy(update={
                    "fetched_at": datetime.now(timezone.utc),
                })
            else:
                # New or changed article: invalidate H2 state
                languages_dict[lang] = LanguageEntry(
                    hash=text_hash,
                    tokens=tokens,
                    chunks=[],            # H2 will repopulate
                    embedded_at=None,     # H2 will repopulate
                    fetched_at=datetime.now(timezone.utc),
                    source_url=current_source_url(corpus, lang),
                )

            if lang == "es":
                title_es = parsed.title
            elif lang == "en":
                title_en = parsed.title

        new_articles.append(ArticleEntry(
            article_id=article_id,
            articulo=articulo,
            title_es=title_es,
            title_en=title_en,
            languages=languages_dict,
        ))

    return Manifest(
        corpus=corpus,
        celex=celex,
        version=version,
        source_format=source_format,
        fetched_at=datetime.now(timezone.utc),
        languages=list(articles_per_lang.keys()),
        http_cache=http_cache,
        stats=Stats(
            articles_total=len(new_articles),
            chunks_total=sum(
                len(le.chunks) for a in new_articles for le in a.languages.values()
            ),
            embedded_total=sum(
                1 for a in new_articles for le in a.languages.values()
                if le.embedded_at is not None
            ),
            raw_size_bytes=current_raw_total_bytes(corpus),
        ),
        articles=new_articles,
    )
```

Key invariant: when `old_lang.hash == text_hash`, we copy `chunks` and `embedded_at` verbatim from the old manifest. This is what makes the pipeline cheap on re-runs — H2 doesn't re-embed unchanged articles.

### 5.8 `scripts/ingest.py`

```python
import argparse
from regulaitor.corpus.ingest import run

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", choices=["ai_act", "gdpr", "all"], default="all")
    p.add_argument("--lang", choices=["es", "en", "all"], default="all")
    p.add_argument("--force-fetch", action="store_true")
    p.add_argument("--force-reprocess", action="store_true")
    p.add_argument("--no-html-fallback", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    summary = run(
        corpus=args.corpus,
        languages=["es", "en"] if args.lang == "all" else [args.lang],
        force_fetch=args.force_fetch,
        force_reprocess=args.force_reprocess,
        allow_html_fallback=not args.no_html_fallback,
        dry_run=args.dry_run,
    )

    print(summary.format_human())
    return 0 if summary.errors == 0 else 1
```

---

## 6. Data flow examples

### 6.1 First run (clean clone)

```
$ python -m scripts.ingest --corpus ai_act --lang es,en
[ingest] Loading manifest corpus/manifests/ai_act.json (not found, creating empty)
[ingest] (ai_act, es) GET https://eur-lex.europa.eu/.../FMX4
        → 200 OK, 1.83 MB, etag W/"abc123"
        → wrote corpus/raw/ai_act_es.xml
[parse] Formex 4 detected, parsing 113 ARTICLE nodes
[parse] (ai_act, es) extracted 113 articles, longest 4920 tokens (art. 6)
[hash] (ai_act, es) computing SHA256 per article ... 113 hashes
[validate] (ai_act, es) coverage: 113/113 ✓ unique ids ✓ hashes recomputable ✓
[ingest] (ai_act, es) writing processed/ai_act_es.json
[ingest] (ai_act, en) ... idem
[manifest] writing corpus/manifests/ai_act.json (atomic)
[stats] articles=113 fetched=2 parsed=2 errors=0
```

### 6.2 Re-run with no upstream changes

```
$ python -m scripts.ingest --corpus ai_act --lang es,en
[ingest] (ai_act, es) GET ... If-Modified-Since: 2026-04-30T18:42:13Z
        → 304 Not Modified, fetch skipped
[ingest] (ai_act, en) ... 304, fetch skipped
[ingest] all corpora already up to date, manifest unchanged
```

### 6.3 EUR-Lex re-publishes consolidated AI Act with art. 6 amended

```
$ python -m scripts.ingest --corpus ai_act --lang es,en
[ingest] (ai_act, es) GET ... 200 OK
[parse] (ai_act, es) extracted 113 articles
[hash] 1 article changed, 112 unchanged
[diff] changed: ai_act.6 (re-process)
[diff] unchanged: 112 articles (chunks and embeddings preserved)
[manifest] writing ai_act.json
[stats] articles=113 fetched=2 parsed=2 reprocessed_articles=2 (1 ES + 1 EN) errors=0
```

H2 reads the diff and only re-embeds article 6.

---

## 7. Error handling

| Failure mode | Detection | Action |
|---|---|---|
| HTTP 5xx | retries exhausted | exit 1, manifest untouched |
| HTTP 304 | status code | success path (no re-process) |
| HTTP 4xx | status code | exit 1 immediate, log CELEX + URL |
| Formex schema violation | `FormexValidationError` from parser | if `--no-html-fallback`: exit 1; else try HTML and log warning |
| Article count mismatch | `validate.py` post-parse | exit 1, list expected vs found, manifest untouched |
| Hash mismatch on unchanged HTTP response | per-article hash compare | warning, reprocess article, log `corruption_suspected` |
| UTF-8 decode error | `lxml` exception | exit 1, log file offset |
| Disk full on manifest write | `os.replace` exception | exit 1, leave `.tmp` for debugging |
| Allowlist violation | `EurLexAllowlistError` | exit 1, never run |

**Atomicity invariant:** The manifest file is updated only via `tmp` + `os.replace`. If anything fails mid-run, the previous manifest remains intact. This guarantees H2 always sees a consistent manifest or no manifest at all.

---

## 8. Testing strategy

### 8.1 Test pyramid

| Level | What | Location | CI? |
|---|---|---|---|
| Unit | `formex_parser.py` against synthetic XML | `tests/unit/corpus/test_formex_parser.py` | yes |
| Unit | `chunker.py` (H2) edge cases | `tests/unit/rag/test_chunking.py` | yes (H2) |
| Unit | `validate.py` cases | `tests/unit/corpus/test_validate.py` | yes |
| Unit | `manifest.py` load/save/diff round-trip | `tests/unit/corpus/test_manifest.py` | yes |
| Contract | Parser output → `ArticleEntry` | `tests/contract/test_parser_contract.py` (hypothesis) | yes |
| Contract | Manifest JSON round-trip → `Manifest` | `tests/contract/test_manifest_contract.py` | yes |
| Integration | `ingest.run` with stub HTTP server | `tests/integration/test_ingest_flow.py` | yes |
| Integration | Re-run idempotency with stub returning 304 | same file | yes |
| Smoke (manual) | Real EUR-Lex fetch | `scripts/smoke_ingest.py` | no — local only, results commit to log |

### 8.2 Fixtures

```
tests/fixtures/formex/
├── ai_act_es_mini.xml        # 5 synthetic articles, valid Formex 4
├── ai_act_en_mini.xml        # 5 synthetic articles, EN versions, same article_ids
├── malformed_no_articles.xml # root present, zero ARTICLE nodes (validation error)
├── malformed_missing_num.xml # ARTICLE without NO.ARTICLE (parser error)
└── ai_act_with_long_article.xml  # one article >3000 tokens (chunker fixture for H2)

tests/fixtures/html/
├── ai_act_es_mini.html       # for fallback parser
└── ai_act_es_broken.html     # template change simulation
```

The fixtures are crafted by hand (10-50 lines each), not snapshots of real EUR-Lex responses, so they cannot drift with EUR-Lex.

### 8.3 Stub HTTP server

`tests/integration/conftest.py` provides a `pytest` fixture that starts a `httpx.MockTransport` (no socket binding) returning canned responses keyed by URL. Supports `If-Modified-Since` semantics (returns 304 when configured).

### 8.4 Coverage target

≥ 90% line coverage on `src/regulaitor/corpus/`. Enforced in CI via `pytest --cov=src/regulaitor/corpus --cov-fail-under=90` (added to `lint` job in H1).

---

## 9. Repo layout impact

```
src/regulaitor/corpus/
├── __init__.py
├── schemas.py
├── eurlex.py
├── formex_parser.py
├── html_parser.py
├── validate.py
├── manifest.py
└── ingest.py

scripts/
└── ingest.py

corpus/
├── raw/                       # Git-LFS, gitignored as source of truth lives in LFS pointers
├── processed/                 # Git-LFS, same
└── manifests/
    ├── ai_act.json            # git-tracked
    └── gdpr.json              # git-tracked

tests/
├── unit/corpus/
├── contract/
├── integration/
└── fixtures/{formex,html}/
```

Git-LFS configuration to add to `.gitattributes`:
```
corpus/raw/** filter=lfs diff=lfs merge=lfs -text
corpus/processed/** filter=lfs diff=lfs merge=lfs -text
```

`.gitignore` adjustment: remove `corpus/raw/` and `corpus/processed/` exclusions (they were gitignored in H0.1 because LFS wasn't set up; now they go into LFS).

---

## 10. New dependencies (to be added to `pyproject.toml` in H1)

| Package | Purpose | Pin |
|---|---|---|
| `httpx` | HTTP client with HTTP/2 and conditional request support | `>=0.27,<1.0` |
| `lxml` | Formex 4 XML parsing | `>=5.3,<6.0` |
| `beautifulsoup4` | HTML fallback parser | `>=4.12,<5.0` |
| `tiktoken` | Token counting for chunker (H2 strictly, but introduced now for `tokens` field) | `>=0.8,<1.0` |
| `tenacity` | HTTP retry with exponential backoff | `>=8.5,<10.0` |
| `hypothesis` | Property-based contract tests | `>=6.0,<7.0` |

Pre-commit and CI updates: none structural — same `lint`, `test`, `security` jobs cover the new modules. Add `coverage` thresholds to `pytest` in `pyproject.toml`.

---

## 11. New skills and MCPs (per ADR 0002)

H1 triggers the introduction of:

- **Skill `rag-ingest`** in `.claude/skills/rag-ingest/SKILL.md`. Procedural skill describing how to add a new corpus (new norma) following the H1 pattern. Proposed before H1 implementation, ≤ 150 lines. **Requires owner OK per CLAUDE.md §12.3.**

H1 deliberately **defers** the following items that ADR 0002 had tentatively scheduled here:

- **Skill `adr-writer`** is **NOT** introduced in H1. Although H1 will produce ADR 0003 (and possibly 0004 for Git-LFS), that is a single batch in a single milestone. The ADR pattern is simple enough that a one-off prompt suffices. Re-evaluate when ≥ 3 ADRs are queued in a single milestone (likely H10 documentation freeze).
- **MCP `fetch`** is **NOT** introduced in H1. The `httpx` direct call in `eurlex.py` with explicit allowlist is sufficient and simpler than installing an MCP. The MCP `fetch` is reserved for H3+ when other agents may need general browse capability.
- **MCP `mcp-server-time`** is **NOT** introduced. Python's `datetime.now(timezone.utc)` is sufficient for ingest timestamps.

The H1 closure entry in the technical decisions log will reference these deferrals, and ADR 0002 will be updated in the same commit to reflect the new schedule (push `adr-writer` to H10, drop `mcp-server-time` for now, push `fetch` to H3).

---

## 12. Open questions (to settle before implementation)

1. **Exact EUR-Lex Formex URL pattern.** The spec assumes `?uri=CELEX:{celex}` with `Accept: application/xml`. Implementation will probe with the real CELEX values and pin the working URL pattern in `eurlex.py`. If Formex isn't directly addressable by CELEX, may need to scrape the Formex link from the document landing page first.
2. **EUR-Lex `If-Modified-Since` reliability.** Some EUR-Lex endpoints don't honor conditional requests; if so, fall back to `ETag` only or to weekly polling. Discovered during smoke test, documented in log.
3. **Token counter model alignment.** `tiktoken` ships GPT tokenizers. BGE-M3 uses XLM-RoBERTa tokenizer. For the chunking threshold, what counter do we use? Provisional answer: use `tiktoken` cl100k_base as a cheap proxy in H1, swap to BGE-M3 tokenizer in H2 when we install the model. Threshold of 1000 is loose enough for the proxy.
4. **GDPR article numbering.** GDPR has 99 articles, but recitals (173) are also citable. Recitals are out of scope for H1 (only `ARTICLE` nodes); if the Auditor needs to cite recitals later, we extend in H2 or open a follow-up.

---

## 13. Acceptance criteria for H1

H1 is "Done" when:

1. `python -m scripts.ingest --corpus all --lang all` against real EUR-Lex completes with exit 0.
2. `corpus/manifests/ai_act.json` and `gdpr.json` exist, validate as `Manifest`, and contain 113 + 99 articles respectively.
3. Re-running the same command immediately produces no manifest diff and reports "all up to date" (idempotency proof).
4. Unit + contract + integration tests pass with ≥ 90% coverage on `src/regulaitor/corpus/`.
5. CI lint + test + security jobs are green.
6. Smoke run output and stats are committed as a new entry in `docs/technical_decisions_log.md` H1 section.
7. Skill `rag-ingest` SKILL.md proposed, approved and committed.
8. ADR 0003 (corpus pipeline) drafted and merged.
9. ADR 0002 updated to reflect deferrals of `adr-writer`, `fetch`, `mcp-server-time` (committed in the same PR as ADR 0003).

---

## 14. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| EUR-Lex doesn't expose Formex 4 for one of the targeted CELEX | Medium | HTML fallback path exists; documented and tested. Smoke run validates assumption early. |
| EUR-Lex changes URL scheme | Low | URL building isolated in `eurlex.py`; one-file fix. Smoke run catches it. |
| Formex 4 schema variation across regulations | Medium | Per-regulation tests in unit suite. Adopt a "best effort" schema with explicit fallback raising. |
| Coverage target 90% blocks merge on legitimate untestable code (e.g., HTTP retries) | Low | Strategic `# pragma: no cover` on retry sleep and atexit hooks. Documented in PR. |
| `tiktoken` proxy diverges significantly from BGE-M3 tokens | Low | Threshold is generous; we accept up to 30% drift in H1. H2 swaps tokenizer. |
| Git-LFS bandwidth quota on free tier | Low | <50 MB per push expected. Quota is 1 GB/month. Monitor on first push. |
| H1 takes longer than expected and starves H2-H10 | Medium | If smoke run reveals Formex unavailable, switch to HTML in same hito; do not extend deadline for "Formex perfect". Honest fallback > paper-perfect spec. |

---

## 15. Implementation order (input to writing-plans skill)

Suggested sequence for the implementation plan:

1. Add dependencies to `pyproject.toml`, `uv sync`.
2. Add `.gitattributes` and configure Git-LFS for `corpus/raw/`, `corpus/processed/`. Update `.gitignore`.
3. Write Pydantic schemas (`schemas.py`) with full type coverage.
4. Write `manifest.py` (load/save/diff) with unit tests.
5. Write `formex_parser.py` against fixtures with unit tests.
6. Write `html_parser.py` against fixtures (smaller scope).
7. Write `validate.py` with unit tests.
8. Write `eurlex.py` with stub HTTP integration tests.
9. Write `ingest.py` orchestrator with full integration test.
10. Write `scripts/ingest.py` CLI wrapper.
11. Propose and write `.claude/skills/rag-ingest/SKILL.md` (after owner OK).
12. Run smoke against real EUR-Lex, capture output.
13. Update `corpus/manifests/*.json` with real data, commit (Git-LFS triggered).
14. Draft ADR 0003 capturing the pipeline architecture.
15. Update ADR 0002 with skills/MCPs deferrals decided in this spec.
16. Update `docs/technical_decisions_log.md` with H1 closure entry (stats from smoke run).
17. PR review, merge, tag.

---

## 16. References

- `CLAUDE.md` §7 (corpus normativo), §10 (stack), §22 (operating rules).
- `docs/adr/0001-project-scope.md`, `docs/adr/0002-skills-mcps-roadmap.md`.
- `docs/technical_decisions_log.md` H1 section.
- `~/.claude/plans/lee-el-archivo-claude-md-sparkling-fairy.md` H1 entry.
- EUR-Lex Formex 4 documentation: <https://op.europa.eu/en/web/eu-vocabularies/formex>
