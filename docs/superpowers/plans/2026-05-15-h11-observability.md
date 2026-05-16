# H11 — Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional LangFuse observability (metadata-only traces, no-op without keys) to the orchestration layer, add cross-platform per-attack timeouts to the redteam runner, run the deferred full 50-attack red team, and document everything (runbook + ADR + closure).

**Architecture:** One new module `observability/langfuse_client.py` exposing `is_enabled()` + `trace_turn()` context manager. The orchestration entry points (`graph.run`, `document_graph.run_document`) wrap their existing flow in `trace_turn`; agents H3-H5 are untouched. Without `LANGFUSE_*` env vars the tracing is a pure no-op (lazy import, zero latency). The redteam runner gains a `ThreadPoolExecutor` + `future.result(timeout)` wrapper so a hung Anthropic call no longer kills the run.

**Tech Stack:** Python 3.11 · `langfuse>=2,<3` SDK · `concurrent.futures.ThreadPoolExecutor` · pytest · LangFuse Cloud free tier.

**Spec:** [docs/superpowers/specs/2026-05-15-h11-observability-design.md](../specs/2026-05-15-h11-observability-design.md) (commit `46fb66a`).

---

## File structure (lock-in)

```
src/regulaitor/observability/
├── __init__.py                 # NEW (Task 1) — package marker + docstring
└── langfuse_client.py          # NEW (Tasks 2-3) — is_enabled, TurnTrace, trace_turn

Modified:
src/regulaitor/orchestration/graph.py            # Task 4 — wrap run() + _trace_record helper
src/regulaitor/orchestration/document_graph.py   # Task 5 — wrap run_document()
redteam/runner.py                                 # Task 6 — _run_with_timeout wrapper
pyproject.toml                                    # Task 1 — +langfuse dep + mypy override
.mcp.json                                         # Task 9 — +langfuse-mcp (explicit OK)
.env                                              # Task 8 doc — user adds LANGFUSE_* (never .env.example)

New tests:
tests/unit/observability/__init__.py             # Task 1
tests/unit/observability/test_langfuse_client.py # Tasks 2-3
tests/unit/redteam/test_runner.py                # Task 6 — extend with timeout test

New docs:
docs/runbook.md                                   # Task 8
docs/adr/0012-observability-architecture.md       # Task 10
```

---

## Task 1: Scaffolding — package, dep, mypy override

**Files:**
- Create: `src/regulaitor/observability/__init__.py`
- Create: `tests/unit/observability/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create observability package**

`src/regulaitor/observability/__init__.py`:
```python
"""H11 — Observability. Optional LangFuse tracing (metadata-only, no-op
without LANGFUSE_* env). Instrumentation lives at the orchestration layer;
agents are untouched."""
```

`tests/unit/observability/__init__.py`:
```python
"""H11 — Observability unit tests."""
```

- [ ] **Step 2: Add langfuse dep to pyproject.toml**

In `[project.optional-dependencies] dev = [ ... ]`, add after the last entry (keep alphabetical-ish grouping with the other langchain entries):
```
    "langfuse>=2,<3",
```

Add a mypy override (langfuse ships no py.typed in some versions). After the last `[[tool.mypy.overrides]]` block, before `[tool.coverage.run]`:
```toml
[[tool.mypy.overrides]]
module = "langfuse"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "langfuse.*"
ignore_missing_imports = true
```

- [ ] **Step 3: Sync deps**

Run: `uv sync --extra dev`
Expected: `langfuse` installed, no resolution errors.

- [ ] **Step 4: Verify pip-audit still clean**

Run: `uv run pip-audit --skip-editable --ignore-vuln CVE-2026-1839 --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2026-6587 2>&1 | tail -3`
Expected: "No known vulnerabilities found" OR new CVEs surfaced. If new CVEs from langfuse transitive deps: document in this task's commit message + add `--ignore-vuln` in `.github/workflows/ci.yml` with rationale (follow the H8 pattern; do not silently ignore).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/observability/ tests/unit/observability/ pyproject.toml uv.lock
git commit -m "chore(h11): scaffold observability package + langfuse dep"
```

---

## Task 2: `langfuse_client.py` — is_enabled + TurnTrace + no-op path

**Files:**
- Create: `src/regulaitor/observability/langfuse_client.py`
- Create: `tests/unit/observability/test_langfuse_client.py`

- [ ] **Step 1: Write failing tests (no-op path)**

`tests/unit/observability/test_langfuse_client.py`:
```python
"""Unit tests for observability/langfuse_client.py."""

from __future__ import annotations

import pytest

from regulaitor.observability import langfuse_client as lc


def test_is_enabled_false_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    assert lc.is_enabled() is False


def test_is_enabled_false_with_partial_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    assert lc.is_enabled() is False


def test_is_enabled_true_with_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    assert lc.is_enabled() is True


def test_trace_turn_noop_yields_inert_accumulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    with lc.trace_turn(
        kind="chat", case_id="c1", corpus="ai_act", language="es"
    ) as tt:
        tt.set_root(verdict="pass", cost_eur_total=0.02)
        tt.span("retriever", n_chunks=5, latency_ms=12)
    # No exception; accumulator captured data but nothing was sent.
    assert tt.kind == "chat"
    assert tt._root_meta["verdict"] == "pass"
    assert tt._spans["retriever"]["n_chunks"] == 5


def test_trace_turn_noop_does_not_import_langfuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without keys, the langfuse SDK must NOT be imported (zero overhead)."""
    import sys

    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delitem(sys.modules, "langfuse", raising=False)
    with lc.trace_turn(kind="chat", case_id="c", corpus="ai_act", language="es"):
        pass
    assert "langfuse" not in sys.modules
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest --no-cov tests/unit/observability/test_langfuse_client.py -v`
Expected: ImportError / ModuleNotFoundError on `regulaitor.observability.langfuse_client`.

- [ ] **Step 3: Write `langfuse_client.py` (no-op path only)**

`src/regulaitor/observability/langfuse_client.py`:
```python
"""H11 — Optional LangFuse tracing. Metadata-only; no raw text leaves the
process. No-op (zero overhead, SDK not imported) when LANGFUSE_* env vars
are absent. Any LangFuse failure is swallowed with a WARNING — observability
never breaks or slows the pipeline (spec §2 enfoque A)."""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger("regulaitor.observability")

_REQUIRED_ENV = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")


def is_enabled() -> bool:
    """True only if all three LANGFUSE_* env vars are present and non-empty."""
    return all(os.environ.get(k) for k in _REQUIRED_ENV)


def hash12(value: str) -> str:
    """sha256[:12] — the canonical redaction primitive (matches sanitizer)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dataclass
class TurnTrace:
    """In-memory metadata accumulator. The orchestration layer fills it;
    on context exit it is flushed to LangFuse when enabled, else inert.
    NEVER store raw query/document/citation text here — only metadata
    and hashes (spec §3.3 redaction rule)."""

    kind: Literal["chat", "document"]
    case_id: str
    corpus: str
    language: str
    _root_meta: dict[str, Any] = field(default_factory=dict)
    _spans: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_root(self, **meta: Any) -> None:
        self._root_meta.update(meta)

    def span(self, name: str, **meta: Any) -> None:
        self._spans[name] = meta


@contextmanager
def trace_turn(
    *,
    kind: Literal["chat", "document"],
    case_id: str,
    corpus: str,
    language: str,
) -> Iterator[TurnTrace]:
    """Yield a TurnTrace. No-op if not is_enabled() (SDK not imported).
    Enabled path is added in the next task."""
    tt = TurnTrace(kind=kind, case_id=case_id, corpus=corpus, language=language)
    if not is_enabled():
        yield tt
        return
    # Enabled path implemented in Task 3.
    yield tt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest --no-cov tests/unit/observability/test_langfuse_client.py -v`
Expected: 5/5 PASS.

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/regulaitor/observability/ tests/unit/observability/ && uv run black --check src/regulaitor/observability/ && uv run mypy src/regulaitor/observability/`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/observability/langfuse_client.py tests/unit/observability/test_langfuse_client.py
git commit -m "feat(h11): langfuse_client is_enabled + TurnTrace + no-op trace_turn"
```

---

## Task 3: `langfuse_client.py` — enabled path + graceful swallow + redaction-hard test

**Files:**
- Modify: `src/regulaitor/observability/langfuse_client.py`
- Modify: `tests/unit/observability/test_langfuse_client.py`

- [ ] **Step 1: Write failing tests (enabled path, swallow, redaction)**

Append to `tests/unit/observability/test_langfuse_client.py`:
```python
class _FakeTrace:
    def __init__(self) -> None:
        self.updated: list[dict] = []
        self.spans: list[tuple[str, dict]] = []

    def update(self, **kw: object) -> None:
        self.updated.append(kw.get("metadata", {}))  # type: ignore[arg-type]

    def span(self, **kw: object) -> None:
        self.spans.append((kw.get("name", ""), kw.get("metadata", {})))  # type: ignore[arg-type]


class _FakeLangfuse:
    last_instance: "_FakeLangfuse | None" = None

    def __init__(self, *a: object, **kw: object) -> None:
        self.traces: list[_FakeTrace] = []
        self.flushed = False
        _FakeLangfuse.last_instance = self

    def trace(self, **kw: object) -> _FakeTrace:
        t = _FakeTrace()
        self.traces.append(t)
        return t

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def _enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    import sys
    import types

    fake_mod = types.ModuleType("langfuse")
    fake_mod.Langfuse = _FakeLangfuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_mod)
    return _FakeLangfuse


def test_trace_turn_enabled_emits_root_and_spans(
    _enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    with lc.trace_turn(
        kind="chat", case_id="c1", corpus="ai_act", language="es"
    ) as tt:
        tt.set_root(verdict="pass", cost_eur_total=0.02, query_sha256_12="abc123")
        tt.span("retriever", n_chunks=5, latency_ms=12)
        tt.span("analyst", latency_ms=3000, cost_eur=0.018)
    inst = _enabled.last_instance
    assert inst is not None
    assert inst.flushed is True
    assert inst.traces[0].updated[-1]["verdict"] == "pass"
    span_names = {n for n, _ in inst.traces[0].spans}
    assert {"retriever", "analyst"} <= span_names


def test_trace_turn_swallows_langfuse_init_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    import sys
    import types

    fake_mod = types.ModuleType("langfuse")

    class _Boom:
        def __init__(self, *a: object, **k: object) -> None:
            raise RuntimeError("langfuse down")

    fake_mod.Langfuse = _Boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_mod)
    # Must NOT raise — pipeline continues.
    with lc.trace_turn(
        kind="chat", case_id="c", corpus="ai_act", language="es"
    ) as tt:
        tt.set_root(verdict="pass")
    assert tt._root_meta["verdict"] == "pass"


def test_trace_turn_swallows_flush_failure(
    _enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom_flush(self: object) -> None:
        raise RuntimeError("flush failed")

    monkeypatch.setattr(_enabled, "flush", _boom_flush)
    # Must NOT raise.
    with lc.trace_turn(
        kind="document", case_id="d", corpus="gdpr", language="es"
    ) as tt:
        tt.set_root(document_verdict="block")


def test_redaction_hard_no_raw_text_in_payload(
    _enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SSDLC: a sentinel resembling raw query/doc/citation text must never
    appear in anything sent to LangFuse. Caller is responsible for hashing;
    this test asserts the client does not stringify the accumulator naively
    AND documents the contract."""
    sentinel = "CONFIDENTIAL_CLIENT_POLICY_TEXT_SENTINEL"
    with lc.trace_turn(
        kind="document", case_id="d", corpus="gdpr", language="es"
    ) as tt:
        # Correct usage: only hashes/metadata. We deliberately pass a hash.
        tt.set_root(document_sha256_12=lc.hash12(sentinel))
        tt.span("sanitizer", n_events=3, blocked_category=None)
    inst = _enabled.last_instance
    serialized = repr(inst.traces[0].updated) + repr(inst.traces[0].spans)
    assert sentinel not in serialized
    assert lc.hash12(sentinel) in serialized
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest --no-cov tests/unit/observability/test_langfuse_client.py -v`
Expected: the 4 new tests FAIL (enabled path is a stub: no flush, no spans emitted).

- [ ] **Step 3: Implement the enabled path**

Replace the `trace_turn` body in `langfuse_client.py` (everything after the no-op `return`) with:
```python
@contextmanager
def trace_turn(
    *,
    kind: Literal["chat", "document"],
    case_id: str,
    corpus: str,
    language: str,
) -> Iterator[TurnTrace]:
    """Yield a TurnTrace. No-op if not is_enabled() (SDK not imported).
    When enabled: open a LangFuse trace, accumulate metadata via the
    yielded TurnTrace, and on exit emit root metadata + sub-spans and
    async-flush. Any LangFuse error is logged WARNING and swallowed —
    the pipeline is never broken or blocked."""
    tt = TurnTrace(kind=kind, case_id=case_id, corpus=corpus, language=language)
    if not is_enabled():
        yield tt
        return
    client: Any = None
    trace: Any = None
    try:
        from langfuse import Langfuse  # lazy import — only on enabled path

        client = Langfuse()
        trace = client.trace(
            name=f"{kind}_turn",
            metadata={"case_id": case_id, "corpus": corpus, "language": language},
        )
    except Exception as exc:  # noqa: BLE001 — observability must never break the pipeline
        logger.warning("langfuse init failed; tracing skipped this turn: %s", exc)
        yield tt
        return
    try:
        yield tt
    finally:
        try:
            trace.update(metadata=dict(tt._root_meta))
            for span_name, span_meta in tt._spans.items():
                trace.span(name=span_name, metadata=dict(span_meta))
            client.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning("langfuse flush failed; trace dropped: %s", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest --no-cov tests/unit/observability/test_langfuse_client.py -v`
Expected: 9/9 PASS (5 from Task 2 + 4 new).

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/regulaitor/observability/ tests/unit/observability/ && uv run black src/regulaitor/observability/ tests/unit/observability/ && uv run mypy src/regulaitor/observability/`
Expected: green (black may reformat — re-run pytest after).

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/observability/langfuse_client.py tests/unit/observability/test_langfuse_client.py
git commit -m "feat(h11): langfuse_client enabled path + graceful swallow + redaction-hard test"
```

---

## Task 4: Instrument chat graph (`graph.py`)

**Files:**
- Modify: `src/regulaitor/orchestration/graph.py`
- Modify: `tests/unit/agents/test_chat_graph.py` (or wherever `graph.run` is unit-tested — verify with `grep -rl "orchestration.graph import\|graph.run(" tests/`; create `tests/unit/orchestration/test_graph_tracing.py` if no suitable file)

- [ ] **Step 1: Write failing regression + tracing test**

Create `tests/unit/orchestration/test_graph_tracing.py` (and `tests/unit/orchestration/__init__.py` if absent with `"""H11 orchestration tracing tests."""`):
```python
"""H11 — chat graph tracing regression: behaviour identical without keys,
metadata emitted with keys. Backend graph is mocked (no LLM)."""

from __future__ import annotations

import pytest

from regulaitor.orchestration import graph as g


def _fake_final_dict() -> dict:
    return {
        "case_id": "c1",
        "query": "test query",
        "corpus": "ai_act",
        "language": "es",
        "errors": [],
        "injection_blocked": False,
        "audited_answer": None,
    }


def test_run_without_keys_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)

    class _Compiled:
        def invoke(self, _initial: object) -> dict:
            return _fake_final_dict()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _Compiled())
    state = g.run(query="test query", corpus="ai_act", language="es", case_id="c1")
    assert state.case_id == "c1"
    assert state.corpus == "ai_act"


def test_run_emits_trace_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _TT:
        def set_root(self, **kw: object) -> None:
            captured.update(kw)

        def span(self, name: str, **kw: object) -> None:
            captured[f"span:{name}"] = kw

    import contextlib

    @contextlib.contextmanager
    def _fake_trace_turn(**_kw: object):
        yield _TT()

    monkeypatch.setattr(g, "trace_turn", _fake_trace_turn)

    class _Compiled:
        def invoke(self, _initial: object) -> dict:
            return _fake_final_dict()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _Compiled())
    g.run(query="test query", corpus="ai_act", language="es", case_id="c1")
    assert "verdict" in captured
    assert "latency_ms_total" in captured
    assert "query_sha256_12" in captured
    # Redaction: raw query never in the captured metadata values.
    assert "test query" not in repr(captured)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest --no-cov tests/unit/orchestration/test_graph_tracing.py -v`
Expected: `test_run_emits_trace_metadata_when_enabled` FAILS (`g.trace_turn` does not exist yet); regression test may pass already.

- [ ] **Step 3: Refactor `_log_turn` to share a record builder + wrap `run`**

In `src/regulaitor/orchestration/graph.py`:

Add import near the top (after existing imports):
```python
from regulaitor.observability.langfuse_client import hash12, trace_turn
```

Extract the record dict so logging and tracing share it. Replace the body of `_log_turn` so it delegates to a new `_trace_record`:
```python
def _trace_record(state: ChatState, latency_ms_total: int) -> dict[str, object]:
    """Metadata-only summary of a chat turn. NO raw query — only a
    sha256[:12] prefix (CLAUDE.md §10.5/§18.8). Shared by the JSON log
    line and the LangFuse trace."""
    query_hash = hash12(state.query)
    verdict: str
    n_findings = 0
    n_citations = 0
    n_validated = 0
    n_blocked = 0
    reason_code: str | None = None
    if state.injection_blocked:
        verdict = "blocked_injection"
        reason_code = state.injection_reason
    elif state.audited_answer is not None:
        audited = state.audited_answer
        verdict = audited.verdict.value
        n_findings = len(audited.answer.findings)
        n_citations = len(audited.audit_results)
        n_validated = sum(1 for r in audited.audit_results if r.validated)
        n_blocked = n_citations - n_validated
        reason_code = None if audited.reason is None else audited.reason.split(":", 1)[0]
    else:
        verdict = "no_answer"
    return {
        "case_id": state.case_id,
        "query_hash": query_hash,
        "corpus": state.corpus,
        "language": state.language,
        "verdict": verdict,
        "n_findings": n_findings,
        "n_citations": n_citations,
        "n_validated": n_validated,
        "n_blocked": n_blocked,
        "latency_ms_total": latency_ms_total,
        "reason_code": reason_code,
        "errors": list(state.errors),
    }


def _log_turn(state: ChatState, latency_ms_total: int) -> None:
    """Emit the structured JSON log line (unchanged output)."""
    record = _trace_record(state, latency_ms_total)
    logger.info("chat_turn: %s", json.dumps(record, ensure_ascii=False))
```

Wrap `run` with `trace_turn`:
```python
def run(*, query: str, corpus: str, language: str, case_id: str) -> ChatState:
    """Run the cached compiled graph; return the final ChatState."""
    with trace_turn(
        kind="chat", case_id=case_id, corpus=corpus, language=language
    ) as tt:
        initial = ChatState(
            case_id=case_id,
            query=query,
            corpus=cast(Norma, corpus),
            language=cast(Language, language),
        )
        t0 = time.monotonic()
        final_dict = _compiled_graph().invoke(initial)
        latency_ms_total = int((time.monotonic() - t0) * 1000)
        state = ChatState.model_validate(final_dict)
        record = _trace_record(state, latency_ms_total)
        logger.info("chat_turn: %s", json.dumps(record, ensure_ascii=False))
        tt.set_root(
            verdict=record["verdict"],
            query_sha256_12=record["query_hash"],
            n_findings=record["n_findings"],
            n_citations=record["n_citations"],
            n_validated=record["n_validated"],
            n_blocked=record["n_blocked"],
            latency_ms_total=record["latency_ms_total"],
        )
        return state
```

Note: `run` now logs directly via `_trace_record` (so `_log_turn` is no longer called from `run` — it stays for any other callers/tests). If a test asserts `_log_turn` is called by `run`, update it to assert the `chat_turn:` log line is emitted instead. Verify with: `grep -rn "_log_turn" tests/ src/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest --no-cov tests/unit/orchestration/ tests/unit/agents/ -v 2>&1 | tail -15`
Expected: tracing tests PASS; pre-existing chat graph tests still PASS (regression zero). If a pre-existing test asserted `_log_turn` call-count, fix it to assert the log output instead.

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/regulaitor/orchestration/graph.py && uv run black src/regulaitor/orchestration/graph.py && uv run mypy src/regulaitor/orchestration/graph.py`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/orchestration/graph.py tests/unit/orchestration/
git commit -m "feat(h11): instrument chat graph with trace_turn (shared _trace_record, regression-zero without keys)"
```

---

## Task 5: Instrument document pipeline (`document_graph.py`)

**Files:**
- Modify: `src/regulaitor/orchestration/document_graph.py`
- Modify: `tests/unit/orchestration/test_graph_tracing.py` (add doc cases)

- [ ] **Step 1: Read the current `run_document` + `_log_document_turn`**

Run: `sed -n '160,265p' src/regulaitor/orchestration/document_graph.py`
Note the `run_document(*, file_bytes, mime_type, language, corpus, case_id) -> DocumentReport` signature and the two `return ... DocumentReport` paths (early-block and normal) — both currently call `_log_document_turn(report)`.

- [ ] **Step 2: Write failing doc-tracing test**

Append to `tests/unit/orchestration/test_graph_tracing.py`:
```python
def test_run_document_emits_trace_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from regulaitor.orchestration import document_graph as dg

    captured: dict = {}

    class _TT:
        def set_root(self, **kw: object) -> None:
            captured.update(kw)

        def span(self, name: str, **kw: object) -> None:
            captured[f"span:{name}"] = kw

    import contextlib

    @contextlib.contextmanager
    def _fake_trace_turn(**_kw: object):
        yield _TT()

    monkeypatch.setattr(dg, "trace_turn", _fake_trace_turn)

    # Stub the pipeline to return a minimal DocumentReport quickly.
    from regulaitor.citation.schemas import AuditVerdict, DocumentReport

    fake = DocumentReport(
        case_id="d1",
        document_hash="0" * 64,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[],
        document_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        document_reason="stub",
        n_segments_total=0,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=42,
        cost_eur_total=0.0,
    )
    monkeypatch.setattr(dg, "_run_pipeline", lambda **kw: fake, raising=False)
    # If _run_pipeline is not the internal name, this test must patch the
    # actual internal entry; see Step 3 note.
    try:
        dg.run_document(
            file_bytes=b"%PDF-1.4 stub",
            mime_type="application/pdf",
            language="es",
            corpus=["ai_act"],
            case_id="d1",
        )
    except Exception:
        pass  # extraction of a stub PDF may fail; we only assert tracing wiring
    assert "document_verdict" in captured or "verdict" in captured
```

> Implementation note for Step 3: `run_document` does NOT have a clean single internal seam to stub. The robust approach: wrap the whole `run_document` body in `with trace_turn(...) as tt:` and call `tt.set_root(...)` from a new `_doc_trace_record(report)` helper just before each `return report`. The test above asserts the wiring; if stubbing the pipeline is impractical, mark this test `@pytest.mark.integration` and rely on the regression test (Step 4) + the langfuse_client unit tests for coverage. Keep the test that proves "without keys, behaviour unchanged".

- [ ] **Step 3: Wrap `run_document` + add `_doc_trace_record`**

In `src/regulaitor/orchestration/document_graph.py`:

Add import:
```python
from regulaitor.observability.langfuse_client import hash12, trace_turn
```

Add a metadata-only record helper (mirror the chat one):
```python
def _doc_trace_record(report: DocumentReport) -> dict[str, object]:
    """Metadata-only summary of a document turn. NO raw document text."""
    return {
        "case_id": report.case_id,
        "document_sha256_12": report.document_hash[:12],
        "corpus": ",".join(report.corpus),
        "language": report.language,
        "document_verdict": report.document_verdict.value,
        "n_segments_total": report.n_segments_total,
        "n_segments_pass": report.n_segments_pass,
        "n_segments_block": report.n_segments_block,
        "n_segments_review": report.n_segments_review,
        "n_segments_blocked_by_injection": report.n_segments_blocked_by_injection,
        "latency_ms_total": report.latency_ms_total,
        "cost_eur_total": report.cost_eur_total,
    }
```

Wrap the `run_document` body: open `with trace_turn(kind="document", case_id=case_id, corpus=",".join(corpus), language=language) as tt:` around the existing logic. Before EACH `return report` (the early-block path and the normal path), insert:
```python
        tt.set_root(**_doc_trace_record(report))
```
Keep `_log_document_turn(report)` calls exactly as they are (unchanged log output).

- [ ] **Step 4: Run tests + regression**

Run: `uv run pytest --no-cov tests/unit/orchestration/ -v 2>&1 | tail -10`
Expected: tracing wiring test PASS (or skipped-integration per Step 2 note); existing document_graph tests still PASS.
Also run the doc integration smoke if present: `uv run pytest --no-cov tests/integration/test_document_flow.py -q 2>&1 | tail -3` (expected: unchanged pass/skip).

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/regulaitor/orchestration/document_graph.py && uv run black src/regulaitor/orchestration/document_graph.py && uv run mypy src/regulaitor/orchestration/document_graph.py`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/orchestration/document_graph.py tests/unit/orchestration/test_graph_tracing.py
git commit -m "feat(h11): instrument document pipeline with trace_turn (metadata-only, regression-zero)"
```

---

## Task 6: Redteam runner per-attack timeout

**Files:**
- Modify: `redteam/runner.py`
- Modify: `tests/unit/redteam/test_runner.py`

- [ ] **Step 1: Write failing timeout test**

Append to `tests/unit/redteam/test_runner.py`:
```python
def test_run_with_timeout_returns_timeout_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time as _time

    from redteam import runner as r

    attack = Attack.model_validate(_attack_dict(id="attack-099", mode="chat"))

    def _slow(_a: object) -> object:
        _time.sleep(2)
        raise AssertionError("should have timed out before returning")

    outcome = r._run_with_timeout(_slow, attack, timeout_s=1)
    assert outcome.attack_id == "attack-099"
    assert outcome.blocked is False
    assert outcome.actual_verdict == "timeout"
    assert "timeout" in (outcome.error or "")
    assert outcome.actual_block_layer == "none"


def test_run_with_timeout_passthrough_on_fast_fn() -> None:
    from redteam import runner as r
    from redteam.schemas import AttackOutcome

    attack = Attack.model_validate(_attack_dict(id="attack-100", mode="chat"))

    def _fast(a: object) -> AttackOutcome:
        return AttackOutcome(
            attack_id=attack.id,
            blocked=True,
            actual_block_layer="auditor",
            actual_verdict="block",
            matches_expected=True,
            latency_ms=10,
            cost_eur=0.0,
            error=None,
        )

    outcome = r._run_with_timeout(_fast, attack, timeout_s=5)
    assert outcome.blocked is True
    assert outcome.actual_verdict == "block"
```

(`_attack_dict` already exists in this test file from H9.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest --no-cov tests/unit/redteam/test_runner.py -v -k timeout`
Expected: FAIL — `runner._run_with_timeout` does not exist.

- [ ] **Step 3: Add the timeout wrapper + wire into `main`**

In `redteam/runner.py`:

> **⚠️ PLAN CORRECTION (2026-05-16, post code-review).** The original snippet
> below used `ThreadPoolExecutor + future.result(timeout)`. Two-stage code
> review found this is a **Critical defect**: `with ThreadPoolExecutor(...)`
> calls `shutdown(wait=True)` on `__exit__`, blocking the timeout return until
> the worker finishes; `concurrent.futures` also registers an `atexit` join
> over non-daemon workers — so on a true silent API hang the runner would
> still hang forever (the exact H9 failure this task prevents). The snippet
> has been corrected to an **abandoned daemon thread + `join(timeout)`**.
> See decisions log §H11 Amendment 1 / §H9 amendment 6.

Add imports (top, with the stdlib group):
```python
import os
import threading
```

Add constants near `_ATTACKS_PATH`:
```python
# Generous ceilings — chat is retriever+LLM (~15-60s typical), doc-E2E is
# multi-segment (minutes); these only trip on a true silent API hang (H9).
_CHAT_TIMEOUT_S = int(os.environ.get("REGULAITOR_REDTEAM_TIMEOUT_CHAT", "300"))
_DOC_TIMEOUT_S = int(os.environ.get("REGULAITOR_REDTEAM_TIMEOUT_DOC", "900"))
```

Add the wrapper function (after `run_doc_attack`, before `aggregate`):
```python
def _run_with_timeout(
    fn: Callable[[Attack], AttackOutcome], attack: Attack, timeout_s: int
) -> AttackOutcome:
    """Run fn(attack) in a daemon thread; if it exceeds timeout_s, return a
    timeout AttackOutcome instead of hanging the whole run (H9 lesson:
    Anthropic API can hang silently with no traceback). The orphaned daemon
    thread is abandoned — it does not block process exit, and consumes at
    most one in-flight API call (~$0.02-0.19). A daemon thread is used
    deliberately: concurrent.futures' executor blocks on shutdown(wait=True)
    at context exit AND registers an atexit join over non-daemon workers,
    either of which would re-introduce the very hang this guards against."""
    box: dict[str, AttackOutcome] = {}
    err: dict[str, Exception] = {}

    def _target() -> None:
        try:
            box["v"] = fn(attack)
        except Exception as exc:  # noqa: BLE001 — marshalled and re-raised below
            err["e"] = exc

    th = threading.Thread(
        target=_target, daemon=True, name=f"redteam-attack-{attack.id}"
    )
    th.start()
    th.join(timeout=timeout_s)
    if th.is_alive():
        return AttackOutcome(
            attack_id=attack.id,
            blocked=False,
            actual_block_layer="none",
            actual_verdict="timeout",
            matches_expected=False,
            latency_ms=timeout_s * 1000,
            cost_eur=0.0,
            error=f"timeout: attack exceeded {timeout_s}s (likely Anthropic hang)",
        )
    if "e" in err:
        raise err["e"]
    return box["v"]
```

Add `Callable` to the imports → `from collections.abc import Callable` if not
present (check top of file; H9 runner imports — add if missing). Also add a
wall-clock **promptness regression test** (a worker sleeping `timeout_s * 5`
must return in `< timeout_s + slack`) — the original test passed only because
its slow fn slept a bounded 2 s and never asserted prompt return.

Wire into `main`'s dispatch loop — replace:
```python
    for attack in attacks:
        if attack.mode == "chat":
            outcomes.append(run_chat_attack(attack))
        else:
            outcomes.append(run_doc_attack(attack))
```
with:
```python
    for attack in attacks:
        if attack.mode == "chat":
            outcomes.append(
                _run_with_timeout(run_chat_attack, attack, _CHAT_TIMEOUT_S)
            )
        else:
            outcomes.append(
                _run_with_timeout(run_doc_attack, attack, _DOC_TIMEOUT_S)
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest --no-cov tests/unit/redteam/test_runner.py -v 2>&1 | tail -10`
Expected: all redteam runner tests PASS including the 2 new timeout tests.

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check redteam/runner.py && uv run black redteam/runner.py && uv run mypy redteam/`
Expected: green.

- [ ] **Step 6: Emit `block_rate` as a LangFuse score (no-op without keys)**

Spec §3.3 lists `block_rate` as a custom score sourced from the redteam runner. Add to `main()` in `redteam/runner.py`, right after `agg = aggregate(...)` and before report rendering:
```python
    try:
        from regulaitor.observability.langfuse_client import is_enabled

        if is_enabled():
            from langfuse import Langfuse  # lazy

            _lf = Langfuse()
            _lf.score(
                name="block_rate",
                value=agg.block_rate,
                comment=f"redteam {meta.mode} run, n={agg.n_total}",
            )
            _lf.flush()
    except Exception as exc:  # noqa: BLE001 — observability never breaks the run
        import logging

        logging.getLogger("regulaitor.observability").warning(
            "langfuse block_rate score emit failed: %s", exc
        )
```
Add a unit test asserting that without keys this block is a no-op (the runner completes and writes the report unchanged). The `citation_recall` / `verdict_match` harness scores from spec §3.3 are explicitly **deferred to H15** (emitting them needs a paid re-eval run; the numbers already live in `evals/reports/latest.md` + decisions log §H10, so pushing them to LangFuse now adds no analytical value — record this deferral in decisions log §H11 + evidence_matrix).

- [ ] **Step 7: Run tests + lint + types**

Run: `uv run pytest --no-cov tests/unit/redteam/ -v 2>&1 | tail -10 && uv run ruff check redteam/runner.py && uv run black redteam/runner.py && uv run mypy redteam/`
Expected: all green, timeout + no-op-score tests pass.

- [ ] **Step 8: Commit**

```bash
git add redteam/runner.py tests/unit/redteam/test_runner.py
git commit -m "fix(h11): per-attack timeout + block_rate LangFuse score in redteam runner (closes H9 hang risk)"
```

---

## Task 7: Full 50-attack redteam run + populate H9 deferred placeholders

**Files:** Modifies `redteam/reports/latest.md`, `docs/security_report.md`, `docs/technical_decisions_log.md`, `docs/adr/0011-redteam-runner.md`, `CLAUDE.md`.

**⚠️ Cost ~$3.3 Anthropic. User-gated. Confirm before running.**

- [ ] **Step 1: Confirm with user**

State: "About to run full `make redteam` (50 attacks, ~$3.3, timeouts now protect against hang). Proceed?" Wait for explicit OK.

- [ ] **Step 2: Backup current smoke report**

```bash
cp redteam/reports/latest.md /tmp/redteam_smoke_pre_h11.md
```

- [ ] **Step 3: Run full redteam in background**

Load `.env` (parse `LANGFUSE_*` + `ANTHROPIC_API_KEY`), then `uv run python -m scripts.redteam` (no `--smoke`). Run in background; the per-attack timeout (Task 6) guarantees it cannot hang indefinitely. Expect ~1.5-3h wall (timeouts cap worst case at 50 × 900s ≈ 12.5h absolute ceiling, but normal completion ~2h).

- [ ] **Step 4: When complete, read metrics**

```bash
grep -E "block_rate \(final\)|Mode:|Total cost" redteam/reports/latest.md
grep -A12 "Per-scenario" redteam/reports/latest.md
grep -c "verdict.*timeout" redteam/reports/latest.md   # how many attacks timed out
```

- [ ] **Step 5: Commit the full report**

```bash
git add redteam/reports/latest.md
git commit -m "docs(h11): full 50-attack redteam run — closes H9 deferred (block_rate <X.XX>)"
```

- [ ] **Step 6: Populate the four `<deferred>` placeholders**

Replace the H9-deferred markers with the measured `block_rate_final` + per-scenario + per-layer numbers, in:
- `docs/security_report.md` — the "Full run deferred" block + the per-scenario/per-layer tables (replace the smoke-only framing with the full result; keep smoke as the pre-improvement baseline).
- `docs/technical_decisions_log.md §H9` amendment 5 — change "deferred to H11" to "completed in H11 (commit `<sha>`): block_rate_final <X.XX>".
- `docs/adr/0011-redteam-runner.md:94` — replace the deferred line with the measured value.
- `CLAUDE.md §27` H9 line — replace "Full run sobre 50 diferido a H11..." with "Full run 50 ataques completado en H11: block_rate <X.XX>".

If block_rate_final < 0.90: this is a calibration signal for H15 (NOT an H9 re-open) — note it explicitly in security_report.md and decisions log, mirroring the H8/H10 metric-honesty pattern. Gate §16.2 #4 stays satisfied by the smoke evidence already documented; the full number is reported transparently.

- [ ] **Step 7: Commit placeholder population**

```bash
git add docs/security_report.md docs/technical_decisions_log.md docs/adr/0011-redteam-runner.md CLAUDE.md
git commit -m "docs(h11): populate H9 deferred placeholders with measured full redteam result"
```

---

## Task 8: `docs/runbook.md`

**Files:**
- Create: `docs/runbook.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbook.md` with these sections (CLAUDE.md §21.6 deliverable):

1. **LangFuse setup**: step-by-step — create free account at cloud.langfuse.com, create a project, copy `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`, set `LANGFUSE_HOST=https://cloud.langfuse.com`, add all three to the local `.env` (NEVER `.env.example` — single `.env` rule). State explicitly: without these the system runs identically (tracing no-op), only the dashboard stays empty.
2. **What the dashboard shows**: per-trace latency, cost over time, custom scores (`block_rate`, `citation_recall`, `verdict_match`). Note that screenshots go into the H17 memoria.
3. **Latency interpretation (closes §17 #7 caveat)**: explain that the per-span latency in LangFuse IS the clean product SLA (~15-60s per query), whereas `evals/reports/latest.md` `latency_p95_ms` (~572s) is batch-under-rate-limit and must NOT be cited as the product SLA.
4. **Operational runbook**: concrete steps if (a) `block_rate` drops below 0.90 → check recent security/ commits, run `make redteam-smoke`; (b) latency p95 rises → check Anthropic status, retriever model cache, recent prompt changes; (c) cost spikes → check token counts per span, retry_triggered rate (H4 fix), unexpected eval/redteam runs.
5. **Reproducibility**: the canonical `make` sequence + the Windows `make` gotcha pointer (already in README).

- [ ] **Step 2: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(h11): add operational runbook (LangFuse setup + dashboard + latency interpretation)"
```

---

## Task 9: `langfuse-mcp` in `.mcp.json`

**Files:**
- Modify: `.mcp.json`

- [ ] **Step 1: Inspect current `.mcp.json`**

Run: `cat .mcp.json`
Note the existing server entry structure (command, args, scopes pattern).

- [ ] **Step 2: Propose the exact command + config to the user, wait for explicit OK**

CLAUDE.md §13 requires explicit approval before adding any MCP. Present the proposed `langfuse-mcp` server block (read-only scopes: query traces/observations only, no write) and the install command. Do NOT edit `.mcp.json` until the user approves the exact block.

- [ ] **Step 3: Add the approved block**

Add the `langfuse-mcp` server to `.mcp.json` exactly as approved (env vars referencing the same `LANGFUSE_*` from `.env`, never inlined secrets).

- [ ] **Step 4: Commit**

```bash
git add .mcp.json
git commit -m "chore(h11): add langfuse-mcp server (read-only traces) to .mcp.json"
```

---

## Task 10: H11 closure — ADR + decisions log + evidence matrix + CLAUDE.md + memory + tag

**Files:**
- Create: `docs/adr/0012-observability-architecture.md`
- Modify: `docs/technical_decisions_log.md` (append §H11)
- Modify: `docs/evidence_matrix.md` (Módulo 3 observability rows + follow-ups + gate #4 full)
- Modify: `CLAUDE.md` §27 (H11 closed + H12 next)
- Memory: rename `h10_closed_h11_starting.md` → `h11_closed_h12_starting.md`, rewrite content; update `MEMORY.md`

- [ ] **Step 1: Write ADR 0012**

`docs/adr/0012-observability-architecture.md` mirroring the ADR 0011 structure: Status/Date, Context (no observability/ module pre-H11; §10.5 requirement; §18.8 privacy; §17 #7 latency caveat), Decision (6 Qs + enfoque A summarized), Consequences (positive: clean SLA measurement, deferred H9 closed; negative: trace metadata only — no content debugging; LangFuse cloud dependency for dashboard only), Alternatives considered (self-hosted, OTel, eager flush, per-agent decorators — all rejected with reasons), References (spec, plan, decisions log §H11).

- [ ] **Step 2: Append decisions log §H11**

Append a `## H11 — Observabilidad + redteam reliability (cerrado <YYYY-MM-DD>, squash `<sha>`, tag `v0.1.1-h11`)` section: 6 brainstorming Qs + enfoque A + amendments during implementation + closure metrics (full redteam block_rate, langfuse instrumentation surface, timeout config) + skill activation note (none — `cost-accounting` stays H17) + artefacts delivered.

- [ ] **Step 3: Update evidence_matrix.md**

- Módulo 3: change "LangFuse traces | `src/regulaitor/observability/langfuse_client.py` | **deferred H11**" → "✅ H11 (metadata-only, no-op without keys)".
- Gate §16.2 #4 row: "smoke 0.92; full deferred H11" → "smoke 0.92 + full <X.XX> (H11)".
- Open follow-ups table: mark "Full redteam 50-attack run" and "LangFuse observability" as ✅ done H11; keep latency-optimization → H15, OTel/Prometheus → HX5.

- [ ] **Step 4: Update CLAUDE.md §27**

Add H11 closed entry after the H10 line; change "Hito siguiente" to H12 (Router multi-LLM + cost analysis).

- [ ] **Step 5: Verify full suite + CI-relevant checks**

```bash
uv run pytest -m "not slow" -q 2>&1 | tail -5
uv run ruff check . 2>&1 | tail -1
uv run mypy 2>&1 | tail -2
uv run python -m scripts.redteam --smoke 2>&1 | tail -1 ; grep "block_rate (final)" redteam/reports/latest.md
```
Expected: tests pass, coverage ≥90% gated, ruff/mypy clean, smoke gate still ≥0.90.

- [ ] **Step 6: Commit closure docs**

```bash
git add docs/adr/0012-observability-architecture.md docs/technical_decisions_log.md docs/evidence_matrix.md CLAUDE.md
git commit -m "docs(h11): close milestone — ADR 0012 + decisions log §H11 + evidence_matrix + CLAUDE.md"
```

- [ ] **Step 7: Push branch + open PR**

```bash
git push -u origin feat/h11-observability
gh pr create --title "feat(h11): observability (LangFuse) + redteam timeout + full 50-attack run" --body "<summary from spec §6 + measured numbers>"
```

- [ ] **Step 8: Wait for CI green + user OK, then squash-merge + tag + memory rename**

After user OK:
- Squash-merge with subject `feat(h11): observability + redteam reliability`.
- Tag `v0.1.1-h11` on the squash commit (confirm scheme with user; alternative `v0.0.11-h11`).
- Populate `<sha>` + `<YYYY-MM-DD>` in ADR 0012, decisions log §H11, CLAUDE.md §27.
- `mv h10_closed_h11_starting.md h11_closed_h12_starting.md`, rewrite for MVP+H11 state + H12 boundary; update `MEMORY.md` index line.

---

## Closure gate checklist (Task 10 wrap-up)

- [ ] `langfuse_client.py`: no-op without keys (SDK not imported), async batching with keys, all failures swallowed with WARNING.
- [ ] `graph.py` + `document_graph.py` instrumented; regression-zero without keys (proven by test).
- [ ] Redaction-hard test green (no sentinel raw text in trace payload).
- [ ] redteam runner timeout test green; `main` dispatch uses `_run_with_timeout`.
- [ ] Full 50-attack `redteam/reports/latest.md` committed; 4 H9 placeholders populated with measured numbers.
- [ ] `docs/runbook.md` + ADR 0012 + decisions log §H11 committed.
- [ ] langfuse-mcp added with explicit user OK.
- [ ] `evidence_matrix.md` + `CLAUDE.md §27` updated.
- [ ] CI 5 jobs green; coverage `observability/` ≥90%.
- [ ] Tag `v0.1.1-h11` (or confirmed scheme) + memory rename + MEMORY.md updated.

---

## Anti-patterns to avoid

- Do NOT store raw query/document/citation text in `TurnTrace` — only metadata + `hash12()`.
- Do NOT make tracing synchronous/blocking (spec rejected enfoque B).
- Do NOT touch agents H3-H5 — instrumentation is orchestration-layer only.
- Do NOT add `.env.example` (hard rule — single `.env`).
- Do NOT import the `langfuse` SDK at module top-level — lazy import inside the enabled path only.
- Do NOT let any LangFuse exception propagate — swallow + WARNING.
- Do NOT edit `.mcp.json` before explicit user approval of the exact server block (CLAUDE.md §13).
- Do NOT run the full redteam (~$3.3) without explicit user confirmation.
- Do NOT skip pre-commit; no `--no-verify`.
- Do NOT re-open H9 if full block_rate < 0.90 — it is an H15 calibration signal, reported honestly.
