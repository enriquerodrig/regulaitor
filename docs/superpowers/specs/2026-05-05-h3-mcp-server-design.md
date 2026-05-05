# H3 — MCP Server + Retriever-Agent + Citation Validator — Design Spec

**Status:** Approved (2026-05-05). **Milestone:** H3.
**Predecessors:** H2 RAG base (`docs/superpowers/specs/2026-05-04-h2-rag-base-design.md`), ADR 0004.
**Branch:** `feat/h3-mcp-server`.
**Tag at closure:** `v0.0.4-h3`.

---

## 1. Goal

Operationalize the "no citation, no answer" rule by introducing the project's first **trust boundary surface**: an MCP server that exposes the corpus and citation primitives via a stable JSON-RPC contract, plus the modules required to make those primitives reliable (Retriever-Agent, schemas, citation validator).

End state:
- `python -m regulaitor.mcp_server` boots, warms up the corpus loader (with hash drift detection) and the reranker, and listens on stdio.
- 3 MCP tools (`search_articles`, `fetch_article`, `validate_citation`) respond with typed Pydantic outputs against the live AI Act + GDPR corpus.
- `RetrieverAgent` class is instantiable and produces a `Context` Pydantic object that H4's LangGraph can consume.
- Citation validator enforces 3 strict checks (article exists, apartado exists, normalized text match) per CLAUDE.md §6.

H3 does NOT introduce: Analyst-Agent, Auditor-Agent, LangGraph wiring, document pipeline (extractor / sanitizer / segmenter), `Finding` / `Answer` schemas, FastAPI endpoints, Streamlit UI, prompt versioning. Those land in H4–H7.

## 2. Glossary

| Term | Meaning in H3 |
|---|---|
| **Citation** | A claim by an LLM that a piece of text exists in a specific corpus location (norma + articulo + apartado + language + text). H3 introduces the Pydantic schema; H4 will produce them. |
| **AuditResult** | Output of the citation validator. Boolean `validated` plus three diagnostic booleans plus a human-readable `reason`. |
| **RetrievedChunk** | One result of `search_articles`. 9 fields including the citable identity (norma + articulo + apartado + language + text), the rerank score, and the corpus version + source URL. |
| **Context** | Wrapper produced by `RetrieverAgent` for H4 LangGraph state: query echo + chunks + retrieval metadata (timestamp, embedding model). |
| **FetchedArticle** | Output of `fetch_article` MCP tool: text + minimal documentary metadata (norma, articulo, apartado, language, version, source_url). |
| **Corpus loader** | Lazy in-memory singleton over `corpus/processed/` and `corpus/manifests/`; populated on `warmup()` with hash drift integrity check. |
| **Trust boundary** | The MCP server is the single public surface; everything inside the process trusts Pydantic-typed inputs. External I/O happens at the MCP boundary only. |

## 3. Architecture

### 3.1 Module map

Four layers, each with a single responsibility:

| Layer | Module(s) (new in H3) | Responsibility |
|---|---|---|
| Public surface (stdio MCP) | `mcp_server/server.py`, `mcp_server/tools.py`, `mcp_server/errors.py`, `mcp_server/__main__.py` | Boot, dispatch, JSON-RPC framing via official `mcp` SDK, error mapping. |
| Agent adapter (in-process) | `agents/retriever.py` | Thin LangGraph-friendly wrapper around the retrieval helper; produces `Context`. |
| Schemas + validator | `citation/schemas.py`, `citation/validator.py` | Pydantic v2 contracts; canonical citation validator. |
| Domain helpers (in-process) | `corpus/loader.py`, `rag/retrieval.py` | Singleton corpus access; canonical retrieval pipeline. |

Existing layers consumed without modification: `rag/embeddings.py`, `rag/store.py`, `rag/reranker.py`, `rag/chunking._normalize`, `corpus/manifest.py`, `corpus/schemas.py`, `corpus/processed/*.json`, `corpus/manifests/*.json`.

### 3.2 Trust boundary diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  External clients (Claude Desktop, evals harness, future API)       │
└────────────────────────────────┬────────────────────────────────────┘
                                 │  stdio (JSON-RPC frames)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  TRUST BOUNDARY: mcp_server/                                         │
│    server.py     stdio bootstrap + dispatch via `mcp` SDK            │
│    tools.py      3 adapters (search / fetch / validate)              │
│    errors.py     NotFoundError, IntegrityError                       │
│    __main__.py   `python -m regulaitor.mcp_server` entry             │
└────────┬────────────────────┬─────────────────────┬─────────────────┘
         │ Pydantic-validated │                     │
         ▼                    ▼                     ▼
┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐
│ rag/retrieval.py│  │ corpus/loader.py │  │ citation/validator.py  │
│ run(query,      │  │ get_article(),   │  │ validate(citation,     │
│  corpus,        │  │ get_paragraph(), │  │  loader=...)           │
│  lang,          │  │ get_manifest_meta│  │  → AuditResult         │
│  top_k=5)       │  │ + warmup()       │  │ (3 strict checks)      │
│ → list[chunk]   │  │   integrity-fail │  │                        │
│                 │  │   -closed        │  │                        │
└────────┬────────┘  └──────────────────┘  └──────────┬─────────────┘
         │                    ▲                       │
         │                    │ uses                  │
         │                    └───────────────────────┘
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  H2 layer: rag/embeddings.py, rag/store.py, rag/reranker.py          │
│  H1 layer: corpus/manifest.py, corpus/processed/*.json               │
└─────────────────────────────────────────────────────────────────────┘

# Separately, in the same Python process (used by H4 LangGraph):
┌─────────────────────────────────────────────────────────────────────┐
│  agents/retriever.py                                                 │
│    class RetrieverAgent:                                             │
│      retrieve(query, corpus, lang) → Context                         │
│      ↓ delegates to the SAME rag/retrieval.run() helper              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 Decision summary (rationale lives in `docs/technical_decisions_log.md` H3 section)

| # | Decision | Rationale (one line) |
|---|---|---|
| 1 | Scope: 3 tools (search, fetch, validate); document tools deferred to H5 | YAGNI; H5 brings extractor/sanitizer/segmenter |
| 2 | Transport: stdio | Simplicity, Claude Desktop compatibility, zero network surface |
| 3 | Architecture: shared helper, thin adapters | One source of truth; no internal RPC; same logic for agent + MCP clients |
| 4 | Validator matching: normalized exact (substring of `_normalize`'d corpus) | Reuses H2 `_normalize`; defensible; closes adversarial fuzzy-match vector |
| 5 | Schemas in H3: `Citation`, `AuditResult`, `RetrievedChunk`, `Context`, `FetchedArticle`. Defer `Finding`, `Answer` to H4 | Define what H3 produces/consumes; avoid premature commitment |
| 6 | Top-k: pre=50 fixed, post=5 default exposed via single `top_k` MCP param | YAGNI calibratorio; A→B is non-breaking |
| 7 | Validator depth: 3 strict checks (article + apartado + text) | Closes "right article wrong apartado" vector; uses H1 paragraph data |
| 8 | `fetch_article` returns text + minimal metadata (no chunks/hash/embedded_at) | Trust boundary minimization; no internal metadata leak |
| 9 | Corpus loader: lazy singleton + warmup + hash drift fail-closed | Defense-in-depth; SSDLC integrity gate at process boot |
| 10 | `RetrievedChunk` shape: 9 fields including version + source_url | Citable in one call; no second RPC round-trip per chunk |
| 11 | Error policy: per-tool semantics (search→`[]`, fetch→`NotFound`, validate→`AuditResult` always) | Each tool's error model fits its domain; clean contract tests |
| 12 | Integrity check: strict fail-closed `RuntimeError` on hash drift | Fail-closed by default; recovery path explicit (`make ingest`) |
| 13 | `Context`: Pydantic wrapper with query + chunks + retrieved_at + embedding_model | Traceability for H8 evals + H11 observability; serializable |

## 4. Components

### 4.1 `corpus/loader.py` (new)

**Responsibility:** in-memory access to manifests + processed JSON. Lazy singleton, warmed up at MCP server boot.

**Public surface:**
```python
def warmup() -> None
    """Load all manifests + processed/ into the singleton.
    Recompute SHA256 hashes of LanguageEntry text and compare against
    manifest. Raise RuntimeError on any mismatch. Idempotent."""

def get_manifest(norma: Norma) -> Manifest
    """Return the parsed manifest. Raises KeyError if not loaded."""

def get_article(norma: Norma, articulo: str, language: Language) -> ArticleEntry
    """Return the (article, language)-specific entry. Raises KeyError if absent."""

def get_paragraph(norma: Norma, articulo: str, apartado: str, language: Language) -> str
    """Return the paragraph text. Raises KeyError if apartado absent."""

def get_manifest_meta(norma: Norma) -> dict[str, str]
    """Return {'version': ..., 'source_url': ...} for the corpus."""

def list_articulos(norma: Norma, language: Language) -> list[str]
    """Sorted list of articulo ids — used by NotFound messages."""

def list_apartados(norma: Norma, articulo: str, language: Language) -> list[str]
    """Sorted list of apartado ids — used by NotFound messages."""

def reset() -> None
    """Test-only: clear singleton state. Production code never calls this."""
```

**Internal state:** module-level `_CORPUS: dict[Norma, Manifest] | None = None`. The singleton is read-only after `warmup()`. No mutation paths.

**Integrity check pseudocode:**
```python
for norma in corpora_with_manifests:
    m = manifest_mod.load(MANIFEST_DIR / f"{norma}.json")
    for article in m.articles:
        for lang, entry in article.languages.items():
            text = _load_processed_article_text(norma, article.articulo, lang)
            computed = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if computed != entry.hash:
                raise RuntimeError(
                    f"manifest hash drift: {norma} art. {article.articulo} {lang} "
                    f"(expected {entry.hash[:16]}..., got {computed[:16]}...). "
                    f"Run `make ingest` to refresh manifest, or restore "
                    f"corpus/processed/ from git-lfs."
                )
    _CORPUS[norma] = m
```

**Test surface:** unit tests with synthetic corpus dirs (a few articles, two languages); integrity drift is tested by mutating the processed JSON between manifest write and warmup call.

### 4.2 `rag/retrieval.py` (new)

**Responsibility:** canonical retrieval pipeline. The single source of truth that both `mcp_server/tools.py::search_articles` and `agents/retriever.py::RetrieverAgent` delegate to.

**Public surface:**
```python
PRE_RERANK: int = 50

def run(
    query: str,
    corpus: Norma,
    language: Language,
    top_k: int = 5,
) -> list[RetrievedChunk]
    """
    1. embeddings.embed([query]) → query_vec
    2. store.connect(INDEX_PATH).search(query_vec).where(
           f"norma = '{corpus}' AND language = '{language}'"
       ).limit(PRE_RERANK).to_list() → candidates
    3. reranker.rerank(query, [c['text'] for c in candidates], top_n=top_k)
       → list[(idx, score)]
    4. enrich each surviving candidate with version + source_url from
       loader.get_manifest_meta(corpus)
    5. return list[RetrievedChunk] sorted by score desc
    """
```

**Notes:**
- `top_k` is **post-rerank** (what the caller sees). `PRE_RERANK` is fixed at 50.
- `score` is the rerank score, normalized to [0, 1] by the reranker module.
- Empty candidate set → `[]`. No exception.
- The `where` clause uses single-quoted literals built from `Norma` and `Language` literals (closed enums), so no SQL injection vector via these args.

### 4.3 `citation/schemas.py` (new)

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from regulaitor.corpus.schemas import Norma, Language

class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)
    norma: Norma
    articulo: str = Field(min_length=1)
    apartado: str | None = None
    language: Language
    text: str = Field(min_length=1)

class AuditResult(BaseModel):
    citation: Citation
    validated: bool
    article_exists: bool
    apartado_exists: bool | None  # None when citation has no apartado
    text_normalized_match: bool
    reason: str | None  # human-readable diagnostic; None iff validated=True

class RetrievedChunk(BaseModel):
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
    query: str
    corpus: Norma
    language: Language
    chunks: list[RetrievedChunk]
    retrieved_at: datetime  # UTC, timezone-aware
    embedding_model: str

class FetchedArticle(BaseModel):
    norma: Norma
    articulo: str
    apartado: str | None
    language: Language
    text: str
    version: str
    source_url: str
```

**Constraints:**
- `frozen=True` on `Citation`, `RetrievedChunk` for hashability + immutability.
- `min_length=1` on `articulo` and `text` of `Citation` rejects empty strings at construction.
- `score` is `0.0 ≤ score ≤ 1.0` enforced by Pydantic; out-of-range raises `ValidationError`.
- `Norma` and `Language` are existing Literal types from `corpus/schemas.py`.

### 4.4 `citation/validator.py` (new)

**Responsibility:** the canonical citation validator. Three strict checks, fail-fast.

**Public surface:**
```python
def validate(citation: Citation, *, loader: Any | None = None) -> AuditResult
    """
    Three sequential checks; each early-exit on failure with specific reason:
      1. article_exists: loader.get_article(citation.norma, citation.articulo,
                                              citation.language) succeeds?
      2. apartado_exists: if citation.apartado is not None, loader.get_paragraph
                            returns text? (None → check skipped, apartado_exists=None)
      3. text_normalized_match: chunking._normalize(citation.text) is a substring of
                                  chunking._normalize(target_text)
                                  where target_text is the apartado paragraph if
                                  apartado was given, else the full article text
                                  (paragraphs joined by \n\n).

    Returns AuditResult. validated == (article_exists AND
                                       (apartado_exists or apartado is None) AND
                                       text_normalized_match).
    `loader` defaults to the corpus.loader singleton; tests inject a mock.
    """
```

**Reason format examples (used in unit + integration tests):**
- `"article_not_found: ai_act has no articulo 999 in language es. Valid range: 1-113."`
- `"apartado_not_found: ai_act art. 6 ES has no apartado 99. Valid apartados: 1, 2, 3, 4, 5, 6, 7."`
- `"text_not_in_apartado: ai_act art. 6.1 ES; cited text not found after normalization (47 chars vs 312 chars apartado)."`
- `"text_not_in_article: ai_act art. 6 ES; cited text not found after normalization (47 chars vs 4334 chars article)."`

### 4.5 `agents/retriever.py` (new)

**Responsibility:** thin LangGraph adapter around the retrieval helper.

```python
class RetrieverAgent:
    def __init__(self, *, embedding_model: str | None = None) -> None:
        """embedding_model defaults to embeddings.model_identifier()."""

    def retrieve(
        self,
        query: str,
        corpus: Norma,
        language: Language,
        top_k: int = 5,
    ) -> Context:
        """Delegates to rag.retrieval.run, wraps in Context."""
```

**No state, no caching, no LLM calls.** Pure adapter. H4's LangGraph node will call this in its turn.

### 4.6 `mcp_server/server.py`, `tools.py`, `errors.py`, `__main__.py` (new)

**Bootstrap (`server.py`):**
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

def run() -> None:
    """Boot: warmup loader (fail-closed) → warmup reranker → register tools → serve stdio."""
    corpus_loader.warmup()      # raises on hash drift; server fails to start
    reranker.warmup()           # download + load; ~1.5s if cached
    server = Server("regulaitor")
    register_tools(server, tools.SEARCH, tools.FETCH, tools.VALIDATE)
    asyncio.run(stdio_server(server))

def register_tools(server, *funcs): ...
```

**Tool adapters (`tools.py`):**
```python
def search_articles(query: str, corpus: Norma, language: Language, top_k: int = 5) -> list[RetrievedChunk]:
    """MCP adapter for search. Logs structured event. Empty results → []."""
    return rag.retrieval.run(query, corpus, language, top_k=top_k)

def fetch_article(norma: Norma, articulo: str, language: Language, apartado: str | None = None) -> FetchedArticle:
    """MCP adapter for fetch. Raises NotFoundError on missing article/apartado."""
    try:
        if apartado is not None:
            text = corpus_loader.get_paragraph(norma, articulo, apartado, language)
        else:
            article = corpus_loader.get_article(norma, articulo, language)
            text = "\n\n".join(p.text for p in article.languages[language].paragraphs)
    except KeyError as e:
        raise NotFoundError(actionable_message_for(e, norma, articulo, apartado, language))
    meta = corpus_loader.get_manifest_meta(norma)
    return FetchedArticle(norma=norma, articulo=articulo, apartado=apartado,
                          language=language, text=text,
                          version=meta["version"], source_url=meta["source_url"])

def validate_citation(citation: Citation) -> AuditResult:
    """MCP adapter for validate. Always returns AuditResult; never raises NotFound."""
    return citation.validator.validate(citation)
```

**Errors (`errors.py`):**
```python
class NotFoundError(Exception):
    """Mapped by MCP SDK to NOT_FOUND error code (-32001)."""

class IntegrityError(RuntimeError):
    """Raised by corpus.loader.warmup() on hash drift."""
```

**Entry point (`__main__.py`):**
```python
from regulaitor.mcp_server.server import run
if __name__ == "__main__":
    run()
```

`make mcp-server` runs `uv run python -m regulaitor.mcp_server`.

## 5. Data flow scenarios

### Scenario A — external client query via MCP

```
Claude Desktop / evals harness → stdio JSON-RPC →
  tools.search_articles(query="alto riesgo", corpus="ai_act", language="es", top_k=5)
    → rag.retrieval.run(...)
        → embeddings.embed([query]) → vec
        → store.search(vec).where("norma='ai_act' AND language='es'").limit(50)
        → reranker.rerank(query, candidates, top_n=5)
        → enrich with corpus.loader.get_manifest_meta("ai_act")
    → list[RetrievedChunk] (5 items, score-sorted desc)
  ← JSON-serialized; client consumes
```

### Scenario B — agent retrieval (H4 LangGraph node)

```
LangGraph state.query="..." →
  RetrieverAgent.retrieve(query, corpus="ai_act", language="es", top_k=5)
    → rag.retrieval.run(...)   # SAME helper as Scenario A
    → Context(query=..., corpus=..., language=..., chunks=[...],
              retrieved_at=now_utc, embedding_model="BAAI/bge-m3")
  → state.context = Context  # H4 reads
```

### Scenario C — citation validation via MCP (Auditor in H4)

```
Auditor → stdio JSON-RPC →
  tools.validate_citation({norma: "ai_act", articulo: "6", apartado: "1",
                            language: "es", text: "..."})
  → Pydantic parse → Citation
  → citation.validator.validate(citation)
      → check 1: corpus.loader.get_article("ai_act", "6", "es") succeeds → article_exists=True
      → check 2: apartado="1" given → corpus.loader.get_paragraph(...) succeeds → apartado_exists=True
      → check 3: target_text = paragraph_text
                  match = chunking._normalize(citation.text) in chunking._normalize(target_text)
                  → text_normalized_match=True
      → AuditResult(validated=True, article_exists=True, apartado_exists=True,
                    text_normalized_match=True, reason=None, citation=citation)
  ← JSON-serialized; Auditor consumes
```

## 6. Error handling

Per Q11 lockdown:

| Tool | Happy path | Resource missing | Bad input | Infra fail |
|---|---|---|---|---|
| `search_articles` | `list[RetrievedChunk]` (1-5) | `[]` (valid result) | `INVALID_PARAMS` (Pydantic) | `INTERNAL_ERROR` |
| `fetch_article` | `FetchedArticle` | `NotFoundError` (-32001) with actionable message | `INVALID_PARAMS` (Pydantic) | `INTERNAL_ERROR` |
| `validate_citation` | `AuditResult(validated=True)` | `AuditResult(validated=False, reason=...)` | `INVALID_PARAMS` (Pydantic) | `INTERNAL_ERROR` |

`IntegrityError` from `corpus.loader.warmup()` propagates to the user (server doesn't start). The actionable message tells the operator how to recover (`make ingest` or restore from git-lfs).

## 7. SSDLC controls

H3 introduces the project's first **trust boundary**, so security is upfront, not retrofit.

| Control | Where | What it prevents |
|---|---|---|
| Pydantic input validation (`min_length`, `Field(ge=, le=)`) | All tool adapters | Empty / malformed input crossing the boundary |
| `frozen=True` on Citation, RetrievedChunk | schemas.py | Mutation between validation and consumption (TOCTOU) |
| Hash drift detection at `loader.warmup()` | corpus/loader.py | Tampered `corpus/processed/` files producing falsely-validated citations |
| Fail-closed on integrity error | server.py | Server running with corrupt corpus state |
| Per-tool error semantics | tools.py + errors.py | Conflating "validation rejected" with "infra failure" → silent failures |
| No PII in structured logs | tools.py | Citation text leakage in operational logs |
| `Norma` / `Language` Literals in store filter strings | rag/retrieval.py | SQL injection via norma/language args (closed enums, no user-supplied strings) |
| stdio-only transport (no port open) | server.py | Network attack surface for H3 (zero) |
| No external HTTP in this surface | (architecture) | The MCP server only talks to the local LanceDB and local files |

The threat model H9 will exercise:
- An attacker with read-write access to `corpus/processed/` modifies a paragraph → `loader.warmup()` detects hash drift, server refuses to start.
- An LLM adversary cites text that's in the article but in the wrong apartado → validator rejects with `apartado_text_mismatch` reason.
- An LLM adversary cites text close to but not equal to corpus text (paraphrase) → validator rejects with `text_not_in_apartado` reason; no fuzzy match accepts it.
- Malformed MCP input (missing fields, wrong types, oversized strings) → Pydantic rejects with `INVALID_PARAMS` before any logic runs.

## 8. Repo layout (post-H3)

```
src/regulaitor/
  corpus/
    loader.py           # NEW H3
    _targets.py
    formex_parser.py    # H1
    html_parser.py      # H1
    pdf_parser.py       # H1
    eurlex.py           # H1
    ingest.py           # H1
    manifest.py         # H1
    schemas.py          # H1
    validate.py         # H1
  rag/
    retrieval.py        # NEW H3
    chunking.py         # H2
    embeddings.py       # H2
    reranker.py         # H2
    schemas.py          # H2
    store.py            # H2
    build.py            # H2
  citation/
    __init__.py         # NEW H3
    schemas.py          # NEW H3
    validator.py        # NEW H3
  agents/
    __init__.py         # NEW H3
    retriever.py        # NEW H3
  mcp_server/
    __init__.py         # NEW H3
    __main__.py         # NEW H3
    server.py           # NEW H3
    tools.py            # NEW H3
    errors.py           # NEW H3

tests/
  unit/
    citation/
      test_schemas.py     # NEW H3
      test_validator.py   # NEW H3
    corpus/
      test_loader.py      # NEW H3
      ...
    rag/
      test_retrieval.py   # NEW H3
      ...
    agents/
      test_retriever.py   # NEW H3
    mcp_server/
      test_tools.py       # NEW H3
      test_server.py      # NEW H3
  contract/
    test_citation_schemas.py  # NEW H3 (round-trip Hypothesis)
    test_mcp_tool_schemas.py  # NEW H3 (snapshot of generated MCP tool schemas)
    test_rag_schemas.py        # H2
  integration/
    test_mcp_search_articles_flow.py     # NEW H3 (slow)
    test_mcp_validate_citation_flow.py    # NEW H3
    test_mcp_fetch_article_flow.py        # NEW H3
    test_loader_integrity_drift.py        # NEW H3
    test_retriever_agent_returns_context.py  # NEW H3
    ...
```

## 9. Dependencies

Added in H3 (one new runtime, zero new dev):

```toml
# pyproject.toml additions
"mcp>=0.4,<2.0",   # official MCP Python SDK; pinned <2.0 for breaking-change protection
```

Already pinned: `pydantic>=2.9,<3.0`, `lancedb`, `FlagEmbedding`, `transformers>=4.44,<5.0` (CVE-2026-1839 mitigation unchanged).

CI workflow unchanged (Lint + Test + Security with the documented `--ignore-vuln CVE-2026-1839`).

## 10. Skills / MCPs introduction

Per ADR 0002 schedule:

- **Skill `prompt-versioning` introduced in H3** as planned. Its first user is H4 (Analyst prompts), so the skill SKILL.md is drafted in H3 closure but exercised in H4. Proposed but not yet activated; user OK gates before activation.
- **Skill `citation-validator` introduced in H3** as planned. Its first user is `citation/validator.py` itself; SKILL.md captures the canonical procedure that future evolutions follow (e.g. fuzzy fallback in H15).
- **No external MCPs** introduced in H3. The project's own MCP server is built; the `fetch` MCP remains deferred (no use case yet).
- **No subagent** introduced in H3. The H1/H2 pattern (`general-purpose` + `superpowers:code-reviewer`) covers H3 implementation. The first project-level subagent (`software-architect`) likely earns its keep on the H3 review of the validator + MCP contract — proposed if reviews surface architectural questions.

## 11. Testing pyramid

Target: **≥165 tests total** at H3 closure (currently 110 + ~55 new). **≥90% global coverage** maintained.

### 11.1 Unit (`tests/unit/`, ~50 new)

- `corpus/test_loader.py` (~12): warmup populates singleton; idempotent second call; hash drift raises with article_id in message; `get_article` hit + miss; `get_paragraph` hit + miss + missing apartado list; `list_articulos` / `list_apartados` sorted output; `reset()` clears state.
- `rag/test_retrieval.py` (~6): `run` calls embeddings/store/reranker with correct args; pre=50 hardcoded; filter clause includes corpus + language; empty store → empty list; result enrichment with version + source_url.
- `citation/test_validator.py` (~12): article missing → `validated=False, reason matches "article_not_found"`; apartado missing (when given) → reason matches "apartado_not_found"; text not in apartado → reason matches "text_not_in_apartado"; text not in article (no apartado given) → reason matches "text_not_in_article"; happy path with apartado → `validated=True`; happy path without apartado → `apartado_exists=None`; normalization handles accents, capitalization, dashes, whitespace; loader injection works in tests.
- `mcp_server/test_tools.py` (~10): each adapter calls helper/loader/validator with correct args; `fetch_article` translates `KeyError` → `NotFoundError` with actionable message; `validate_citation` always returns `AuditResult`; `search_articles` returns `[]` on empty.
- `mcp_server/test_server.py` (~4): warmup sequence (loader before reranker); register_tools wires the right callables; `run()` covered by integration test, not unit.
- `agents/test_retriever.py` (~4): `RetrieverAgent.retrieve` delegates to `rag.retrieval.run`; output is `Context`; `embedding_model` populated from `embeddings.model_identifier()`; `retrieved_at` is timezone-aware UTC.
- `citation/test_schemas.py` (~6): `Citation` empty `text` rejected; empty `articulo` rejected; `RetrievedChunk` `score` out-of-range rejected; `Citation`/`RetrievedChunk` are frozen (assignment raises); `Context` requires timezone-aware datetime; `FetchedArticle` accepts `apartado=None`.

### 11.2 Contract (`tests/contract/`, ~5 new)

- `test_citation_schemas.py` (~3): Hypothesis round-trip for Citation, AuditResult, RetrievedChunk, Context, FetchedArticle. `model_dump_json()` → `model_validate_json()` is identity.
- `test_mcp_tool_schemas.py` (~2): snapshot test of the JSON Schemas exposed by the MCP SDK for the 3 tools. Any breaking change to a tool signature flips the snapshot diff.

### 11.3 Integration (`tests/integration/`, ~5 new; some `slow`)

- `test_mcp_search_articles_flow.py` (slow): subprocess-launches `python -m regulaitor.mcp_server`, sends a real query via stdio JSON-RPC, parses response, asserts: 5 results, all `norma=ai_act lang=es`, scores monotonically decreasing, version field is the expected CELEX. Uses real BGE-M3 + reranker + LanceDB; takes ~10s wall-clock with cache warm.
- `test_mcp_validate_citation_flow.py`: 3 valid citations (literal text from real apartados) → all `validated=True`. 3 invalid citations (right article, wrong text / wrong apartado / nonexistent article) → each `validated=False` with the expected `reason` substring. No subprocess; calls `tools.validate_citation` directly with the live loader.
- `test_mcp_fetch_article_flow.py`: `fetch_article("ai_act", "6", "es", apartado="1")` → text matches the known apartado 1 of art. 6 ES. `fetch_article("ai_act", "999", "es")` → `NotFoundError` with valid range in message. `fetch_article` without `apartado` → text matches the full article concatenation.
- `test_loader_integrity_drift.py`: copy real corpus to tmpdir; mutate one paragraph; call `loader.warmup()` pointed at tmpdir; assert `RuntimeError` with that article_id and "hash drift" in message.
- `test_retriever_agent_returns_context.py`: instantiate `RetrieverAgent`; `retrieve("alto riesgo", "ai_act", "es")` → `Context` with `embedding_model="BAAI/bge-m3"`, `retrieved_at` within last 5 seconds, ≥1 chunk.

## 12. Acceptance criteria

H3 closes Done when ALL of the following hold:

1. ✅ `python -m regulaitor.mcp_server` boots cleanly. Total warmup <2s after first run (cache warm); first run dominated by reranker model load.
2. ✅ All 3 MCP tools answer correctly per Section 5 scenarios.
3. ✅ Smoke set: 3 valid + 3 invalid known citations produce expected `AuditResult` per Section 4.4 reason format.
4. ✅ `RetrieverAgent` produces a well-formed `Context` against the live LanceDB.
5. ✅ Loader hash drift fails server boot; recovery path message tested in integration.
6. ✅ `pytest -m "not slow"` passes on Windows + Linux (CI). `pytest` (with slow) passes locally.
7. ✅ Coverage ≥90% global; per-module ≥85% for `corpus/loader.py`, `rag/retrieval.py`, `citation/`, `agents/retriever.py`, `mcp_server/`.
8. ✅ CI green: lint (ruff + black + mypy), test, security (bandit + pip-audit with documented ignores).
9. ✅ ADR 0005 (MCP server architecture) committed.
10. ✅ Decisions log H3 section: 13 decisions + closure entry with real numbers.
11. ✅ Skills `prompt-versioning` + `citation-validator` SKILL.md drafted (per ADR 0002 schedule).
12. ✅ Tag `v0.0.4-h3` published after squash-merge to `main`.

## 13. Open questions deferred to plan / writing-plans phase

These are implementation details, not architecture:

- Exact MCP SDK version pin (test `mcp>=0.4` vs latest stable; resolve at Task 0 of the plan).
- Subprocess test harness for stdio integration test (likely `subprocess.Popen` + a minimal JSON-RPC client; resolve at Task implementing first integration test).
- Rate limiting on MCP tools: deferred to H7 (FastAPI gets rate limits; stdio MCP server is local single-client so not needed in H3).
- `actionable_message_for(...)` helper in `tools.py`: factored or inlined? Resolve in code review.
- Whether `loader.reset()` is exposed publicly or via test-only helper module.

## 14. Risk register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|-----------|------------|
| 1 | MCP SDK Python <1.0; APIs may change | Medium | Medium | Pin exact version; isolate SDK use in `server.py`; review SDK release notes at H4 start |
| 2 | stdio framing on Windows: CRLF/LF encoding issues | High | Low | Use SDK's stdio_server (handles encoding); local Windows integration test in CI for catch |
| 3 | Reranker warmup adds ~1.5s to MCP server boot | Low | High | Acceptable for MVP; document in runbook; H11 may add async warmup |
| 4 | Citation text from PDF carries soft-hyphens / ligatures not in `_normalize` | Medium | Medium | Add adversarial normalization tests with samples extracted from real corpus PDF; extend `_normalize` if needed in H8 evaluation |
| 5 | Validator accepts text from a different apartado of the same article (when no apartado given in citation) | Medium | Low | Documented behaviour: when no apartado, match against full article. H4 Auditor SHOULD always include apartado in citations; if it doesn't, that's a stronger separate rule |
| 6 | Loader integrity check adds 50-100ms to warmup | Negligible | High | Documented as feature, not bug. Trade-off accepted per Q12 |
| 7 | LangGraph node in H4 doesn't fit the `RetrieverAgent.retrieve()` signature exactly | Low | Medium | The signature is intentionally minimal; H4 wraps it in whatever adapter LangGraph needs |
| 8 | Hash drift recovery message points to `make ingest` but operator may not have set up Git-LFS for `corpus/processed/` | Medium | Low | Recovery message also mentions "or restore from git-lfs"; runbook documents the LFS dependency |

## 15. Implementation order (high-level; detail in plan)

1. Dependencies + branch setup.
2. `citation/schemas.py` (foundation; tested first).
3. `corpus/loader.py` (independent of agents/MCP; tested with synthetic corpus dirs).
4. `rag/retrieval.py` (depends on loader for enrichment).
5. `citation/validator.py` (depends on loader, schemas).
6. `agents/retriever.py` (depends on retrieval, schemas).
7. `mcp_server/errors.py` + `tools.py` (depends on all above).
8. `mcp_server/server.py` + `__main__.py` (bootstrap glue).
9. Contract tests (Hypothesis round-trips, MCP schema snapshot).
10. Integration tests (subprocess MCP, integrity drift, retriever-agent).
11. Skills (`prompt-versioning`, `citation-validator`) SKILL.md drafts.
12. ADR 0005 + decisions log closure entry + Makefile `mcp-server` target.
13. CI verify, smoke run, manifest of final stats.
14. PR, squash-merge, tag.

## 16. References

- `docs/superpowers/specs/2026-05-04-h2-rag-base-design.md` — H2 spec.
- `docs/adr/0004-rag-architecture.md` — RAG architecture ADR.
- `docs/adr/0002-skills-mcps-roadmap.md` — Skills/MCPs schedule.
- `docs/technical_decisions_log.md` H3 section (will land alongside this spec).
- `CLAUDE.md` §6 (no citation, no answer), §8 (agents), §9 (MCP server tools), §10 (stack), §16.1 (H3 deliverables).
- `corpus/manifests/{ai_act,gdpr}.json` — boundary contract from H1/H2.
- `corpus/indexes/regulaitor.lance/` — LanceDB store from H2.
- Model Context Protocol specification: <https://modelcontextprotocol.io/specification>.
