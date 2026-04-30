# H1 — Corpus AI Act + RGPD — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the corpus fetch / parse / validate / manifest pipeline for AI Act (CELEX `32024R1689`) and GDPR (CELEX `02016R0679-20160504`) in Spanish and English, following `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md`. End state: green CI, ≥90% coverage on `src/regulaitor/corpus/`, and a successful smoke run against real EUR-Lex with the resulting manifests committed.

**Architecture:** Orchestrator (`corpus/ingest.py`) wires four stages — fetch (`eurlex.py` over `httpx`, conditional HTTP), parse (`formex_parser.py` over Formex 4 XML; `html_parser.py` as fallback), validate (`validate.py` invariants), and manifest write (`manifest.py` atomic JSON). H2 will later read `corpus/processed/` and extend manifests with chunks + embeddings.

**Tech Stack:** Python 3.11 · `uv` · Pydantic v2 · `httpx` · `lxml` · `beautifulsoup4` · `tiktoken` (token proxy) · `tenacity` (retries) · `hypothesis` (contract tests) · Git-LFS · pytest · ruff · black · mypy.

**Branch:** All work on `feat/h1-corpus-ingest`. Open PR on Task 14 for merge to `main`.

---

## Task map

0. Branch + dependencies + Git-LFS configuration
1. Pydantic schemas
2. Manifest module (load / save / diff)
3. Test fixtures (synthetic Formex + HTML)
4. Formex parser
5. HTML fallback parser
6. Validation invariants
7. EUR-Lex HTTP client
8. Ingest orchestrator
9. CLI wrapper
10. Contract tests + coverage gate enforcement
11. Skill `rag-ingest` proposal
12. Smoke run against real EUR-Lex
13. Documentation closure (ADR 0003, ADR 0002 update, decisions log)
14. Push, verify CI, open PR, merge, tag `v0.0.2-h1`

---

## Task 0: Branch + dependencies + Git-LFS

**Files:**
- Create branch: `feat/h1-corpus-ingest`
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `.gitattributes`
- Verify: `git lfs install`, `uv sync`

- [ ] **Step 0.1: Create branch and ensure clean working tree**

```bash
git checkout main
git pull --ff-only
git status   # must be clean
git checkout -b feat/h1-corpus-ingest
```

Expected: `Switched to a new branch 'feat/h1-corpus-ingest'`.

- [ ] **Step 0.2: Add new dependencies to pyproject.toml**

Insert into the `dependencies` array (currently empty `[]`):

```toml
dependencies = [
    "httpx>=0.27,<1.0",
    "lxml>=5.3,<6.0",
    "beautifulsoup4>=4.12,<5.0",
    "tiktoken>=0.8,<1.0",
    "tenacity>=8.5,<10.0",
    "pydantic>=2.9,<3.0",
]
```

Add `hypothesis` and `pytest-cov` to `dev`:

```toml
dev = [
    "pytest>=9.0.3,<11.0",
    "pytest-cov>=5.0,<7.0",
    "hypothesis>=6.0,<7.0",
    "ruff>=0.7,<0.10",
    "black>=26.3.1,<28.0",
    "mypy>=1.11,<2.0",
    "bandit>=1.7,<2.0",
    "pip-audit>=2.7,<3.0",
    "pre-commit>=3.8,<5.0",
]
```

Add coverage configuration in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/regulaitor"]
branch = true

[tool.coverage.report]
fail_under = 90
show_missing = true
skip_covered = false
exclude_also = [
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

Update `pytest` config to enable coverage and the new contract / integration directories:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra -q --strict-markers --cov=src/regulaitor/corpus --cov-report=term-missing --cov-fail-under=0"
markers = [
    "integration: integration tests using stub HTTP server",
    "contract: contract tests using hypothesis",
]
```

Note: `--cov-fail-under=0` is a placeholder until Task 10, where we raise it to 90.

Update `mypy.files` to include the new modules:

```toml
[tool.mypy]
python_version = "3.11"
files = ["src", "scripts"]
strict_optional = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
no_implicit_optional = true
```

- [ ] **Step 0.3: Update .gitignore for LFS-managed corpus directories**

Find these lines in `.gitignore`:

```
corpus/raw/
corpus/processed/
corpus/indexes/
*.lance
```

Replace with:

```
# corpus/raw and corpus/processed are tracked via Git-LFS (see .gitattributes)
# corpus/indexes is the LanceDB store, kept local per machine
corpus/indexes/
*.lance
```

The corpus/raw and corpus/processed directories will now be tracked through LFS pointers.

- [ ] **Step 0.4: Create .gitattributes for LFS**

Create `.gitattributes` at repo root:

```
# Git-LFS for corpus binaries
corpus/raw/** filter=lfs diff=lfs merge=lfs -text
corpus/processed/** filter=lfs diff=lfs merge=lfs -text

# Normalise line endings on text files (avoid LF-CRLF warnings on Windows)
* text=auto
*.py text eol=lf
*.md text eol=lf
*.toml text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.json text eol=lf
*.xml text eol=lf
*.html text eol=lf
```

- [ ] **Step 0.5: Update CI workflow to fetch LFS files**

In `.github/workflows/ci.yml`, every `actions/checkout@v4` step needs `lfs: true`. Update each of the three jobs:

```yaml
      - uses: actions/checkout@v4
        with:
          lfs: true
```

- [ ] **Step 0.6: Install Git-LFS locally and sync deps**

```bash
git lfs install
uv sync --extra dev
```

Expected: LFS hooks installed, dependencies resolved including new ones.

- [ ] **Step 0.7: Verify all tools still work after deps bump**

```bash
uv run ruff check .
uv run black --check .
uv run mypy
uv run pytest
```

Expected: all green (the smoke test from H0.1 still passes; we haven't added new code yet, just deps).

- [ ] **Step 0.8: Commit**

```bash
git add pyproject.toml uv.lock .gitignore .gitattributes .github/workflows/ci.yml
git commit -m "chore(h1): add corpus deps, configure Git-LFS, raise CI checkout to lfs:true"
```

If `pre-commit` modifies any file, re-stage and re-commit.

---

## Task 1: Pydantic schemas

**Files:**
- Create: `src/regulaitor/corpus/__init__.py`
- Create: `src/regulaitor/corpus/schemas.py`
- Create: `tests/unit/corpus/__init__.py`
- Create: `tests/unit/corpus/test_schemas.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/unit/corpus/__init__.py` (empty) and `tests/unit/corpus/test_schemas.py`:

```python
"""Unit tests for corpus.schemas: construction, validation, serialization."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from regulaitor.corpus.schemas import (
    ArticleEntry,
    HttpCacheEntry,
    LanguageEntry,
    Manifest,
    Stats,
)


def _now() -> datetime:
    return datetime(2026, 4, 30, 18, 42, 13, tzinfo=timezone.utc)


def test_language_entry_minimal_construction() -> None:
    le = LanguageEntry(
        hash="sha256:abc",
        tokens=412,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32024R1689",
    )
    assert le.chunks == []
    assert le.embedded_at is None


def test_language_entry_round_trips() -> None:
    le = LanguageEntry(
        hash="sha256:abc",
        tokens=412,
        chunks=["ai_act.6.1.es", "ai_act.6.2.es"],
        embedded_at=_now(),
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32024R1689",
    )
    payload = le.model_dump_json()
    restored = LanguageEntry.model_validate_json(payload)
    assert restored == le


def test_article_entry_requires_at_least_one_language() -> None:
    with pytest.raises(ValidationError):
        ArticleEntry(article_id="ai_act.1", articulo="1", languages={})


def test_manifest_full_round_trip() -> None:
    le_es = LanguageEntry(
        hash="sha256:aa",
        tokens=100,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32024R1689",
    )
    le_en = LanguageEntry(
        hash="sha256:bb",
        tokens=95,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
    )
    article = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        title_es="Objeto",
        title_en="Subject matter",
        languages={"es": le_es, "en": le_en},
    )
    manifest = Manifest(
        corpus="ai_act",
        celex="32024R1689",
        version="2024-07-12",
        source_format="formex4",
        fetched_at=_now(),
        languages=["es", "en"],
        http_cache={
            "es": HttpCacheEntry(etag='W/"abc"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT"),
            "en": HttpCacheEntry(etag='W/"def"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT"),
        },
        stats=Stats(articles_total=1, raw_size_bytes=1024),
        articles=[article],
    )
    payload = manifest.model_dump_json()
    restored = Manifest.model_validate_json(payload)
    assert restored == manifest


def test_manifest_rejects_unknown_corpus() -> None:
    with pytest.raises(ValidationError):
        Manifest(
            corpus="random_law",  # type: ignore[arg-type]
            celex="X",
            version="2024-01-01",
            source_format="formex4",
            fetched_at=_now(),
            languages=["es"],
            http_cache={"es": HttpCacheEntry()},
            stats=Stats(articles_total=0, raw_size_bytes=0),
            articles=[],
        )


def test_http_cache_entry_all_fields_optional() -> None:
    assert HttpCacheEntry().etag is None
    assert HttpCacheEntry().last_modified is None
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
uv run pytest tests/unit/corpus/test_schemas.py -v
```

Expected: collection error or all tests fail with `ModuleNotFoundError: No module named 'regulaitor.corpus'`.

- [ ] **Step 1.3: Create the corpus package and schemas module**

Create `src/regulaitor/corpus/__init__.py`:

```python
"""Corpus ingestion: fetch, parse, validate, manifest writing."""
```

Create `src/regulaitor/corpus/schemas.py`:

```python
"""Pydantic v2 schemas for the corpus pipeline.

Schemas are stable for H1; H2 extends them by populating `LanguageEntry.chunks`
and `LanguageEntry.embedded_at` rather than adding new fields.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Norma = Literal["ai_act", "gdpr", "nis2", "dora"]
Language = Literal["es", "en"]
SourceFormat = Literal["formex4", "html"]


class HttpCacheEntry(BaseModel):
    """Conditional-request hints captured per (corpus, language) on the last fetch."""

    etag: str | None = None
    last_modified: str | None = None  # raw HTTP date string (RFC 7231)


class LanguageEntry(BaseModel):
    """Per-language metadata for one article. H2 fills `chunks` and `embedded_at`."""

    hash: str  # "sha256:<hex>" — SHA256 of the raw article text
    tokens: int
    chunks: list[str] = Field(default_factory=list)
    embedded_at: datetime | None = None
    fetched_at: datetime
    source_url: str


class ArticleEntry(BaseModel):
    """One article across all available languages."""

    article_id: str  # e.g. "ai_act.6"
    articulo: str
    title_es: str | None = None
    title_en: str | None = None
    languages: dict[Language, LanguageEntry]

    @field_validator("languages")
    @classmethod
    def _at_least_one_language(cls, v: dict[Language, LanguageEntry]) -> dict[Language, LanguageEntry]:
        if not v:
            raise ValueError("at least one language entry required")
        return v


class Stats(BaseModel):
    """Per-manifest counters used for diagnostics and the decisions log."""

    articles_total: int
    chunks_total: int = 0
    embedded_total: int = 0
    raw_size_bytes: int


class Manifest(BaseModel):
    """Top-level manifest written to corpus/manifests/<corpus>.json."""

    corpus: Norma
    celex: str
    version: str  # consolidation date YYYY-MM-DD
    source_format: SourceFormat
    fetched_at: datetime
    languages: list[Language]
    http_cache: dict[Language, HttpCacheEntry]
    stats: Stats
    articles: list[ArticleEntry]
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/corpus/test_schemas.py -v
```

Expected: 6 passed.

- [ ] **Step 1.5: Run the full lint suite**

```bash
uv run ruff check .
uv run black --check .
uv run mypy
```

Expected: all green.

- [ ] **Step 1.6: Commit**

```bash
git add src/regulaitor/corpus/__init__.py src/regulaitor/corpus/schemas.py \
        tests/unit/corpus/__init__.py tests/unit/corpus/test_schemas.py
git commit -m "feat(corpus): add Pydantic v2 schemas for manifest, articles, language entries"
```

---

## Task 2: Manifest module

**Files:**
- Create: `src/regulaitor/corpus/manifest.py`
- Create: `tests/unit/corpus/test_manifest.py`

Provides `load`, `save_atomic`, `diff` over the `Manifest` schema.

- [ ] **Step 2.1: Write the failing test**

Create `tests/unit/corpus/test_manifest.py`:

```python
"""Unit tests for corpus.manifest: load, save_atomic, diff."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.schemas import (
    ArticleEntry,
    HttpCacheEntry,
    LanguageEntry,
    Manifest,
    Stats,
)


def _now() -> datetime:
    return datetime(2026, 4, 30, 18, 42, 13, tzinfo=timezone.utc)


def _make_lang_entry(text_hash: str, tokens: int = 100) -> LanguageEntry:
    return LanguageEntry(
        hash=text_hash,
        tokens=tokens,
        fetched_at=_now(),
        source_url="https://eur-lex.europa.eu/x",
    )


def _make_manifest(articles: list[ArticleEntry]) -> Manifest:
    return Manifest(
        corpus="ai_act",
        celex="32024R1689",
        version="2024-07-12",
        source_format="formex4",
        fetched_at=_now(),
        languages=["es", "en"],
        http_cache={"es": HttpCacheEntry(), "en": HttpCacheEntry()},
        stats=Stats(articles_total=len(articles), raw_size_bytes=0),
        articles=articles,
    )


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert manifest_mod.load(tmp_path / "missing.json") is None


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    article = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        languages={"es": _make_lang_entry("sha256:aa"), "en": _make_lang_entry("sha256:bb")},
    )
    m = _make_manifest([article])
    path = tmp_path / "ai_act.json"
    manifest_mod.save_atomic(path, m)
    assert path.exists()
    loaded = manifest_mod.load(path)
    assert loaded == m


def test_save_atomic_uses_tmp_then_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """save_atomic must never leave a partial file at the target path."""
    m = _make_manifest([])
    path = tmp_path / "ai_act.json"

    real_replace = manifest_mod.os.replace
    captured: dict[str, object] = {}

    def spy(src: str, dst: str) -> None:
        captured["src"] = src
        captured["dst"] = dst
        real_replace(src, dst)

    monkeypatch.setattr(manifest_mod.os, "replace", spy)
    manifest_mod.save_atomic(path, m)
    assert captured["dst"] == str(path)
    assert str(captured["src"]).endswith(".tmp")


def test_diff_no_old_manifest_marks_all_added() -> None:
    new = _make_manifest([
        ArticleEntry(
            article_id="ai_act.1",
            articulo="1",
            languages={"es": _make_lang_entry("sha256:aa")},
        ),
        ArticleEntry(
            article_id="ai_act.2",
            articulo="2",
            languages={"es": _make_lang_entry("sha256:bb")},
        ),
    ])
    diff = manifest_mod.diff(None, new)
    assert sorted(diff.added_articles) == ["ai_act.1", "ai_act.2"]
    assert diff.removed_articles == []
    assert diff.changed_articles == []
    assert diff.unchanged_articles == []


def test_diff_detects_changed_added_removed_unchanged() -> None:
    art1_old = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        languages={"es": _make_lang_entry("sha256:OLD1")},
    )
    art2_old = ArticleEntry(
        article_id="ai_act.2",
        articulo="2",
        languages={"es": _make_lang_entry("sha256:KEEP")},
    )
    art3_old = ArticleEntry(
        article_id="ai_act.3",
        articulo="3",
        languages={"es": _make_lang_entry("sha256:GONE")},
    )

    art1_new = ArticleEntry(
        article_id="ai_act.1",
        articulo="1",
        languages={"es": _make_lang_entry("sha256:NEW1")},  # changed
    )
    art2_new = ArticleEntry(
        article_id="ai_act.2",
        articulo="2",
        languages={"es": _make_lang_entry("sha256:KEEP")},  # unchanged
    )
    art4_new = ArticleEntry(
        article_id="ai_act.4",
        articulo="4",
        languages={"es": _make_lang_entry("sha256:NEW4")},  # added
    )
    # art3 dropped → removed

    old = _make_manifest([art1_old, art2_old, art3_old])
    new = _make_manifest([art1_new, art2_new, art4_new])
    diff = manifest_mod.diff(old, new)
    assert diff.added_articles == ["ai_act.4"]
    assert diff.removed_articles == ["ai_act.3"]
    assert diff.changed_articles == ["ai_act.1"]
    assert diff.unchanged_articles == ["ai_act.2"]
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/corpus/test_manifest.py -v
```

Expected: `ModuleNotFoundError: No module named 'regulaitor.corpus.manifest'`.

- [ ] **Step 2.3: Implement `corpus/manifest.py`**

Create `src/regulaitor/corpus/manifest.py`:

```python
"""Atomic load / save / diff of corpus manifests."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from regulaitor.corpus.schemas import Manifest


@dataclass(frozen=True)
class ManifestDiff:
    added_articles: list[str]
    removed_articles: list[str]
    changed_articles: list[str]
    unchanged_articles: list[str]


def load(path: Path) -> Manifest | None:
    """Load a manifest from disk, returning None if the file is absent."""
    if not path.exists():
        return None
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_atomic(path: Path, manifest: Manifest) -> None:
    """Write the manifest atomically: temp file then os.replace.

    Guarantees the target file is either the previous valid manifest or the
    new one — never a partial write. Crucial because downstream H2 reads it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = manifest.model_dump_json(indent=2)
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def diff(old: Manifest | None, new: Manifest) -> ManifestDiff:
    """Compute per-article diff between two manifests by article_id and hash.

    An article is `changed` when its `article_id` exists in both but the union
    of language hashes differs. `unchanged` when all language hashes match.
    """
    if old is None:
        return ManifestDiff(
            added_articles=sorted(a.article_id for a in new.articles),
            removed_articles=[],
            changed_articles=[],
            unchanged_articles=[],
        )

    old_index = {a.article_id: a for a in old.articles}
    new_index = {a.article_id: a for a in new.articles}

    added = sorted(new_index.keys() - old_index.keys())
    removed = sorted(old_index.keys() - new_index.keys())

    changed: list[str] = []
    unchanged: list[str] = []
    for aid in sorted(old_index.keys() & new_index.keys()):
        old_hashes = {lang: le.hash for lang, le in old_index[aid].languages.items()}
        new_hashes = {lang: le.hash for lang, le in new_index[aid].languages.items()}
        if old_hashes == new_hashes:
            unchanged.append(aid)
        else:
            changed.append(aid)

    return ManifestDiff(
        added_articles=added,
        removed_articles=removed,
        changed_articles=changed,
        unchanged_articles=unchanged,
    )
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/corpus/test_manifest.py -v
```

Expected: 5 passed.

- [ ] **Step 2.5: Lint and commit**

```bash
uv run ruff check . && uv run black --check . && uv run mypy
git add src/regulaitor/corpus/manifest.py tests/unit/corpus/test_manifest.py
git commit -m "feat(corpus): add manifest module with atomic save and per-article diff"
```

---

## Task 3: Test fixtures (synthetic Formex + HTML)

**Files:**
- Create: `tests/fixtures/formex/ai_act_es_mini.xml`
- Create: `tests/fixtures/formex/ai_act_en_mini.xml`
- Create: `tests/fixtures/formex/malformed_no_articles.xml`
- Create: `tests/fixtures/formex/malformed_missing_num.xml`
- Create: `tests/fixtures/formex/ai_act_with_long_article.xml`
- Create: `tests/fixtures/html/ai_act_es_mini.html`
- Create: `tests/fixtures/html/ai_act_es_broken.html`

These are hand-crafted, NOT snapshots of real EUR-Lex. They cannot drift with EUR-Lex updates and serve as a stable contract for the parsers.

- [ ] **Step 3.1: Create the Spanish mini Formex fixture**

`tests/fixtures/formex/ai_act_es_mini.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CONS.ACT>
  <ARTICLE>
    <NO.ARTICLE>1</NO.ARTICLE>
    <TI.ART>Objeto</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>El presente Reglamento establece normas armonizadas relativas a la introduccion en el mercado y la puesta en servicio de sistemas de inteligencia artificial.</TXT>
    </PARAG>
    <PARAG>
      <NO.P>2</NO.P>
      <TXT>El presente Reglamento se aplica a los proveedores que introduzcan en el mercado o pongan en servicio sistemas de IA en la Union.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>2</NO.ARTICLE>
    <TI.ART>Ambito de aplicacion</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>El presente Reglamento se aplica a sistemas de IA introducidos en el mercado de la Union.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>3</NO.ARTICLE>
    <TI.ART>Definiciones</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>A efectos del presente Reglamento se entendera por sistema de IA un sistema basado en una maquina.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>4</NO.ARTICLE>
    <TI.ART>Alfabetizacion en materia de IA</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>Los proveedores y responsables del despliegue de sistemas de IA adoptaran medidas para garantizar un nivel suficiente de alfabetizacion en materia de IA.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>5</NO.ARTICLE>
    <TI.ART>Practicas de IA prohibidas</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>Quedan prohibidas las practicas de IA siguientes: la introduccion en el mercado de un sistema de IA que utilice tecnicas subliminales.</TXT>
    </PARAG>
  </ARTICLE>
</CONS.ACT>
```

- [ ] **Step 3.2: Create the English mini Formex fixture**

`tests/fixtures/formex/ai_act_en_mini.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CONS.ACT>
  <ARTICLE>
    <NO.ARTICLE>1</NO.ARTICLE>
    <TI.ART>Subject matter</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>This Regulation lays down harmonised rules concerning the placing on the market and putting into service of artificial intelligence systems.</TXT>
    </PARAG>
    <PARAG>
      <NO.P>2</NO.P>
      <TXT>This Regulation applies to providers placing on the market or putting into service AI systems in the Union.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>2</NO.ARTICLE>
    <TI.ART>Scope</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>This Regulation applies to AI systems placed on the market in the Union.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>3</NO.ARTICLE>
    <TI.ART>Definitions</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>For the purposes of this Regulation an AI system means a machine-based system.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>4</NO.ARTICLE>
    <TI.ART>AI literacy</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>Providers and deployers of AI systems shall take measures to ensure a sufficient level of AI literacy.</TXT>
    </PARAG>
  </ARTICLE>
  <ARTICLE>
    <NO.ARTICLE>5</NO.ARTICLE>
    <TI.ART>Prohibited AI practices</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>The following AI practices shall be prohibited: the placing on the market of an AI system that deploys subliminal techniques.</TXT>
    </PARAG>
  </ARTICLE>
</CONS.ACT>
```

- [ ] **Step 3.3: Create malformed fixtures**

`tests/fixtures/formex/malformed_no_articles.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CONS.ACT>
  <FOREWORD>El presente Reglamento entra en vigor.</FOREWORD>
</CONS.ACT>
```

`tests/fixtures/formex/malformed_missing_num.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CONS.ACT>
  <ARTICLE>
    <TI.ART>Articulo sin numero</TI.ART>
    <PARAG>
      <NO.P>1</NO.P>
      <TXT>Este articulo no tiene NO.ARTICLE.</TXT>
    </PARAG>
  </ARTICLE>
</CONS.ACT>
```

- [ ] **Step 3.4: Create a long-article fixture (for chunker calibration in H2)**

`tests/fixtures/formex/ai_act_with_long_article.xml`:

Use a single article whose `<TXT>` content is repeated to exceed ~3000 tokens. To keep this plan readable, use a Python helper to generate it once:

```python
# Run once interactively, then commit the resulting file.
content = "Este Reglamento establece obligaciones detalladas. " * 600
xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<CONS.ACT>\n'
    '  <ARTICLE>\n'
    '    <NO.ARTICLE>6</NO.ARTICLE>\n'
    '    <TI.ART>Reglas de clasificacion</TI.ART>\n'
    '    <PARAG>\n'
    '      <NO.P>1</NO.P>\n'
    f'      <TXT>{content}</TXT>\n'
    '    </PARAG>\n'
    '  </ARTICLE>\n'
    '</CONS.ACT>\n'
)
from pathlib import Path
Path("tests/fixtures/formex/ai_act_with_long_article.xml").write_text(xml, encoding="utf-8")
```

Run this once via `uv run python -c "<paste>"` and commit the resulting file.

- [ ] **Step 3.5: Create HTML fixtures**

`tests/fixtures/html/ai_act_es_mini.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>AI Act mini</title></head>
<body>
  <div class="eli-main-title">REGLAMENTO MINI</div>
  <div id="art_1">
    <p class="ti-art">Articulo 1</p>
    <p class="sti-art">Objeto</p>
    <p class="normal">El presente Reglamento establece normas armonizadas.</p>
  </div>
  <div id="art_2">
    <p class="ti-art">Articulo 2</p>
    <p class="sti-art">Ambito de aplicacion</p>
    <p class="normal">El presente Reglamento se aplica a sistemas de IA.</p>
  </div>
</body>
</html>
```

`tests/fixtures/html/ai_act_es_broken.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head><title>Broken</title></head>
<body>
  <p>EUR-Lex template change: no recognisable article markers.</p>
</body>
</html>
```

- [ ] **Step 3.6: Commit fixtures**

```bash
git add tests/fixtures/
git commit -m "test(corpus): add synthetic Formex and HTML fixtures for parser tests"
```

---

## Task 4: Formex parser

**Files:**
- Create: `src/regulaitor/corpus/formex_parser.py`
- Create: `tests/unit/corpus/test_formex_parser.py`

- [ ] **Step 4.1: Write the failing tests**

`tests/unit/corpus/test_formex_parser.py`:

```python
"""Unit tests for FormexParser against synthetic XML fixtures."""
from pathlib import Path

import pytest

from regulaitor.corpus.formex_parser import (
    FormexParser,
    FormexValidationError,
    ParsedArticle,
    ParsedParagraph,
)

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "formex"


def test_parse_mini_es_returns_5_articles() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_es_mini.xml").read_bytes())
    assert len(articles) == 5
    assert [a.articulo for a in articles] == ["1", "2", "3", "4", "5"]


def test_parse_mini_es_extracts_titles_and_text() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_es_mini.xml").read_bytes())
    art1 = articles[0]
    assert art1.title == "Objeto"
    assert "normas armonizadas" in art1.text
    assert "proveedores" in art1.text
    assert len(art1.paragraphs) == 2
    assert art1.paragraphs[0].apartado == "1"
    assert art1.paragraphs[1].apartado == "2"


def test_parse_mini_en_returns_5_articles() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_en_mini.xml").read_bytes())
    assert len(articles) == 5
    assert articles[0].title == "Subject matter"


def test_parse_no_articles_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError, match="zero ARTICLE"):
        parser.parse((FIX / "malformed_no_articles.xml").read_bytes())


def test_parse_missing_article_number_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError, match="NO.ARTICLE"):
        parser.parse((FIX / "malformed_missing_num.xml").read_bytes())


def test_parse_invalid_xml_raises() -> None:
    parser = FormexParser()
    with pytest.raises(FormexValidationError):
        parser.parse(b"<not><valid")


def test_parsed_article_text_collapses_whitespace() -> None:
    parser = FormexParser()
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<CONS.ACT><ARTICLE><NO.ARTICLE>1</NO.ARTICLE>"
        b"<TI.ART>T</TI.ART><PARAG><NO.P>1</NO.P>"
        b"<TXT>line1   line2\n\nline3</TXT></PARAG></ARTICLE></CONS.ACT>"
    )
    article = parser.parse(xml)[0]
    assert article.text == "line1 line2 line3"
    assert article.paragraphs[0].text == "line1 line2 line3"


def test_long_article_returns_single_parsed_article() -> None:
    parser = FormexParser()
    articles = parser.parse((FIX / "ai_act_with_long_article.xml").read_bytes())
    assert len(articles) == 1
    assert articles[0].articulo == "6"
    assert len(articles[0].text) > 5000  # stress text
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/corpus/test_formex_parser.py -v
```

Expected: ModuleNotFoundError on `regulaitor.corpus.formex_parser`.

- [ ] **Step 4.3: Implement the parser**

Create `src/regulaitor/corpus/formex_parser.py`:

```python
"""Parse Formex 4 XML (EUR-Lex Office of Publications schema) into ParsedArticle.

Synthetic fixtures live in tests/fixtures/formex/. Real EUR-Lex Formex documents
have additional namespaces and elements; the parser uses tolerant XPath that
ignores unknown elements while requiring the structural minimum (ARTICLE with
NO.ARTICLE and at least one PARAG/TXT).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree


class FormexValidationError(Exception):
    """Raised when the input is not parseable Formex 4 or fails structural checks."""


@dataclass(frozen=True)
class ParsedParagraph:
    apartado: str
    text: str


@dataclass(frozen=True)
class ParsedArticle:
    articulo: str
    title: str | None
    text: str
    paragraphs: list[ParsedParagraph] = field(default_factory=list)


_WS_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _text_content(node: etree._Element) -> str:
    """Concatenate all text inside the node (including nested tags) and normalise."""
    return _normalise("".join(node.itertext()))


class FormexParser:
    """Parse Formex 4 byte content into ParsedArticle list."""

    ARTICLE_XPATH = ".//ARTICLE"
    NO_ARTICLE_XPATH = "./NO.ARTICLE"
    TITLE_XPATH = "./TI.ART"
    PARAG_XPATH = "./PARAG"
    NO_P_XPATH = "./NO.P"
    TXT_XPATH = "./TXT"

    def parse(self, xml_bytes: bytes) -> list[ParsedArticle]:
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise FormexValidationError(f"invalid XML: {exc}") from exc

        articles_nodes = root.xpath(self.ARTICLE_XPATH)
        if not articles_nodes:
            raise FormexValidationError("zero ARTICLE nodes found")

        out: list[ParsedArticle] = []
        for node in articles_nodes:
            num_nodes = node.xpath(self.NO_ARTICLE_XPATH)
            if not num_nodes:
                raise FormexValidationError("ARTICLE without NO.ARTICLE")
            articulo = _normalise(num_nodes[0].text or "")
            if not articulo:
                raise FormexValidationError("ARTICLE NO.ARTICLE is empty")

            title_nodes = node.xpath(self.TITLE_XPATH)
            title = _normalise(title_nodes[0].text or "") if title_nodes else None

            paragraphs: list[ParsedParagraph] = []
            for p_node in node.xpath(self.PARAG_XPATH):
                num_p_nodes = p_node.xpath(self.NO_P_XPATH)
                txt_nodes = p_node.xpath(self.TXT_XPATH)
                if not num_p_nodes or not txt_nodes:
                    continue  # tolerate; some PARAGs lack numbering
                apartado = _normalise(num_p_nodes[0].text or "")
                paragraph_text = _text_content(txt_nodes[0])
                if apartado and paragraph_text:
                    paragraphs.append(ParsedParagraph(apartado=apartado, text=paragraph_text))

            article_text = " ".join(p.text for p in paragraphs)
            if not article_text:
                # Fallback: collect any text under ARTICLE if there are no PARAGs
                article_text = _text_content(node)
                if not article_text:
                    raise FormexValidationError(f"ARTICLE {articulo} has empty text")

            out.append(ParsedArticle(
                articulo=articulo,
                title=title,
                text=article_text,
                paragraphs=paragraphs,
            ))
        return out
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/corpus/test_formex_parser.py -v
```

Expected: 8 passed.

- [ ] **Step 4.5: Lint and commit**

```bash
uv run ruff check . && uv run black --check . && uv run mypy
git add src/regulaitor/corpus/formex_parser.py tests/unit/corpus/test_formex_parser.py
git commit -m "feat(corpus): add Formex 4 parser with structural validation"
```

---

## Task 5: HTML fallback parser

**Files:**
- Create: `src/regulaitor/corpus/html_parser.py`
- Create: `tests/unit/corpus/test_html_parser.py`

Same `parse()` signature as FormexParser. Used only when Formex isn't available for a particular consolidated version.

- [ ] **Step 5.1: Write the failing tests**

`tests/unit/corpus/test_html_parser.py`:

```python
"""Unit tests for HtmlParser against synthetic HTML fixtures."""
from pathlib import Path

import pytest

from regulaitor.corpus.html_parser import HtmlParser, HtmlParseError

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "html"


def test_parse_mini_returns_2_articles() -> None:
    parser = HtmlParser()
    articles = parser.parse((FIX / "ai_act_es_mini.html").read_bytes())
    assert len(articles) == 2
    assert [a.articulo for a in articles] == ["1", "2"]
    assert articles[0].title == "Objeto"
    assert "normas armonizadas" in articles[0].text


def test_parse_broken_template_raises() -> None:
    parser = HtmlParser()
    with pytest.raises(HtmlParseError, match="no recognisable article"):
        parser.parse((FIX / "ai_act_es_broken.html").read_bytes())
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/corpus/test_html_parser.py -v
```

- [ ] **Step 5.3: Implement HtmlParser**

Create `src/regulaitor/corpus/html_parser.py`:

```python
"""Best-effort HTML fallback parser for EUR-Lex pages.

Used only when Formex 4 isn't available for a given consolidated version.
Brittle by design — EUR-Lex template changes will require updates here, not
in the upstream pipeline. Document any update in docs/technical_decisions_log.md.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph

_NUM_RE = re.compile(r"art[íi]culo\s+(\d+)", re.IGNORECASE)


class HtmlParseError(Exception):
    """Raised when no recognisable article markers are found in the HTML."""


class HtmlParser:
    """Parse EUR-Lex HTML by extracting div blocks with id matching ^art_\\d+$."""

    def parse(self, html_bytes: bytes) -> list[ParsedArticle]:
        soup = BeautifulSoup(html_bytes, "html.parser")
        article_divs = soup.find_all("div", id=re.compile(r"^art_\d+$"))
        if not article_divs:
            raise HtmlParseError("no recognisable article markers (expected div#art_N)")

        out: list[ParsedArticle] = []
        for div in article_divs:
            div_id = div.get("id", "")
            articulo = div_id.removeprefix("art_")
            title_node = div.find("p", class_="sti-art")
            title = title_node.get_text(strip=True) if title_node else None

            paragraph_text = " ".join(
                p.get_text(strip=True) for p in div.find_all("p", class_="normal")
            ).strip()
            if not paragraph_text:
                paragraph_text = div.get_text(strip=True)

            paragraphs = [ParsedParagraph(apartado="1", text=paragraph_text)] if paragraph_text else []
            out.append(ParsedArticle(
                articulo=articulo,
                title=title,
                text=paragraph_text,
                paragraphs=paragraphs,
            ))
        return out
```

- [ ] **Step 5.4: Run tests, lint, commit**

```bash
uv run pytest tests/unit/corpus/test_html_parser.py -v
uv run ruff check . && uv run black --check . && uv run mypy
git add src/regulaitor/corpus/html_parser.py tests/unit/corpus/test_html_parser.py
git commit -m "feat(corpus): add HTML fallback parser for EUR-Lex when Formex unavailable"
```

---

## Task 6: Validation invariants

**Files:**
- Create: `src/regulaitor/corpus/validate.py`
- Create: `tests/unit/corpus/test_validate.py`

- [ ] **Step 6.1: Write the failing tests**

`tests/unit/corpus/test_validate.py`:

```python
"""Unit tests for validate.validate against synthetic ParsedArticle lists."""
import pytest

from regulaitor.corpus.formex_parser import ParsedArticle
from regulaitor.corpus.validate import (
    EXPECTED_ARTICLE_COUNTS,
    ValidationFailure,
    validate,
)


def _art(num: str, text: str = "x") -> ParsedArticle:
    return ParsedArticle(articulo=num, title=None, text=text, paragraphs=[])


def test_expected_counts_constants() -> None:
    assert EXPECTED_ARTICLE_COUNTS["ai_act"] == 113
    assert EXPECTED_ARTICLE_COUNTS["gdpr"] == 99


def test_validate_full_coverage_returns_ok_report() -> None:
    articles = [_art(str(i)) for i in range(1, 114)]
    report = validate("ai_act", articles, strict=False)
    assert report.coverage_ok is True
    assert report.expected == 113
    assert report.found == 113
    assert report.duplicates == []
    assert report.missing == []


def test_validate_partial_coverage_strict_raises() -> None:
    articles = [_art(str(i)) for i in range(1, 50)]  # only 49 of 113
    with pytest.raises(ValidationFailure):
        validate("ai_act", articles, strict=True)


def test_validate_detects_duplicates() -> None:
    articles = [_art("1"), _art("2"), _art("2"), _art("3")]
    report = validate("ai_act", articles, strict=False)
    assert "2" in report.duplicates


def test_validate_detects_empty_text() -> None:
    articles = [_art("1", text="")]
    report = validate("ai_act", articles, strict=False)
    assert "1" in report.empty


def test_validate_unknown_corpus_raises() -> None:
    with pytest.raises(KeyError):
        validate("unknown", [_art("1")], strict=False)  # type: ignore[arg-type]
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/corpus/test_validate.py -v
```

- [ ] **Step 6.3: Implement validation**

Create `src/regulaitor/corpus/validate.py`:

```python
"""Article-level invariants checked after parsing and before manifest write."""
from __future__ import annotations

from dataclasses import dataclass, field

from regulaitor.corpus.formex_parser import ParsedArticle
from regulaitor.corpus.schemas import Norma

EXPECTED_ARTICLE_COUNTS: dict[Norma, int] = {
    "ai_act": 113,
    "gdpr": 99,
    # nis2 and dora pinned in H14
}


@dataclass
class ValidationReport:
    coverage_ok: bool
    expected: int
    found: int
    duplicates: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)


class ValidationFailure(Exception):
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


def validate(corpus: Norma, articles: list[ParsedArticle], *, strict: bool = True) -> ValidationReport:
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
```

- [ ] **Step 6.4: Run tests, lint, commit**

```bash
uv run pytest tests/unit/corpus/test_validate.py -v
uv run ruff check . && uv run black --check . && uv run mypy
git add src/regulaitor/corpus/validate.py tests/unit/corpus/test_validate.py
git commit -m "feat(corpus): add validation invariants (coverage, duplicates, empty)"
```

---

## Task 7: EUR-Lex HTTP client

**Files:**
- Create: `src/regulaitor/corpus/eurlex.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/unit/corpus/test_eurlex.py`

The client uses `httpx` directly with an explicit allowlist. We test it with `httpx.MockTransport` so no real network calls in CI.

- [ ] **Step 7.1: Write the failing tests**

Create `tests/integration/__init__.py` (empty).

Create `tests/integration/conftest.py`:

```python
"""Shared fixtures for integration tests using httpx.MockTransport (no sockets)."""
from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest


@pytest.fixture
def mock_transport_factory() -> Callable[[Callable[[httpx.Request], httpx.Response]], httpx.MockTransport]:
    def _make(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    return _make
```

Create `tests/unit/corpus/test_eurlex.py`:

```python
"""Unit tests for EurLexClient with mocked HTTP transport."""
from __future__ import annotations

import httpx
import pytest

from regulaitor.corpus.eurlex import (
    EurLexAllowlistError,
    EurLexClient,
    FetchResultModified,
    FetchResultNotModified,
)
from regulaitor.corpus.schemas import HttpCacheEntry


def test_fetch_formex_200_returns_modified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<CONS.ACT/>",
            headers={"ETag": 'W/"abc"', "Last-Modified": "Fri, 12 Jul 2024 00:00:00 GMT"},
        )

    client = EurLexClient(transport=httpx.MockTransport(handler))
    result = client.fetch_formex(celex="32024R1689", language="es")
    assert isinstance(result, FetchResultModified)
    assert result.content == b"<CONS.ACT/>"
    assert result.etag == 'W/"abc"'


def test_fetch_formex_304_returns_not_modified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304, content=b"")

    client = EurLexClient(transport=httpx.MockTransport(handler))
    cache = HttpCacheEntry(etag='W/"abc"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT")
    result = client.fetch_formex(celex="32024R1689", language="es", cache=cache)
    assert isinstance(result, FetchResultNotModified)


def test_fetch_formex_4xx_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    client = EurLexClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_formex(celex="bad", language="es")


def test_allowlist_blocks_non_eurlex_url() -> None:
    client = EurLexClient()
    with pytest.raises(EurLexAllowlistError):
        client._enforce_allowlist("https://evil.example/formex.xml")


def test_conditional_headers_set_when_cache_present() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["if_none_match"] = request.headers.get("If-None-Match", "")
        captured["if_modified_since"] = request.headers.get("If-Modified-Since", "")
        return httpx.Response(304)

    client = EurLexClient(transport=httpx.MockTransport(handler))
    cache = HttpCacheEntry(etag='W/"xyz"', last_modified="Fri, 12 Jul 2024 00:00:00 GMT")
    client.fetch_formex(celex="32024R1689", language="es", cache=cache)
    assert captured["if_none_match"] == 'W/"xyz"'
    assert captured["if_modified_since"] == "Fri, 12 Jul 2024 00:00:00 GMT"
```

- [ ] **Step 7.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/corpus/test_eurlex.py -v
```

- [ ] **Step 7.3: Implement EurLexClient**

Create `src/regulaitor/corpus/eurlex.py`:

```python
"""HTTP client for EUR-Lex with allowlist and conditional requests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from regulaitor.corpus.schemas import HttpCacheEntry, Language

ALLOWED_HOSTS = {"eur-lex.europa.eu"}


class EurLexAllowlistError(Exception):
    """Raised when a URL outside the allowlist is requested."""


@dataclass(frozen=True)
class FetchResultModified:
    content: bytes
    etag: str | None
    last_modified: str | None
    source_url: str
    fetched_at: datetime


@dataclass(frozen=True)
class FetchResultNotModified:
    pass


FetchResult = FetchResultModified | FetchResultNotModified

_LANG_TO_PATH: dict[Language, str] = {"es": "ES", "en": "EN"}


def _formex_url(celex: str, language: Language) -> str:
    return (
        f"https://eur-lex.europa.eu/legal-content/{_LANG_TO_PATH[language]}"
        f"/TXT/?uri=CELEX:{celex}"
    )


def _html_url(celex: str, language: Language) -> str:
    return (
        f"https://eur-lex.europa.eu/legal-content/{_LANG_TO_PATH[language]}"
        f"/TXT/HTML/?uri=CELEX:{celex}"
    )


class EurLexClient:
    """HTTP client targeting EUR-Lex with retry, conditional requests, allowlist."""

    def __init__(
        self,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "RegulAItor-corpus-ingest/0.1"},
        )

    def fetch_formex(
        self,
        celex: str,
        language: Language,
        cache: HttpCacheEntry | None = None,
    ) -> FetchResult:
        url = _formex_url(celex, language)
        return self._fetch(url, language=language, cache=cache, accept="application/xml")

    def fetch_html(
        self,
        celex: str,
        language: Language,
        cache: HttpCacheEntry | None = None,
    ) -> FetchResult:
        url = _html_url(celex, language)
        return self._fetch(url, language=language, cache=cache, accept="text/html")

    def _enforce_allowlist(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        if host not in ALLOWED_HOSTS:
            raise EurLexAllowlistError(f"host '{host}' not in allowlist")

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    def _fetch(
        self,
        url: str,
        *,
        language: Language,
        cache: HttpCacheEntry | None,
        accept: str,
    ) -> FetchResult:
        self._enforce_allowlist(url)
        headers: dict[str, str] = {"Accept": accept}
        if cache is not None:
            if cache.etag:
                headers["If-None-Match"] = cache.etag
            if cache.last_modified:
                headers["If-Modified-Since"] = cache.last_modified

        response = self._client.get(url, headers=headers)
        if response.status_code == 304:
            return FetchResultNotModified()
        response.raise_for_status()
        return FetchResultModified(
            content=response.content,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
            source_url=str(response.url),
            fetched_at=datetime.now(timezone.utc),
        )

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 7.4: Run tests, lint, commit**

```bash
uv run pytest tests/unit/corpus/test_eurlex.py tests/integration/ -v
uv run ruff check . && uv run black --check . && uv run mypy
git add src/regulaitor/corpus/eurlex.py tests/unit/corpus/test_eurlex.py \
        tests/integration/__init__.py tests/integration/conftest.py
git commit -m "feat(corpus): add EurLexClient with allowlist, conditional requests, retries"
```

---

## Task 8: Ingest orchestrator

**Files:**
- Create: `src/regulaitor/corpus/ingest.py`
- Create: `tests/integration/test_ingest_flow.py`

This is the longest task. Read the spec §5.7 (orchestrator pseudocode) and §5.7 cont. (`build_manifest`) before implementing.

- [ ] **Step 8.1: Write the failing integration test**

`tests/integration/test_ingest_flow.py`:

```python
"""Integration tests for ingest.run() end-to-end with mocked HTTP."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from regulaitor.corpus import ingest, manifest as manifest_mod


@pytest.fixture
def es_xml() -> bytes:
    return Path("tests/fixtures/formex/ai_act_es_mini.xml").read_bytes()


@pytest.fixture
def en_xml() -> bytes:
    return Path("tests/fixtures/formex/ai_act_en_mini.xml").read_bytes()


def _make_handler(es_xml: bytes, en_xml: bytes, *, etag: str = 'W/"v1"'):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "ES/TXT" in path:
            content = es_xml
        elif "EN/TXT" in path:
            content = en_xml
        else:
            return httpx.Response(404)
        if request.headers.get("If-None-Match") == etag:
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=content,
            headers={"ETag": etag, "Last-Modified": "Fri, 12 Jul 2024 00:00:00 GMT"},
        )

    return handler


def test_first_run_creates_manifest_with_5_articles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    es_xml: bytes,
    en_xml: bytes,
) -> None:
    monkeypatch.setattr(ingest, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(ingest, "PROCESSED_DIR", tmp_path / "processed")

    # Inject mock client by monkeypatching the EurLexClient constructor
    handler = _make_handler(es_xml, en_xml)
    monkeypatch.setattr(
        ingest, "EurLexClient",
        lambda **kw: ingest._make_test_client(httpx.MockTransport(handler)),
    )
    # Override expected counts so 5-article fixture passes coverage
    monkeypatch.setattr(
        "regulaitor.corpus.validate.EXPECTED_ARTICLE_COUNTS",
        {"ai_act": 5, "gdpr": 99},
    )

    summary = ingest.run(corpus="ai_act", languages=["es", "en"])
    assert summary.errors == 0
    manifest_path = tmp_path / "manifests" / "ai_act.json"
    m = manifest_mod.load(manifest_path)
    assert m is not None
    assert m.stats.articles_total == 5
    assert {a.articulo for a in m.articles} == {"1", "2", "3", "4", "5"}
    assert all("es" in a.languages and "en" in a.languages for a in m.articles)


def test_rerun_with_no_changes_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    es_xml: bytes,
    en_xml: bytes,
) -> None:
    monkeypatch.setattr(ingest, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(ingest, "PROCESSED_DIR", tmp_path / "processed")
    handler = _make_handler(es_xml, en_xml)
    monkeypatch.setattr(
        ingest, "EurLexClient",
        lambda **kw: ingest._make_test_client(httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "regulaitor.corpus.validate.EXPECTED_ARTICLE_COUNTS",
        {"ai_act": 5, "gdpr": 99},
    )

    first = ingest.run(corpus="ai_act", languages=["es", "en"])
    second = ingest.run(corpus="ai_act", languages=["es", "en"])
    assert first.errors == 0
    assert second.errors == 0
    assert second.fetch_skipped == 2  # both ES and EN returned 304
    diffs = second.diffs.get("ai_act")
    assert diffs is not None
    assert diffs.changed_articles == []
    assert diffs.added_articles == []
    assert sorted(diffs.unchanged_articles) == ["ai_act.1", "ai_act.2", "ai_act.3", "ai_act.4", "ai_act.5"]
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_ingest_flow.py -v
```

Expected: ModuleNotFoundError on `regulaitor.corpus.ingest`.

- [ ] **Step 8.3: Implement the orchestrator**

Create `src/regulaitor/corpus/ingest.py`:

```python
"""Corpus ingest orchestrator: fetch → parse → validate → manifest write.

H1 scope: lands raw + processed + manifest (article-level metadata).
H2 will read processed/ to chunk + embed + write LanceDB.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
from regulaitor.corpus.formex_parser import FormexParser, FormexValidationError, ParsedArticle
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
from regulaitor.corpus.validate import EXPECTED_ARTICLE_COUNTS, validate

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
    """Helper used by tests to inject a mock transport."""
    return EurLexClient(transport=transport)


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
    old_index = (
        {a.article_id: a for a in old_manifest.articles} if old_manifest else {}
    )
    all_articulos = sorted(
        {a.articulo for parsed in articles_per_lang.values() for a in parsed},
        key=lambda x: int(x) if x.isdigit() else 10**9,
    )
    now = datetime.now(timezone.utc)
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
                    source_url="",  # filled by caller (see run())
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
                old_cache = (
                    old_manifest.http_cache.get(lang) if old_manifest else None
                )
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
                        # Reuse old data; re-construct ParsedArticle from manifest + processed cache.
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
                    fetch_result = client.fetch_html(CELEX[c], lang, cache)
                    if isinstance(fetch_result, FetchResultNotModified):
                        summary.errors += 1
                        continue
                    parsed = html_parser.parse(fetch_result.content)
                    _write_atomic(RAW_DIR / f"{c}_{lang}.xml", fetch_result.content)

                source_format = fetch_format
                report = validate(c, parsed, strict=True)
                logger.info(
                    "validate %s/%s: %d/%d", c, lang, report.found, report.expected
                )

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
                                    {"apartado": p.apartado, "text": p.text}
                                    for p in a.paragraphs
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
                raw_total_bytes=raw_total_bytes or (
                    old_manifest.stats.raw_size_bytes if old_manifest else 0
                ),
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


def _reload_processed(path: Path) -> list[ParsedArticle]:
    data = json.loads(path.read_text(encoding="utf-8"))
    from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph

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
```

- [ ] **Step 8.4: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_ingest_flow.py -v
```

Expected: 2 passed.

- [ ] **Step 8.5: Run full test suite to verify nothing broke**

```bash
uv run pytest -v
```

Expected: all green (≥ 30 tests).

- [ ] **Step 8.6: Lint and commit**

```bash
uv run ruff check . && uv run black --check . && uv run mypy
git add src/regulaitor/corpus/ingest.py tests/integration/test_ingest_flow.py
git commit -m "feat(corpus): add ingest orchestrator with idempotent fetch and manifest build"
```

---

## Task 9: CLI wrapper

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/ingest.py`
- Create: `tests/unit/test_scripts_ingest.py`

- [ ] **Step 9.1: Write the failing test**

`tests/unit/test_scripts_ingest.py`:

```python
"""Smoke test for the CLI argument parsing in scripts/ingest.py."""
from scripts.ingest import _build_parser


def test_default_args() -> None:
    args = _build_parser().parse_args([])
    assert args.corpus == "all"
    assert args.lang == "all"
    assert args.force_fetch is False
    assert args.force_reprocess is False
    assert args.no_html_fallback is False
    assert args.dry_run is False


def test_specific_corpus_lang() -> None:
    args = _build_parser().parse_args(["--corpus", "ai_act", "--lang", "es"])
    assert args.corpus == "ai_act"
    assert args.lang == "es"


def test_force_flags() -> None:
    args = _build_parser().parse_args(["--force-fetch", "--force-reprocess", "--dry-run"])
    assert args.force_fetch is True
    assert args.force_reprocess is True
    assert args.dry_run is True
```

- [ ] **Step 9.2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_scripts_ingest.py -v
```

Expected: ModuleNotFoundError on `scripts.ingest`.

- [ ] **Step 9.3: Create `scripts/__init__.py` (empty) and the CLI**

Create `scripts/__init__.py` (empty file).

Create `scripts/ingest.py`:

```python
"""CLI wrapper for regulaitor.corpus.ingest.run.

Usage:
    python -m scripts.ingest --corpus ai_act --lang es,en
    python -m scripts.ingest --force-fetch --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys

from regulaitor.corpus.ingest import run


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="regulaitor.ingest", description="Ingest a regulatory corpus from EUR-Lex.")
    p.add_argument("--corpus", choices=["ai_act", "gdpr", "all"], default="all")
    p.add_argument("--lang", choices=["es", "en", "all"], default="all")
    p.add_argument("--force-fetch", action="store_true", help="Ignore HTTP 304 cache")
    p.add_argument("--force-reprocess", action="store_true", help="Reprocess all articles, ignore hash cache")
    p.add_argument("--no-html-fallback", action="store_true", help="Disable HTML fallback when Formex fails")
    p.add_argument("--dry-run", action="store_true", help="Do not write the manifest")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    summary = run(
        corpus=args.corpus,
        languages="all" if args.lang == "all" else [args.lang],
        force_fetch=args.force_fetch,
        force_reprocess=args.force_reprocess,
        allow_html_fallback=not args.no_html_fallback,
        dry_run=args.dry_run,
    )
    print(summary.format_human())
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 9.4: Run tests, lint, commit**

```bash
uv run pytest tests/unit/test_scripts_ingest.py -v
uv run ruff check . && uv run black --check . && uv run mypy
git add scripts/__init__.py scripts/ingest.py tests/unit/test_scripts_ingest.py
git commit -m "feat(corpus): add CLI wrapper scripts/ingest.py"
```

---

## Task 10: Contract tests + coverage gate

**Files:**
- Create: `tests/contract/__init__.py`
- Create: `tests/contract/test_parser_contract.py`
- Create: `tests/contract/test_manifest_contract.py`
- Modify: `pyproject.toml` (`--cov-fail-under=90`)
- Modify: `Makefile` (lint target runs full coverage check)

- [ ] **Step 10.1: Write parser contract test (hypothesis-based)**

`tests/contract/__init__.py` (empty).

`tests/contract/test_parser_contract.py`:

```python
"""Contract tests: parser output round-trips through Pydantic schemas."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph

# ASCII-safe text avoids accidental encoding edge cases in tests.
text_strategy = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="<>&"),
    min_size=1,
    max_size=200,
)


@given(num=st.integers(min_value=1, max_value=200), text=text_strategy)
def test_parsed_article_roundtrips_to_dict(num: int, text: str) -> None:
    article = ParsedArticle(articulo=str(num), title="t", text=text, paragraphs=[
        ParsedParagraph(apartado="1", text=text),
    ])
    assert article.text == text
    assert article.paragraphs[0].apartado == "1"


@given(text=text_strategy)
@settings(max_examples=50)
def test_paragraph_text_preserved(text: str) -> None:
    p = ParsedParagraph(apartado="1", text=text)
    assert p.text == text


pytestmark = pytest.mark.contract
```

- [ ] **Step 10.2: Write manifest contract test**

`tests/contract/test_manifest_contract.py`:

```python
"""Contract test: manifest written by save_atomic round-trips through load."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.schemas import (
    ArticleEntry,
    HttpCacheEntry,
    LanguageEntry,
    Manifest,
    Stats,
)


def _now() -> datetime:
    return datetime(2026, 4, 30, 18, 42, 13, tzinfo=timezone.utc)


hex_hash = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64).map(lambda h: f"sha256:{h}")


@given(
    n_articles=st.integers(min_value=0, max_value=10),
    article_hashes=st.lists(hex_hash, max_size=10, unique=True),
)
@settings(max_examples=20)
def test_manifest_roundtrip(tmp_path: Path, n_articles: int, article_hashes: list[str]) -> None:
    article_hashes = (article_hashes + [f"sha256:{'0' * 64}"] * n_articles)[:n_articles]
    articles = [
        ArticleEntry(
            article_id=f"ai_act.{i}",
            articulo=str(i),
            languages={
                "es": LanguageEntry(
                    hash=h,
                    tokens=10,
                    fetched_at=_now(),
                    source_url="https://eur-lex.europa.eu/x",
                ),
            },
        )
        for i, h in enumerate(article_hashes, start=1)
    ]
    m = Manifest(
        corpus="ai_act",
        celex="32024R1689",
        version="2024-07-12",
        source_format="formex4",
        fetched_at=_now(),
        languages=["es"],
        http_cache={"es": HttpCacheEntry()},
        stats=Stats(articles_total=len(articles), raw_size_bytes=0),
        articles=articles,
    )
    path = tmp_path / "ai_act.json"
    manifest_mod.save_atomic(path, m)
    loaded = manifest_mod.load(path)
    assert loaded == m


pytestmark = pytest.mark.contract
```

- [ ] **Step 10.3: Run contract tests**

```bash
uv run pytest tests/contract/ -v
```

Expected: green.

- [ ] **Step 10.4: Raise the coverage gate to 90%**

Edit `pyproject.toml` `[tool.pytest.ini_options]`:

```toml
addopts = "-ra -q --strict-markers --cov=src/regulaitor/corpus --cov-report=term-missing --cov-fail-under=90"
```

- [ ] **Step 10.5: Run full test suite with coverage**

```bash
uv run pytest
```

Expected: all green AND coverage ≥ 90% on `src/regulaitor/corpus/`. If below, add focused tests until it clears.

- [ ] **Step 10.6: Update Makefile lint target to enforce coverage in `make test`**

The `pytest` target already enforces it via `--cov-fail-under=90`. Optional: add a Make target shortcut:

```makefile
test-cov:
	$(UV) run pytest --cov-report=html
	@echo "HTML coverage report in htmlcov/"
```

- [ ] **Step 10.7: Commit**

```bash
git add pyproject.toml Makefile tests/contract/
git commit -m "test(corpus): add hypothesis contract tests and enforce 90% coverage gate"
```

---

## Task 11: Skill `rag-ingest` proposal

**Files:**
- Create: `.claude/skills/rag-ingest/SKILL.md`

Per CLAUDE.md §12.3: propose the SKILL.md content to the owner BEFORE writing the file.

- [ ] **Step 11.1: Draft the SKILL.md proposal in chat (do not write file yet)**

Present the following draft to the owner and wait for OK:

````markdown
---
name: rag-ingest
description: Use this skill when adding a new regulatory corpus (NIS2, DORA, or any future norma) following the H1 RegulAItor pattern. Ensures the new corpus integrates with the existing fetch/parse/validate/manifest pipeline without ad-hoc divergence.
version: 1
allowed-tools: Read, Edit, Write, Bash
---

# Skill: rag-ingest

## When to use

A new regulatory corpus is being added to RegulAItor. Examples:
- "Add NIS2 to the corpus."
- "Ingest DORA in Spanish and English."
- "Replace AI Act with the next consolidated version."

Do NOT use this skill for non-regulatory documents (those go through the user document pipeline in src/regulaitor/document/).

## Procedure

1. Read `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` and the latest H1 closure entry in `docs/technical_decisions_log.md`.
2. Confirm the EUR-Lex CELEX, the consolidated date, and the languages to fetch with the owner.
3. Update constants:
   - `src/regulaitor/corpus/ingest.py` `CELEX` and `VERSION` dicts.
   - `src/regulaitor/corpus/validate.py` `EXPECTED_ARTICLE_COUNTS`.
4. Add fixture files in `tests/fixtures/formex/{new_corpus}_{lang}_mini.xml` for ES and EN (5-10 articles, hand-crafted).
5. Add a unit test in `tests/unit/corpus/test_formex_parser.py` parametrising the new fixture.
6. Run `uv run python -m scripts.ingest --corpus {new_corpus}` against EUR-Lex (smoke).
7. Verify article count matches `EXPECTED_ARTICLE_COUNTS`.
8. Commit `corpus/manifests/{new_corpus}.json` plus LFS pointers for `corpus/raw/` and `corpus/processed/`.
9. Update `docs/technical_decisions_log.md` with the new corpus entry (version, languages, smoke run stats).
10. If the new corpus reveals a Formex schema variation the parser doesn't handle, raise a follow-up ADR — do NOT silently extend `formex_parser.py` without recording the decision.

## What this skill does NOT do

- Does not chunk, embed or write to LanceDB. That is H2 territory.
- Does not modify `src/regulaitor/agents/` or `mcp_server/`.
- Does not bypass the propose-and-wait rule for new MCPs (e.g. don't install `playwright` even if EUR-Lex changes scheme).

## Verification

Before merging:
- `uv run pytest --cov-fail-under=90` green.
- Manifest round-trips through `Manifest.model_validate_json`.
- Smoke output recorded in `docs/technical_decisions_log.md`.
````

- [ ] **Step 11.2: After owner OK, write the file**

```bash
mkdir -p .claude/skills/rag-ingest
# write the approved content to .claude/skills/rag-ingest/SKILL.md
```

- [ ] **Step 11.3: Commit**

```bash
git add .claude/skills/rag-ingest/SKILL.md
git commit -m "feat(skills): add rag-ingest skill for future corpus additions"
```

---

## Task 12: Smoke run against real EUR-Lex

**Files:**
- Modify: `corpus/manifests/ai_act.json` (created by smoke)
- Modify: `corpus/manifests/gdpr.json` (created by smoke)
- LFS-track: `corpus/raw/*.xml`, `corpus/processed/*.json`

This is the only task that hits the network. Run locally; do not run in CI (CI uses stubs only).

- [ ] **Step 12.1: Run the ingest against real EUR-Lex**

```bash
uv run python -m scripts.ingest --corpus all --lang all --verbose 2>&1 | tee /tmp/h1-smoke.log
```

Expected: exit 0, manifests written, output similar to spec §6.1.

If a Formex 404 happens, the run will fall back to HTML automatically (per `--no-html-fallback` not set). If both Formex and HTML fail, the run fails with a clear error and we update the URL constants in `eurlex.py` accordingly (and record in the log).

- [ ] **Step 12.2: Verify article counts**

```bash
uv run python - <<'PY'
import json
for c in ("ai_act", "gdpr"):
    m = json.loads(open(f"corpus/manifests/{c}.json", encoding="utf-8").read())
    print(c, "articles:", m["stats"]["articles_total"])
PY
```

Expected: `ai_act articles: 113` and `gdpr articles: 99`.

- [ ] **Step 12.3: Run idempotency proof**

```bash
uv run python -m scripts.ingest --corpus all --lang all
```

Expected: summary shows `fetch_skipped: 4` (2 corpora × 2 langs all 304), all `unchanged_articles` populated, `changed_articles` empty.

- [ ] **Step 12.4: Verify LFS tracking**

```bash
git status
git lfs ls-files
```

Expected: `corpus/raw/*.xml` and `corpus/processed/*.json` listed under LFS.

- [ ] **Step 12.5: Commit smoke artefacts**

```bash
git add corpus/manifests/ corpus/raw/ corpus/processed/
git commit -m "chore(corpus): smoke run output — AI Act 113 articles, GDPR 99 articles, ES+EN"
```

---

## Task 13: Documentation closure

**Files:**
- Create: `docs/adr/0003-corpus-pipeline.md`
- Modify: `docs/adr/0002-skills-mcps-roadmap.md`
- Modify: `docs/technical_decisions_log.md`

- [ ] **Step 13.1: Draft ADR 0003**

Create `docs/adr/0003-corpus-pipeline.md`:

```markdown
# ADR 0003 — Corpus pipeline architecture

- **Status:** Accepted
- **Date:** 2026-04-30 (H1 closure)
- **Deciders:** Project owner.

## Context

H1 needs a reproducible, idempotent way to land regulatory corpora (AI Act, GDPR) into the repository in a form that downstream RAG (H2) can consume without re-implementing source parsing.

## Decision

Implement the corpus pipeline as four isolated modules under `src/regulaitor/corpus/`:

- `eurlex.py` — HTTP client with allowlist (`eur-lex.europa.eu` only), conditional requests via `If-Modified-Since` + `ETag`, and tenacity retries on connection errors.
- `formex_parser.py` — primary parser over Formex 4 XML using lxml XPath. Strict structural validation: ARTICLE without NO.ARTICLE raises.
- `html_parser.py` — fallback parser using BeautifulSoup. Used only when Formex returns 404 or schema-violating content.
- `validate.py` — invariants: expected article count per corpus, no duplicates, no empty articles.
- `manifest.py` — atomic load/save of `corpus/manifests/<corpus>.json` and per-article diff.
- `ingest.py` — orchestrator wiring the above; `_build_manifest` preserves H2 chunks/embeddings when an article hash hasn't changed.

The CLI entry point is `python -m scripts.ingest` with idempotency flags `--force-fetch` and `--force-reprocess`.

Storage: `corpus/raw/` and `corpus/processed/` tracked via Git-LFS; `corpus/manifests/*.json` tracked as plain git for clean diffs.

## Alternatives considered

- **Single-file ingest script.** Rejected: tangles HTTP, parsing, validation in one place, hard to test in isolation, hard to reuse in H2.
- **DVC instead of Git-LFS.** Rejected: <1 GB total expected, DVC adds external infrastructure that doesn't earn its keep at this scale.
- **Akoma Ntoso XML over Formex 4.** Rejected: GDPR consolidated isn't fully published in Akoma Ntoso; running two parsers is more complex than Formex+HTML fallback.
- **Manifest with per-chunk hashes (instead of per-article).** Rejected: chunks live in H2; tying H1 manifest to chunk identity creates false coupling. We hash per article and let H2 derive its own chunk identity from the article text.

## Consequences

### Positive

- Each module is independently testable; coverage gate ≥ 90% achievable without integration shortcuts.
- Re-runs are cheap: HTTP 304 short-circuits download; per-article hash short-circuits embedding cost (in H2).
- Adding NIS2 / DORA in H14 means updating constants (`CELEX`, `VERSION`, `EXPECTED_ARTICLE_COUNTS`) and adding fixtures, no architecture change.

### Negative

- HTML fallback parser is brittle by design — EUR-Lex template changes will require manual updates. Mitigation: keep it minimal, document any changes in the decisions log.
- Token counter uses tiktoken (cl100k_base) as a proxy for BGE-M3 tokens. Drift is acceptable for chunking thresholds in H2 but not for billing math; H2 will swap to the BGE-M3 tokenizer.

## References

- `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md`
- `docs/superpowers/plans/2026-04-30-h1-corpus-ingest.md`
- `docs/technical_decisions_log.md` H1 section
```

- [ ] **Step 13.2: Update ADR 0002 with deferrals**

In `docs/adr/0002-skills-mcps-roadmap.md`, move `adr-writer` from H1 to H10 in the calendar table; mark MCP `mcp-server-time` as "not introduced" with rationale "Python datetime sufficient"; mark MCP `fetch` as deferred to H3+. Add a note at the bottom:

```markdown
## 2026-04-30 update

H1 implementation deferred:
- `adr-writer` → H10 (single batch in H1 didn't justify the skill).
- MCP `fetch` → H3+ (httpx direct in eurlex.py with explicit allowlist is simpler).
- MCP `mcp-server-time` → not introduced (Python datetime is sufficient).

See `docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` §11 for full rationale.
```

- [ ] **Step 13.3: Add H1 closure entry to the decisions log**

Append to `docs/technical_decisions_log.md` (under "H1" section, replacing the "Pendientes de decisión" placeholder if present):

```markdown
### 2026-04-30 · H1 cerrado — corpus AI Act + RGPD ingestados

- **Decisión:** H1 implementado y cerrado. Pipeline `corpus/` operativo con 2 corpus (AI Act, GDPR) en 2 idiomas (ES, EN). Cobertura {N}% en `src/regulaitor/corpus/`. CI verde en commit `<hash>`.
- **Smoke run stats:**
  - AI Act: 113 artículos, ES + EN, source_format=formex4 (o html si fallback).
  - GDPR: 99 artículos, ES + EN, source_format=formex4 (o html si fallback).
  - Tamaño raw total: ~{X} MB (Git-LFS).
  - Tiempo total ingest: ~{T} segundos.
- **Diferimientos confirmados** (vs ADR 0002 inicial):
  - Skill `adr-writer` → H10.
  - MCP `fetch` → H3+.
  - MCP `mcp-server-time` → no introducido.
- **Lecciones:**
  - {Anota aquí las sorpresas reales del smoke: URL pattern divergences, Formex coverage gaps, tokenizer drift, etc.}
- **Enlace:** ADR 0003, commit `<hash>`, PR `#<n>`, CI run `<id>`.
```

Replace the `{N}`, `{X}`, `{T}`, `<hash>`, etc. with real values from the smoke run.

- [ ] **Step 13.4: Commit documentation**

```bash
git add docs/adr/0002-skills-mcps-roadmap.md docs/adr/0003-corpus-pipeline.md docs/technical_decisions_log.md
git commit -m "docs(h1): land ADR 0003, update ADR 0002 deferrals, add H1 closure log entry"
```

---

## Task 14: Push, verify CI, open PR, merge, tag

- [ ] **Step 14.1: Push the branch**

```bash
git push -u origin feat/h1-corpus-ingest
```

- [ ] **Step 14.2: Open the pull request**

```bash
gh pr create --title "H1: corpus AI Act + RGPD ingest pipeline" --body "$(cat <<'EOF'
## Summary

- Implements the corpus fetch / parse / validate / manifest pipeline per the H1 spec (`docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md`).
- AI Act (CELEX 32024R1689) and GDPR (CELEX 02016R0679-20160504) ingested in Spanish and English.
- Idempotent re-runs via HTTP `If-Modified-Since` + per-article SHA256 hash.
- Test coverage ≥90% on `src/regulaitor/corpus/`.
- ADR 0003 lands the pipeline architecture; ADR 0002 updated with skill/MCP deferrals.
- Decisions log updated with smoke run stats.

## Test plan

- [ ] Local: `uv run pytest` green
- [ ] Local: `uv run python -m scripts.ingest --corpus all --lang all` exit 0
- [ ] Local: re-run shows `fetch_skipped: 4`, no diff
- [ ] CI: lint, test, security all green
- [ ] Manifests visible in repo: `corpus/manifests/ai_act.json` (113 articles), `corpus/manifests/gdpr.json` (99 articles)
EOF
)"
```

- [ ] **Step 14.3: Watch CI**

```bash
gh pr checks --watch
```

Expected: lint, test, security green.

- [ ] **Step 14.4: Self-review the PR**

Read the PR diff in the GitHub UI. Confirm:
- No accidental `.env` or secrets.
- No `print()` debug statements in production code.
- All new public APIs have docstrings.
- Manifest stats match expected counts.

- [ ] **Step 14.5: Merge to main and tag**

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
git tag -a v0.0.2-h1 -m "H1 closed: corpus AI Act + RGPD ingest pipeline operational"
git push origin v0.0.2-h1
```

- [ ] **Step 14.6: Verify the tag triggered nothing unexpected and CI is still green on main**

```bash
gh run list --limit 3
```

H1 is officially CLOSED. Update `~/.claude/plans/lee-el-archivo-claude-md-sparkling-fairy.md` and the next session can plan H2.

---

## Self-review checklist (executed at the end of plan-writing)

- [x] **Spec coverage:** every section of the spec has at least one task implementing it.
  - §4 Architecture → Tasks 1-9.
  - §5 Components → Tasks 1-9 by module.
  - §6 Data flow → Tasks 8 (orchestrator) + 12 (smoke).
  - §7 Error handling → covered in Tasks 4, 6, 7, 8 (raises + tests).
  - §8 Testing → Tasks 1-10 (unit, contract, integration).
  - §9 Repo layout → Task 0 (LFS) + every Task creating files.
  - §10 Dependencies → Task 0.
  - §11 Skills/MCPs → Task 11 (rag-ingest only) + Task 13 (ADR 0002 update).
  - §12 Open questions → resolved during Task 8 (URL pattern), Task 12 (smoke confirms).
  - §13 Acceptance criteria → Task 14 (PR template includes them).
  - §14 Risk register → mitigations baked into Tasks 4, 5, 7, 12.
  - §15 Implementation order → followed exactly.

- [x] **No placeholders:** all code blocks contain runnable code; all commands have expected outputs; no "TBD" / "implement later".

- [x] **Type consistency:** `ParsedArticle`, `ParsedParagraph`, `Manifest`, `LanguageEntry`, `ArticleEntry` referenced consistently across tasks. `ingest.run()` signature matches in Tasks 8 and 9.

- [x] **Spec gaps:** none found. Open questions in spec §12 are addressed during implementation tasks (URL pattern in Task 8, fallback path in Task 8, tokenizer drift documented in ADR 0003).

---

## Execution handoff

Plan complete and saved. Two execution options:

**1. Subagent-driven (recommended for H1)** — A fresh subagent executes each task; you and I review between tasks. Best when tasks are independent enough to dispatch and the per-task review catches drift early.

**2. Inline execution** — I execute the tasks in this session in batches with checkpoints. Lower latency but bigger context window cost.

For H1 specifically I lean **subagent-driven** because:
- 14 tasks is enough that fresh-context-per-task pays off.
- Tasks 1-9 are independent (each module is self-contained); Tasks 11-14 sequence on real-world artefacts (smoke run, PR, merge).
- Per-task subagent review is the closest to professional pair programming for a TFM.
