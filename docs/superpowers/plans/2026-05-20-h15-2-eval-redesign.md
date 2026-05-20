# H15.2 — Eval Rede-design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the H15.1 §22.22 design-defect by wiring `DEFAULT_CONFIG.top_k`/`pre_rerank` into the explicit-corpus `rag.retrieval.run()` via a default-None pattern, so the existing 30-case calibration A/B genuinely measures the tuning lever for the first time, while keeping production behavior BYTE-IDENTICAL to `v0.1.6-h15.1` when `REGULAITOR_RETRIEVAL_CONFIG` is unset.

**Architecture:** The H15.1 implementation chose a conservative interpretation of T6 — hardcoding `PRE_RERANK=50` and `top_k=5` inside `run()` even though T6 only asserts the WHERE-CLAUSE byte-identicality. H15.2 surgically reinterprets T6 at its actual narrower scope and threads `DEFAULT_CONFIG` consumption into `run()` via per-call resolution of `None` parameters. The WHERE-CLAUSE construction stays byte-identical character-for-character under both env-unset (production) and env-set (eval) states. `_enrich`/`run_auto`/`_apply_purity_gate` are untouched. §6 (Auditor + citation/validator) is byte-unchanged.

**Tech Stack:** Python 3.11, Pydantic v2, LanceDB, BGE-M3 embeddings + `bge-reranker-v2-m3` (local, $0 for retrieval), `uv`, pytest, the H15 eval harness + router cost accumulator (`models/router.py` `_record_cost_eur` / `get_accumulated_cost_eur`).

---

## Conventions (apply to every task)

- **Branch:** all tasks land on `feat/h15-2-eval-redesign` (created from `main @ 2540dcb`, the post-H15.1-close tip). `finishing-a-development-branch` (post-T10) squash-merges to `main` + tag `v0.1.7-h15.2` + post-merge populate of `<squash-sha>` placeholders + memory roll-forward (H1–H15.1 established pattern).
- **Commits:** conventional, **NO** AI/Co-Authored footer. Local commits use `SKIP=gitleaks git commit ...` — **NEVER** `--no-verify`. PowerShell quirk: use `$env:SKIP="gitleaks"; git commit -F c:\tmp\msg.txt` for multi-line messages (here-strings can break on embedded quotes).
- **Gate:** the authoritative gate is `uv run pytest -m "not slow"` (CI-equivalent) with coverage **≥90%** AND `uv run mypy src` exit 0 (T4 cross-milestone gate-hygiene pattern carried from H15.1). A single-file `pytest path::test -v` is only for the red/green TDD loop. Use `pytest --junit-xml=C:\tmp\X.xml` for exact test-count assertions.
- **Script invocation that needs secrets:** `uv run --env-file .env python -m scripts.X` (bare `python -m` does NOT load `.env` — H13 lesson). Tasks 1–5 + 9–10 are **$0** (no secrets, local only).
- **Paid runs (T6, T7, T8) are USER-GATED:** the controller (not a subagent) executes them as persistent background jobs, each preceded by a `--limit 3` probe + a running cost-tally + explicit user OK + user credit confirmation. H14 lesson: never delegate a 30–100 min paid job to a subagent. Real cost via `models/router.py` `get_accumulated_cost_eur()` — no new instrument.
- **§22.22 honesty:** never present a non-measured number as measured; the done-when is "measured improvement OR documented deeper system-level ceiling — both defend"; **no promised metric number**; **REVERT any candidate that improves a metric but regresses no-leakage or safety**.
- **Frozen control:** `evals/reports/h15/candidate-v1.2.md` (H15 30-calibration). **NO paid re-baseline** — H15.2 env-unset behavior is byte-identical to v0.1.6-h15.1 / v0.1.5-h15 by construction (asserted by the new keystone test).
- **HARD-revert checks** (run before every closure / before promoting any candidate to production defaults): T6 WHERE-CLAUSE green under env-unset AND env-set; H15 30-calib `citation_recall` carry-forward ≥0.71; redteam-smoke `block_rate` ≥0.92 (prompt-blind); 6 H15 designated block cases (chat-014/015/029/030 + nis2-006/dora-006) content-safe under winning config (C1 manual backstop carried).

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/regulaitor/rag/retrieval.py` | `run()` signature evolution to `top_k=None, pre_rerank=None`; per-call resolution from `DEFAULT_CONFIG`; WHERE-CLAUSE byte-identical | T2 |
| `src/regulaitor/agents/retriever.py` | `RetrieverAgent.retrieve(top_k=None)` pass-through | T3 |
| `src/regulaitor/mcp_server/tools.py` | `search_articles(top_k=None)` pass-through | T3 |
| `tests/unit/test_explicit_path_unchanged.py` (T6) | **UNCHANGED** — already asserts only WHERE-CLAUSE + empty short-circuit; carries forward | T2 (verify green) |
| `tests/unit/test_explicit_config_wired.py` (NEW) | Keystone proof: env-unset → defaults; env-set → override; WHERE-CLAUSE byte-identical both states | T1 |
| `tests/unit/agents/test_retriever.py:83` | Update `top_k=5` assertion → `top_k=None` (pass-through behavior change) | T3 |
| `docs/adr/0018-retriever-config-wired-into-explicit-path.md` (NEW) | Constraint-reinterpretation ADR; T6 scope clarified | T5 |
| `docs/retriever_h15-2_redesign.md` (NEW) | Honest H15.2 study report (~250–350 lines) | T9 |
| `evals/reports/h15/h15_2-cand1-probe.md` (NEW, force-add) | cand-1 3-case probe report | T6 |
| `evals/reports/h15/h15_2-cand1.md` (NEW, force-add) | cand-1 30-case full report | T6 |
| `evals/reports/h15/h15_2-cand2-probe.md` (NEW, force-add) | cand-2 3-case probe report | T7 |
| `evals/reports/h15/h15_2-cand2.md` (NEW, force-add) | cand-2 30-case full report | T7 |
| `evals/reports/h15/h15_2-holdout.md` (NEW, force-add) | Holdout 14-case report (only if winner) | T8 |
| `docs/technical_decisions_log.md`, `docs/evidence_matrix.md`, `CLAUDE.md` | Closure + named microhito follow-ups | T10 |

---

### Task 1: TDD the keystone wiring test (FAILS by design against current code)

**Files:**
- Create: `tests/unit/test_explicit_config_wired.py`

**Context:** This is the central H15.2 proof. It must assert three properties simultaneously:
1. **env-unset** → `run()` uses `top_k=5, pre_rerank=50` (production-byte-identical to v0.1.6-h15.1).
2. **env-set** (via monkeypatched `DEFAULT_CONFIG`) → `run()` uses the override values.
3. **WHERE-CLAUSE** = exactly `f"norma = '{corpus}' AND language = '{language}'"` under BOTH env states (the no-leakage carry — the central H15.2 proof).

The test monkeypatches `retrieval.DEFAULT_CONFIG` at module-attribute level (the same pattern H15.1 uses for the auto-path tests) so we don't need to re-import the module or manipulate `os.environ` at test time. This relies on the implementation reading `DEFAULT_CONFIG.top_k`/`DEFAULT_CONFIG.pre_rerank` at CALL TIME (attribute access on the module), not capturing the values at function-definition time — a critical implementation requirement that T2 must honor.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_explicit_config_wired.py
"""H15.2 keystone proof — the explicit-corpus retrieval path must:
(a) under env-unset, use DEFAULT_CONFIG.top_k=5 and DEFAULT_CONFIG.pre_rerank=50
    (production byte-identical to v0.1.6-h15.1);
(b) under env-set (monkeypatched DEFAULT_CONFIG), use the override values
    (closes the §22.22 design-defect disclosed POST-SPEND in H15.1-T10/T11);
(c) WHERE-CLAUSE construction stays byte-identical character-for-character under
    BOTH env states (the no-leakage carry; T6 §22.18/H14 invariant scope).

Property (c) is the central proof: the §22.18/H14 no-leakage guarantee is
about cross-corpus contamination (the where-clause), NOT about specific
top_k/pre_rerank values — H15.2 corrects the H15.1 implementation's
conservative interpretation of T6 at the architecturally-correct narrower scope.
"""
from __future__ import annotations

from regulaitor.rag import retrieval


class _SearchStub:
    """Captures the `.limit(N)` argument and the where-clause."""

    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def where(self, c: str):  # type: ignore[no-untyped-def]
        self._captured["where_clause"] = c
        return self

    def limit(self, n: int):  # type: ignore[no-untyped-def]
        self._captured["pre_rerank"] = n
        return self

    def to_list(self):  # type: ignore[no-untyped-def]
        return []  # empty -> short-circuit returns [] (T6 carry; no _enrich path needed)


class _TableStub:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def search(self, _v):  # type: ignore[no-untyped-def]
        return _SearchStub(self._captured)


def _install_stubs(monkeypatch, captured: dict) -> None:
    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: _TableStub(captured))

    def _rerank_stub(_q, _passages, top_n: int):
        captured["top_n"] = top_n
        return []  # empty -> run() returns [] without entering _enrich

    monkeypatch.setattr(retrieval.reranker, "rerank", _rerank_stub)


def test_env_unset_uses_default_config_defaults(monkeypatch) -> None:
    """Production-byte-identical: DEFAULT_CONFIG() defaults → top_k=5, pre_rerank=50."""
    monkeypatch.setattr(retrieval, "DEFAULT_CONFIG", retrieval.RetrievalConfig())
    captured: dict = {}
    _install_stubs(monkeypatch, captured)

    out = retrieval.run("q", "ai_act", "es")

    assert out == []
    assert captured["pre_rerank"] == 50  # DEFAULT_CONFIG.pre_rerank
    assert captured["top_n"] == 5  # DEFAULT_CONFIG.top_k
    assert captured["where_clause"] == "norma = 'ai_act' AND language = 'es'"


def test_env_set_overrides_default_config(monkeypatch) -> None:
    """Override flows through: DEFAULT_CONFIG(pre_rerank=80, top_k=3) → run() uses those."""
    monkeypatch.setattr(
        retrieval,
        "DEFAULT_CONFIG",
        retrieval.RetrievalConfig(pre_rerank=80, top_k=3),
    )
    captured: dict = {}
    _install_stubs(monkeypatch, captured)

    out = retrieval.run("q", "gdpr", "en")

    assert out == []
    assert captured["pre_rerank"] == 80
    assert captured["top_n"] == 3
    assert captured["where_clause"] == "norma = 'gdpr' AND language = 'en'"


def test_explicit_top_k_overrides_default_config(monkeypatch) -> None:
    """Backward-compat: callers passing explicit top_k still win (per-call override
    survives the wiring change; eval harness + existing tests rely on this)."""
    monkeypatch.setattr(
        retrieval,
        "DEFAULT_CONFIG",
        retrieval.RetrievalConfig(pre_rerank=80, top_k=3),
    )
    captured: dict = {}
    _install_stubs(monkeypatch, captured)

    out = retrieval.run("q", "nis2", "es", top_k=10)

    assert out == []
    assert captured["pre_rerank"] == 80  # DEFAULT_CONFIG (no explicit pre_rerank)
    assert captured["top_n"] == 10  # explicit top_k wins
    assert captured["where_clause"] == "norma = 'nis2' AND language = 'es'"


def test_where_clause_byte_identical_under_both_env_states(monkeypatch) -> None:
    """The central H15.2 proof: WHERE-CLAUSE construction is byte-identical
    under env-unset (DEFAULT_CONFIG()) AND env-set (DEFAULT_CONFIG(80,3)).
    This is the §22.18/H14 no-leakage invariant at its actual narrow scope.
    T6 (tests/unit/test_explicit_path_unchanged.py) asserts this for env-unset;
    this test extends the assertion to env-set, proving the wiring change does
    not touch the no-leakage-critical line."""
    captured_unset: dict = {}
    captured_set: dict = {}

    monkeypatch.setattr(retrieval, "DEFAULT_CONFIG", retrieval.RetrievalConfig())
    _install_stubs(monkeypatch, captured_unset)
    retrieval.run("q", "dora", "es")

    monkeypatch.setattr(
        retrieval,
        "DEFAULT_CONFIG",
        retrieval.RetrievalConfig(pre_rerank=80, top_k=3),
    )
    _install_stubs(monkeypatch, captured_set)
    retrieval.run("q", "dora", "es")

    # Same query, same corpus, same language → WHERE-CLAUSE must be byte-identical
    assert captured_unset["where_clause"] == captured_set["where_clause"]
    assert captured_unset["where_clause"] == "norma = 'dora' AND language = 'es'"
```

- [ ] **Step 2: Run the test suite to verify it FAILS by design**

Run: `uv run pytest tests/unit/test_explicit_config_wired.py -v`

Expected: 4 FAILED. The first three fail with `assert <captured value> == <expected>` because the current `run()` hardcodes `PRE_RERANK=50` (line 199 of `retrieval.py`) and uses the function-parameter `top_k` directly (line 202) — it never consults `DEFAULT_CONFIG`. Specifically:
- `test_env_unset_uses_default_config_defaults`: `captured["pre_rerank"]` will be `50` (matches), `captured["top_n"]` will be `5` (matches, because function default is 5), `where_clause` matches → **this one might pass by coincidence**. Re-check: actually all three values match the current defaults by coincidence in env-unset → may pass. The TRUE failing test is the env-set one.
- `test_env_set_overrides_default_config`: `captured["pre_rerank"]` will be `50` (hardcoded), expected `80` → **FAILS**. `captured["top_n"]` will be `5` (function default), expected `3` → **FAILS**.
- `test_explicit_top_k_overrides_default_config`: `captured["pre_rerank"]` will be `50`, expected `80` → **FAILS**.
- `test_where_clause_byte_identical_under_both_env_states`: WHERE-CLAUSE is built the same way in both cases (matches), so this **PASSES** by coincidence in the current code (the WHERE-CLAUSE truly is byte-identical today; the change won't affect it).

Result: **at least 2 tests must FAIL** (`test_env_set_overrides_default_config` + `test_explicit_top_k_overrides_default_config`). If they don't, the test is wrong. Confirm the failure modes match the diagnosis above before proceeding.

- [ ] **Step 3: Commit the failing test**

```bash
git checkout -b feat/h15-2-eval-redesign  # from main @ 2540dcb
git add tests/unit/test_explicit_config_wired.py
$env:SKIP="gitleaks"; git commit -m "test(h15.2): T1 keystone wiring test (4 properties; env-set FAILS by design pre-T2)"
```

---

### Task 2: Wire `DEFAULT_CONFIG` into `rag/retrieval.run()` (T1 turns green)

**Files:**
- Modify: `src/regulaitor/rag/retrieval.py:177-207` (`run()` function)

**Context:** The wiring change. `run()` signature evolves to `(query, corpus, language, top_k=None, pre_rerank=None)`. When a param is `None`, the function reads from `DEFAULT_CONFIG.top_k` / `DEFAULT_CONFIG.pre_rerank` AT CALL TIME (attribute access on the module-level `DEFAULT_CONFIG`, NOT captured at function-definition time — this is what makes the monkeypatch in T1 work). The WHERE-CLAUSE construction line stays byte-identical character-for-character. `_enrich` / `run_auto` / `_apply_purity_gate` / `RetrievalConfig` / `_config_from_env` / `DEFAULT_CONFIG` initialization are all untouched. The `PRE_RERANK = 50` module constant stays (documents the default value of `RetrievalConfig.pre_rerank`; removing it would be a separate cleanup, out of scope).

- [ ] **Step 1: Apply the wiring change**

Edit `src/regulaitor/rag/retrieval.py`. Replace the entire `run()` function (lines 177–207) with:

```python
def run(
    query: str,
    corpus: Norma,
    language: Language,
    top_k: int | None = None,
    pre_rerank: int | None = None,
) -> list[RetrievedChunk]:
    """Explicit-corpus retrieval. Production-byte-identical to v0.1.6-h15.1 when
    `REGULAITOR_RETRIEVAL_CONFIG` is unset (the env default). `corpus` is one of
    the four norms — never "auto" (the graph routes "auto" to run_auto).

    Resolution of `top_k` / `pre_rerank` (H15.2, ADR-0018 — closes the §22.22
    design-defect disclosed POST-SPEND in H15.1-T10/T11):
      - `top_k=None` -> `DEFAULT_CONFIG.top_k` (default 5) resolved AT CALL TIME.
      - `pre_rerank=None` -> `DEFAULT_CONFIG.pre_rerank` (default 50) resolved
         AT CALL TIME.
      - Explicit non-None values win (per-call override, backward-compatible).

    Call-time resolution (NOT function-definition-time capture) lets the eval
    harness rebind `DEFAULT_CONFIG` via `REGULAITOR_RETRIEVAL_CONFIG` env at
    process start and have the explicit-corpus path consume those values — this
    is exactly what H15.1's 30-calibration A/B was structurally unable to
    measure (the §22.22 defect this milestone closes).

    The `where` clause interpolates `corpus` and `language` directly. Both are
    closed `Literal` enums (`Norma`, `Language`) typed at the function
    boundary, so the values are not user-controlled strings -- no SQL
    injection vector. Pyright/mypy enforce the constraint upstream. The
    construction is byte-identical character-for-character to v0.1.6-h15.1
    under any env state — the no-leakage-critical §22.18/H14 invariant
    (asserted by T6 `tests/unit/test_explicit_path_unchanged.py` for env-unset
    and by `tests/unit/test_explicit_config_wired.py` for env-set).
    """
    effective_top_k = top_k if top_k is not None else DEFAULT_CONFIG.top_k
    effective_pre_rerank = pre_rerank if pre_rerank is not None else DEFAULT_CONFIG.pre_rerank

    [query_vec] = embeddings.embed([query])

    table = store.connect(INDEX_PATH)
    where_clause = f"norma = '{corpus}' AND language = '{language}'"
    candidates = table.search(query_vec).where(where_clause).limit(effective_pre_rerank).to_list()

    passages = [c["text"] for c in candidates]
    reranked = reranker.rerank(query, passages, top_n=effective_top_k)

    if not reranked:
        return []

    return _enrich(candidates, reranked)
```

- [ ] **Step 2: Run the keystone test — expect all 4 PASS**

Run: `uv run pytest tests/unit/test_explicit_config_wired.py -v`

Expected: 4 PASSED. If `test_env_unset_uses_default_config_defaults` still passes, confirms byte-identical default behavior. If `test_env_set_overrides_default_config` now passes, confirms the wiring works. If `test_explicit_top_k_overrides_default_config` passes, confirms backward-compat. If `test_where_clause_byte_identical_under_both_env_states` passes, confirms the no-leakage carry.

- [ ] **Step 3: Run T6 — must STAY green unchanged**

Run: `uv run pytest tests/unit/test_explicit_path_unchanged.py -v`

Expected: 1 PASSED. T6's stub `_S.limit(_n)` ignores its argument (line 21: `def limit(self, _n): return self`), so the change from `.limit(PRE_RERANK)` to `.limit(effective_pre_rerank)` is invisible to T6. T6 only asserts the WHERE-CLAUSE string — that's unchanged.

- [ ] **Step 4: Run all retrieval unit tests — must stay green**

Run: `uv run pytest tests/unit/test_retrieval_run_branches.py tests/unit/test_retrieval_config_env.py tests/unit/test_purity_gate.py tests/unit/test_auto_threading.py tests/unit/rag/test_retrieval.py -v`

Expected: all PASSED (no regressions; the auto path and `_apply_purity_gate` are untouched).

- [ ] **Step 5: Commit the wiring**

```bash
git add src/regulaitor/rag/retrieval.py
$env:SKIP="gitleaks"; git commit -m "feat(h15.2): T2 wire DEFAULT_CONFIG into explicit run() via default-None (T6 unchanged; T1 green)"
```

---

### Task 3: Thread default-None through `RetrieverAgent.retrieve()` and `search_articles()`

**Files:**
- Modify: `src/regulaitor/agents/retriever.py:25-36` (`RetrieverAgent.retrieve`)
- Modify: `src/regulaitor/mcp_server/tools.py:30-44` (`search_articles`)
- Modify: `tests/unit/agents/test_retriever.py:68-83` (the `default_top_k_is_5` test must reflect the new pass-through behavior)

**Context:** Two production wrappers need to accept `top_k=None` and pass it through unchanged. The behavior is: caller passes nothing → wrapper passes `None` → `run()` resolves to `DEFAULT_CONFIG.top_k` (= 5 when env unset → byte-identical to v0.1.6-h15.1). Caller passes an explicit `top_k=N` → wrapper passes `N` → `run()` honors the explicit value (backward-compat).

The existing test `test_retriever_agent_default_top_k_is_5` (test_retriever.py:68-83) asserts `run_mock.assert_called_once_with("q", "ai_act", "es", top_k=5)` — this WILL FAIL after this task because the wrapper now passes `top_k=None`. Update the assertion to reflect the new (correct) pass-through behavior — the test was over-constrained (asserting "5 specifically" rather than "the default flowed through"); the effective `top_k=5` is now an invariant of `DEFAULT_CONFIG` not of the wrapper, and the rename of the test will reflect that.

- [ ] **Step 1: Update `agents/retriever.py:25-36`**

Replace the `retrieve` method body (line 25 onward) with:

```python
    def retrieve(
        self,
        query: str,
        corpus: CorpusSelector,
        language: Language,
        top_k: int | None = None,
    ) -> Context:
        if corpus == "auto":
            chunks, resolved = rag_retrieval.run_auto(query, language, rag_retrieval.DEFAULT_CONFIG)
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

(Only line 30 changes: `top_k: int = 5` → `top_k: int | None = None`. The body that passes `top_k=top_k` already does the right thing — `None` propagates to `run()` which resolves it.)

- [ ] **Step 2: Update `mcp_server/tools.py:30-44`**

Replace `search_articles` (lines 30–44) with:

```python
def search_articles(
    query: str,
    corpus: CorpusSelector,
    language: Language,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks for `query` filtered by corpus + language.

    `top_k=None` (the default) lets `rag_retrieval.run()` resolve from
    `DEFAULT_CONFIG.top_k` at call time (H15.2, ADR-0018) — production
    byte-identical to v0.1.6-h15.1 under env-unset.

    When corpus="auto", triggers cross-corpus retrieval (multi-corpus rerank +
    post-rerank purity gate via ADR-0017), returning chunks that may span
    multiple norms; the resolved norma list is discarded at this boundary.
    """
    if corpus == "auto":
        return rag_retrieval.run_auto(query, language, rag_retrieval.DEFAULT_CONFIG)[0]
    return rag_retrieval.run(query, corpus, language, top_k=top_k)
```

(Only line 34 changes: `top_k: int = 5` → `top_k: int | None = None`. The body already passes `top_k=top_k`.)

- [ ] **Step 3: Update the over-constrained `test_retriever_agent_default_top_k_is_5` test**

The test at `tests/unit/agents/test_retriever.py:68-83` currently asserts:

```python
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
```

Replace it with (rename + updated assertion + docstring explaining the H15.2 change):

```python
def test_retriever_agent_default_top_k_passes_none_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H15.2: the RetrieverAgent's default `top_k` is `None` (pass-through);
    `rag_retrieval.run()` resolves None -> DEFAULT_CONFIG.top_k at call time
    (= 5 when REGULAITOR_RETRIEVAL_CONFIG is unset, production-byte-identical).
    The wrapper no longer hardcodes 5 — that invariant moved into DEFAULT_CONFIG
    where the env-override can reach it (ADR-0018, closes §22.22 design-defect)."""
    run_mock = MagicMock(return_value=[])

    from regulaitor.agents import retriever

    monkeypatch.setattr(retriever.rag_retrieval, "run", run_mock)
    monkeypatch.setattr(
        retriever.embeddings, "model_identifier", MagicMock(return_value="BAAI/bge-m3")
    )

    agent = RetrieverAgent()
    agent.retrieve("q", "ai_act", "es")

    run_mock.assert_called_once_with("q", "ai_act", "es", top_k=None)
```

- [ ] **Step 4: Run affected tests — all must pass**

Run: `uv run pytest tests/unit/agents/test_retriever.py tests/unit/mcp_server/test_tools.py tests/unit/test_auto_threading.py -v`

Expected: all PASSED. Specifically:
- `tests/unit/agents/test_retriever.py::test_retriever_agent_delegates_with_correct_args` (line 50) — passes explicit `top_k=10`, asserts `top_k=10` propagates. STAYS GREEN (explicit value wins, unchanged).
- `tests/unit/agents/test_retriever.py::test_retriever_agent_default_top_k_passes_none_through` (the renamed test) — now asserts `top_k=None` — GREEN.
- `tests/unit/mcp_server/test_tools.py::test_search_articles_delegates_to_helper` (line 33) — passes explicit `top_k=3`, asserts `top_k=3` propagates. STAYS GREEN.
- `tests/unit/mcp_server/test_tools.py::test_search_articles_returns_empty_on_no_results` (line 46) — no `assert_called_once_with` check; STAYS GREEN.
- `tests/unit/test_auto_threading.py` — auto path untouched; STAYS GREEN.

- [ ] **Step 5: Commit the threading change**

```bash
git add src/regulaitor/agents/retriever.py src/regulaitor/mcp_server/tools.py tests/unit/agents/test_retriever.py
$env:SKIP="gitleaks"; git commit -m "feat(h15.2): T3 thread default-None through RetrieverAgent + search_articles (update over-constrained test)"
```

---

### Task 4: Pre-paid verification gate ($0)

**Files:** none modified — verification only.

**Context:** Before spending any user credit on the paid A/B re-experiment (T6–T8), prove the H15.2 wiring change passes the full authoritative gate, the strict mypy gate (the H15.1-T4 cross-milestone hygiene pattern), and the redteam-smoke gate (prompt-blind — retriever change shouldn't affect, but verify). Also grep all callers passing explicit `top_k` to confirm backward-compat by exhaustive listing. If any check fails, fix or revert BEFORE the user is asked to commit money.

- [ ] **Step 1: Full pytest gate (authoritative)**

Run: `uv run pytest -m "not slow" --junit-xml=C:\tmp\h15-2-t4-pytest.xml`

Expected: ALL PASSED, coverage ≥90%. Read the summary line carefully — pytest's bottom line `<N> passed, <M> failed, <K> skipped` is authoritative. The junit-xml file gives the exact test count for the closure commit.

If any test fails: the wiring change broke something. Diagnose by name (the failing test points at which interface contract is violated), fix in the smallest patch that restores green, re-run. **Do not proceed to T5 until this is fully green.**

- [ ] **Step 2: Strict mypy gate**

Run: `uv run mypy src`

Expected: `Success: no issues found in <N> source files` and exit code 0. H15.1-T4 made this gate explicit after discovering it had been silently red since H13 (`db991dc`) because `pytest -m "not slow"` does NOT run mypy. Carry that hygiene forward.

If mypy errors appear: most likely the `int | None` type annotation triggered a downstream type-flow issue. Fix annotations only (no runtime behavior change). Re-run.

- [ ] **Step 3: Redteam-smoke gate (prompt-blind, retriever-change-unaffected)**

Run: `uv run --env-file .env python -m redteam.runner --smoke`

Expected: `block_rate >= 0.92` (the frozen §16.2#4 gate). The retriever change should not affect this because: (a) the redteam smoke attacks are prompt-injection / refusal-test, prompt-blind to retrieval depth; (b) production behavior is byte-identical under env-unset.

If `block_rate < 0.92`: STOP. The wiring change has unexpectedly affected the safety floor. Diagnose by examining which attack(s) now pass that previously blocked. Most likely culprit: a stub or sanitizer dependency on the retrieval signature (unlikely, but verify).

- [ ] **Step 4: Grep callers of `retrieve(`, `rag_retrieval.run(`, `search_articles(`**

Run:

```powershell
$paths = @('src','tests')
foreach ($p in $paths) {
  Write-Output "=== $p ==="
  Get-ChildItem -Recurse -Include *.py -Path $p | Select-String -Pattern '\.retrieve\(|rag_retrieval\.run\(|search_articles\('
}
```

Expected: only the production wrappers (`graph.py:99`, `document_graph.py:153`) call `.retrieve()` without `top_k` (they get None → byte-identical via DEFAULT_CONFIG). Test files that pass explicit `top_k=N` (e.g. `test_retriever.py:39`, `test_retriever.py:63`, `test_tools.py:40`, `test_h14_cross_corpus_retrieval.py:59` via the local `_retrieve` helper) keep working — explicit value wins. No call site in production code passes an explicit `top_k` other than the eval harness (which passes nothing and benefits from the wiring).

Visually confirm no caller breaks. If any caller passes an explicit positional argument in the wrong position, the `int | None` annotation will catch it at mypy step; otherwise visual inspection is sufficient.

- [ ] **Step 5: No commit at this step**

T4 is verification-only. If all four steps pass, proceed to T5 (ADR). If any fails, fix the underlying issue and re-run T4 — do NOT proceed to a paid step on a red gate.

---

### Task 5: ADR-0018 — constraint reinterpretation

**Files:**
- Create: `docs/adr/0018-retriever-config-wired-into-explicit-path.md`

**Context:** Mirrors the ADR-0017 structure exactly (status / context / decision / consequences / alternatives / references). The honest framing: H15.1 chose a conservative interpretation of T6; H15.2 corrects it at T6's actual narrower scope. Production behavior unchanged; eval-time behavior now genuinely measurable. This is a small, surgical ADR (~80–120 lines) — much shorter than ADR-0017 because the scope is narrower.

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0018-retriever-config-wired-into-explicit-path.md` with:

```markdown
# ADR 0018 — Retriever `RetrievalConfig` wired into explicit-corpus `run()` path (H15.2)

- **Status:** Accepted — 2026-05-20 — squash `<squash-sha>`, tag `v0.1.7-h15.2`
- **Deciders:** Project owner.
- **Companion ADRs:** 0017 (H15.1 — the milestone whose §22.22 design-defect this
  ADR closes), 0016 (H15 — the calibration study + C1 content-based safety
  backstop carried), 0013 (router multi-LLM — the
  `REGULAITOR_ROUTER_MODE` eval-override seam precedent for env-driven config).

## Context

H15.1 (ADR-0017) added the opt-in `corpus="auto"` cross-corpus retrieval path and
introduced `RetrievalConfig` (`pre_rerank`, `top_k`, `purity_threshold`,
`query_normalize`) as the contained tuning levers, with the explicit-corpus path
kept byte-identical to `v0.1.5-h15` "by construction" — the explicit `run()`
function continued to use the module-level `PRE_RERANK = 50` constant and the
function-parameter default `top_k = 5`, never consulting `DEFAULT_CONFIG`.

H15.1's spec §4 intended the 30-case calibration A/B to measure the tuning lever
on the explicit-corpus calibration set. The A/B ran (~€3.01) and surfaced a
**milestone-consequential design-defect §22.22** in H15.1-T10/T11 (POST-SPEND):
because the explicit-corpus path consumed `DEFAULT_CONFIG` in ZERO sites and the
30 calibration cases are all explicit-corpus, `REGULAITOR_RETRIEVAL_CONFIG` had
no mechanism on the measurement — the €3.01 of cand-1+cand-2 deltas measured
LLM-provider non-determinism, NOT a real tuning-lever signal.

The H15.1 §4.3 framing called the no-leakage guarantee (T6,
`tests/unit/test_explicit_path_unchanged.py`) and the spec §4 A/B intent
"mutually exclusive as designed". On re-grounding for H15.2, T6 was found to
assert EXACTLY two properties: (a) the WHERE-CLAUSE string equals
`f"norma = '{corpus}' AND language = '{language}'"`; (b) an empty-rerank
short-circuit returns `[]`. T6 does **not** assert `PRE_RERANK=50`, does **not**
assert `top_k=5`, does **not** assert that `run()` is config-insensitive — the
stub `_S.limit(_n)` ignores its argument and the test passes `top_k=5`
explicitly. The §22.18/H14 no-leakage guarantee is fundamentally about
cross-corpus contamination (the WHERE-CLAUSE), not about specific
`top_k`/`pre_rerank` values.

The H15.1 framing was the conservative implementation interpretation of T6's
actual narrower scope. The architectural constraint is genuinely narrower than
the H15.1 implementation chose.

## Decision

Wire `DEFAULT_CONFIG.top_k` and `DEFAULT_CONFIG.pre_rerank` into the explicit
`rag.retrieval.run()` via the default-`None` parameter pattern, with per-call
attribute resolution. Production behavior remains byte-identical to
`v0.1.6-h15.1` when `REGULAITOR_RETRIEVAL_CONFIG` is unset; eval-time behavior
becomes genuinely config-sensitive when the env is set.

`run(query, corpus, language, top_k=None, pre_rerank=None)`. `top_k=None` →
resolves to `DEFAULT_CONFIG.top_k` AT CALL TIME. `pre_rerank=None` → resolves to
`DEFAULT_CONFIG.pre_rerank` AT CALL TIME. Explicit non-`None` values win
(backward-compat). Call-time resolution (NOT function-definition-time capture)
is what makes the eval harness's `REGULAITOR_RETRIEVAL_CONFIG` env-override flow
through. `RetrieverAgent.retrieve` and `mcp_server.tools.search_articles` adopt
the same default-`None` pass-through pattern.

The WHERE-CLAUSE construction line stays byte-identical character-for-character
under any env state — the no-leakage-critical line. `_enrich`, `run_auto`,
`_apply_purity_gate`, `RetrievalConfig`, `_config_from_env`, `DEFAULT_CONFIG`
initialization, `PRE_RERANK` module constant, all unchanged. §6 (Auditor +
`citation/validator`) byte-unchanged. No LanceDB re-ingest.

The keystone assertion is `tests/unit/test_explicit_config_wired.py`: env-unset
→ defaults (production-byte-identical); env-set → override flows through;
WHERE-CLAUSE byte-identical under BOTH env states. T6
(`tests/unit/test_explicit_path_unchanged.py`) is unchanged and continues to
pass — it already asserted exactly what H15.2 preserves.

## Consequences

**Positive:**

- The H15.1 §22.22 design-defect is closed: the 30-case calibration A/B is now
  genuinely capable of measuring the tuning lever on the explicit-corpus path.
  The H15.2 re-experiment (T6–T8) produces real signal where H15.1's measured
  €3.01 was provably non-determinism noise.
- Production behavior is byte-identical to `v0.1.6-h15.1` when
  `REGULAITOR_RETRIEVAL_CONFIG` is unset — verified by the new keystone test
  asserting `top_k=5, pre_rerank=50` under env-unset and by T6 continuing to
  pass unchanged.
- The §22.18/H14 no-leakage guarantee is preserved at its actual scope (the
  WHERE-CLAUSE) under BOTH env-unset and env-set — the keystone test extends
  T6's invariant to the env-set case.
- The §6 "no citation, no answer" Auditor / citation-validator invariant is 100%
  intact: those components are byte-unchanged.
- The LLM-free retriever principle is preserved: `run()` calls no LLM; the
  config resolution is a pure attribute access.
- The `REGULAITOR_RETRIEVAL_CONFIG` env seam (ADR-0017) now has end-to-end
  effect on both the auto path AND the explicit path — the H15.1 surface remains
  exactly the same, with the H15.2 wiring making the surface genuine.

**Negative / accepted (documented honestly per §22.22):**

- The H15.1 implementation's conservative interpretation of T6 was a
  measurement-design gap that cost €3.01 of paid LLM time before being
  surfaced. The honest TFM-defense framing is: H15.1's per-task reviews
  validated per-task correctness but did not chequed cross-task design
  coherence (the A/B's ability to actually measure what the spec said it
  measured); H15.2 surfaces and closes that gap. Discipline: any future
  measurement-design choice involving multiple integration sites (env →
  config → consuming code path) should be reviewed for end-to-end effect
  BEFORE paid measurement (a new follow-up registered at H15.2 closure).
- Two production wrappers (`RetrieverAgent.retrieve` and `search_articles`)
  changed signature default from `top_k=5` to `top_k=None`. This is observable
  from the outside via reflection or `inspect.signature` but **not** from any
  test that calls with explicit `top_k=N` (the dominant pattern in the
  codebase). One existing test (`test_retriever_agent_default_top_k_is_5`) was
  updated to assert the new (correct) pass-through behavior — the old name was
  over-constrained (it asserted "5 specifically" rather than "the default flowed
  through to DEFAULT_CONFIG"); the renamed test
  `test_retriever_agent_default_top_k_passes_none_through` asserts the
  architectural invariant the wrapper actually upholds.
- Measured A/B results (cand-1 / cand-2 / holdout-if-winner numbers, real costs,
  HARD-revert verification) are produced in T6–T8 and reported in
  `docs/retriever_h15-2_redesign.md`. This ADR records the **decision and
  framework**; outcome numbers are not yet measured at ADR-write time.

## Alternatives considered

- **Re-architect `run()` to take a `RetrievalConfig` parameter explicitly** —
  rejected (YAGNI, breaking change at every call site). The default-`None`
  pattern preserves the existing signatures' positional shape while threading
  the config seam through.
- **Extend the gold-set with auto-path cases at N≥15 (Option B from H15.2
  brainstorming)** — rejected for H15.2. The tuning lever is now measurable on
  the existing 30-calibration set via the surgical wiring fix, so gold-set
  extension is not needed for H15.2's success condition (it would also require
  paid re-baseline, blowing the budget). Registered as a future fase-optimización
  microhito option (not the chosen next step at H15.2 closure — that is the
  user's decision at closure time, among the deferred items).
- **Capture `DEFAULT_CONFIG` values at function-definition time** (e.g.
  `def run(top_k: int = DEFAULT_CONFIG.top_k, ...)`) — rejected. Function
  defaults are evaluated once at module import; the env-override would only
  work if set BEFORE the first `import regulaitor.rag.retrieval`. The
  per-call attribute resolution is the architecturally-correct choice for
  the env-override seam.
- **Modify T6 to assert the broader "config-insensitivity" invariant** —
  rejected. T6's actual narrow scope IS the right architectural invariant
  (the WHERE-CLAUSE no-leakage line); broadening it would re-encode the
  H15.1 conservative implementation interpretation as architecture, which
  is exactly what H15.2 corrects.

## References

- Spec: `docs/superpowers/specs/2026-05-20-h15-2-eval-redesign-design.md`
- Plan: `docs/superpowers/plans/2026-05-20-h15-2-eval-redesign.md`
- Decisions log `§H15.2` (D1–D5, constraint reinterpretation, A/B re-experiment
  results, named microhito follow-ups — populated post-Tasks-6–10)
- ADR 0017 (H15.1 — the milestone whose §22.22 design-defect this ADR closes)
- ADR 0016 (H15 — calibration study + C1 content-based safety backstop carried)
- `src/regulaitor/rag/retrieval.py` (`run()` per-call DEFAULT_CONFIG resolution)
- `tests/unit/test_explicit_config_wired.py` (keystone proof)
- `tests/unit/test_explicit_path_unchanged.py` (T6 — unchanged, continues to pass)
- `evals/reports/h15/h15_2-cand1.md`, `h15_2-cand2.md`, `h15_2-holdout.md` (if winner)
- `docs/retriever_h15-2_redesign.md` (study report — produced in T9)
```

- [ ] **Step 2: Commit ADR-0018**

```bash
git add docs/adr/0018-retriever-config-wired-into-explicit-path.md
$env:SKIP="gitleaks"; git commit -m "docs(h15.2): T5 ADR-0018 retriever config wired into explicit path (constraint reinterpretation)"
```

---

### Task 6: USER-GATED paid cand-1 re-experiment (probe → full)

**Files:**
- Create (force-add): `evals/reports/h15/h15_2-cand1-probe.md`
- Create (force-add): `evals/reports/h15/h15_2-cand1.md`

**Context:** First A/B re-experiment under the H15.2 genuine measurement. Same config as H15.1 cand-1: `REGULAITOR_RETRIEVAL_CONFIG={"pre_rerank":80,"top_k":8}`. Frozen control = `evals/reports/h15/candidate-v1.2.md` (H15 30-calib, Analyst v1.2, env-unset). Cost ceiling estimated ~€1.65 (probe €0.15 + full €1.50). **Controller runs this as a persistent background job; NOT delegated to a subagent (H14 lesson — never delegate a 30–100 min paid job to a subagent).**

- [ ] **Step 1: Cost-tally & user-gate BEFORE the probe**

Compute the running cost so far (zero before T6 if T1–T5 are $0 as expected). Present to user:

> **T6 — paid step 1 (probe)**
> - Running cost so far: $X (T1–T5 = $0; H15+H15.1 historical = $0 charged against today's milestone)
> - About to spend: ~€0.15 (cand-1 probe `--limit 3` on `REGULAITOR_RETRIEVAL_CONFIG={"pre_rerank":80,"top_k":8}`, Analyst v1.2)
> - Estimated full T6 envelope: ~€1.65 (probe €0.15 + full 30-case €1.50)
> - Total H15.2 envelope reminder: ~€3.30 if no winner / ~€4.15 if winner ships
> - **OK to proceed with the probe?** Please confirm credits available.

Wait for explicit user OK. **DO NOT PROCEED without explicit confirmation.**

- [ ] **Step 2: Run cand-1 probe (3 cases, persistent background)**

```powershell
$env:REGULAITOR_RETRIEVAL_CONFIG='{"pre_rerank":80,"top_k":8}'
$env:REGULAITOR_ANALYST_PROMPT_VERSION="v1.2"
uv run --env-file .env python -m evals.harness --limit 3 --report evals/reports/h15/h15_2-cand1-probe.md
```

Run as a persistent background job (`run_in_background: true` on the Bash tool). Expected wall time: ~12–18 min (probe runs 3 chat cases against Analyst v1.2 + judge + Auditor, with retriever now consuming the cand-1 config genuinely).

When complete: read `evals/reports/h15/h15_2-cand1-probe.md` for the per-case rows + total cost. Compare to H15.1's cand-1 probe — if total cost is ~€0.15 (±50%), proceed; if wildly off (e.g. €0.50), investigate (could indicate config not flowing through — re-verify via `test_explicit_config_wired.py` and the probe report's per-case retrieval evidence).

- [ ] **Step 3: Cost-tally & user-gate BEFORE the full 30-case run**

Update the tally with the measured probe cost. Present to user:

> **T6 — paid step 2 (full 30-case)**
> - Running cost so far: probe ~€X.XX (measured)
> - About to spend: ~€1.50 (cand-1 full 30-case, same config)
> - **OK to proceed with the full run?** Please confirm credits available.

Wait for explicit user OK.

- [ ] **Step 4: Run cand-1 full 30-case (persistent background)**

```powershell
$env:REGULAITOR_RETRIEVAL_CONFIG='{"pre_rerank":80,"top_k":8}'
$env:REGULAITOR_ANALYST_PROMPT_VERSION="v1.2"
uv run --env-file .env python -m evals.harness --report evals/reports/h15/h15_2-cand1.md
```

Run as a persistent background job. Expected wall time: ~60–90 min. The harness writes `evals/reports/h15/h15_2-cand1.md` with per-case + aggregate metrics + measured total cost. Reports directory is `.gitignored`; force-add at commit time per H15/H15.1 evidence-tracking precedent.

- [ ] **Step 5: Read cand-1 report — compare to H15 frozen control**

When complete, read `evals/reports/h15/h15_2-cand1.md` and `evals/reports/h15/candidate-v1.2.md` (frozen control). Note for the study report (T9):
- Aggregate deltas (verdict_match, faithfulness, answer_relevancy, context_precision, context_recall, citation_precision, citation_recall, severity_match).
- Per-case retrieval transparency: does the retriever now bring different candidates than H15.1's measurement (the §22.22 fix verification — different ≠ better, but different IS the proof that the env override now reaches the explicit path).
- Measured total cost (router accumulator at end of report).

**No HARD-revert verdict yet** — that's at T8 (holdout) only if a candidate is named winner. T6 is just the cand-1 measurement.

- [ ] **Step 6: Commit cand-1 evidence**

```bash
git add -f evals/reports/h15/h15_2-cand1-probe.md evals/reports/h15/h15_2-cand1.md
$env:SKIP="gitleaks"; git commit -m "evidence(h15.2): T6 cand-1 (pre_rerank=80,top_k=8) 30-case A/B vs H15 frozen control (genuine lever measurement)"
```

---

### Task 7: USER-GATED paid cand-2 re-experiment (probe → full)

**Files:**
- Create (force-add): `evals/reports/h15/h15_2-cand2-probe.md`
- Create (force-add): `evals/reports/h15/h15_2-cand2.md`

**Context:** Second A/B re-experiment. Same config as H15.1 cand-2: `REGULAITOR_RETRIEVAL_CONFIG={"pre_rerank":80,"top_k":3}`. Same frozen control. Same ~€1.65 cost ceiling. Same controller-as-persistent-background discipline.

- [ ] **Step 1: Cost-tally & user-gate BEFORE the probe**

Update tally with T6 measured costs. Present to user:

> **T7 — paid step 1 (probe)**
> - Running cost so far: T6 ~€X.XX (measured: probe €X + full €X)
> - About to spend: ~€0.15 (cand-2 probe `--limit 3` on `REGULAITOR_RETRIEVAL_CONFIG={"pre_rerank":80,"top_k":3}`, Analyst v1.2)
> - Estimated full T7 envelope: ~€1.65
> - **OK to proceed with the probe?** Please confirm credits available.

Wait for explicit user OK.

- [ ] **Step 2: Run cand-2 probe (3 cases, persistent background)**

```powershell
$env:REGULAITOR_RETRIEVAL_CONFIG='{"pre_rerank":80,"top_k":3}'
$env:REGULAITOR_ANALYST_PROMPT_VERSION="v1.2"
uv run --env-file .env python -m evals.harness --limit 3 --report evals/reports/h15/h15_2-cand2-probe.md
```

Run as a persistent background job. Same sanity-check at end (~€0.15 expected).

- [ ] **Step 3: Cost-tally & user-gate BEFORE the full 30-case run**

> **T7 — paid step 2 (full 30-case)**
> - Running cost so far: T6 ~€X.XX + T7 probe ~€X.XX (measured)
> - About to spend: ~€1.50 (cand-2 full 30-case, same config)
> - **OK to proceed with the full run?** Please confirm credits available.

Wait for explicit user OK.

- [ ] **Step 4: Run cand-2 full 30-case (persistent background)**

```powershell
$env:REGULAITOR_RETRIEVAL_CONFIG='{"pre_rerank":80,"top_k":3}'
$env:REGULAITOR_ANALYST_PROMPT_VERSION="v1.2"
uv run --env-file .env python -m evals.harness --report evals/reports/h15/h15_2-cand2.md
```

Run as persistent background. Same ~60–90 min wall time.

- [ ] **Step 5: Read cand-2 report — compare to H15 frozen control AND cand-1**

When complete, read all three (`h15_2-cand2.md`, `candidate-v1.2.md`, `h15_2-cand1.md`). For T9 the study report needs the full 3-way comparison: control vs cand-1 vs cand-2.

**Winner criterion** (spec §4, no promised number): a candidate wins if it improves on the H15 frozen control on the canonical metrics (verdict_match, faithfulness, answer_relevancy, context_precision, context_recall, citation_precision, citation_recall, severity_match) WITHOUT regressing the HARD floors:
- WHERE-CLAUSE / T6 byte-identical (guaranteed structurally — no behavior change there).
- `citation_recall` ≥ 0.71 on the 30-calib (H15 carry-forward measured floor; distinct from §16.2#5 MVP gate ≥0.40).
- 6 H15 designated block cases content-safe (chat-014/015/029/030 — verified in the H15.2 cand reports' per-case section; nis2-006/dora-006 verified in T8 holdout if applicable).
- Redteam-smoke ≥0.92 — verified separately at T8 if production defaults will change.

Decide:
- **Both candidates clearly win** → pick the better one as `winner_config` (e.g. higher faithfulness without citation_recall regression). T8 will holdout-verify that one.
- **Exactly one candidate wins** → it's the `winner_config`. T8 will holdout-verify.
- **Neither candidate wins** → no winner. Skip T8. Production defaults stay `top_k=5, pre_rerank=50`. The H15.2 contribution is the measurement-design fix + the now-genuine evidence that the H15-documented system-level ceiling is real (H15-style "documented deeper ceiling — both defend").
- **A candidate improves a key metric BUT regresses a HARD floor** → that candidate is REVERTED (per spec §6 + §22.22). If the other candidate is clean, it's the winner; else no winner.

Record the winner decision (or no-winner) in a working note for T8 and T9.

- [ ] **Step 6: Commit cand-2 evidence**

```bash
git add -f evals/reports/h15/h15_2-cand2-probe.md evals/reports/h15/h15_2-cand2.md
$env:SKIP="gitleaks"; git commit -m "evidence(h15.2): T7 cand-2 (pre_rerank=80,top_k=3) 30-case A/B vs H15 frozen control"
```

---

### Task 8: USER-GATED paid holdout-if-winner (CONDITIONAL on T7)

**Files (CONDITIONAL on T7 producing a winner):**
- Create (force-add): `evals/reports/h15/h15_2-holdout.md`
- Modify (CONDITIONAL on holdout passing HARD-revert): `src/regulaitor/rag/retrieval.py:35-36` (update `RetrievalConfig` defaults to winning values)

**Context:** Two paths:
- **If T7 produced a winner**: holdout-verify on the 14 H14 chat cases (`evals/h15_holdout_chat_ids.txt`) using the winner config. HARD-revert check. If clean → update production `RetrievalConfig` defaults to winning values + that becomes H15.2's measured contribution. If NOT clean → REVERT (winner is rejected; H15.2 ships the wiring fix without a default change).
- **If T7 produced NO winner**: SKIP T8 entirely. Document the "no winner" outcome in T9 study report. Production defaults stay unchanged.

**This task is conditional** — if no winner, jump directly to T9.

#### 8a. CONDITIONAL on winner: Cost-tally & user-gate BEFORE holdout

- [ ] **Step 1: Cost-tally & user-gate**

> **T8 — paid holdout (CONDITIONAL — winner identified at T7)**
> - Running cost so far: T6 + T7 measured ~€X.XX
> - Winner config: `REGULAITOR_RETRIEVAL_CONFIG={...}` (the winning candidate)
> - About to spend: ~€0.85 (14 H14 chat cases, same Analyst v1.2 + same judge)
> - Total H15.2 envelope reminder: ~€4.15 (current spend + holdout)
> - **OK to proceed with holdout?** Please confirm credits available.

Wait for explicit user OK.

- [ ] **Step 2: Run holdout (14 cases, persistent background)**

```powershell
$env:REGULAITOR_RETRIEVAL_CONFIG='<the-winner-config-json>'
$env:REGULAITOR_ANALYST_PROMPT_VERSION="v1.2"
uv run --env-file .env python -m evals.harness --ids-file evals/h15_holdout_chat_ids.txt --report evals/reports/h15/h15_2-holdout.md
```

Run as persistent background. ~30–45 min wall time. The harness writes per-case + aggregate metrics + measured cost.

#### 8b. HARD-revert verification (whether or not winner is provisional)

- [ ] **Step 3: HARD-revert checks**

Read `evals/reports/h15/h15_2-holdout.md`. Verify ALL of:
1. **`citation_recall` ≥ 0.71** on the 30-calib (re-check: this was the floor from H15; the candidate cand-X report already shows this — read it and confirm ≥0.71).
2. **WHERE-CLAUSE / T6** — run `uv run pytest tests/unit/test_explicit_path_unchanged.py tests/unit/test_explicit_config_wired.py -v` with the winner config in env: all green.
3. **Redteam-smoke ≥0.92** under the winner config:
   ```powershell
   $env:REGULAITOR_RETRIEVAL_CONFIG='<the-winner-config-json>'
   uv run --env-file .env python -m redteam.runner --smoke
   ```
   Expected `block_rate >= 0.92`. If <0.92: the winner config has unexpectedly affected the prompt-blind safety floor — REVERT this candidate.
4. **6 H15 designated block cases content-safe** under the winner config: read `evals/reports/h15/h15_2-cand{1|2}.md` per-case section for chat-014/015/029/030 (the 4 calibration block cases). Read `h15_2-holdout.md` per-case for nis2-006/dora-006 (the 2 holdout block cases). For each, verify the answer rejects the malicious premise without fabricating an article and citing a real corpus article to refute (the C1 content-based manual backstop — DURA per ADR-0016 Consequences; authoritative over the mechanical `safety_ok` rule).

**If ALL 4 checks pass → winner is confirmed.** Proceed to step 4.
**If ANY check fails → REVERT.** The winner candidate is rejected. H15.2 ships the wiring fix without a production-default change. Document the rejection in T9 study report. Skip step 4. Proceed to T9.

#### 8c. CONDITIONAL on HARD-revert PASS: Update production defaults

- [ ] **Step 4: Update `RetrievalConfig` defaults to winning values**

Edit `src/regulaitor/rag/retrieval.py:35-36`. Replace the current defaults:

```python
    pre_rerank: int = PRE_RERANK  # 50
    top_k: int = 5
```

With the winner config's values (example for cand-1 winner):

```python
    pre_rerank: int = 80  # H15.2 measured winner: T6+T7+T8 holdout HARD-revert clean
    top_k: int = 8        # H15.2 measured winner: T6+T7+T8 holdout HARD-revert clean
```

(Adjust per actual winner config from T7. Keep the `PRE_RERANK = 50` module-level constant as the historical default reference — it stays as documentation of the v0.1.6-h15.1 default.)

- [ ] **Step 5: Re-run gate after defaults change**

Run: `uv run pytest -m "not slow" --junit-xml=C:\tmp\h15-2-t8-pytest.xml`

Expected: all PASSED, coverage ≥90%. Critical: `test_env_unset_uses_default_config_defaults` (the keystone test) was asserting `top_k=5, pre_rerank=50` — it will FAIL if defaults changed because env-unset now returns the WINNER values. Update that ONE test to assert the new defaults:

```python
def test_env_unset_uses_default_config_defaults(monkeypatch) -> None:
    """Production-byte-identical: DEFAULT_CONFIG() defaults → top_k=<winner>, pre_rerank=<winner>.
    H15.2 measured winner update: T8 HARD-revert verified clean (per ADR-0018 §Decision)."""
    ...
    assert captured["pre_rerank"] == <winner pre_rerank>  # H15.2 winner
    assert captured["top_n"] == <winner top_k>  # H15.2 winner
```

Re-run pytest → all green.

- [ ] **Step 6: Commit holdout evidence + (CONDITIONAL) production-default change**

```bash
git add -f evals/reports/h15/h15_2-holdout.md
# If winner shipped:
git add src/regulaitor/rag/retrieval.py tests/unit/test_explicit_config_wired.py
$env:SKIP="gitleaks"; git commit -m "evidence(h15.2): T8 holdout HARD-revert clean — promote winner config to production defaults"
# If NO winner shipped:
$env:SKIP="gitleaks"; git commit -m "evidence(h15.2): T8 holdout — winner candidate REVERTED on HARD-revert (documented deeper ceiling)"
```

---

### Task 9: Study report `docs/retriever_h15-2_redesign.md` [Opus]

**Files:**
- Create: `docs/retriever_h15-2_redesign.md`

**Context:** The honest H15.2 narrative. Mirrors the structure of H15.1's `docs/retriever_optimization.md` but shorter (~250–350 lines, vs H15.1's ~520) because scope is tighter. Honest framing throughout: H15.2 corrects H15.1's conservative interpretation of T6 at the architecturally-correct narrower scope; closes the §22.22 design-defect. Result honesty: report what was measured (improvement OR documented deeper ceiling) without overstating. References and corrects (does NOT rewrite or hide) H15.1's `docs/retriever_optimization.md` §4.

Use Opus for this task — the §22.22 honest narrative + cross-milestone framing + winner/no-winner branch is design-judgment work, exactly the kind H15.1's T11 study report needed Opus for.

- [ ] **Step 1: Write the study report**

Structure (mirrors H15.1's report; sections sized per the tighter H15.2 scope):

```markdown
# H15.2 Retriever Eval Rede-design — Study Report

## 1. Headline (the §22.22 honest done-when)

Two-sentence summary. Example shapes:
- WINNER: "H15.2 wired DEFAULT_CONFIG into the explicit-corpus run() path,
  closing the H15.1 §22.22 design-defect. On the now-genuine A/B vs the H15
  frozen control, cand-X (`pre_rerank=80, top_k=Y`) measured +ΔA faithfulness
  / +ΔB context_precision / citation_recall PASS (≥0.71 floor carry); T8 holdout
  HARD-revert clean; promoted to production defaults."
- NO-WINNER: "H15.2 wired DEFAULT_CONFIG into the explicit-corpus run() path,
  closing the H15.1 §22.22 design-defect. The now-genuine A/B re-experiment
  measured cand-1 / cand-2 against the H15 frozen control with no candidate
  improving without HARD-floor regression — the H15-documented system-level
  ceiling holds under a properly-exercised tuning sweep. Production defaults
  unchanged; the measurement-design fix is itself the H15.2 contribution."

## 2. Constraint reinterpretation (the keystone)

Re-state T6's actual narrow scope (WHERE-CLAUSE + empty short-circuit; NOT
config-insensitivity). Re-state H15.1 §4.3's "mutually exclusive as designed"
framing as conservative implementation interpretation. Show the surgical
correction (per-call DEFAULT_CONFIG resolution; WHERE-CLAUSE preserved).
Cross-link ADR-0018.

## 3. Wiring change (what shipped)

The default-None pattern. Per-call resolution. Production-byte-identical-under-
env-unset (asserted by `test_explicit_config_wired.py`). The 2 wrapper signature
changes (RetrieverAgent + search_articles). The 1 test rename. Reference the
specific commits (T1–T5 in this branch).

## 4. A/B re-experiment results (genuinely measured)

The full table: H15 control vs cand-1 (pre_rerank=80, top_k=8) vs cand-2
(pre_rerank=80, top_k=3). All canonical metrics. Measured total cost (router
accumulator). Per-case retrieval transparency: how the wider top_k=8 brought
different chunks (cand-1) and how the narrower top_k=3 reduced noise (cand-2)
vs H15.1's measurement where the env had ZERO effect on the explicit path.

(WINNER branch:) Identify the winner. Show the holdout (14 H14 chat) numbers.
Show the HARD-revert verification (citation_recall floor, T6, redteam-smoke,
6 block cases content-safe).
(NO-WINNER branch:) Show why neither candidate cleared the bar. Be honest about
which metric regressed which floor. Frame as "documented deeper ceiling".

## 5. §22.22 honest disclosures

- The wiring change's design was a small fix to a measurement-design gap
  surfaced POST-SPEND in H15.1. The honest acknowledgment: H15.1's per-task
  reviews validated per-task correctness but did not check cross-task design
  coherence (env → config → consuming code path end-to-end effect). H15.2 fixed
  the gap; the discipline lesson is captured in ADR-0018 Consequences (review
  multi-integration measurement designs for end-to-end effect BEFORE paid
  measurement).
- (WINNER branch:) The improvement is measured, not claimed. The HARD-revert
  guardrails caught nothing — that is the honest "all-clear" signal. The
  improvement may not generalize beyond the 30-calibration + 14-holdout
  distribution; mitigation = future calibration on a broader gold set (deferred
  microhito).
- (NO-WINNER branch:) The non-result is measured, not just absent. The
  H15-documented system-level ceiling is now backed by a properly-exercised
  tuning sweep on the same calibration set. The contribution is the
  measurement-design fix itself.

## 6. Deferred fase-optimización microhitos (the H15.2 follow-up bundle)

Named items, each ready to be picked as the next milestone at H15.2 closure
(user's call; H16/H17 untouched):

- **xcorpus-002 verdict regression** (RHR→block on auto path; H15.1 §22.22
  open question; ~€0.5 when executed; purity_threshold sweep + reranker
  diagnosis on n=1).
- **Document segmenter** (the "0 segmentos" confound from H15 probe; doc-mode
  A/B blocked until this lands; segmenter overhaul + segmentation A/B).
- **No-Answer-residual robustness** (2/14 holdout empty-answer from H15;
  Analyst schema-adherence work).
- **Auditor RHR-aggregation** (+ `MonotonicEscalatePolicy` /
  `_COUNCIL_BINDING` seam; still OFF; §6-invariante-adjacent work merits its
  own milestone).
- **Citation-metric granularity confound** (gold H8 apartado-level vs H14
  article-level; eval-instrument work; requires full A/B re-baseline if metric
  changed).
- **§17 thresholds + LLM-judge same-provider-family** (Haiku judge vs Sonnet
  prod, ADR-0010; router-multi-LLM-judge future milestone).
- **Gold-set extension with auto-path cases at N≥15** (Option B from H15.2
  brainstorming, rejected for H15.2; reconsider as own milestone if H15.2
  produced no-winner and auto path is the next investigation).

## 7. Cost accounting

T6 measured: cand-1 probe €X + full €X.
T7 measured: cand-2 probe €X + full €X.
T8 measured (if executed): holdout €X.
**Total H15.2 paid spend: €X.XX of ~€4.15 ceiling.**
Comparison to H15.1: H15.1 spent €3.92 measured (cand-1 €1.48 + cand-2 €1.53 +
holdout €0.75 + probe €0.16); H15.2 spends ~equal money on the now-genuine
measurement (vs H15.1's non-determinism noise).

## 8. References

- ADR-0018 (constraint reinterpretation decision).
- Spec: `docs/superpowers/specs/2026-05-20-h15-2-eval-redesign-design.md`.
- Plan: `docs/superpowers/plans/2026-05-20-h15-2-eval-redesign.md`.
- H15.1's `docs/retriever_optimization.md` §4 (the H15.1 measurement and the
  §22.22 disclosure this report closes; H15.1's report stays unchanged at its
  time — historical accuracy).
- H15's `docs/auditor_calibration.md` (the frozen control's calibration study).
- ADR-0017 (H15.1's auto path + RetrievalConfig — H15.2 builds on it).
- ADR-0016 (H15's calibration study; C1 content-based safety backstop carried).
```

Fill in actual numbers from T6 / T7 / T8 reports. Keep WINNER and NO-WINNER as parallel narratives — write the one that applies.

- [ ] **Step 2: Commit the study report**

```bash
git add docs/retriever_h15-2_redesign.md
$env:SKIP="gitleaks"; git commit -m "docs(h15.2): T9 study report — constraint reinterpretation + A/B re-experiment results"
```

---

### Task 10: Closure [Opus]

**Files:**
- Modify: `docs/technical_decisions_log.md` (append §H15.2)
- Modify: `docs/evidence_matrix.md` (add H15.2 row; update ADR-count gate to 18)
- Modify: `CLAUDE.md` §16.3 (mark H15.2 done) + §27 (Hitos cerrados H15.2 bullet + Hito siguiente = chosen deferred microhito; H16/H17 unchanged)

**Context:** End-of-milestone bookkeeping. Mirrors the H15.1-T11 closure structure. Names the chosen next milestone explicitly (user's pick from the T9 deferred-fase-optimización bundle — solicit at closure time). The H15.2 entry includes: the §22.22 disclosure resolution, the measured outcome (WINNER or NO-WINNER), the named microhito follow-ups, the cost accounting, and the pattern lesson (review multi-integration measurement designs for end-to-end effect BEFORE paid measurement).

Use Opus for this task — the cross-milestone framing + the WINNER/NO-WINNER branch + the closure-time microhito naming is design-judgment work, exactly the kind H15.1's T11 closure needed Opus for.

- [ ] **Step 1: Append `§H15.2` to `docs/technical_decisions_log.md`**

Mirror the H15/H15.1 entry structure. Include:
- The §22.22 honest framing (constraint reinterpretation; H15.1's §22.22 closed).
- The A/B re-experiment results table (control / cand-1 / cand-2 / holdout-if-winner).
- D1-D5 outcomes (each decision with its result).
- HARD-revert verification (each of the 4 checks with PASS/FAIL).
- Measured cost (T6 + T7 + T8) with router-accumulator citation.
- The 5 named microhito follow-ups (per the T9 deferred-fase-optimización bundle).
- The user's chosen next milestone for §27.
- The pattern lesson: multi-integration measurement designs must be reviewed for end-to-end effect BEFORE paid measurement.

(Exact text written at closure time per actual T6–T9 results.)

- [ ] **Step 2: Update `docs/evidence_matrix.md`**

Append an H15.2 row in the appropriate table (mirror H15 / H15.1 row format).
Increment the ADR-count gate from 17 to 18 (the new ADR-0018).
Update the decisions-log line count.
Add `docs/retriever_h15-2_redesign.md` + `docs/adr/0018-…md` + the 5 new evidence reports to the listing.

- [ ] **Step 3: Update `CLAUDE.md` §16.3**

Mark H15.2 as done with the squash placeholder pattern: `<squash-sha>` placeholder for the post-merge populate step (H1–H15.1 precedent — the controller populates after squash-merge).

- [ ] **Step 4: Update `CLAUDE.md` §27 Hitos cerrados / Hito siguiente**

Append the H15.2 "Hitos cerrados" bullet (mirror H15.1's bullet structure — comprehensive multi-line summary; H15.1 set the precedent for milestone-completeness in §27 bullets).

Replace the "Hito siguiente" entry with the user-chosen next milestone (one of: xcorpus-002 / segmenter / no-Answer-residual / Auditor-RHR / citation-granularity / LLM-judge-same-provider / gold-set-extension). **H16 and H17 stay unchanged in the roadmap** — the chosen microhito is a sibling of the H15.1/H15.2 pattern, inserted without renumbering. Solicit the user's pick at closure time.

- [ ] **Step 5: Commit the closure**

```bash
git add docs/technical_decisions_log.md docs/evidence_matrix.md CLAUDE.md
$env:SKIP="gitleaks"; git commit -m "docs(h15.2): T10 closure — decisions §H15.2 + evidence_matrix + CLAUDE.md (next: <chosen microhito>)"
```

---

## Branch Completion (post-T10)

Use `superpowers:finishing-a-development-branch`. The H1–H15.1 pattern:

1. Verify gate green: `uv run pytest -m "not slow"` ≥90% + `uv run mypy src` exit 0.
2. Branch base: `main @ 2540dcb`.
3. Squash-merge `feat/h15-2-eval-redesign` to `main` with the body capturing T1–T10 (mirroring H15.1's squash body; §22.22 honest).
4. Annotated tag `v0.1.7-h15.2` on the squash commit.
5. Post-merge: populate `<squash-sha>` placeholders across ADR-0018, decisions log §H15.2, evidence_matrix, CLAUDE.md §27. Commit `docs(h15.2): populate post-merge squash SHA + close H15.2`.
6. Memory roll-forward: `h15-1_closed_h15-2_starting.md` → `h15-2_closed_<next>_starting.md`; update `MEMORY.md` line 3.
7. Delete branch (`git branch -D feat/h15-2-eval-redesign`).

Critical: do NOT auto-push; user-gated.

---

## Done-when summary (spec §6 mirror)

- [ ] Code: explicit `run()` reads `DEFAULT_CONFIG`; T6 stays green unchanged; `test_explicit_config_wired.py` green (all 4 properties); production byte-identical to v0.1.6-h15.1 when env-unset; full gate `pytest -m "not slow"` ≥90% green + `mypy src` exit 0.
- [ ] Measurement-design fix lands: A/B genuinely measures the lever (T1 keystone proof + T6/T7 producing config-induced behavior change vs H15.1's measured non-determinism).
- [ ] HARD-revert checks NONE fire (WHERE-CLAUSE/T6, citation_recall floor ≥0.71 carry, redteam-smoke ≥0.92, 6 H15 block cases content-safe — all verified on winning config if production defaults change at T8).
- [ ] Outcome: measured improvement on now-genuine A/B + holdout-if-winner OR documented deeper system-level ceiling — both defend (H15-style honest done-when, NO promised number).
- [ ] Closure: ADR-0018; `docs/retriever_h15-2_redesign.md` study report; decisions §H15.2 + named microhito follow-ups; evidence_matrix H15.2 row + ADR-count → 18; CLAUDE.md §16.3 (H15.2 done) + §27 (Hitos cerrados H15.2 bullet + Hito siguiente = chosen microhito); memory roll-forward; tag `v0.1.7-h15.2`.
