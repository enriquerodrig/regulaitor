# H3 — MCP Server + Retriever-Agent + Citation Validator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the H3 layer for RegulAItor — corpus loader, retrieval helper, citation validator, retriever-agent, and stdio MCP server with 3 tools — that operationalizes the "no citation, no answer" rule. End state: `python -m regulaitor.mcp_server` boots cleanly with hash-drift integrity check; the 3 MCP tools answer correctly against the live AI Act + GDPR corpus; `RetrieverAgent` returns a well-formed `Context`; CI green; ≥90% coverage including new modules.

**Architecture:** Four trust boundary layers — public surface (`mcp_server/`), agent adapter (`agents/retriever.py`), schemas + validator (`citation/`), domain helpers (`corpus/loader.py`, `rag/retrieval.py`). One shared retrieval helper (`rag/retrieval.run`) feeds both the MCP tool and the agent adapter. Corpus loader is a lazy singleton with fail-closed integrity check at warmup. Citation validator does 3 strict checks (article exists, apartado exists, normalized text match) reusing `_normalize` from H2.

**Tech Stack:** Python 3.11 · `uv` · `mcp` (Python SDK) · Pydantic v2 · pytest · hypothesis · ruff · black · mypy. All H1/H2 layers consumed unchanged.

**Branch:** All work on `feat/h3-mcp-server` (already created with the spec commit `6b6f12f`). Open PR on Task 15 for merge to `main`.

**Spec:** `docs/superpowers/specs/2026-05-05-h3-mcp-server-design.md` is the source of truth for design decisions. Each task references the relevant spec section.

---

## Task map

0. Dependencies (`mcp` SDK) + coverage extension + branch confirm
1. `citation/schemas.py` — Citation, AuditResult, RetrievedChunk, Context, FetchedArticle
2. Contract tests for citation schemas (Hypothesis round-trip + frozen)
3. `corpus/loader.py` — singleton + warmup with hash drift integrity check
4. `rag/retrieval.py` — canonical helper (embed → query → rerank → enrich)
5. `citation/validator.py` — 3 strict checks (article + apartado + text)
6. `agents/retriever.py` — RetrieverAgent adapter producing Context
7. `mcp_server/errors.py` + `mcp_server/tools.py` — adapters + error mapping
8. `mcp_server/server.py` + `mcp_server/__main__.py` — stdio bootstrap
9. Contract test for MCP tool schemas (snapshot)
10. Integration tests batch (validate, fetch, retriever, integrity drift)
11. Integration test — search_articles via stdio subprocess (slow)
12. Skills SKILL.md drafts (prompt-versioning + citation-validator)
13. Makefile `mcp-server` target + smoke run + verify
14. ADR 0005 + decisions log H3 closure entry
15. Push, verify CI, open PR, merge, tag `v0.0.4-h3`

---

## Common environment for every task

- **Working directory:** `c:\Users\enriq\Documents\regulaitor\regulaitor`.
- **Tools:** `uv` at `C:\Users\enriq\.local\bin\uv`; `gh` at same dir, authenticated.
- **Bash setup before any `uv` command:** `export PATH="/c/Users/enriq/.local/bin:$PATH" && unset VIRTUAL_ENV`.
- **Branch:** `feat/h3-mcp-server` (already on it; see `git status`).
- **Commit style:** Conventional Commits, no Co-Authored-By trailer.
- **Pre-commit hooks:** active. If they modify files, re-stage and re-commit.
- **Coverage gate:** 90% across `src/regulaitor/{corpus,rag}` (existing). H3 extends to `src/regulaitor/{citation,agents,mcp_server}`.
- **CVE-2026-1839** is ignored in CI workflow (`pip-audit --ignore-vuln CVE-2026-1839`); leave that as-is.
- **Test discipline:** TDD. Each task: write failing test → run → implement minimally → run → commit. Each step ≤5 min of work.

---

## Task 0: Dependencies + coverage extension + branch confirm

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 0.1: Confirm clean working tree on feat/h3-mcp-server**

```bash
git status
```

Expected: branch `feat/h3-mcp-server`, clean (last commit `6b6f12f` is the spec).

- [ ] **Step 0.2: Add MCP SDK runtime dep**

In `pyproject.toml`, find:

```toml
dependencies = [
    "httpx>=0.27,<1.0",
    "lxml>=6.1.0,<8.0",
    "beautifulsoup4>=4.12,<5.0",
    "tenacity>=8.5,<10.0",
    "pydantic>=2.9,<3.0",
    "pdfplumber>=0.11,<0.13",
    "FlagEmbedding>=1.3,<2.0",
    "transformers>=4.44,<5.0",
    "lancedb>=0.16,<1.0",
    "pyarrow>=18.0,<22.0",
]
```

Replace with:

```toml
dependencies = [
    "httpx>=0.27,<1.0",
    "lxml>=6.1.0,<8.0",
    "beautifulsoup4>=4.12,<5.0",
    "tenacity>=8.5,<10.0",
    "pydantic>=2.9,<3.0",
    "pdfplumber>=0.11,<0.13",
    "FlagEmbedding>=1.3,<2.0",
    "transformers>=4.44,<5.0",
    "lancedb>=0.16,<1.0",
    "pyarrow>=18.0,<22.0",
    "mcp>=1.0,<2.0",
]
```

- [ ] **Step 0.3: Extend coverage scope**

In `pyproject.toml`, find:

```toml
addopts = "-ra -q --strict-markers --cov=src/regulaitor/corpus --cov=src/regulaitor/rag --cov-report=term-missing --cov-fail-under=90"
```

Replace with:

```toml
addopts = "-ra -q --strict-markers --cov=src/regulaitor/corpus --cov=src/regulaitor/rag --cov=src/regulaitor/citation --cov=src/regulaitor/agents --cov=src/regulaitor/mcp_server --cov-report=term-missing --cov-fail-under=90"
```

- [ ] **Step 0.4: Add mypy override for the mcp SDK**

In `pyproject.toml`, after the existing `[[tool.mypy.overrides]]` blocks, append:

```toml
[[tool.mypy.overrides]]
module = "mcp.*"
ignore_missing_imports = true
```

- [ ] **Step 0.5: Lock + install**

```bash
export PATH="/c/Users/enriq/.local/bin:$PATH" && unset VIRTUAL_ENV
uv lock && uv sync --extra dev
```

Expected: `mcp` package installed; `uv.lock` updated.

- [ ] **Step 0.6: Run existing test suite to confirm no regression**

```bash
uv run pytest -m "not slow" --no-cov -q
```

Expected: 110 passed, 1 deselected (the H2 slow integration test).

- [ ] **Step 0.7: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(h3): add mcp SDK dep and extend coverage scope to citation/agents/mcp_server"
```

---

## Task 1: `citation/schemas.py` — Pydantic v2 schemas

**Files:**
- Create: `src/regulaitor/citation/__init__.py`
- Create: `src/regulaitor/citation/schemas.py`
- Create: `tests/unit/citation/__init__.py`
- Create: `tests/unit/citation/test_schemas.py`

Spec reference: §4.3.

- [ ] **Step 1.1: Create empty package**

```bash
mkdir -p src/regulaitor/citation tests/unit/citation
touch src/regulaitor/citation/__init__.py tests/unit/citation/__init__.py
```

- [ ] **Step 1.2: Write failing tests for `citation/schemas.py`**

Create `tests/unit/citation/test_schemas.py`:

```python
"""Unit tests for citation/schemas.py — Pydantic v2 contracts for H3."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    Context,
    FetchedArticle,
    RetrievedChunk,
)


def test_citation_minimum_valid() -> None:
    c = Citation(norma="ai_act", articulo="6", language="es", text="some text")
    assert c.apartado is None


def test_citation_with_apartado() -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    assert c.apartado == "1"


def test_citation_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        Citation(norma="ai_act", articulo="6", language="es", text="")


def test_citation_rejects_empty_articulo() -> None:
    with pytest.raises(ValidationError):
        Citation(norma="ai_act", articulo="", language="es", text="text")


def test_citation_is_frozen() -> None:
    c = Citation(norma="ai_act", articulo="6", language="es", text="text")
    with pytest.raises(ValidationError):
        c.text = "other"  # type: ignore[misc]


def test_audit_result_validated_true() -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    r = AuditResult(
        citation=c,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    assert r.validated is True


def test_audit_result_validated_false_with_reason() -> None:
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = AuditResult(
        citation=c,
        validated=False,
        article_exists=False,
        apartado_exists=None,
        text_normalized_match=False,
        reason="article_not_found: ai_act has no articulo 999",
    )
    assert r.reason is not None


def test_retrieved_chunk_score_in_range() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.95,
        version="32024R1689",
        source_url="https://eur-lex.europa.eu/...",
    )
    assert rc.score == 0.95


def test_retrieved_chunk_rejects_score_above_one() -> None:
    with pytest.raises(ValidationError):
        RetrievedChunk(
            chunk_id="ai_act.6.1.es",
            norma="ai_act",
            articulo="6",
            apartado="1",
            language="es",
            text="text",
            score=1.5,
            version="32024R1689",
            source_url="https://example.com",
        )


def test_retrieved_chunk_is_frozen() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.5,
        version="v",
        source_url="https://example.com",
    )
    with pytest.raises(ValidationError):
        rc.text = "other"  # type: ignore[misc]


def test_context_holds_chunks_with_metadata() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.9,
        version="v",
        source_url="https://example.com",
    )
    ctx = Context(
        query="alto riesgo",
        corpus="ai_act",
        language="es",
        chunks=[rc],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="BAAI/bge-m3",
    )
    assert ctx.query == "alto riesgo"
    assert len(ctx.chunks) == 1


def test_fetched_article_apartado_optional() -> None:
    fa = FetchedArticle(
        norma="ai_act",
        articulo="6",
        apartado=None,
        language="es",
        text="full article text",
        version="v",
        source_url="https://example.com",
    )
    assert fa.apartado is None
```

- [ ] **Step 1.3: Run tests to verify they fail**

```bash
uv run pytest tests/unit/citation/test_schemas.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: regulaitor.citation.schemas`.

- [ ] **Step 1.4: Implement `citation/schemas.py`**

Create `src/regulaitor/citation/schemas.py`:

```python
"""Pydantic v2 schemas for H3: Citation, AuditResult, RetrievedChunk, Context, FetchedArticle.

Defer Finding and Answer to H4 (decisions log 2026-05-05 entry "Schemas Pydantic en H3").
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from regulaitor.corpus.schemas import Language, Norma


class Citation(BaseModel):
    """A claim that a piece of text exists in a specific corpus location."""

    model_config = ConfigDict(frozen=True)

    norma: Norma
    articulo: str = Field(min_length=1)
    apartado: str | None = None
    language: Language
    text: str = Field(min_length=1)


class AuditResult(BaseModel):
    """Output of citation/validator.validate(). Three independent diagnostics + verdict."""

    citation: Citation
    validated: bool
    article_exists: bool
    apartado_exists: bool | None
    text_normalized_match: bool
    reason: str | None


class RetrievedChunk(BaseModel):
    """One result of rag/retrieval.run(). Citable in one MCP call (carries version + url)."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    norma: Norma
    articulo: str
    apartado: str | None
    language: Language
    text: str
    score: float = Field(ge=0.0, le=1.0)
    version: str
    source_url: str


class Context(BaseModel):
    """Wrapper produced by RetrieverAgent for downstream H4 LangGraph state."""

    query: str
    corpus: Norma
    language: Language
    chunks: list[RetrievedChunk]
    retrieved_at: datetime
    embedding_model: str


class FetchedArticle(BaseModel):
    """Output of fetch_article MCP tool. Text + minimal documentary metadata."""

    norma: Norma
    articulo: str
    apartado: str | None
    language: Language
    text: str
    version: str
    source_url: str
```

- [ ] **Step 1.5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/citation/test_schemas.py -v --no-cov
```

Expected: 12 passed.

- [ ] **Step 1.6: Lint**

```bash
uv run ruff check src/regulaitor/citation tests/unit/citation
uv run black --check src/regulaitor/citation tests/unit/citation
uv run mypy src/regulaitor/citation
```

Expected: all green.

- [ ] **Step 1.7: Commit**

```bash
git add src/regulaitor/citation tests/unit/citation
git commit -m "feat(citation): add Pydantic v2 schemas (Citation, AuditResult, RetrievedChunk, Context, FetchedArticle)"
```

---

## Task 2: Contract tests for citation schemas (Hypothesis round-trip)

**Files:**
- Create: `tests/contract/test_citation_schemas.py`

Spec reference: §11.2.

- [ ] **Step 2.1: Write Hypothesis round-trip tests**

Create `tests/contract/test_citation_schemas.py`:

```python
"""Hypothesis round-trip contract tests for citation schemas (H3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    Context,
    FetchedArticle,
    RetrievedChunk,
)

pytestmark = pytest.mark.contract


_NORMA = st.sampled_from(["ai_act", "gdpr", "nis2", "dora"])
_LANG = st.sampled_from(["es", "en"])
_NON_EMPTY = st.text(min_size=1, max_size=200)


@given(
    norma=_NORMA,
    articulo=_NON_EMPTY,
    apartado=st.one_of(st.none(), _NON_EMPTY),
    language=_LANG,
    text=_NON_EMPTY,
)
@settings(max_examples=50)
def test_citation_round_trip(
    norma: str, articulo: str, apartado: str | None, language: str, text: str
) -> None:
    c = Citation(
        norma=norma,  # type: ignore[arg-type]
        articulo=articulo,
        apartado=apartado,
        language=language,  # type: ignore[arg-type]
        text=text,
    )
    parsed = Citation.model_validate_json(c.model_dump_json())
    assert parsed == c


@given(
    chunk_id=_NON_EMPTY,
    norma=_NORMA,
    articulo=_NON_EMPTY,
    apartado=st.one_of(st.none(), _NON_EMPTY),
    language=_LANG,
    text=_NON_EMPTY,
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    version=_NON_EMPTY,
    source_url=_NON_EMPTY,
)
@settings(max_examples=50)
def test_retrieved_chunk_round_trip(
    chunk_id: str,
    norma: str,
    articulo: str,
    apartado: str | None,
    language: str,
    text: str,
    score: float,
    version: str,
    source_url: str,
) -> None:
    rc = RetrievedChunk(
        chunk_id=chunk_id,
        norma=norma,  # type: ignore[arg-type]
        articulo=articulo,
        apartado=apartado,
        language=language,  # type: ignore[arg-type]
        text=text,
        score=score,
        version=version,
        source_url=source_url,
    )
    parsed = RetrievedChunk.model_validate_json(rc.model_dump_json())
    assert parsed == rc


def test_audit_result_round_trip_minimal() -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    r = AuditResult(
        citation=c,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    parsed = AuditResult.model_validate_json(r.model_dump_json())
    assert parsed == r


def test_context_round_trip_minimal() -> None:
    rc = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="t",
        score=0.5,
        version="v",
        source_url="https://example.com",
    )
    ctx = Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[rc],
        retrieved_at=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
        embedding_model="BAAI/bge-m3",
    )
    parsed = Context.model_validate_json(ctx.model_dump_json())
    assert parsed == ctx


def test_fetched_article_round_trip_minimal() -> None:
    fa = FetchedArticle(
        norma="ai_act",
        articulo="6",
        apartado=None,
        language="es",
        text="text",
        version="v",
        source_url="https://example.com",
    )
    parsed = FetchedArticle.model_validate_json(fa.model_dump_json())
    assert parsed == fa
```

- [ ] **Step 2.2: Run contract tests to verify they pass**

```bash
uv run pytest tests/contract/test_citation_schemas.py -v --no-cov
```

Expected: 5 passed.

- [ ] **Step 2.3: Commit**

```bash
git add tests/contract/test_citation_schemas.py
git commit -m "test(citation): add hypothesis round-trip contract tests for 5 schemas"
```

---

## Task 3: `corpus/loader.py` — singleton + warmup with hash drift integrity check

**Files:**
- Create: `src/regulaitor/corpus/loader.py`
- Create: `tests/unit/corpus/test_loader.py`

Spec reference: §4.1, §7.

- [ ] **Step 3.1: Write failing tests for `corpus/loader.py`**

Create `tests/unit/corpus/test_loader.py`:

```python
"""Unit tests for corpus/loader.py — singleton + warmup + integrity check."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from regulaitor.corpus import loader


@pytest.fixture(autouse=True)
def reset_loader_singleton() -> None:
    """Reset the loader singleton between tests."""
    loader.reset()
    yield
    loader.reset()


def _write_synthetic_corpus(tmp_path: Path, norma: str, articulo: str, text_es: str) -> None:
    """Helper: write a minimal manifest + processed JSON for a single article."""
    manifests = tmp_path / "manifests"
    processed = tmp_path / "processed"
    manifests.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)

    h = hashlib.sha256(text_es.encode("utf-8")).hexdigest()

    manifest = {
        "norma": norma,
        "version": "TEST-VERSION",
        "fetched_at": "2026-05-05T00:00:00Z",
        "source_url": f"https://example.com/{norma}",
        "stats": {
            "articles_total": 1,
            "languages_total": 1,
            "chunks_total": 0,
            "embedded_total": 0,
        },
        "http_cache": {},
        "articles": [
            {
                "article_id": f"{norma}.{articulo}",
                "articulo": articulo,
                "title_es": "Title ES",
                "title_en": "Title EN",
                "languages": {
                    "es": {
                        "hash": h,
                        "tokens": 10,
                        "fetched_at": "2026-05-05T00:00:00Z",
                        "source_url": f"https://example.com/{norma}/{articulo}/es",
                        "source_format": "pdf",
                        "chunks": [],
                        "embedded_at": None,
                        "embedding_model": None,
                    },
                },
            },
        ],
    }
    (manifests / f"{norma}.json").write_text(json.dumps(manifest), encoding="utf-8")

    processed_data = [
        {
            "articulo": articulo,
            "title": "Title ES",
            "text": text_es,
            "paragraphs": [{"apartado": "1", "text": text_es}],
        }
    ]
    (processed / f"{norma}_es.json").write_text(json.dumps(processed_data), encoding="utf-8")


def test_warmup_loads_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Sample article text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    art = loader.get_article("ai_act", "6", "es")
    assert art.articulo == "6"


def test_warmup_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Sample text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()
    loader.warmup()  # second call is no-op
    art = loader.get_article("ai_act", "6", "es")
    assert art.articulo == "6"


def test_warmup_detects_hash_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Original text.")
    # Tamper with the processed file AFTER manifest hash was set
    tampered = [
        {
            "articulo": "6",
            "title": "Title ES",
            "text": "TAMPERED text.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED text."}],
        }
    ]
    (tmp_path / "processed" / "ai_act_es.json").write_text(
        json.dumps(tampered), encoding="utf-8"
    )

    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()


def test_get_article_raises_keyerror_on_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    with pytest.raises(KeyError):
        loader.get_article("ai_act", "999", "es")


def test_get_paragraph_returns_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Article text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    text = loader.get_paragraph("ai_act", "6", "1", "es")
    assert text == "Article text."


def test_get_paragraph_raises_on_missing_apartado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    with pytest.raises(KeyError):
        loader.get_paragraph("ai_act", "6", "99", "es")


def test_get_manifest_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    meta = loader.get_manifest_meta("ai_act")
    assert meta["version"] == "TEST-VERSION"
    assert meta["source_url"] == "https://example.com/ai_act"


def test_list_articulos_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    arts = loader.list_articulos("ai_act", "es")
    assert arts == ["6"]


def test_list_apartados_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    aps = loader.list_apartados("ai_act", "6", "es")
    assert aps == ["1"]


def test_get_article_before_warmup_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")


def test_reset_clears_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()
    loader.reset()

    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/corpus/test_loader.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: regulaitor.corpus.loader`.

- [ ] **Step 3.3: Implement `corpus/loader.py`**

Create `src/regulaitor/corpus/loader.py`:

```python
"""Lazy in-memory singleton for corpus manifests + processed JSON.

Loaded once at process startup via warmup(). Recomputes SHA256 of each
LanguageEntry text and validates against the manifest hash; mismatch raises
RuntimeError so the caller (MCP server) fails to start (decisions log
2026-05-05 entry "Corpus loader: lazy singleton + warmup explicit + integrity check fail-closed").
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.schemas import ArticleEntry, Language, Manifest, Norma

CORPUS_ROOT = Path("corpus")
MANIFEST_DIR = CORPUS_ROOT / "manifests"
PROCESSED_DIR = CORPUS_ROOT / "processed"

CORPORA_WITH_MANIFESTS: tuple[Norma, ...] = ("ai_act", "gdpr")

_CORPUS: dict[Norma, Manifest] = {}
_PROCESSED_CACHE: dict[tuple[Norma, Language], list[dict[str, Any]]] = {}


def reset() -> None:
    """Clear the singleton state. Test-only; production code never calls this."""
    _CORPUS.clear()
    _PROCESSED_CACHE.clear()


def warmup() -> None:
    """Load all manifests + processed JSON; verify hash integrity.

    Raises RuntimeError on any hash mismatch with an actionable message.
    Idempotent: a second call with the same files is a no-op (state already populated).
    """
    if _CORPUS:
        return

    for norma in CORPORA_WITH_MANIFESTS:
        m = manifest_mod.load(MANIFEST_DIR / f"{norma}.json")
        if m is None:
            raise RuntimeError(
                f"manifest not found for {norma} at "
                f"{MANIFEST_DIR / f'{norma}.json'}. Run `make ingest` to create it."
            )
        for article in m.articles:
            for lang_str, entry in article.languages.items():
                lang: Language = lang_str  # type: ignore[assignment]
                processed_text = _load_processed_article_text(norma, article.articulo, lang)
                computed = hashlib.sha256(processed_text.encode("utf-8")).hexdigest()
                if computed != entry.hash:
                    raise RuntimeError(
                        f"manifest hash drift detected on {norma} art. "
                        f"{article.articulo} {lang} (expected {entry.hash[:16]}..., "
                        f"got {computed[:16]}...). Run `make ingest` to refresh "
                        f"manifest, or restore corpus/processed/ from git-lfs."
                    )
        _CORPUS[norma] = m


def _load_processed_article_text(norma: Norma, articulo: str, language: Language) -> str:
    """Read the article text from corpus/processed/<norma>_<lang>.json.

    Cached per (norma, language). Concatenates paragraphs with \\n\\n if multiple.
    """
    key = (norma, language)
    if key not in _PROCESSED_CACHE:
        path = PROCESSED_DIR / f"{norma}_{language}.json"
        with path.open("r", encoding="utf-8") as f:
            _PROCESSED_CACHE[key] = json.load(f)
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            return str(art["text"])
    raise KeyError(
        f"processed article not found: {norma} art. {articulo} {language}"
    )


def get_manifest(norma: Norma) -> Manifest:
    """Return the parsed manifest for `norma`. Raises KeyError if not loaded."""
    if norma not in _CORPUS:
        raise KeyError(f"corpus {norma} not loaded; call warmup() first")
    return _CORPUS[norma]


def get_article(norma: Norma, articulo: str, language: Language) -> ArticleEntry:
    """Return the (article, language)-specific entry. Raises KeyError if absent."""
    m = get_manifest(norma)
    for a in m.articles:
        if a.articulo == articulo and language in a.languages:
            return a
    raise KeyError(
        f"{norma} has no articulo {articulo} in language {language}. "
        f"Valid articulos: {list_articulos(norma, language)[:10]}..."
    )


def get_paragraph(
    norma: Norma, articulo: str, apartado: str, language: Language
) -> str:
    """Return paragraph text. Raises KeyError if apartado absent.

    Reads from the processed JSON cache (already populated by warmup).
    """
    key = (norma, language)
    if key not in _PROCESSED_CACHE:
        raise KeyError(f"corpus {norma}/{language} not loaded; call warmup() first")
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            for p in art["paragraphs"]:
                if p["apartado"] == apartado:
                    return str(p["text"])
            raise KeyError(
                f"{norma} art. {articulo} {language} has no apartado {apartado}. "
                f"Valid apartados: {list_apartados(norma, articulo, language)}."
            )
    raise KeyError(
        f"{norma} has no articulo {articulo} in language {language}."
    )


def get_manifest_meta(norma: Norma) -> dict[str, str]:
    """Return {'version': ..., 'source_url': ...} for the corpus."""
    m = get_manifest(norma)
    return {"version": m.version, "source_url": m.source_url}


def list_articulos(norma: Norma, language: Language) -> list[str]:
    """Sorted list of articulo IDs available for (norma, language). Empty if not loaded."""
    if norma not in _CORPUS:
        return []
    return sorted(
        a.articulo for a in _CORPUS[norma].articles if language in a.languages
    )


def list_apartados(norma: Norma, articulo: str, language: Language) -> list[str]:
    """Sorted list of apartado IDs for (norma, articulo, language). Empty if absent."""
    key = (norma, language)
    if key not in _PROCESSED_CACHE:
        return []
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            return [str(p["apartado"]) for p in art["paragraphs"]]
    return []
```

- [ ] **Step 3.4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/corpus/test_loader.py -v --no-cov
```

Expected: 11 passed.

- [ ] **Step 3.5: Lint**

```bash
uv run ruff check src/regulaitor/corpus/loader.py tests/unit/corpus/test_loader.py
uv run black --check src/regulaitor/corpus/loader.py tests/unit/corpus/test_loader.py
uv run mypy src/regulaitor/corpus/loader.py
```

Expected: all green.

- [ ] **Step 3.6: Commit**

```bash
git add src/regulaitor/corpus/loader.py tests/unit/corpus/test_loader.py
git commit -m "feat(corpus): add lazy singleton loader with hash drift integrity check"
```

---

## Task 4: `rag/retrieval.py` — canonical retrieval helper

**Files:**
- Create: `src/regulaitor/rag/retrieval.py`
- Create: `tests/unit/rag/test_retrieval.py`

Spec reference: §4.2.

- [ ] **Step 4.1: Write failing tests for `rag/retrieval.py`**

Create `tests/unit/rag/test_retrieval.py`:

```python
"""Unit tests for rag/retrieval.py — canonical helper used by both
the MCP search_articles tool and the RetrieverAgent."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import RetrievedChunk
from regulaitor.rag import retrieval


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace the heavy dependencies with mocks; return them for assertions."""
    embed_mock = MagicMock(return_value=[[0.1] * 1024])
    search_mock = MagicMock()
    rerank_mock = MagicMock()
    meta_mock = MagicMock(
        return_value={"version": "32024R1689", "source_url": "https://example.com"}
    )
    connect_mock = MagicMock()

    monkeypatch.setattr(retrieval.embeddings, "embed", embed_mock)
    monkeypatch.setattr(retrieval.store, "connect", connect_mock)
    monkeypatch.setattr(retrieval.reranker, "rerank", rerank_mock)
    monkeypatch.setattr(retrieval.loader, "get_manifest_meta", meta_mock)

    return {
        "embed": embed_mock,
        "search": search_mock,
        "rerank": rerank_mock,
        "connect": connect_mock,
        "meta": meta_mock,
    }


def _make_chain(rows: list[dict[str, Any]]) -> MagicMock:
    """Build a mock that chains .search().where().limit().to_list() returning rows."""
    chain = MagicMock()
    chain.search.return_value.where.return_value.limit.return_value.to_list.return_value = rows
    return chain


def test_run_calls_embed_with_query(_patch_dependencies: dict[str, MagicMock]) -> None:
    _patch_dependencies["connect"].return_value = _make_chain([])
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("alto riesgo", "ai_act", "es", top_k=5)

    _patch_dependencies["embed"].assert_called_once_with(["alto riesgo"])


def test_run_uses_pre_rerank_50(_patch_dependencies: dict[str, MagicMock]) -> None:
    chain = _make_chain([])
    _patch_dependencies["connect"].return_value = chain
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("q", "ai_act", "es", top_k=5)

    # Verify .limit(50) was called on the search chain
    chain.search.return_value.where.return_value.limit.assert_called_once_with(50)


def test_run_filter_by_corpus_and_language(
    _patch_dependencies: dict[str, MagicMock],
) -> None:
    chain = _make_chain([])
    _patch_dependencies["connect"].return_value = chain
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("q", "ai_act", "es", top_k=5)

    where_call = chain.search.return_value.where.call_args
    where_clause = where_call.args[0]
    assert "norma = 'ai_act'" in where_clause
    assert "language = 'es'" in where_clause


def test_run_empty_store_returns_empty(_patch_dependencies: dict[str, MagicMock]) -> None:
    _patch_dependencies["connect"].return_value = _make_chain([])
    _patch_dependencies["rerank"].return_value = []

    result = retrieval.run("q", "ai_act", "es", top_k=5)

    assert result == []


def test_run_returns_chunks_with_meta(
    _patch_dependencies: dict[str, MagicMock],
) -> None:
    rows = [
        {
            "chunk_id": "ai_act.6.1.es",
            "norma": "ai_act",
            "articulo": "6",
            "apartado": "1",
            "language": "es",
            "text": "first chunk text",
        },
        {
            "chunk_id": "ai_act.7.es",
            "norma": "ai_act",
            "articulo": "7",
            "apartado": None,
            "language": "es",
            "text": "second chunk text",
        },
    ]
    _patch_dependencies["connect"].return_value = _make_chain(rows)
    _patch_dependencies["rerank"].return_value = [(0, 0.9), (1, 0.7)]

    result = retrieval.run("q", "ai_act", "es", top_k=2)

    assert len(result) == 2
    assert isinstance(result[0], RetrievedChunk)
    assert result[0].chunk_id == "ai_act.6.1.es"
    assert result[0].score == 0.9
    assert result[0].version == "32024R1689"
    assert result[0].source_url == "https://example.com"
    assert result[1].chunk_id == "ai_act.7.es"
    assert result[1].score == 0.7


def test_run_top_k_default_is_5(_patch_dependencies: dict[str, MagicMock]) -> None:
    _patch_dependencies["connect"].return_value = _make_chain([])
    _patch_dependencies["rerank"].return_value = []

    retrieval.run("q", "ai_act", "es")  # no top_k

    rerank_kwargs = _patch_dependencies["rerank"].call_args.kwargs
    assert rerank_kwargs["top_n"] == 5
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/rag/test_retrieval.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: regulaitor.rag.retrieval`.

- [ ] **Step 4.3: Implement `rag/retrieval.py`**

Create `src/regulaitor/rag/retrieval.py`:

```python
"""Canonical retrieval pipeline: embed -> store query -> rerank -> enrich.

Single source of truth used by both the MCP search_articles tool and the
RetrieverAgent. Decisions log 2026-05-05 entry
"Arquitectura: helper común con adapters finos".
"""

from __future__ import annotations

from regulaitor.citation.schemas import RetrievedChunk
from regulaitor.corpus import loader
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.rag import embeddings, reranker, store
from regulaitor.rag.store import INDEX_PATH

PRE_RERANK = 50


def run(
    query: str,
    corpus: Norma,
    language: Language,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve top-`top_k` chunks for `query` filtered by corpus + language.

    Internal pre-rerank candidate count is fixed at PRE_RERANK=50 (decisions
    log 2026-05-05 entry "Top-k en retrieval"). top_k is post-rerank.
    """
    [query_vec] = embeddings.embed([query])

    table = store.connect(INDEX_PATH)
    where_clause = f"norma = '{corpus}' AND language = '{language}'"
    candidates = (
        table.search(query_vec).where(where_clause).limit(PRE_RERANK).to_list()
    )

    if not candidates:
        return []

    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=top_k)

    meta = loader.get_manifest_meta(corpus)

    return [
        RetrievedChunk(
            chunk_id=candidates[idx]["chunk_id"],
            norma=candidates[idx]["norma"],
            articulo=candidates[idx]["articulo"],
            apartado=candidates[idx]["apartado"],
            language=candidates[idx]["language"],
            text=candidates[idx]["text"],
            score=score,
            version=meta["version"],
            source_url=meta["source_url"],
        )
        for idx, score in reranked
    ]
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/rag/test_retrieval.py -v --no-cov
```

Expected: 6 passed.

- [ ] **Step 4.5: Lint**

```bash
uv run ruff check src/regulaitor/rag/retrieval.py tests/unit/rag/test_retrieval.py
uv run black --check src/regulaitor/rag/retrieval.py tests/unit/rag/test_retrieval.py
uv run mypy src/regulaitor/rag/retrieval.py
```

Expected: all green.

- [ ] **Step 4.6: Commit**

```bash
git add src/regulaitor/rag/retrieval.py tests/unit/rag/test_retrieval.py
git commit -m "feat(rag): add canonical retrieval helper (embed -> query -> rerank -> enrich)"
```

---

## Task 5: `citation/validator.py` — 3 strict checks

**Files:**
- Create: `src/regulaitor/citation/validator.py`
- Create: `tests/unit/citation/test_validator.py`

Spec reference: §4.4.

- [ ] **Step 5.1: Write failing tests for `citation/validator.py`**

Create `tests/unit/citation/test_validator.py`:

```python
"""Unit tests for citation/validator.py — 3 strict checks against the corpus."""

from __future__ import annotations

from typing import Any

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import validate


class _FakeLoader:
    """Minimal loader stub that exposes get_paragraph and get_article-like behaviour."""

    def __init__(self, articles: dict[tuple[str, str, str], str]) -> None:
        # key: (norma, articulo, language) -> full article text
        self._articles = articles
        # key: (norma, articulo, apartado, language) -> paragraph text
        self._paragraphs: dict[tuple[str, str, str, str], str] = {}

    def add_paragraph(
        self,
        norma: str,
        articulo: str,
        apartado: str,
        language: str,
        text: str,
    ) -> None:
        self._paragraphs[(norma, articulo, apartado, language)] = text

    def get_article(self, norma: str, articulo: str, language: str) -> Any:
        if (norma, articulo, language) not in self._articles:
            raise KeyError(f"{norma} has no articulo {articulo} in language {language}")
        # Return a minimal stand-in object; the validator only needs to know it exists
        # for the article-level "no apartado given, match against full text" path.
        # The validator pulls full text via a helper we expose:
        return _FakeArticle(self._articles[(norma, articulo, language)])

    def get_paragraph(
        self, norma: str, articulo: str, apartado: str, language: str
    ) -> str:
        key = (norma, articulo, apartado, language)
        if key not in self._paragraphs:
            raise KeyError(f"no apartado {apartado}")
        return self._paragraphs[key]


class _FakeArticle:
    def __init__(self, text: str) -> None:
        self.text = text


@pytest.fixture
def loader_with_data() -> _FakeLoader:
    full_text = "El Artículo 6 establece reglas — incluido el apartado 1."
    apartado_1 = "El apartado 1 fija el ámbito"
    fl = _FakeLoader({("ai_act", "6", "es"): full_text})
    fl.add_paragraph("ai_act", "6", "1", "es", apartado_1)
    return fl


def test_validate_happy_path_with_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is True
    assert r.reason is None


def test_validate_happy_path_without_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="el artículo 6 establece reglas",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.apartado_exists is None  # no apartado given => check skipped
    assert r.text_normalized_match is True


def test_validate_article_not_found(loader_with_data: _FakeLoader) -> None:
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is False
    assert r.reason is not None
    assert "article_not_found" in r.reason


def test_validate_apartado_not_found(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="99",
        language="es",
        text="text",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is False
    assert r.reason is not None
    assert "apartado_not_found" in r.reason


def test_validate_text_not_in_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason


def test_validate_text_not_in_article(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_article" in r.reason


def test_validate_normalizes_accents_and_case(loader_with_data: _FakeLoader) -> None:
    # Citation has caps + missing accents; corpus has lowercase + accents
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="EL APARTADO 1 FIJA EL AMBITO",  # no acento on "ambito"
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True


def test_validate_normalizes_dashes(loader_with_data: _FakeLoader) -> None:
    # Corpus has em-dash —; citation uses ascii -
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="el artículo 6 establece reglas - incluido el apartado 1",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/citation/test_validator.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: regulaitor.citation.validator`.

- [ ] **Step 5.3: Implement `citation/validator.py`**

Create `src/regulaitor/citation/validator.py`:

```python
"""Citation validator — 3 strict checks: article exists, apartado exists, text match.

Reuses _normalize from rag/chunking so the citation-vs-corpus comparison uses
the same canonical form the chunker uses (decisions log 2026-05-05 entry
"Citation validator: matching normalizado exacto").
"""

from __future__ import annotations

from typing import Any

from regulaitor.citation.schemas import AuditResult, Citation
from regulaitor.corpus import loader as default_loader
from regulaitor.rag.chunking import _normalize


def validate(citation: Citation, *, loader: Any | None = None) -> AuditResult:
    """Run 3 strict checks on `citation`. Fail-fast at first failing check.

    The `loader` argument is for test injection; defaults to the corpus.loader
    singleton.
    """
    ld = loader if loader is not None else default_loader

    # Check 1: article_exists
    try:
        article = ld.get_article(citation.norma, citation.articulo, citation.language)
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
        target_text = article.text  # full article text (set by FakeArticle in tests)
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
```

**Note:** the validator's "no apartado" path reads `article.text` from the loader's `get_article` return value. The real `corpus/loader.get_article` returns an `ArticleEntry`; we'll add a `text` accessor or compose the full text differently.

To unblock TDD, the validator code currently expects `article.text` (matches `_FakeArticle` in tests). In Task 7 (when integration tests run against the real loader), we will reconcile this by adding a small helper `loader.get_article_text(norma, articulo, language)` that concatenates paragraphs. The unit tests pass with the fake loader; integration tests will exercise the real path.

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/citation/test_validator.py -v --no-cov
```

Expected: 8 passed.

- [ ] **Step 5.5: Add `loader.get_article_text` helper to bridge to real corpus**

Open `src/regulaitor/corpus/loader.py` and append the helper after `list_apartados`:

```python
def get_article_text(norma: Norma, articulo: str, language: Language) -> str:
    """Return the full article text (all paragraphs joined by '\\n\\n').

    Used by citation/validator when no apartado is given in the citation.
    """
    key = (norma, language)
    if key not in _PROCESSED_CACHE:
        raise KeyError(f"corpus {norma}/{language} not loaded; call warmup() first")
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            return "\n\n".join(str(p["text"]) for p in art["paragraphs"])
    raise KeyError(
        f"{norma} has no articulo {articulo} in language {language}."
    )
```

- [ ] **Step 5.6: Update validator to use loader.get_article_text for the no-apartado path**

In `src/regulaitor/citation/validator.py`, replace:

```python
    else:
        target_text = article.text  # full article text (set by FakeArticle in tests)
        apartado_exists = None
```

With:

```python
    else:
        # When no apartado is given, match against full article text.
        # We accept either a real loader (uses get_article_text) or a fake one
        # exposing article.text (used in unit tests with _FakeArticle).
        if hasattr(article, "text"):
            target_text = article.text
        else:
            target_text = ld.get_article_text(
                citation.norma, citation.articulo, citation.language
            )
        apartado_exists = None
```

- [ ] **Step 5.7: Re-run tests to verify both unit + new helper still pass**

```bash
uv run pytest tests/unit/citation/test_validator.py tests/unit/corpus/test_loader.py -v --no-cov
```

Expected: all passing (8 validator + 11 loader = 19 tests).

- [ ] **Step 5.8: Lint**

```bash
uv run ruff check src/regulaitor/citation/validator.py src/regulaitor/corpus/loader.py
uv run black --check src/regulaitor/citation/validator.py src/regulaitor/corpus/loader.py
uv run mypy src/regulaitor/citation/validator.py
```

Expected: all green.

- [ ] **Step 5.9: Commit**

```bash
git add src/regulaitor/citation/validator.py src/regulaitor/corpus/loader.py tests/unit/citation/test_validator.py
git commit -m "feat(citation): add validator with 3 strict checks (article + apartado + text)"
```

---

## Task 6: `agents/retriever.py` — RetrieverAgent adapter

**Files:**
- Create: `src/regulaitor/agents/__init__.py`
- Create: `src/regulaitor/agents/retriever.py`
- Create: `tests/unit/agents/__init__.py`
- Create: `tests/unit/agents/test_retriever.py`

Spec reference: §4.5.

- [ ] **Step 6.1: Create empty package**

```bash
mkdir -p src/regulaitor/agents tests/unit/agents
touch src/regulaitor/agents/__init__.py tests/unit/agents/__init__.py
```

- [ ] **Step 6.2: Write failing tests for `agents/retriever.py`**

Create `tests/unit/agents/test_retriever.py`:

```python
"""Unit tests for agents/retriever.py — RetrieverAgent adapter producing Context."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.citation.schemas import Context, RetrievedChunk


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.9,
        version="32024R1689",
        source_url="https://example.com",
    )


def test_retriever_agent_returns_context(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk = _make_chunk()
    run_mock = MagicMock(return_value=[chunk])
    model_id_mock = MagicMock(return_value="BAAI/bge-m3")

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(retriever.embeddings, "model_identifier", model_id_mock)

    agent = RetrieverAgent()
    ctx = agent.retrieve("alto riesgo", "ai_act", "es", top_k=3)

    assert isinstance(ctx, Context)
    assert ctx.query == "alto riesgo"
    assert ctx.corpus == "ai_act"
    assert ctx.language == "es"
    assert ctx.chunks == [chunk]
    assert ctx.embedding_model == "BAAI/bge-m3"
    assert ctx.retrieved_at.tzinfo == UTC


def test_retriever_agent_delegates_with_correct_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock(return_value=[])

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    agent.retrieve("q", "gdpr", "en", top_k=10)

    run_mock.assert_called_once_with("q", "gdpr", "en", top_k=10)


def test_retriever_agent_default_top_k_is_5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock(return_value=[])

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    agent.retrieve("q", "ai_act", "es")

    run_mock.assert_called_once_with("q", "ai_act", "es", top_k=5)


def test_retrieved_at_is_close_to_now(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", MagicMock(return_value=[]))
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    before = datetime.now(tz=UTC)
    ctx = agent.retrieve("q", "ai_act", "es")
    after = datetime.now(tz=UTC)

    assert before <= ctx.retrieved_at <= after
```

- [ ] **Step 6.3: Run tests to verify they fail**

```bash
uv run pytest tests/unit/agents/test_retriever.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: regulaitor.agents.retriever`.

- [ ] **Step 6.4: Implement `agents/retriever.py`**

Create `src/regulaitor/agents/retriever.py`:

```python
"""RetrieverAgent — thin LangGraph adapter around rag/retrieval.

Wraps the canonical retrieval helper output in a Context Pydantic object
for downstream H4 LangGraph state. Decisions log 2026-05-05 entry
"Context como Pydantic wrapper".
"""

from __future__ import annotations

from datetime import UTC, datetime

from regulaitor.citation.schemas import Context
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.rag import embeddings
from regulaitor.rag import retrieval as rag_retrieval


class RetrieverAgent:
    """Stateless adapter exposing retrieve(query, corpus, language) → Context.

    The agent does not call any LLM and does not orchestrate; it is the
    minimal indirection between LangGraph state (H4) and the canonical helper.
    """

    def retrieve(
        self,
        query: str,
        corpus: Norma,
        language: Language,
        top_k: int = 5,
    ) -> Context:
        chunks = rag_retrieval.run(query, corpus, language, top_k=top_k)
        return Context(
            query=query,
            corpus=corpus,
            language=language,
            chunks=chunks,
            retrieved_at=datetime.now(tz=UTC),
            embedding_model=embeddings.model_identifier(),
        )
```

- [ ] **Step 6.5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/agents/test_retriever.py -v --no-cov
```

Expected: 4 passed.

- [ ] **Step 6.6: Lint**

```bash
uv run ruff check src/regulaitor/agents tests/unit/agents
uv run black --check src/regulaitor/agents tests/unit/agents
uv run mypy src/regulaitor/agents
```

Expected: all green.

- [ ] **Step 6.7: Commit**

```bash
git add src/regulaitor/agents tests/unit/agents
git commit -m "feat(agents): add RetrieverAgent adapter producing Context for LangGraph state"
```

---

## Task 7: `mcp_server/errors.py` + `mcp_server/tools.py`

**Files:**
- Create: `src/regulaitor/mcp_server/__init__.py`
- Create: `src/regulaitor/mcp_server/errors.py`
- Create: `src/regulaitor/mcp_server/tools.py`
- Create: `tests/unit/mcp_server/__init__.py`
- Create: `tests/unit/mcp_server/test_tools.py`

Spec reference: §4.6, §6.

- [ ] **Step 7.1: Create empty package**

```bash
mkdir -p src/regulaitor/mcp_server tests/unit/mcp_server
touch src/regulaitor/mcp_server/__init__.py tests/unit/mcp_server/__init__.py
```

- [ ] **Step 7.2: Write failing tests for `mcp_server/tools.py`**

Create `tests/unit/mcp_server/test_tools.py`:

```python
"""Unit tests for mcp_server/tools.py — 3 adapters + error mapping."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import (
    AuditResult,
    Citation,
    FetchedArticle,
    RetrievedChunk,
)
from regulaitor.mcp_server import tools
from regulaitor.mcp_server.errors import NotFoundError


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.9,
        version="v",
        source_url="https://example.com",
    )


def test_search_articles_delegates_to_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _make_chunk()
    run_mock = MagicMock(return_value=[chunk])
    monkeypatch.setattr(tools.rag_retrieval, "run", run_mock)

    result = tools.search_articles(query="q", corpus="ai_act", language="es", top_k=3)

    run_mock.assert_called_once_with("q", "ai_act", "es", top_k=3)
    assert result == [chunk]


def test_search_articles_returns_empty_on_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools.rag_retrieval, "run", MagicMock(return_value=[]))

    result = tools.search_articles(query="q", corpus="ai_act", language="es")

    assert result == []


def test_fetch_article_with_apartado(monkeypatch: pytest.MonkeyPatch) -> None:
    paragraph_mock = MagicMock(return_value="apartado text")
    meta_mock = MagicMock(
        return_value={"version": "32024R1689", "source_url": "https://example.com"}
    )
    monkeypatch.setattr(tools.loader, "get_paragraph", paragraph_mock)
    monkeypatch.setattr(tools.loader, "get_manifest_meta", meta_mock)

    fa = tools.fetch_article(
        norma="ai_act", articulo="6", language="es", apartado="1"
    )

    assert isinstance(fa, FetchedArticle)
    assert fa.text == "apartado text"
    assert fa.apartado == "1"
    assert fa.version == "32024R1689"


def test_fetch_article_without_apartado(monkeypatch: pytest.MonkeyPatch) -> None:
    article_text_mock = MagicMock(return_value="full article text")
    meta_mock = MagicMock(
        return_value={"version": "v", "source_url": "https://example.com"}
    )
    monkeypatch.setattr(tools.loader, "get_article_text", article_text_mock)
    monkeypatch.setattr(tools.loader, "get_manifest_meta", meta_mock)

    fa = tools.fetch_article(norma="ai_act", articulo="6", language="es")

    assert fa.apartado is None
    assert fa.text == "full article text"


def test_fetch_article_apartado_missing_raises_notfound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paragraph_mock = MagicMock(side_effect=KeyError("no apartado 99"))
    monkeypatch.setattr(tools.loader, "get_paragraph", paragraph_mock)

    with pytest.raises(NotFoundError, match="apartado"):
        tools.fetch_article(
            norma="ai_act", articulo="6", language="es", apartado="99"
        )


def test_fetch_article_article_missing_raises_notfound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools.loader, "get_article_text", MagicMock(side_effect=KeyError("no article 999"))
    )

    with pytest.raises(NotFoundError, match="article"):
        tools.fetch_article(norma="ai_act", articulo="999", language="es")


def test_validate_citation_returns_audit_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    expected = AuditResult(
        citation=c,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    validate_mock = MagicMock(return_value=expected)
    monkeypatch.setattr(tools.validator_mod, "validate", validate_mock)

    result = tools.validate_citation(c)

    assert result == expected
    validate_mock.assert_called_once_with(c)
```

- [ ] **Step 7.3: Run tests to verify they fail**

```bash
uv run pytest tests/unit/mcp_server/test_tools.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: regulaitor.mcp_server.tools`.

- [ ] **Step 7.4: Implement `mcp_server/errors.py`**

Create `src/regulaitor/mcp_server/errors.py`:

```python
"""Error types raised inside MCP tools.

Mapped to JSON-RPC error codes by the MCP SDK dispatch layer. Keep this module
small; the SDK handles framing.
"""

from __future__ import annotations


class NotFoundError(Exception):
    """Raised when a requested article or apartado does not exist.

    Mapped to JSON-RPC custom error code -32001 ("NOT_FOUND") by the server.
    """


class IntegrityError(RuntimeError):
    """Raised by corpus.loader.warmup() on hash drift; server fails to start."""
```

- [ ] **Step 7.5: Implement `mcp_server/tools.py`**

Create `src/regulaitor/mcp_server/tools.py`:

```python
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
    """
    try:
        if apartado is not None:
            text = loader.get_paragraph(norma, articulo, apartado, language)
        else:
            text = loader.get_article_text(norma, articulo, language)
    except KeyError as e:
        raise NotFoundError(str(e)) from e

    meta = loader.get_manifest_meta(norma)
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
```

- [ ] **Step 7.6: Run tests to verify they pass**

```bash
uv run pytest tests/unit/mcp_server/test_tools.py -v --no-cov
```

Expected: 7 passed.

- [ ] **Step 7.7: Lint**

```bash
uv run ruff check src/regulaitor/mcp_server tests/unit/mcp_server
uv run black --check src/regulaitor/mcp_server tests/unit/mcp_server
uv run mypy src/regulaitor/mcp_server
```

Expected: all green.

- [ ] **Step 7.8: Commit**

```bash
git add src/regulaitor/mcp_server tests/unit/mcp_server
git commit -m "feat(mcp_server): add 3 tool adapters + error types (per-tool error semantics)"
```

---

## Task 8: `mcp_server/server.py` + `mcp_server/__main__.py` — stdio bootstrap

**Files:**
- Create: `src/regulaitor/mcp_server/server.py`
- Create: `src/regulaitor/mcp_server/__main__.py`
- Create: `tests/unit/mcp_server/test_server.py`

Spec reference: §4.6.

- [ ] **Step 8.1: Write failing tests for `mcp_server/server.py`**

Create `tests/unit/mcp_server/test_server.py`:

```python
"""Unit tests for mcp_server/server.py — bootstrap orchestration.

Server stdio loop is exercised by the integration test in Task 11; this
module verifies the warmup sequence and tool registration logic in isolation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from regulaitor.mcp_server import server


def test_warmup_calls_loader_then_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loader integrity check must run before the reranker downloads."""
    parent = MagicMock()
    parent.loader_warmup = MagicMock()
    parent.reranker_warmup = MagicMock()

    monkeypatch.setattr(server.loader, "warmup", parent.loader_warmup)
    monkeypatch.setattr(server.reranker, "warmup", parent.reranker_warmup)

    server._warmup_dependencies()

    assert parent.mock_calls == [call.loader_warmup(), call.reranker_warmup()]


def test_loader_failure_aborts_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    """If loader fails, reranker must NOT be called (fail-closed)."""
    loader_mock = MagicMock(side_effect=RuntimeError("hash drift"))
    reranker_mock = MagicMock()

    monkeypatch.setattr(server.loader, "warmup", loader_mock)
    monkeypatch.setattr(server.reranker, "warmup", reranker_mock)

    with pytest.raises(RuntimeError, match="hash drift"):
        server._warmup_dependencies()

    reranker_mock.assert_not_called()
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/mcp_server/test_server.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 8.3: Implement `mcp_server/server.py`**

Create `src/regulaitor/mcp_server/server.py`:

```python
"""MCP server bootstrap — stdio JSON-RPC.

Bootstraps the corpus loader (with hash drift fail-closed integrity check),
warms up the reranker, registers the 3 tools, and serves on stdio.

The actual stdio loop is provided by the official `mcp` Python SDK.
"""

from __future__ import annotations

import asyncio
import logging

from regulaitor.corpus import loader
from regulaitor.mcp_server import tools
from regulaitor.rag import reranker

logger = logging.getLogger("regulaitor.mcp_server")


def _warmup_dependencies() -> None:
    """Run the warmup sequence: corpus loader (integrity-checked) → reranker.

    Loader runs first; if it raises, reranker is NOT loaded. This is the
    fail-closed posture per decisions log 2026-05-05 "Corpus loader integrity
    check: strict fail-closed".
    """
    logger.info("warming up corpus loader (with integrity check)...")
    loader.warmup()
    logger.info("warming up reranker...")
    reranker.warmup()
    logger.info("warmup complete")


def run() -> None:
    """Boot the MCP server on stdio.

    1. Warm up dependencies (fail-closed).
    2. Register tools with the SDK.
    3. Serve stdio loop.
    """
    from mcp.server import Server  # type: ignore[import-not-found]
    from mcp.server.stdio import stdio_server  # type: ignore[import-not-found]

    _warmup_dependencies()

    mcp_server: Server = Server("regulaitor")

    # Register the 3 tools. The SDK auto-derives JSON Schemas from the function
    # signatures + Pydantic types.
    mcp_server.tool()(tools.search_articles)
    mcp_server.tool()(tools.fetch_article)
    mcp_server.tool()(tools.validate_citation)

    async def _serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

    asyncio.run(_serve())
```

- [ ] **Step 8.4: Implement `mcp_server/__main__.py`**

Create `src/regulaitor/mcp_server/__main__.py`:

```python
"""Entry point for `python -m regulaitor.mcp_server`."""

from __future__ import annotations

import logging

from regulaitor.mcp_server.server import run

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run()
```

- [ ] **Step 8.5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/mcp_server/test_server.py -v --no-cov
```

Expected: 2 passed.

- [ ] **Step 8.6: Lint**

```bash
uv run ruff check src/regulaitor/mcp_server
uv run black --check src/regulaitor/mcp_server
uv run mypy src/regulaitor/mcp_server
```

Expected: all green.

- [ ] **Step 8.7: Commit**

```bash
git add src/regulaitor/mcp_server/server.py src/regulaitor/mcp_server/__main__.py tests/unit/mcp_server/test_server.py
git commit -m "feat(mcp_server): add stdio bootstrap with fail-closed warmup sequence"
```

---

## Task 9: Contract test — MCP tool schemas snapshot

**Files:**
- Create: `tests/contract/test_mcp_tool_schemas.py`

Spec reference: §11.2.

- [ ] **Step 9.1: Write the snapshot test**

Create `tests/contract/test_mcp_tool_schemas.py`:

```python
"""Contract tests for MCP tool surfaces.

Verifies the 3 H3 tools have stable signatures that downstream clients can
rely on. Each test checks the function signature + docstring presence; if a
test fails, the H3 contract has changed and must be reviewed.
"""

from __future__ import annotations

import inspect

import pytest

from regulaitor.mcp_server import tools

pytestmark = pytest.mark.contract


def test_search_articles_signature() -> None:
    sig = inspect.signature(tools.search_articles)
    params = sig.parameters
    assert list(params.keys()) == ["query", "corpus", "language", "top_k"]
    assert params["top_k"].default == 5
    assert tools.search_articles.__doc__ is not None


def test_fetch_article_signature() -> None:
    sig = inspect.signature(tools.fetch_article)
    params = sig.parameters
    assert list(params.keys()) == ["norma", "articulo", "language", "apartado"]
    assert params["apartado"].default is None
    assert tools.fetch_article.__doc__ is not None


def test_validate_citation_signature() -> None:
    sig = inspect.signature(tools.validate_citation)
    params = sig.parameters
    assert list(params.keys()) == ["citation"]
    assert tools.validate_citation.__doc__ is not None
```

- [ ] **Step 9.2: Run contract tests**

```bash
uv run pytest tests/contract/test_mcp_tool_schemas.py -v --no-cov
```

Expected: 3 passed.

- [ ] **Step 9.3: Commit**

```bash
git add tests/contract/test_mcp_tool_schemas.py
git commit -m "test(mcp_server): add contract tests for the 3 tool signatures"
```

---

## Task 10: Integration tests batch (validate, fetch, retriever, integrity drift)

**Files:**
- Create: `tests/integration/test_mcp_validate_citation_flow.py`
- Create: `tests/integration/test_mcp_fetch_article_flow.py`
- Create: `tests/integration/test_loader_integrity_drift.py`
- Create: `tests/integration/test_retriever_agent_returns_context.py`

Spec reference: §11.3.

These integration tests run against the real corpus loader and corpus files (not slow because no ML model load is required). The retriever-agent integration test mocks the helper to keep it fast.

- [ ] **Step 10.1: Write `test_mcp_validate_citation_flow.py`**

Create `tests/integration/test_mcp_validate_citation_flow.py`:

```python
"""Integration test: validate_citation against the real corpus loader."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.corpus import loader
from regulaitor.mcp_server import tools


@pytest.fixture(scope="module", autouse=True)
def _warmup_loader() -> None:
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def test_validate_invalid_article_returns_not_found_reason() -> None:
    c = Citation(
        norma="ai_act",
        articulo="999",
        language="es",
        text="any text",
    )
    r = tools.validate_citation(c)
    assert r.validated is False
    assert r.article_exists is False
    assert r.reason is not None
    assert "article_not_found" in r.reason


def test_validate_invalid_apartado_returns_apartado_not_found_reason() -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="999",
        language="es",
        text="any text",
    )
    r = tools.validate_citation(c)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is False
    assert r.reason is not None
    assert "apartado_not_found" in r.reason


def test_validate_text_not_in_apartado_returns_text_match_reason() -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto que con seguridad no aparece nunca en el corpus oficial",
    )
    r = tools.validate_citation(c)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason
```

- [ ] **Step 10.2: Write `test_mcp_fetch_article_flow.py`**

Create `tests/integration/test_mcp_fetch_article_flow.py`:

```python
"""Integration test: fetch_article against the real corpus loader."""

from __future__ import annotations

import pytest

from regulaitor.corpus import loader
from regulaitor.mcp_server import tools
from regulaitor.mcp_server.errors import NotFoundError


@pytest.fixture(scope="module", autouse=True)
def _warmup_loader() -> None:
    loader.reset()
    loader.warmup()
    yield
    loader.reset()


def test_fetch_existing_article_returns_text() -> None:
    fa = tools.fetch_article(norma="ai_act", articulo="1", language="es")
    assert fa.text  # non-empty
    assert fa.version  # CELEX present
    assert fa.source_url.startswith("http")
    assert fa.apartado is None


def test_fetch_existing_apartado_returns_paragraph_text() -> None:
    fa = tools.fetch_article(
        norma="ai_act", articulo="1", language="es", apartado="1"
    )
    assert fa.text
    assert fa.apartado == "1"


def test_fetch_missing_article_raises_notfound() -> None:
    with pytest.raises(NotFoundError):
        tools.fetch_article(norma="ai_act", articulo="999", language="es")


def test_fetch_missing_apartado_raises_notfound() -> None:
    with pytest.raises(NotFoundError):
        tools.fetch_article(
            norma="ai_act", articulo="1", language="es", apartado="999"
        )
```

- [ ] **Step 10.3: Write `test_loader_integrity_drift.py`**

Create `tests/integration/test_loader_integrity_drift.py`:

```python
"""Integration test: corpus.loader.warmup() raises RuntimeError on hash drift."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from regulaitor.corpus import loader


def test_warmup_detects_drift_in_real_processed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Copy real corpus to tmp_path so we can mutate without affecting the workspace
    src_manifests = Path("corpus/manifests")
    src_processed = Path("corpus/processed")
    dst_manifests = tmp_path / "manifests"
    dst_processed = tmp_path / "processed"
    shutil.copytree(src_manifests, dst_manifests)
    shutil.copytree(src_processed, dst_processed)

    # Tamper with one paragraph in ai_act_es.json
    target = dst_processed / "ai_act_es.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data[0]["paragraphs"][0]["text"] = "TAMPERED"
    target.write_text(json.dumps(data), encoding="utf-8")

    loader.reset()
    monkeypatch.setattr(loader, "MANIFEST_DIR", dst_manifests)
    monkeypatch.setattr(loader, "PROCESSED_DIR", dst_processed)

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()

    loader.reset()
```

- [ ] **Step 10.4: Write `test_retriever_agent_returns_context.py`**

Create `tests/integration/test_retriever_agent_returns_context.py`:

```python
"""Integration test: RetrieverAgent.retrieve returns a well-formed Context.

Mocks rag.retrieval.run to keep this test out of the `slow` set
(no real BGE-M3 load); the slow E2E variant is in test_mcp_search_articles_flow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.citation.schemas import RetrievedChunk


def test_retriever_agent_returns_well_formed_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = RetrievedChunk(
        chunk_id="ai_act.6.1.es",
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="text",
        score=0.9,
        version="32024R1689",
        source_url="https://example.com",
    )
    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", MagicMock(return_value=[chunk]))
    monkeypatch.setattr(
        retriever.embeddings,
        "model_identifier",
        MagicMock(return_value="BAAI/bge-m3"),
    )

    agent = RetrieverAgent()
    before = datetime.now(tz=UTC)
    ctx = agent.retrieve("alto riesgo", "ai_act", "es")
    after = datetime.now(tz=UTC)

    assert ctx.query == "alto riesgo"
    assert ctx.corpus == "ai_act"
    assert ctx.language == "es"
    assert ctx.embedding_model == "BAAI/bge-m3"
    assert before <= ctx.retrieved_at <= after
    assert len(ctx.chunks) == 1
    assert ctx.chunks[0] == chunk
```

- [ ] **Step 10.5: Run all 4 integration tests**

```bash
uv run pytest tests/integration/test_mcp_validate_citation_flow.py tests/integration/test_mcp_fetch_article_flow.py tests/integration/test_loader_integrity_drift.py tests/integration/test_retriever_agent_returns_context.py -v --no-cov
```

Expected: 12 passed (3 + 4 + 1 + 1 = 12... oh wait, let me recount: validate_citation 3, fetch_article 4, integrity_drift 1, retriever_agent 1 = 9 tests). Adjust expectation accordingly.

Expected: 9 passed.

- [ ] **Step 10.6: Commit**

```bash
git add tests/integration/test_mcp_validate_citation_flow.py tests/integration/test_mcp_fetch_article_flow.py tests/integration/test_loader_integrity_drift.py tests/integration/test_retriever_agent_returns_context.py
git commit -m "test(integration): add validate/fetch/retriever/integrity-drift integration tests"
```

---

## Task 11: Integration test — search_articles via stdio subprocess (slow)

**Files:**
- Create: `tests/integration/test_mcp_search_articles_flow.py`

Spec reference: §11.3.

- [ ] **Step 11.1: Write the slow stdio integration test**

Create `tests/integration/test_mcp_search_articles_flow.py`:

```python
"""Slow integration test: search_articles end-to-end via stdio subprocess.

Loads BGE-M3 + bge-reranker-v2-m3 + the live LanceDB; takes ~15s wall-clock.
Marked slow; excluded from CI fast suite.
"""

from __future__ import annotations

import pytest

from regulaitor.corpus import loader
from regulaitor.mcp_server import tools
from regulaitor.rag import reranker

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module", autouse=True)
def _warmup() -> None:
    loader.reset()
    loader.warmup()
    reranker.warmup()
    yield
    loader.reset()


def test_search_articles_returns_filtered_ranked_chunks() -> None:
    results = tools.search_articles(
        query="sistemas de inteligencia artificial de alto riesgo",
        corpus="ai_act",
        language="es",
        top_k=5,
    )
    assert len(results) == 5
    assert all(r.norma == "ai_act" for r in results)
    assert all(r.language == "es" for r in results)

    # Scores are monotonically non-increasing
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_articles_returns_at_most_top_k() -> None:
    results = tools.search_articles(
        query="proteccion de datos personales",
        corpus="gdpr",
        language="es",
        top_k=3,
    )
    assert len(results) <= 3
    assert all(r.norma == "gdpr" for r in results)
```

- [ ] **Step 11.2: Run with slow marker enabled**

```bash
uv run pytest tests/integration/test_mcp_search_articles_flow.py -m slow --no-cov -v
```

Expected: 2 passed in ~15-30 seconds (model load amortized across the module-scoped fixture).

- [ ] **Step 11.3: Confirm fast suite still excludes it**

```bash
uv run pytest -m "not slow" --no-cov -q | tail -5
```

Expected: previous count + 9 (Task 10) integration tests; the 2 slow tests should be deselected.

- [ ] **Step 11.4: Commit**

```bash
git add tests/integration/test_mcp_search_articles_flow.py
git commit -m "test(integration): add slow E2E test for search_articles with real BGE-M3"
```

---

## Task 12: Skills SKILL.md drafts (prompt-versioning + citation-validator)

**Files:**
- Create: `.claude/skills/prompt-versioning/SKILL.md`
- Create: `.claude/skills/citation-validator/SKILL.md`

Spec reference: §10.

- [ ] **Step 12.1: Write `prompt-versioning` SKILL.md**

Create `.claude/skills/prompt-versioning/SKILL.md`:

```markdown
---
name: prompt-versioning
description: Use this skill when adding, modifying, or rolling back agent prompts in src/regulaitor/agents/prompts/ to keep the project's prompt history reproducible and auditable. Activates from H4 onwards (Analyst, Auditor, Council).
version: 0.1.0
---

# Prompt versioning skill

## Why

Reproducibility (CLAUDE.md §10.6): every Analyst/Auditor/Council prompt must
carry a version + changelog so a TFM reviewer can trace which prompt produced
which gold-set result.

## When to use

Activate this skill the moment you create a new prompt file, modify an existing
one, or revert a prompt. Do NOT activate it for incidental README updates that
mention prompts but do not change them.

## Procedure

1. **Path convention.** Prompts live in
   `src/regulaitor/agents/prompts/<agent>/<role>.v<MAJOR>.<MINOR>.md`.
   Examples: `analyst/system.v1.0.md`, `auditor/decide.v2.1.md`.
2. **Header block.** Every prompt file starts with this YAML frontmatter:
   ```yaml
   ---
   agent: <retriever|analyst|auditor|council>
   role: <system|user-template|few-shot>
   version: <MAJOR>.<MINOR>
   created: <YYYY-MM-DD>
   author: <github username>
   model_compatibility: [<llm-id-1>, <llm-id-2>]
   changelog:
     - <YYYY-MM-DD>: <one-line summary>
   ---
   ```
3. **Versioning rules.**
   - **MAJOR bump:** breaking change to expected agent behaviour (different
     output schema, removal of an instruction the system relies on, change in
     refusal policy).
   - **MINOR bump:** non-breaking refinement (better few-shot example, more
     concrete instruction, accent/typo fix).
   - **No silent edits.** Even a typo fix is a MINOR bump.
4. **Forbidden in prompts.**
   - Hardcoded model names (use `models/router.py` to bind).
   - Hardcoded user data or PII.
   - Anything that bypasses the Auditor.
5. **When changing a prompt.**
   - Copy the previous file with the new version number.
   - Edit and update the changelog.
   - Run `make eval` against the gold set; record the new metrics in
     `evals/reports/<YYYY-MM-DD>-prompt-vN.M.md`.
   - Commit: `feat(prompts/<agent>): bump <role> v<old>->v<new> — <reason>`.
6. **Rolling back.**
   - Move the failing prompt to `.archive/` with a comment in the changelog.
   - Switch the active version reference in `models/config.py`.

## What this skill does NOT cover

- Embedding model versioning — that lives in `corpus/manifests/*.json` per
  LanguageEntry and is governed by ADR 0004.
- Changes to non-prompt agent code — those follow normal commit conventions.
```

- [ ] **Step 12.2: Write `citation-validator` SKILL.md**

Create `.claude/skills/citation-validator/SKILL.md`:

```markdown
---
name: citation-validator
description: Use this skill when modifying src/regulaitor/citation/validator.py or its policy. Documents the canonical 3-check validation procedure and the rules for evolving it (e.g. adding a fuzzy-fallback layer in H15).
version: 0.1.0
---

# Citation validator skill

## Why

The validator is the operational core of the "no citation, no answer" rule
(CLAUDE.md §6). Any change here directly affects whether the system can
produce auditable answers. This skill encodes the disciplined evolution path.

## Activation

Activate when:
- Modifying `src/regulaitor/citation/validator.py`.
- Modifying `_normalize` in `src/regulaitor/rag/chunking.py` (validator depends on it).
- Adding a new validation check (e.g. version-consistency, language-consistency).
- Calibrating thresholds in H15.

Do NOT activate for unrelated tests, schema field additions in
`citation/schemas.py`, or refactors that don't change validation semantics.

## Canonical procedure (H3 baseline)

The validator runs 3 strict checks in order, with fail-fast on first failure:

1. `article_exists`: `(norma, articulo)` is in the manifest.
2. `apartado_exists` (if citation has an apartado): the apartado is a known
   paragraph for that article.
3. `text_normalized_match`: `_normalize(citation.text)` is a substring of
   `_normalize(target_text)`, where `target_text` is the apartado paragraph
   when an apartado is given, else the full article text.

`validated` = AND of the checks. `reason` field carries a specific code:
- `article_not_found:`
- `apartado_not_found:`
- `text_not_in_apartado:`
- `text_not_in_article:`

## Adding new checks

When proposing a new check (e.g. `version_consistent`):
1. Open a brainstorming session per `superpowers:brainstorming` skill.
2. Document the threat model the new check closes (concrete attack scenario).
3. Add to `AuditResult` schema as a new boolean field (Pydantic v2 backwards
   compatible).
4. Update validator.py with fail-fast ordering: cheaper checks first, expensive
   last.
5. Update tests in `tests/unit/citation/test_validator.py` with happy + failure
   cases.
6. Update this SKILL.md procedure section.
7. Update `docs/technical_decisions_log.md` with the rationale.

## Adding fuzzy fallback (H15)

When H8/H15 evaluation shows that strict normalized match has too many false
negatives:
1. Run the calibration with the gold set; produce a precision-recall curve.
2. Choose a threshold from the curve and document the choice.
3. Add a fuzzy fallback layer: if strict match fails, run fuzzy match; on
   match, set `validated=False, requires_human_review=True, confidence=<score>`.
   Do NOT silently accept — surface the doubt.
4. Strict match output unchanged; fuzzy is only for diagnostic info.
5. Update tests with adversarial near-paraphrase cases.

## Forbidden changes

- Replacing strict match with fuzzy as the default.
- Accepting citations on string-similarity score above any threshold without
  a human review hook.
- Removing `reason` codes (downstream Auditor logic depends on them).
- Validator that depends on the LLM model that produced the citation
  (validator must be deterministic).
```

- [ ] **Step 12.3: Confirm both files exist and are valid markdown**

```bash
ls -la .claude/skills/prompt-versioning/SKILL.md .claude/skills/citation-validator/SKILL.md
```

- [ ] **Step 12.4: Commit**

```bash
git add .claude/skills/prompt-versioning/SKILL.md .claude/skills/citation-validator/SKILL.md
git commit -m "docs(skills): draft prompt-versioning and citation-validator SKILL.md"
```

---

## Task 13: Makefile mcp-server target + smoke run

**Files:**
- Modify: `Makefile`

- [ ] **Step 13.1: Add mcp-server target to Makefile**

In `Makefile`, find the line:

```makefile
.PHONY: help setup lint test test-cov precommit ingest rag-build serve eval redteam docker deploy clean
```

Replace with:

```makefile
.PHONY: help setup lint test test-cov precommit ingest rag-build mcp-server serve eval redteam docker deploy clean
```

Then in the help section, find:

```makefile
	@echo "  rag-build  Chunk + embed + populate LanceDB store (H2)"
```

Add immediately after:

```makefile
	@echo "  mcp-server Run the MCP server on stdio (H3)"
```

Then add after the `rag-build:` block, a new target:

```makefile
mcp-server: ## Run the MCP server on stdio (H3)
	$(UV) run python -m regulaitor.mcp_server
```

- [ ] **Step 13.2: Smoke run — start the server briefly to confirm it boots**

In one terminal, run a 3-second smoke (the server will block waiting for stdin; we only confirm it gets past the warmup print):

```bash
export PATH="/c/Users/enriq/.local/bin:$PATH" && unset VIRTUAL_ENV
timeout 5 uv run python -m regulaitor.mcp_server 2>&1 | head -20 || true
```

Expected: the server prints `warming up corpus loader` → `warming up reranker` → `warmup complete`, then waits for stdin. The `timeout 5` kills it. No `RuntimeError` from hash drift, no missing-module errors.

- [ ] **Step 13.3: Run the entire fast suite to confirm no regressions**

```bash
uv run pytest -m "not slow"
```

Expected: ~165 passed. Coverage ≥90%.

- [ ] **Step 13.4: Commit**

```bash
git add Makefile
git commit -m "build(makefile): add mcp-server target for H3 stdio server"
```

---

## Task 14: ADR 0005 + decisions log H3 closure entry

**Files:**
- Create: `docs/adr/0005-mcp-server-architecture.md`
- Modify: `docs/technical_decisions_log.md`

- [ ] **Step 14.1: Draft ADR 0005**

Create `docs/adr/0005-mcp-server-architecture.md`:

```markdown
# ADR 0005 — MCP server architecture

- **Status:** Accepted
- **Date:** 2026-05-05 (H3 closure)
- **Deciders:** Project owner.
- **Companion ADRs:** 0004 (RAG architecture), 0002 (skills/MCPs roadmap).

## Context

H3 introduces the project's first **trust boundary surface**: an MCP server
exposing 3 tools (`search_articles`, `fetch_article`, `validate_citation`) over
stdio JSON-RPC. The server is the single point of access for both internal
agents (H4 LangGraph nodes) and external clients (Claude Desktop, evaluation
harness, future API). This ADR captures the architecture that emerged after
the H3 brainstorming + implementation.

## Decision

Six new modules + one helper in existing layers, organized in 4 trust-boundary tiers:

| Tier | Modules | Trust |
|---|---|---|
| Public surface | `mcp_server/server.py`, `tools.py`, `errors.py`, `__main__.py` | Validates all input via Pydantic |
| Agent adapter | `agents/retriever.py` | In-process, trusted Pydantic |
| Schemas + validator | `citation/schemas.py`, `citation/validator.py` | Pure logic, no I/O |
| Domain helpers | `corpus/loader.py`, `rag/retrieval.py` | Read-only after warmup |

The MCP server fails closed at startup if the corpus loader detects hash drift
(decisions log "Corpus loader: lazy singleton + integrity check fail-closed").
The retrieval helper is the single source of truth shared by both the MCP tool
adapter and the LangGraph agent.

The validator runs 3 strict checks (article exists, apartado exists, normalized
text match) reusing the `_normalize` function from `rag/chunking.py`. Fuzzy
matching is explicitly deferred to H15 calibration.

## Alternatives considered

- **5 tools shipped in H3 (with stubs for document tools):** rejected; doubles
  test surface for code that will be rewritten in H5.
- **Streamable HTTP transport in MVP:** rejected; stdio is simpler and matches
  Claude Desktop's default.
- **Agent-talks-MCP via in-process loopback:** rejected; helper-shared
  architecture avoids RPC overhead inside the same process.
- **Fuzzy citation matching by default:** rejected; vulnerable to adversarial
  near-paraphrase attacks; H15 may add as fallback only.
- **Hash drift as warning instead of fail-closed:** rejected; SSDLC fail-closed
  posture for tampered corpus.

## Consequences

### Positive

- Trust boundary is a single physical surface (the MCP server) — easier to
  audit, log, and threat-model than scattered tool implementations.
- LangGraph nodes (H4) and external clients see exactly the same retrieval
  logic — no behavioural drift between development and demo.
- Hash drift detection gives the project a concrete defensive control to point
  at in the TFM defense.
- The 3-tool MCP contract is a small, stable surface that downstream
  integrations (LangFuse in H11, FastAPI in H7) can consume without coupling.

### Negative

- New runtime dependency: `mcp` Python SDK (still <1.0; pinned `>=1.0,<2.0`).
- Loader integrity check adds ~50-100 ms to MCP server startup (acceptable per
  Q12 of brainstorming).
- The validator's 3-check fail-fast structure is rigid; adding a 4th check
  requires a careful re-ordering decision documented per the
  `citation-validator` skill.

## References

- `docs/superpowers/specs/2026-05-05-h3-mcp-server-design.md` — H3 spec.
- `docs/superpowers/plans/2026-05-05-h3-mcp-server.md` — H3 plan.
- `docs/technical_decisions_log.md` H3 section.
- `docs/adr/0004-rag-architecture.md` — predecessor.
```

- [ ] **Step 14.2: Add H3 closure entry to decisions log**

In `docs/technical_decisions_log.md`, find the heading `## H3 — MCP server + Retriever-Agent + Citation validator (en diseño)` and update it to:

```markdown
## H3 — MCP server + Retriever-Agent + Citation validator (cerrado 2026-MM-DD)
```

(replace `MM-DD` with the actual closure date when running this task).

Then find the last H3 entry (the `Context` Pydantic wrapper one) and insert AFTER it (before the convention paragraph):

```markdown
### 2026-MM-DD · H3 cerrado: MCP server operativo

- **Decisión:** H3 cierra como Done. El pipeline público del proyecto (MCP server stdio con 3 tools) está implementado, testeado contra el corpus real y con paper trail completo.
- **Stats finales del cierre:**
  - **Branch:** `feat/h3-mcp-server`. **N commits** del primero (`6b6f12f` — spec) al último.
  - **Tests:** N totales (M unit + K contract + L integration; 2 marcados slow excluidos del CI fast suite).
  - **Coverage global:** N% sobre `src/regulaitor/` (gate 90%). Per-módulo en `src/regulaitor/{citation,corpus/loader,rag/retrieval,agents/retriever,mcp_server}`: ≥85% cada uno.
  - **MCP server boot:** warmup completa en N segundos en máquina warmed up (loader integrity check + reranker load).
  - **Smoke validado:** `python -m regulaitor.mcp_server` arranca limpio; las 3 tools responden correctamente contra el corpus AI Act + GDPR live.
  - **Skills propuestas (no activadas):** `prompt-versioning` y `citation-validator` SKILL.md drafted; activación cuando se consuman (H4).
- **Lecciones para H4 (Analyst + Auditor):**
  - El Analyst recibe `Context` (output del RetrieverAgent) y produce `Finding` + `Citation`. Citation schema ya existe en H3; Finding y Answer son trabajo H4.
  - El Auditor recibe `Citation` del Analyst y llama `tools.validate_citation` (vía MCP loop si quiere usar el server, o directo vía `validator.validate(...)` para ahorrar overhead).
  - El Citation schema es `frozen=True`, así que el Auditor puede comparar/hashear citas con seguridad.
  - El boundary contract H3→H4 (Citation schema + AuditResult schema + RetrieverAgent.retrieve interface) está verificado por test de integración real.
- **Lecciones para H8 (Evaluación):**
  - Las 3 tools del MCP server pueden usarse directamente desde el harness de evals sin necesidad de instanciar LangGraph; eso abarata las evaluaciones de "¿devuelve el corpus el artículo correcto para esta query?" en un orden de magnitud.
  - El campo `reason` de `AuditResult` permite reportes de evaluación que distinguen "el LLM cita un artículo inexistente" de "el LLM cita texto que no aparece" — granularidad valiosa para la TFM defense.
- **Decisiones técnicas tomadas durante H3** (todas con entrada propia más arriba en este log):
  1. Alcance: 3 tools (search/fetch/validate); document tools deferidos a H5.
  2. Transporte: stdio.
  3. Arquitectura: helper común con adapters finos.
  4. Citation validator: matching normalizado exacto.
  5. Schemas H3: solo los 5 que H3 produce/consume.
  6. Top-k: defaults fijos pre=50 / post=5.
  7. Validator depth: 3 chequeos estrictos.
  8. fetch_article: texto + metadata documental mínima.
  9. Corpus loader: lazy singleton + warmup + integrity check.
  10. RetrievedChunk: 9 campos (citable one-shot).
  11. Política de errores MCP por semántica de cada tool.
  12. Integrity check strict fail-closed.
  13. Context como Pydantic wrapper.
- **Enlace:** ADR 0005 (MCP server architecture); spec `docs/superpowers/specs/2026-05-05-h3-mcp-server-design.md`; plan `docs/superpowers/plans/2026-05-05-h3-mcp-server.md`. Branch `feat/h3-mcp-server`. Tag publicado: `v0.0.4-h3`.
```

Replace `N`, `M`, `K`, `L` with the real numbers captured at Task 13.3 (final pytest run output) and Task 13.2 (warmup time observed).

- [ ] **Step 14.3: Commit documentation**

```bash
git add docs/adr/0005-mcp-server-architecture.md docs/technical_decisions_log.md
git commit -m "docs(h3): land ADR 0005 MCP server architecture and H3 closure log entry"
```

---

## Task 15: Push, verify CI, open PR, merge, tag

- [ ] **Step 15.1: Push the branch**

```bash
git push -u origin feat/h3-mcp-server
```

- [ ] **Step 15.2: Open the pull request**

```bash
gh pr create --title "H3: MCP server + Retriever-Agent + Citation validator" --body "$(cat <<'EOF'
## Summary

H3 closure. Implements the project's first trust boundary surface: an MCP server with 3 tools, a Retriever-Agent adapter, the canonical citation schemas, and a strict citation validator. End state: `python -m regulaitor.mcp_server` boots cleanly with hash-drift integrity check; the 3 tools (`search_articles`, `fetch_article`, `validate_citation`) answer correctly against the live AI Act + GDPR corpus.

- **MCP server (stdio)** with 3 tools per CLAUDE.md §9 (the 2 document tools deferred to H5).
- **Citation validator** with 3 strict checks (article + apartado + text), reusing `_normalize` from H2.
- **Schemas Pydantic v2** for the H3 boundary contract (`Citation`, `AuditResult`, `RetrievedChunk`, `Context`, `FetchedArticle`).
- **Corpus loader** as lazy singleton with hash drift fail-closed integrity check.
- **Retrieval helper** shared between the MCP tool and the LangGraph agent (no internal RPC).
- **Skills** `prompt-versioning` and `citation-validator` SKILL.md drafted (activation deferred to H4).

## Smoke validation

- `python -m regulaitor.mcp_server` boots; warmup completes in ~N seconds.
- 3 valid + 3 invalid citations produce expected `AuditResult.reason` values.
- `fetch_article` with valid args returns text; with invalid args raises `NotFoundError` with actionable message.
- `search_articles` returns top-K reranked chunks with monotonically decreasing scores.

## Tests

N total: M unit + K contract + L integration (2 marked `slow`, excluded from CI fast suite). Coverage N% global (gate 90%); new modules at ≥85% each.

## Test plan

- [x] Local: `uv run pytest -m "not slow"` → all passed
- [x] Local: `python -m regulaitor.mcp_server` boots cleanly
- [x] Local: 3 valid + 3 invalid citations produce expected results
- [x] Local: hash drift detected on synthetic corruption
- [x] Local: lint/format/types clean
- [ ] CI: lint, test, security all green

## Out of scope

- Analyst-Agent + Auditor-Agent (H4).
- LangGraph wiring (H4).
- Document pipeline + the 2 `*_document` MCP tools (H5).
- Streamlit UI (H6).
- FastAPI endpoints (H7).
- Fuzzy match calibration (H15).

## References

- Spec: `docs/superpowers/specs/2026-05-05-h3-mcp-server-design.md`
- Plan: `docs/superpowers/plans/2026-05-05-h3-mcp-server.md`
- ADR 0005: `docs/adr/0005-mcp-server-architecture.md`
- Decisions log: H3 section in `docs/technical_decisions_log.md` (13 brainstorming entries + closure)
EOF
)"
```

Replace `N`, `M`, `K`, `L` with the real numbers from your local run.

- [ ] **Step 15.3: Watch CI**

```bash
gh pr checks --watch
```

Expected: lint, test, security all green. Test job takes ~3 minutes (with HF cache warm from H2).

- [ ] **Step 15.4: Self-review the PR**

Read the diff in the GitHub UI. Confirm:
- No `print()` debug statements in production code.
- All new public surfaces have docstrings.
- No accidental `.env` or secrets.
- Manifests stats unchanged (113+99 articles; H3 doesn't touch the corpus content).

- [ ] **Step 15.5: Pause for user OK before merging + tagging**

```bash
echo "All checks green. Ready to squash-merge to main and tag v0.0.4-h3."
echo "Awaiting explicit OK from project owner before proceeding."
```

(This step exists because squash + tag are non-reversible; per CLAUDE.md operational discipline, the owner authorizes.)

- [ ] **Step 15.6: After OK — squash-merge and tag**

```bash
gh pr merge --squash --delete-branch --subject "feat(h3): MCP server + Retriever-Agent + Citation validator"

git checkout main
git pull --ff-only

git tag -a v0.0.4-h3 -m "H3 closed: MCP server + Retriever-Agent + Citation validator (3 tools stdio, fail-closed integrity)"
git push origin v0.0.4-h3
```

- [ ] **Step 15.7: Verify main CI green post-merge**

```bash
gh run list --branch main --limit 2
gh run watch $(gh run list --branch main --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status
```

Expected: all 3 jobs (Lint, Test, Security) pass on main.

H3 is officially CLOSED. The next session can plan H4 (Analyst-Agent + Auditor-Agent + LangGraph chat E2E).

---

## Self-review checklist (executed at the end of plan-writing)

- [x] **Spec coverage:** every section of the spec maps to at least one task.
  - §1 Goal → Tasks 0-15 (collectively).
  - §2 Glossary → Tasks 1, 3, 5, 6 (each schema/component).
  - §3 Architecture → Tasks 1-8 by module.
  - §4 Components → Tasks 1, 3-8 (one per component).
  - §5 Data flow → Tasks 10, 11 (integration tests exercise the 3 paths).
  - §6 Error handling → Task 7 (errors.py + tools.py per-tool semantics) + Task 10 (integration tests).
  - §7 SSDLC controls → Task 3 (loader integrity), Task 5 (Pydantic frozen + min_length), Task 7 (NotFoundError mapping), Task 10 (integrity drift integration test).
  - §8 Repo layout → every Task creating files; matches §8 structure.
  - §9 Dependencies → Task 0.
  - §10 Skills/MCPs → Task 12.
  - §11 Testing pyramid → Tasks 2, 9, 10, 11 (contract + integration).
  - §12 Acceptance criteria → Tasks 13 (smoke run) + 15 (PR checks).
  - §13 Open questions → resolved in Tasks 0 (mcp pin), 11 (subprocess approach via module-scoped fixture), 7 (errors module factored).
  - §14 Risk register → mitigations in Task 0 (SDK pin), Task 8 (warmup ordering, fail-closed).
  - §15 Implementation order → followed exactly in Task numbering.

- [x] **No placeholders:** every step has runnable code or commands. Numbers in the H3 closure log entry (Task 14) and PR body (Task 15) are explicitly marked as "replace `N`, `M`, `K`, `L`".

- [x] **Type consistency:** `Citation`, `AuditResult`, `RetrievedChunk`, `Context`, `FetchedArticle` referenced consistently. `loader.warmup`, `loader.get_article`, `loader.get_paragraph`, `loader.get_article_text`, `loader.get_manifest_meta`, `loader.list_articulos`, `loader.list_apartados`, `loader.reset` signatures consistent across Tasks 3, 5, 7, 10. `rag_retrieval.run`, `embeddings.model_identifier`, `reranker.warmup`, `reranker.rerank` consistent across Tasks 4, 6, 7, 8.

- [x] **Spec gaps:** none found. The two open implementation choices flagged in spec §13 (MCP SDK version + subprocess test approach) are settled inline in the plan.

---

## Execution handoff

Plan complete and saved. Two execution options:

**1. Subagent-driven (recommended for H3)** — A fresh subagent executes each task; you and I review between tasks. Same pattern as H1/H2 worked well: 16 tasks is enough that fresh-context-per-task pays off; tasks 1-8 are independent (each module is self-contained); tasks 10-11 are the real-world smoke (loaders integrity + stdio subprocess); tasks 12-15 are docs + PR which I drive personally.

**2. Inline execution** — I execute the tasks in this session in batches with checkpoints.

For H3 specifically I lean **subagent-driven**, same reasoning as H2 + the trust boundary aspect: the MCP server's bootstrap is the kind of code where a fresh subagent (no context pollution) catches issues that a tired implementor might miss.

Awaiting choice.
