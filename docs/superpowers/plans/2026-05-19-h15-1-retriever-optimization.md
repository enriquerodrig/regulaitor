# H15.1 — Retriever Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `corpus="auto"` retrieval path (multi-corpus → existing rerank → deterministic post-rerank purity gate) plus a `RetrievalConfig` of contained tuning levers, with the explicit-corpus path byte-identical to `v0.1.5-h15`, then measure it honestly vs the already-committed H15 frozen control.

**Architecture:** `rag/retrieval.run()` branches on `corpus`: any of the four norms → today's code verbatim (single-`norma` where-clause, regression-zero by construction); `"auto"` → drop the `norma` filter, rerank across 4 corpora, then a pure `_apply_purity_gate` collapses to one corpus when the top-`top_k` is corpus-dominant (no-leakage) else returns multi-corpus. Auditor + citation validator are byte-unchanged (they already validate every citation per-corpus, §6 intact). No LanceDB re-ingest.

**Tech Stack:** Python 3.11, Pydantic v2, LanceDB, BGE-M3 embeddings + `bge-reranker-v2-m3` (all local, $0), `uv`, pytest, the H15 eval harness + router cost accumulator.

---

## Conventions (apply to every task)

- **Commits:** conventional, **NO** AI/Co-Authored footer. Local commits use `SKIP=gitleaks git commit ...` — **NEVER** `--no-verify`.
- **Gate:** the authoritative gate is `uv run pytest -m "not slow"` (CI-equivalent) with coverage **≥90%**. A single-file `pytest path::test` is only for the red/green TDD loop.
- **Script invocation that needs secrets:** `uv run --env-file .env python -m scripts.X` (bare `python -m` does NOT load `.env` — H13 lesson). Tasks 1–7 are **$0** (no secrets, local only).
- **Paid runs (Tasks 8–9) are USER-GATED:** the controller (not a subagent) executes them as persistent background jobs, each preceded by a `--limit 3` probe + a running cost-tally + explicit user OK + user credit confirmation. H14 lesson: never delegate a 30–100 min paid job to a subagent.
- **§22.22 honesty:** never present a non-measured number as measured; the done-when is "measured improvement OR documented deeper system-level ceiling — both defend"; **no promised metric number**; revert any candidate that regresses no-leakage or safety.
- **Frozen control:** `evals/reports/h15/candidate-v1.2.md` (30 calibration) + `evals/reports/h15/holdout-v1.2-chat.md` (14 holdout), already committed. **No paid re-baseline.**

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/regulaitor/corpus/schemas.py` | add `CorpusSelector` alias (Norma unchanged) | T1 |
| `src/regulaitor/citation/schemas.py` | `Context.corpus` widen + `resolved_normas` | T1 |
| `src/regulaitor/rag/retrieval.py` | `RetrievalConfig`, pure `_apply_purity_gate`, `run()` auto-branch | T2, T3 |
| `src/regulaitor/api/schemas.py` | add `"auto"` to `AskRequest.corpus` | T4 |
| `src/regulaitor/orchestration/state.py` | `ChatState.corpus` widen | T4 |
| `src/regulaitor/orchestration/graph.py` | `run()` cast widen (pass-through) | T4 |
| `src/regulaitor/agents/retriever.py` | type widen + populate `resolved_normas` | T4 |
| `src/regulaitor/mcp_server/tools.py` | `search_articles` type widen (pass-through) | T4 |
| `evals/schemas.py` | `GoldCaseChat.corpus_esperado` widen | T5 |
| `evals/harness.py` | thread `"auto"` end-to-end | T5 |
| `evals/gold_set.jsonl` | xcorpus-001/002 → `corpus_esperado:"auto"` | T5 |
| `docs/adr/0017-retriever-cross-corpus-auto.md` | architecture ADR | T7 |
| `docs/retriever_optimization.md` | honest study report | T10 |
| `docs/technical_decisions_log.md`, `docs/evidence_matrix.md`, `CLAUDE.md` | closure | T11 |

---

### Task 1: `CorpusSelector` type + `Context` schema extension

**Files:**
- Modify: `src/regulaitor/corpus/schemas.py` (after line 14, `Norma = Literal[...]`)
- Modify: `src/regulaitor/citation/schemas.py:56-64` (`Context`)
- Test: `tests/unit/test_corpus_selector_schema.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_corpus_selector_schema.py
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import Context


def test_context_accepts_explicit_corpus_with_empty_resolved_normas() -> None:
    ctx = Context(
        query="q",
        corpus="gdpr",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="m",
        resolved_normas=[],
    )
    assert ctx.corpus == "gdpr"
    assert ctx.resolved_normas == []


def test_context_accepts_auto_and_multi_resolved_normas() -> None:
    ctx = Context(
        query="q",
        corpus="auto",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="m",
        resolved_normas=["nis2", "dora"],
    )
    assert ctx.corpus == "auto"
    assert ctx.resolved_normas == ["nis2", "dora"]


def test_context_rejects_unknown_corpus() -> None:
    with pytest.raises(ValidationError):
        Context(
            query="q",
            corpus="bogus",
            language="es",
            chunks=[],
            retrieved_at=datetime.now(tz=UTC),
            embedding_model="m",
            resolved_normas=[],
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_corpus_selector_schema.py -q --no-cov`
Expected: FAIL (`Context` has no `resolved_normas`; `corpus="auto"` rejected — current type is `Norma`).

- [ ] **Step 3: Add `CorpusSelector` in `corpus/schemas.py`**

After line 14 (`Norma = Literal["ai_act", "gdpr", "nis2", "dora"]`) add:

```python
# H15.1: opt-in cross-corpus retrieval selector. `Norma` itself is unchanged
# (H1-stable). "auto" triggers the multi-corpus retrieve + post-rerank purity
# gate (ADR-0017). Any of the four norms keeps the byte-identical single-corpus
# path (no-leakage by construction, §22.18 / H14).
CorpusSelector = Literal["ai_act", "gdpr", "nis2", "dora", "auto"]
```

- [ ] **Step 4: Widen `Context` in `citation/schemas.py`**

Change the import line 14 and the `Context` class (lines 56-64):

```python
from regulaitor.corpus.schemas import CorpusSelector, Language, Norma
```

```python
class Context(BaseModel):
    """Wrapper produced by RetrieverAgent for downstream H4 LangGraph state."""

    query: str
    corpus: CorpusSelector
    language: Language
    chunks: list[RetrievedChunk]
    retrieved_at: datetime
    embedding_model: str
    resolved_normas: list[Norma] = Field(default_factory=list)
```

(`Field` is already imported in `citation/schemas.py`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_corpus_selector_schema.py -q --no-cov`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_corpus_selector_schema.py src/regulaitor/corpus/schemas.py src/regulaitor/citation/schemas.py
SKIP=gitleaks git commit -m "feat(h15.1): CorpusSelector type + Context.resolved_normas"
```

---

### Task 2: `RetrievalConfig` + pure `_apply_purity_gate`

**Files:**
- Modify: `src/regulaitor/rag/retrieval.py` (add config + helper; do NOT touch `run()` yet)
- Test: `tests/unit/test_purity_gate.py` (create)

The gate input is the reranked list as `(RetrievedChunk-like, score)` already enriched with `.norma`. To keep the helper pure and trivially testable, it operates on a list of `(norma, item)` pairs already ordered best-first, returns the kept subset (same order), plus the resolved normas.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_purity_gate.py
from __future__ import annotations

from regulaitor.rag.retrieval import RetrievalConfig, _apply_purity_gate


def _pairs(normas: list[str]) -> list[tuple[str, int]]:
    # (norma, payload) ordered best-first; payload is an opaque int id.
    return [(n, i) for i, n in enumerate(normas)]


def test_single_corpus_dominant_collapses_to_that_norma() -> None:
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    pairs = _pairs(["gdpr", "gdpr", "gdpr", "gdpr", "nis2"])  # 4/5 = 0.8 ≥ 0.6
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["gdpr"]
    assert all(n == "gdpr" for n, _ in kept)
    assert len(kept) == 4


def test_genuine_multi_corpus_returns_top_k_unfiltered() -> None:
    cfg = RetrievalConfig(top_k=4, purity_threshold=0.6)
    pairs = _pairs(["nis2", "dora", "nis2", "dora", "gdpr"])  # max share 2/4 = 0.5 < 0.6
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert [n for n, _ in kept] == ["nis2", "dora", "nis2", "dora"]
    assert sorted(resolved) == ["dora", "nis2"]


def test_threshold_is_inclusive_boundary() -> None:
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    pairs = _pairs(["dora", "dora", "dora", "nis2", "gdpr"])  # 3/5 = 0.6 == threshold
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["dora"]  # >= is inclusive


def test_empty_rerank_returns_empty() -> None:
    cfg = RetrievalConfig(top_k=5, purity_threshold=0.6)
    kept, resolved = _apply_purity_gate([], cfg)
    assert kept == []
    assert resolved == []


def test_share_window_is_top_k_not_full_list() -> None:
    # 10 items, top_k=4: only the first 4 count toward the share.
    cfg = RetrievalConfig(top_k=4, purity_threshold=0.75)
    pairs = _pairs(["gdpr", "gdpr", "gdpr", "gdpr", "nis2", "nis2", "nis2", "nis2", "nis2", "nis2"])
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert resolved == ["gdpr"]  # top-4 are all gdpr (4/4 = 1.0)
    assert len(kept) == 4


def test_tie_no_corpus_reaches_threshold_returns_multi() -> None:
    cfg = RetrievalConfig(top_k=4, purity_threshold=0.6)
    pairs = _pairs(["ai_act", "gdpr", "nis2", "dora"])  # each 1/4 = 0.25
    kept, resolved = _apply_purity_gate(pairs, cfg)
    assert len(kept) == 4
    assert sorted(resolved) == ["ai_act", "dora", "gdpr", "nis2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_purity_gate.py -q --no-cov`
Expected: FAIL (`RetrievalConfig` / `_apply_purity_gate` not defined).

- [ ] **Step 3: Add `RetrievalConfig` + `_apply_purity_gate` to `rag/retrieval.py`**

Insert after the `PRE_RERANK = 50` line (keep `PRE_RERANK` for backward references; `RetrievalConfig.pre_rerank` defaults to it):

```python
from collections import Counter
from dataclasses import dataclass
from typing import TypeVar


@dataclass(frozen=True)
class RetrievalConfig:
    """H15.1 tuning levers. Frozen defaults == v0.1.5-h15 behaviour so the
    explicit-corpus path is provably unchanged; the `auto` path and any tuned
    value are the A/B variable (ADR-0017). `query_normalize` stays deterministic
    (no LLM — preserves the LLM-free-retriever principle)."""

    pre_rerank: int = PRE_RERANK  # 50
    top_k: int = 5
    purity_threshold: float = 0.6  # auto path only; >= is inclusive
    query_normalize: bool = False  # default identity == current behaviour


DEFAULT_CONFIG = RetrievalConfig()

_T = TypeVar("_T")


def _apply_purity_gate(
    ranked: list[tuple[str, _T]], cfg: RetrievalConfig
) -> tuple[list[tuple[str, _T]], list[str]]:
    """Deterministic post-rerank corpus purity gate (ADR-0017).

    `ranked` is the reranked list best-first as (norma, payload). share(norma)
    = count of that norma among the top-`cfg.top_k` divided by `cfg.top_k`.
    If max share >= cfg.purity_threshold -> collapse to that norma (no-leakage
    restored); else -> return the top-`cfg.top_k` multi-corpus. Returns
    (kept_pairs_best_first, sorted_resolved_normas).
    """
    if not ranked:
        return [], []
    window = ranked[: cfg.top_k]
    counts = Counter(n for n, _ in window)
    top_norma, top_count = counts.most_common(1)[0]
    if top_count / cfg.top_k >= cfg.purity_threshold:
        kept = [(n, p) for (n, p) in ranked if n == top_norma][: cfg.top_k]
        return kept, [top_norma]
    return window, sorted(counts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_purity_gate.py -q --no-cov`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_purity_gate.py src/regulaitor/rag/retrieval.py
SKIP=gitleaks git commit -m "feat(h15.1): RetrievalConfig + pure post-rerank purity gate"
```

---

### Task 3: `rag/retrieval.run()` auto-branch (explicit path byte-identical)

**Files:**
- Modify: `src/regulaitor/rag/retrieval.py` (`run()`)
- Test: `tests/unit/test_retrieval_run_branches.py` (create)

The current `run()` (grounded):

```python
def run(query: str, corpus: Norma, language: Language, top_k: int = 5) -> list[RetrievedChunk]:
    [query_vec] = embeddings.embed([query])
    table = store.connect(INDEX_PATH)
    where_clause = f"norma = '{corpus}' AND language = '{language}'"
    candidates = table.search(query_vec).where(where_clause).limit(PRE_RERANK).to_list()
    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=top_k)
    if not reranked:
        return []
    meta = loader.get_manifest_meta(corpus)
    return [RetrievedChunk(...) for idx, score in reranked]
```

The explicit-corpus branch must stay **byte-identical** in behaviour. The test mocks `embeddings.embed`, `store.connect`, `reranker.rerank`, `loader.get_manifest_meta` so it is $0/local and asserts: (a) explicit corpus → single-`norma` where-clause used, output identical to pre-change logic; (b) `"auto"` → where-clause has NO `norma`, gate applied, `resolved_normas` correct.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_retrieval_run_branches.py
from __future__ import annotations

import pytest

from regulaitor.rag import retrieval


class _FakeSearch:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.where_clause: str | None = None

    def where(self, clause: str) -> "_FakeSearch":
        self.where_clause = clause
        return self

    def limit(self, _n: int) -> "_FakeSearch":
        return self

    def to_list(self) -> list[dict]:
        return self._rows


class _FakeTable:
    def __init__(self, rows: list[dict]) -> None:
        self.search_obj = _FakeSearch(rows)

    def search(self, _vec: object) -> _FakeSearch:
        return self.search_obj


def _row(norma: str, art: str) -> dict:
    return {
        "chunk_id": f"{norma}-{art}",
        "norma": norma,
        "articulo": art,
        "apartado": None,
        "language": "es",
        "text": f"text-{norma}-{art}",
    }


@pytest.fixture
def _patch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(
        retrieval.loader,
        "get_manifest_meta",
        lambda _c: {"version": "v", "source_url": "u"},
    )

    def _factory(rows: list[dict]):
        table = _FakeTable(rows)
        monkeypatch.setattr(retrieval.store, "connect", lambda _p: table)
        return table

    return _factory


def test_explicit_corpus_uses_single_norma_where_clause(_patch, monkeypatch) -> None:
    rows = [_row("gdpr", "5"), _row("gdpr", "6")]
    table = _patch(rows)
    monkeypatch.setattr(
        retrieval.reranker, "rerank", lambda _q, _p, top_n: [(0, 0.9), (1, 0.8)]
    )
    out = retrieval.run("q", "gdpr", "es", top_k=5)
    assert table.search_obj.where_clause == "norma = 'gdpr' AND language = 'es'"
    assert [c.norma for c in out] == ["gdpr", "gdpr"]


def test_auto_drops_norma_filter_and_applies_gate(_patch, monkeypatch) -> None:
    # 4 gdpr + 1 nis2 in rerank order -> 4/5 = 0.8 >= 0.6 -> collapse to gdpr.
    rows = [
        _row("gdpr", "1"), _row("gdpr", "2"), _row("gdpr", "3"),
        _row("gdpr", "4"), _row("nis2", "9"),
    ]
    table = _patch(rows)
    monkeypatch.setattr(
        retrieval.reranker,
        "rerank",
        lambda _q, _p, top_n: [(0, 0.9), (1, 0.85), (2, 0.8), (3, 0.75), (4, 0.5)],
    )
    monkeypatch.setattr(
        retrieval.loader,
        "get_manifest_meta",
        lambda _c: {"version": "v", "source_url": "u"},
    )
    out, resolved = retrieval.run_auto("q", "es", retrieval.RetrievalConfig())
    assert "norma" not in (table.search_obj.where_clause or "")
    assert table.search_obj.where_clause == "language = 'es'"
    assert resolved == ["gdpr"]
    assert all(c.norma == "gdpr" for c in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_retrieval_run_branches.py -q --no-cov`
Expected: FAIL (`run_auto` not defined; explicit `run` test should already pass — it pins the unchanged behaviour).

- [ ] **Step 3: Refactor `run()` minimally + add `run_auto()`**

Keep `run()` signature/behaviour for explicit corpora byte-identical. Extract the `candidates → rerank → RetrievedChunk` enrichment into a shared private helper so the auto path reuses it without duplicating. Add `run_auto()`:

```python
def _enrich(
    candidates: list[dict], reranked: list[tuple[int, float]], corpus_for_meta: str
) -> list[RetrievedChunk]:
    meta = loader.get_manifest_meta(corpus_for_meta)
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


def run(query: str, corpus: Norma, language: Language, top_k: int = 5) -> list[RetrievedChunk]:
    """Explicit-corpus retrieval. BYTE-IDENTICAL behaviour to v0.1.5-h15
    (single-`norma` where-clause; no purity gate). `corpus` is one of the four
    norms — never "auto" (the graph routes "auto" to run_auto)."""
    [query_vec] = embeddings.embed([query])
    table = store.connect(INDEX_PATH)
    where_clause = f"norma = '{corpus}' AND language = '{language}'"
    candidates = table.search(query_vec).where(where_clause).limit(PRE_RERANK).to_list()
    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=top_k)
    if not reranked:
        return []
    return _enrich(candidates, reranked, corpus)


def run_auto(
    query: str, language: Language, cfg: RetrievalConfig
) -> tuple[list[RetrievedChunk], list[str]]:
    """H15.1 cross-corpus path (ADR-0017): multi-corpus retrieve -> rerank ->
    post-rerank purity gate. Returns (chunks, resolved_normas)."""
    [query_vec] = embeddings.embed([query])
    table = store.connect(INDEX_PATH)
    where_clause = f"language = '{language}'"
    candidates = (
        table.search(query_vec).where(where_clause).limit(cfg.pre_rerank).to_list()
    )
    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=cfg.pre_rerank)
    if not reranked:
        return [], []
    ranked_pairs = [(candidates[idx]["norma"], (idx, score)) for idx, score in reranked]
    kept, resolved = _apply_purity_gate(ranked_pairs, cfg)
    enriched = _enrich(candidates, [p for _, p in kept], resolved[0] if resolved else "")
    return enriched, resolved
```

Note: `_enrich`'s `corpus_for_meta` is only used for `version`/`source_url`; on the multi-corpus branch each kept chunk may belong to a different norma, so `_enrich` must look up meta **per chunk**. Fix `_enrich` to resolve meta by `candidates[idx]["norma"]` (correctness — a DORA chunk must carry DORA's version/url):

```python
def _enrich(
    candidates: list[dict], reranked: list[tuple[int, float]]
) -> list[RetrievedChunk]:
    out: list[RetrievedChunk] = []
    for idx, score in reranked:
        c = candidates[idx]
        meta = loader.get_manifest_meta(c["norma"])
        out.append(
            RetrievedChunk(
                chunk_id=c["chunk_id"], norma=c["norma"], articulo=c["articulo"],
                apartado=c["apartado"], language=c["language"], text=c["text"],
                score=score, version=meta["version"], source_url=meta["source_url"],
            )
        )
    return out
```

Update both `run()` and `run_auto()` to call `_enrich(candidates, reranked)` (drop the 3rd arg). Update the Task-3 test's explicit assertion accordingly (it already only asserts `.norma`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_retrieval_run_branches.py tests/unit/test_purity_gate.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Run the existing retrieval/MCP regression to prove explicit path unchanged**

Run: `uv run pytest tests/ -q --no-cov -k "retriev or search_articles or rag"`
Expected: PASS (explicit-corpus behaviour byte-identical; `_enrich` per-chunk meta is behaviour-neutral for single-corpus since all chunks share the norma).

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_retrieval_run_branches.py src/regulaitor/rag/retrieval.py
SKIP=gitleaks git commit -m "feat(h15.1): run_auto multi-corpus path; explicit run() byte-identical"
```

---

### Task 4: Thread `"auto"` through the type boundary (pass-through only)

**Files:**
- Modify: `src/regulaitor/api/schemas.py:43`, `src/regulaitor/orchestration/state.py:24`, `src/regulaitor/orchestration/graph.py` (`run()` cast + `_retriever_node`), `src/regulaitor/agents/retriever.py`, `src/regulaitor/mcp_server/tools.py`
- Test: `tests/unit/test_auto_threading.py` (create)

**Routing decision:** `RetrieverAgent.retrieve` dispatches on `corpus`: explicit → `rag_retrieval.run` (unchanged); `"auto"` → `rag_retrieval.run_auto` with `DEFAULT_CONFIG`, and populates `Context.resolved_normas`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_auto_threading.py
from __future__ import annotations

import pytest

from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.rag import retrieval


def test_retriever_explicit_corpus_calls_run_not_auto(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(retrieval, "run", lambda *a, **k: (called.setdefault("run", a), [])[1])
    monkeypatch.setattr(
        retrieval, "run_auto", lambda *a, **k: called.setdefault("auto", a) or ([], [])
    )
    monkeypatch.setattr(retrieval.embeddings, "model_identifier", lambda: "m")
    ctx = RetrieverAgent().retrieve("q", "gdpr", "es")
    assert "run" in called and "auto" not in called
    assert ctx.corpus == "gdpr"
    assert ctx.resolved_normas == ["gdpr"]


def test_retriever_auto_calls_run_auto_and_sets_resolved(monkeypatch) -> None:
    monkeypatch.setattr(
        retrieval, "run_auto", lambda q, lang, cfg: ([], ["nis2", "dora"])
    )
    monkeypatch.setattr(retrieval.embeddings, "model_identifier", lambda: "m")
    ctx = RetrieverAgent().retrieve("q", "auto", "es")
    assert ctx.corpus == "auto"
    assert ctx.resolved_normas == ["nis2", "dora"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_auto_threading.py -q --no-cov`
Expected: FAIL (`RetrieverAgent.retrieve` does not branch on `"auto"`, no `resolved_normas`).

- [ ] **Step 3: Apply the type-widen + dispatch changes**

`src/regulaitor/api/schemas.py:43` —
`corpus: Literal["ai_act", "gdpr", "nis2", "dora"]` →
`corpus: Literal["ai_act", "gdpr", "nis2", "dora", "auto"]`

`src/regulaitor/orchestration/state.py` — change the import (line 14) to add `CorpusSelector` and `corpus: Norma` (line 24) → `corpus: CorpusSelector`:
```python
from regulaitor.corpus.schemas import CorpusSelector, Language, Norma  # noqa: F401
```
```python
    corpus: CorpusSelector
```

`src/regulaitor/orchestration/graph.py` — line 250 `corpus=cast(Norma, corpus)` → `corpus=cast(CorpusSelector, corpus)`; add `CorpusSelector` to the line-28 import. `_retriever_node` (line 99) is unchanged (it forwards `state.corpus`).

`src/regulaitor/agents/retriever.py` — replace the whole `retrieve` method:
```python
    def retrieve(
        self,
        query: str,
        corpus: CorpusSelector,
        language: Language,
        top_k: int = 5,
    ) -> Context:
        if corpus == "auto":
            chunks, resolved = rag_retrieval.run_auto(
                query, language, rag_retrieval.DEFAULT_CONFIG
            )
        else:
            chunks = rag_retrieval.run(query, corpus, language, top_k=top_k)
            resolved = [corpus]
        return Context(
            query=query,
            corpus=corpus,
            language=language,
            chunks=chunks,
            retrieved_at=datetime.now(tz=UTC),
            embedding_model=embeddings.model_identifier(),
            resolved_normas=resolved,
        )
```
Add `CorpusSelector` to the retriever's `corpus.schemas` import.

`src/regulaitor/mcp_server/tools.py` — `search_articles` `corpus: Norma` → `corpus: CorpusSelector`; body: if `corpus == "auto"` return `rag_retrieval.run_auto(query, language, rag_retrieval.DEFAULT_CONFIG)[0]` else `rag_retrieval.run(query, corpus, language, top_k=top_k)`. Add `CorpusSelector` import.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_auto_threading.py -q --no-cov`
Expected: PASS (2 passed).

- [ ] **Step 5: Full regression (type-widen must not break consumers)**

Run: `uv run pytest -m "not slow" -q`
Expected: green, coverage ≥90%. (Resolves any contract test that pins the `corpus` enum — update such a test's expected enum to include `"auto"` if and only if it asserts the schema literal; do NOT loosen behavioural assertions.)

- [ ] **Step 6: Commit**

```bash
git add -A
SKIP=gitleaks git commit -m "feat(h15.1): thread corpus=auto through api/graph/retriever/mcp (pass-through)"
```

---

### Task 5: Eval harness + gold set `"auto"` end-to-end

**Files:**
- Modify: `evals/schemas.py` (`GoldCaseChat.corpus_esperado`), `evals/harness.py` (already forwards `corpus=case.corpus_esperado` to `run()` at ~line 211 — only the type widens), `evals/gold_set.jsonl` (xcorpus-001/002)
- Test: `tests/unit/test_harness_auto_case.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_harness_auto_case.py
from __future__ import annotations

from evals.schemas import GoldCaseChat


def test_goldcasechat_accepts_auto_corpus() -> None:
    gc = GoldCaseChat.model_validate(
        {
            "id": "xcorpus-001",
            "tipo": "chat",
            "entrada": "q",
            "corpus_esperado": "auto",
            "articulos_esperados": ["1", "47"],
            "severidad_esperada": "high",
            "criterios_evaluacion": ["c"],
            "salida_esperada": None,
            "requiere_revision_humana": True,
            "expected_verdict": "requires_human_review",
        }
    )
    assert gc.corpus_esperado == "auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_harness_auto_case.py -q --no-cov`
Expected: FAIL (`corpus_esperado` typed `Norma`, rejects `"auto"`).

- [ ] **Step 3: Widen `GoldCaseChat.corpus_esperado`**

In `evals/schemas.py`, change `GoldCaseChat.corpus_esperado` from `Norma` to `CorpusSelector` (add the `from regulaitor.corpus.schemas import CorpusSelector` import). Leave `GoldCaseDoc` unchanged (doc-mode out of scope).

- [ ] **Step 4: Flip xcorpus gold cases to `"auto"`**

In `evals/gold_set.jsonl`, lines for `xcorpus-001` and `xcorpus-002`: change `"corpus_esperado":"dora"` → `"corpus_esperado":"auto"` (xcorpus-001) and `"corpus_esperado":"nis2"` → `"corpus_esperado":"auto"` (xcorpus-002). **Leave `articulos_esperados` unchanged** (`["1","47"]`, `["23","35"]` — the correctness expectation; the cross-corpus fix is judged per-case by whether `resolved_normas` now spans both corpora + the LLM-judge criteria, NOT by the granularity-confounded exact-match metric — documented in the study report).

- [ ] **Step 5: Run test + harness import smoke**

Run: `uv run pytest tests/unit/test_harness_auto_case.py -q --no-cov && uv run python -c "import evals.harness"`
Expected: PASS + clean import.

- [ ] **Step 6: Commit**

```bash
git add evals/schemas.py evals/gold_set.jsonl tests/unit/test_harness_auto_case.py
SKIP=gitleaks git commit -m "feat(h15.1): gold xcorpus-001/002 -> corpus=auto; harness accepts auto"
```

---

### Task 6: $0 pre-paid verification gate (no-leakage + safety baseline)

**Files:**
- Test: `tests/unit/test_explicit_path_unchanged.py` (create)
- No production change. This task PROVES the HARD guards before any paid spend.

- [ ] **Step 1: Write the explicit-path-unchanged assertion test**

```python
# tests/unit/test_explicit_path_unchanged.py
"""HARD guard: the explicit-corpus retrieval path must be byte-identical to
v0.1.5-h15 (single-norma where-clause, no gate). This pins it."""
from __future__ import annotations

import pytest

from regulaitor.rag import retrieval


def test_explicit_where_clause_is_exactly_single_norma(monkeypatch) -> None:
    captured = {}

    class _S:
        def where(self, c): captured["w"] = c; return self
        def limit(self, _n): return self
        def to_list(self): return []

    class _T:
        def search(self, _v): return _S()

    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: _T())
    monkeypatch.setattr(retrieval.reranker, "rerank", lambda *a, **k: [])
    out = retrieval.run("q", "nis2", "en", top_k=5)
    assert out == []
    assert captured["w"] == "norma = 'nis2' AND language = 'en'"
```

- [ ] **Step 2: Run it — must PASS immediately** (it asserts the unchanged contract)

Run: `uv run pytest tests/unit/test_explicit_path_unchanged.py -q --no-cov`
Expected: PASS.

- [ ] **Step 3: Authoritative gate**

Run: `uv run pytest -m "not slow" -q`
Expected: green; record exact `N passed`, `1 skipped` (the expected `ANTHROPIC_API_KEY` integration skip), `Total coverage: NN%` ≥90%. If <90% → STOP, report BLOCKED with the real number (H13/H14 false-alarm lesson; use `--junit-xml=C:\tmp\h15_1_gate.xml` parsed via `xml.etree` for the exact count — the Git-bash pipe eats pytest's summary line).

- [ ] **Step 4: Safety baseline ($0 deterministic, prompt-blind)**

Run: `uv run python -m scripts.redteam --smoke` then read `redteam/reports/latest.md` `block_rate`. Expected: **0.92** (== frozen §16.2#4). Then `git checkout HEAD -- redteam/reports/latest.md` (restore canonical; the run is deterministic + prompt-blind so identical-substance — H15 precedent). Record the value for the study report.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_explicit_path_unchanged.py
SKIP=gitleaks git commit -m "test(h15.1): pin explicit-corpus path unchanged (HARD no-leakage guard)"
```

---

### Task 7: ADR 0017 — cross-corpus `auto` + purity gate

**Files:**
- Create: `docs/adr/0017-retriever-cross-corpus-auto.md`

- [ ] **Step 1: Write ADR 0017** mirroring `docs/adr/0015-nis2-dora-corpus.md` structure exactly (read it first): `# ADR 0017 — Retriever cross-corpus auto path + post-rerank purity gate (H15.1)`; `**Status:** Accepted — 2026-05-19 — squash \`<squash-sha>\`, tag \`v0.1.6-h15.1\``; `**Deciders:**`; `**Companion ADRs:** 0004 (RAG architecture — this extends the retrieval pipeline), 0016 (H15 calibration — the system-level ceiling this attacks; same frozen-control A/B discipline), 0013 (eval-override seam precedent)`; `## Context` (the §22.18-stable single-corpus no-leakage vs the structural cross-corpus gap; required-`corpus` API field; H15 documented context_precision ceiling); `## Decision` D1–D5 verbatim from the spec §2; `## Consequences` (positive: opt-in additive, explicit path byte-identical/regression-zero-by-construction, LLM-free retriever preserved, §6 invariant intact; negative/accepted-honest: purity-threshold is a tuned heuristic, xcorpus N=2 defended by correctness not aggregate, auto-path reranks more candidates = local latency only, the citation-metric granularity confound persists on xcorpus expected-articles and is documented not fixed); `## Alternatives considered` (pre-retrieval centroid router; LLM router; always-multi-corpus — all rejected with the brainstorming reasons); `## References` (spec `docs/superpowers/specs/2026-05-19-h15-1-retriever-optimization-design.md`, plan, decisions §H15.1, ADR-0016).

- [ ] **Step 2: Commit**

```bash
git add docs/adr/0017-retriever-cross-corpus-auto.md
SKIP=gitleaks git commit -m "docs(h15.1): ADR 0017 — cross-corpus auto path + purity gate"
```

---

### Task 8: USER-GATED A/B candidate runs (≤3 RetrievalConfig iterations)

**This task is executed by the CONTROLLER, not a subagent (H14 lesson). Each paid run: `--limit 3` probe → cost-tally + explicit user OK + user credit confirmation → full run as a persistent background job.**

- [ ] **Step 1: Wire a config selector for the A/B (eval-only, mirrors the H15 env-seam pattern)**

Add an eval-only override so a candidate `RetrievalConfig` can be selected without changing production defaults: an env var `REGULAITOR_RETRIEVAL_CONFIG` (JSON, e.g. `{"pre_rerank":80,"top_k":8,"purity_threshold":0.55}`) read **once** in `rag/retrieval.DEFAULT_CONFIG` construction; unset → frozen defaults (production byte-identical). TDD it like Task 1–3 ($0 unit test: unset → defaults; valid JSON → overridden; invalid → WARNING + defaults). Commit `feat(h15.1): eval-only REGULAITOR_RETRIEVAL_CONFIG override (frozen-default inert)`.

- [ ] **Step 2: `--limit 3` probe (≈€0.15) — USER-GATED**

Controller posts the running H15.1 cost tally, requests explicit user OK + credit confirmation, then runs as a background job:
`uv run --env-file .env python -m scripts.h15_run --version v1.2 --cases-file evals/h15_calibration_ids.txt --tag h15_1-cand1-probe --limit 3` (Analyst stays v1.2; the variable is `REGULAITOR_RETRIEVAL_CONFIG`). Verify clean exit + cost; abort/iterate if anomalous.

- [ ] **Step 3: Full 30-calibration candidate run — USER-GATED**

After probe OK + fresh user OK: background job, no `--limit`, tag `h15_1-cand1`, against `evals/h15_calibration_ids.txt` (30; xcorpus-001/002 now `"auto"`). Snapshot to `evals/reports/h15_1/cand1.md` (mirror `scripts/h15_run` isolation). Compare vs the committed frozen control `evals/reports/h15/candidate-v1.2.md` using `scripts/h15_ab_compare.ab_delta`. Report per-case xcorpus-001/002 (correctness, `resolved_normas` + judge criteria) **separately** from the 28-explicit aggregate delta.

- [ ] **Step 4: ≤2 further iterations only if directionally justified**

If cand1 shows no movement, iterate the `RetrievalConfig` (≤3 total) with the same probe→OK→background discipline. Stop at the first config that improves the 28-explicit aggregate without regressing no-leakage/safety, OR after 3 iterations document the deeper ceiling (D5 honest outcome — both defend). No metric-gaming.

- [ ] **Step 5: Commit the evidence**

Force-add the gitignored `evals/reports/h15_1/*` (H12/H15 evidence precedent) + the chosen frozen `RetrievalConfig` (the production default is updated to the winning config ONLY if it improved without regression; else production defaults stay = v0.1.5-h15 and only the correctness `auto` path ships). Commit `test(h15.1): A/B candidate evidence + frozen RetrievalConfig`.

---

### Task 9: USER-GATED holdout (measured ONCE)

- [ ] **Step 1: `--limit 3` holdout probe — USER-GATED** (de-risk the hardened harness live, H15 lesson): background `... --cases-file evals/h15_holdout_chat_ids.txt --tag h15_1-holdout-probe --limit 3`.

- [ ] **Step 2: Full 14-case holdout, ONCE, on the frozen winner config — USER-GATED**

After probe OK + fresh user OK + credit confirmation: background job, tag `h15_1-holdout`, `evals/h15_holdout_chat_ids.txt` (14 H14 chat). **Measured once, never iterated** (D4). Compare vs the committed `evals/reports/h15/holdout-v1.2-chat.md`. Honest-defer (document partial, no re-run/hack) if sustained external API degradation recurs (H15 precedent).

- [ ] **Step 3: Commit** force-added `evals/reports/h15_1/holdout.md` evidence. `test(h15.1): holdout single measurement evidence`.

---

### Task 10: `docs/retriever_optimization.md` — honest study report [Opus]

**Files:**
- Create: `docs/retriever_optimization.md`

- [ ] **Step 1: Write the report** (Opus subagent; numbers ONLY from committed `evals/reports/h15_1/*` + the frozen `evals/reports/h15/*` control; never invented). Sections: (1) Goal & honest framing (the documented context_precision ceiling H15 left; §22.22 — not metric-gaming); (2) Architecture recap (opt-in auto + purity gate; explicit path byte-identical); (3) Method (single variable = retriever; frozen control = committed H15 reports, **no re-baseline**; the eval-only `REGULAITOR_RETRIEVAL_CONFIG`; calibration 30 / holdout 14 once; ≤3 iterations); (4) **Cross-corpus correctness result** — xcorpus-001/002 **per-case** (resolved_normas now spans both corpora? judge criteria? — defended by correctness, explicitly NOT folded into the 30-mean); (5) **Tuning-lever A/B** — the 28-explicit + 12-holdout `ab_delta` table vs the frozen control, honest: measured improvement OR documented deeper ceiling; (6) HARD non-regression — explicit-path-unchanged (structural + asserted), redteam-smoke 0.92, the 6 H15 block cases content-safe (C1 manual backstop carried, per-case); (7) Honest interpretation & verdict (no overclaim; if no tuning improvement, ship only the correctness fix + document the deeper ceiling — the H15 honest-ceiling precedent); (8) Real measured cost (router accumulator, itemized, vs the ~$10 ceiling; re-baseline saved ≈€1.85); (9) Caveats (N small; the citation-metric granularity confound persists on xcorpus expected-articles and is documented not fixed; judge same provider family ADR-0010).

- [ ] **Step 2: Commit** `docs(h15.1): retriever optimization study report`.

---

### Task 11: Closure [Opus] (controller does squash/tag/memory)

**Files:**
- Create/Modify: `docs/technical_decisions_log.md` (expand §H15.1), `docs/evidence_matrix.md`, `CLAUDE.md`

- [ ] **Step 1: Full gate** `uv run pytest -m "not slow" -q` → record exact `N passed / 0 failed / 1 expected-skip`, coverage NN% ≥90% (junit-xml for the exact count). If <90% STOP/BLOCKED with the real number.

- [ ] **Step 2: Expand decisions §H15.1** — the section already exists (planning stub from `5fd2fad`). Replace the closing `*(Sección a ampliar al cierre…)*` line with the closed record: D1–D5 outcomes, the auto-path + purity-gate architecture, the cross-corpus correctness result (per-case), the tuning-lever A/B (honest: improvement or documented deeper ceiling), HARD non-regression result, real measured cost, the two-stage-review-caught defects, and end exactly: `H15.1 cerrado 2026-05-19. Squash \`<squash-sha>\`, tag \`v0.1.6-h15.1\` (post-merge).`

- [ ] **Step 3: evidence_matrix + CLAUDE.md §27** — evidence_matrix: Módulo-3 retriever row → ✅ H15.1 + `docs/retriever_optimization.md` + headline (cross-corpus correctness + tuning delta or documented ceiling); refresh state header to H15.1-closed; ADR-count gate → 0001–0017 (17 ADRs — verify `ls docs/adr/*.md | wc -l`); decisions-log line-count reference updated (`wc -l`). CLAUDE.md: §16.3 mark H15.1 done; move H15.1 into `### Hitos cerrados` (dense, mirror H15 bullet density: opt-in auto path, explicit-path byte-identical, cross-corpus-by-correctness, tuning honest outcome, HARD guards, real cost, tag `v0.1.6-h15.1`, squash `<squash-sha>` post-merge, "Ver §H15.1"); `### Hito siguiente` → **H16 — Despliegue público MVP (Hugging Face Spaces)**.

- [ ] **Step 4: Commit** `docs(h15.1): close milestone — decisions §H15.1 + evidence_matrix + CLAUDE.md §27`.

- [ ] **Step 5: Hand off to finishing-a-development-branch** (CONTROLLER, USER-GATED): final whole-branch review → user picks finish option → squash-merge `feat(h15.1): retriever optimization` → annotated tag `v0.1.6-h15.1` on the squash commit → post-merge `docs(h15.1): populate post-merge SHA` filling every `<squash-sha>` → delete branch → memory roll-forward `h15_closed_h16_starting.md` → `h15-1_closed_h16_starting.md` + MEMORY.md index.

---

## Self-Review

**Spec coverage:** §1 goal → T1–T9; §2 D1 scope → plan is retriever-only (no segmenter/no-Answer/Auditor tasks); D2 contained levers → T2 `RetrievalConfig`, no re-ingest task exists; D3 explicit byte-identical + auto gate → T3 (+T6 asserted); D4 frozen control/no re-baseline/≤3 iter/USER-GATED → T8–T9; D5 honest done-when → T8.4/T10.7. §3 architecture file table → T1–T5 one task per boundary. §4 A/B method → T8–T9. §5 HARD guards → T6 (explicit-path + redteam-smoke) + T8.4/T9 (safety per-candidate). §6 done-when → T10/T11. §7 deliverables → all tasks. §8 out-of-scope → no task touches segmenter/Auditor/re-ingest/LLM-routing. §9 risks → purity threshold (T2 tests + T8 A/B), PRE_RERANK starvation (T8 iteration lever), xcorpus N=2 (T8.3/T10 per-case correctness), no improvement (T8.4/T10 honest ceiling), schema regressions (T4.5 full gate). No gaps.

**Placeholder scan:** `<squash-sha>` is the deliberate post-merge-filled token (H1–H15 pattern), not a gap. Task 8/9 paid steps are explicit USER-GATED controller procedures with exact commands. `RetrievalConfig` default `purity_threshold=0.6` is pinned (justified: a clearly single-corpus query yields ≥3/5 same-norma in the top-5; it is also an explicit A/B lever). No "TBD"/"add error handling"/"similar to Task N".

**Type consistency:** `CorpusSelector` (defined T1 `corpus/schemas.py`) used identically in `Context` (T1), `ChatState`/`api`/`graph`/`retriever`/`mcp` (T4), `GoldCaseChat` (T5). `RetrievalConfig`/`DEFAULT_CONFIG`/`_apply_purity_gate`/`run_auto` signatures defined in T2–T3 and consumed unchanged in T4 (`run_auto(query, language, cfg) -> (chunks, resolved)`), T8 (`REGULAITOR_RETRIEVAL_CONFIG` → `DEFAULT_CONFIG`). `_enrich(candidates, reranked)` 2-arg final form consistent across T3. No drift.
