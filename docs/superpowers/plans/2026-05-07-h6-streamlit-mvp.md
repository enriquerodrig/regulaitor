# H6 Streamlit MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a 2-tab Streamlit MVP that wraps the H4 chat pipeline (`run()`) and the H5 document pipeline (`run_document()`), with a persistent legal disclaimer banner and the "no citation, no answer" rule visible in every output.

**Architecture:** 5 files in `src/regulaitor/ui_streamlit/` (empty `__init__.py`, `_render.py` helpers, `tab_ask.py`, `tab_analyze.py`, `app.py` entry). The backend H1-H5 is reused unchanged. Streamlit `st.warning` provides the persistent disclaimer banner, `st.tabs` separates Pregunta from Analiza documento, `st.session_state` keeps a single-slot last-result for each tab. `st.form` + `st.spinner` cover the submit/loading UX. ANTHROPIC_API_KEY consumed only via env var (no UI input — SSDLC).

**Tech Stack:** Python 3.11, Streamlit ≥1.40 (uses `streamlit.testing.v1.AppTest` introduced in 1.28), pytest with monkeypatch for unit tests, the existing H1-H5 backend.

**Reference spec:** `docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md` — read this first.

---

## File Structure

### Created (8)

```
src/regulaitor/ui_streamlit/__init__.py
src/regulaitor/ui_streamlit/_render.py
src/regulaitor/ui_streamlit/tab_ask.py
src/regulaitor/ui_streamlit/tab_analyze.py
src/regulaitor/ui_streamlit/app.py

tests/unit/test_ui_render_helpers.py
tests/unit/test_ui_tab_helpers.py
tests/integration/test_streamlit_smoke.py

docs/adr/0008-streamlit-ui-architecture.md
```

### Modified (5)

```
pyproject.toml          (+streamlit>=1.40,<2.0; coverage scope: ui_streamlit/)
Makefile                (+serve target)
CLAUDE.md               (§27 hitos cerrados +H6; Hito siguiente → H7)
README.md               (Quickstart +sección UI)
docs/technical_decisions_log.md   (+§H6)
```

---

## Task 1: Streamlit dep + `ui_streamlit/` package skeleton

**Goal:** Add Streamlit to runtime deps and create the empty package marker. Foundation for every later task.

**Files:**
- Modify: `pyproject.toml`
- Create: `src/regulaitor/ui_streamlit/__init__.py`

- [ ] **Step 1: Add `streamlit>=1.40,<2.0` to `pyproject.toml`**

Open `pyproject.toml`. Locate `[project] dependencies = [ ... ]`. Add a new entry inside the list:

```toml
"streamlit>=1.40,<2.0",
```

Also extend `[tool.coverage.run].source` to include `src/regulaitor/ui_streamlit`:

```toml
[tool.coverage.run]
source = [
    "src/regulaitor/citation",
    "src/regulaitor/agents",
    "src/regulaitor/rag",
    "src/regulaitor/corpus",
    "src/regulaitor/models",
    "src/regulaitor/orchestration",
    "src/regulaitor/security",
    "src/regulaitor/document",
    "src/regulaitor/mcp_server",
    "src/regulaitor/ui_streamlit",
]
branch = true
```

If the existing `[tool.coverage.run]` has a different shape (single `source = "src/regulaitor"`), simply ensure the existing pattern covers the new package — no edit needed in that case. Verify with: `uv run coverage debug config 2>&1 | head -20`.

Add a mypy override at the bottom of the mypy config block (Streamlit's stubs are partial):

```toml
[[tool.mypy.overrides]]
module = "streamlit"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "streamlit.*"
ignore_missing_imports = true
```

- [ ] **Step 2: Run `uv sync` and verify install**

Run: `uv sync --all-extras`
Expected: streamlit installs cleanly. `uv.lock` regenerates.

Run: `uv run python -c "import streamlit; print(streamlit.__version__)"`
Expected: prints `1.40.x` or higher.

- [ ] **Step 3: Create the package marker**

Create `src/regulaitor/ui_streamlit/__init__.py` with a single newline:

```python

```

(Just an empty file with one newline. The `end-of-file-fixer` pre-commit hook may rewrite this to truly empty — accept that.)

- [ ] **Step 4: Run lint**

Run: `uv run ruff check pyproject.toml src/regulaitor/ui_streamlit/__init__.py`
Run: `uv run black --check src/regulaitor/ui_streamlit/__init__.py`
Run: `uv run mypy src/regulaitor/ui_streamlit/`
All clean.

- [ ] **Step 5: Verify no regressions**

Run: `uv run pytest tests/ -m "not slow and not document_slow" --no-cov -q 2>&1 | tail -5`
Expected: all H1-H5 tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/ui_streamlit/__init__.py pyproject.toml uv.lock
git commit -m "feat(h6): add streamlit dep + ui_streamlit package skeleton

Streamlit ≥1.40,<2.0 (uses streamlit.testing.v1.AppTest from 1.28+).
Coverage scope extended to ui_streamlit/. mypy override for
streamlit (partial stubs upstream)."
```

Pre-commit must pass without `--no-verify`.

---

## Task 2: `_render.py` — render helpers

**Goal:** Implement the 6 render helpers shared between tabs (`verdict_badge`, `finding`, `sanitizer_log_expander`, `error_message`, `chat_state`, `document_report`). All are functions that call Streamlit primitives; they're testable by monkeypatching the `streamlit` module.

**Files:**
- Create: `src/regulaitor/ui_streamlit/_render.py`
- Create: `tests/unit/test_ui_render_helpers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_ui_render_helpers.py`:

```python
"""Tests for ui_streamlit._render — pure-ish functions that call Streamlit primitives.

We monkeypatch streamlit primitives to capture calls and verify the right
ones fire with the expected arguments. Coverage focus: branching on
verdict, severity, exception type.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Context,
    DocumentReport,
    Finding,
    OutlineEntry,
    Page,
    SanitizedDocument,
    SanitizerEvent,
    Segment,
    SegmentResult,
)
from regulaitor.orchestration.state import ChatState
from regulaitor.ui_streamlit import _render


@pytest.fixture
def streamlit_recorder(monkeypatch):
    """Capture all streamlit calls into a list of (method, args, kwargs)."""
    calls: list[tuple[str, tuple, dict]] = []

    class _Expander:
        def __init__(self, label, expanded=False):
            calls.append(("expander_open", (label,), {"expanded": expanded}))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append(("expander_close", (), {}))

    def _expander(label, *, expanded=False):
        return _Expander(label, expanded=expanded)

    class _Cols:
        def __init__(self, n):
            self._n = n
            calls.append(("columns", (n,), {}))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _columns(n):
        return [_Col() for _ in range(n)]

    for method in (
        "success", "error", "warning", "info",
        "markdown", "metric", "dataframe", "caption",
    ):
        monkeypatch.setattr(
            f"streamlit.{method}",
            lambda *a, _m=method, **kw: calls.append((_m, a, kw)),
        )
    monkeypatch.setattr("streamlit.expander", _expander)
    monkeypatch.setattr("streamlit.columns", _columns)
    return calls


def _citation() -> Citation:
    return Citation(
        norma="ai_act", articulo="6", apartado="1",
        language="es", text="texto literal del corpus",
    )


def _finding(text: str = "hallazgo X", sev: str = "medium") -> Finding:
    return Finding(text=text, citations=[_citation()], severity=sev)


def _answer() -> Answer:
    return Answer(query="q", language="es", text="resumen", findings=[_finding()])


def _audited(verdict: AuditVerdict = AuditVerdict.PASS) -> AuditedAnswer:
    return AuditedAnswer(
        answer=_answer(),
        verdict=verdict,
        audit_results=[
            AuditResult(
                citation=_citation(), validated=True, article_exists=True,
                apartado_exists=True, text_normalized_match=True, reason=None,
            )
        ],
        reason=None,
    )


def _chat_state(verdict: AuditVerdict = AuditVerdict.PASS, blocked: bool = False) -> ChatState:
    return ChatState(
        case_id="ch-test",
        query="q",
        corpus="ai_act",
        language="es",
        injection_blocked=blocked,
        injection_reason="ignore-previous" if blocked else None,
        context=None,
        answer=None if blocked else _answer(),
        audited_answer=None if blocked else _audited(verdict),
        errors=[],
    )


# ---------- verdict_badge ----------

def test_verdict_badge_pass(streamlit_recorder):
    _render.verdict_badge(AuditVerdict.PASS)
    methods = [c[0] for c in streamlit_recorder]
    assert "success" in methods
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "success")
    assert "✓" in msg or "PASS" in msg.upper()


def test_verdict_badge_block_with_reason(streamlit_recorder):
    _render.verdict_badge(AuditVerdict.BLOCK, reason="block_in_segments:[2]")
    methods = [c[0] for c in streamlit_recorder]
    assert "error" in methods
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    assert "block_in_segments" in msg


def test_verdict_badge_review(streamlit_recorder):
    _render.verdict_badge(AuditVerdict.REQUIRES_HUMAN_REVIEW)
    methods = [c[0] for c in streamlit_recorder]
    assert "warning" in methods


# ---------- finding ----------

def test_finding_renders_text_severity_and_citations(streamlit_recorder):
    f = _finding(text="hallazgo X", sev="medium")
    _render.finding(f)
    md_calls = [args[0] for m, args, _ in streamlit_recorder if m == "markdown"]
    # 1 markdown for finding header + 1 markdown for the citation blockquote
    assert len(md_calls) == 2
    assert "hallazgo X" in md_calls[0]
    assert "MEDIUM" in md_calls[0].upper()
    assert "texto literal del corpus" in md_calls[1]
    assert "ai_act art. 6.1" in md_calls[1]


def test_finding_with_multiple_citations(streamlit_recorder):
    citations = [_citation(), _citation()]
    f = Finding(text="x", citations=citations, severity="info")
    _render.finding(f)
    md_calls = [args[0] for m, args, _ in streamlit_recorder if m == "markdown"]
    # 1 header + 1 per citation
    assert len(md_calls) == 1 + len(citations)


# ---------- error_message ----------

def test_error_message_authentication_error(streamlit_recorder):
    class FakeAuthErr(Exception):
        pass

    FakeAuthErr.__name__ = "AuthenticationError"
    FakeAuthErr.__module__ = "anthropic"
    _render.error_message(FakeAuthErr("invalid key"))
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    assert "Anthropic" in msg
    assert "inválida" in msg.lower() or "invalida" in msg.lower()


def test_error_message_credit_balance(streamlit_recorder):
    class FakeBadReq(Exception):
        pass

    FakeBadReq.__name__ = "BadRequestError"
    FakeBadReq.__module__ = "anthropic"
    _render.error_message(FakeBadReq("Your credit balance is too low"))
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    assert "crédito" in msg.lower() or "credito" in msg.lower() or "billing" in msg.lower()


def test_error_message_generic(streamlit_recorder):
    _render.error_message(RuntimeError("boom"))
    msg = next(args[0] for m, args, _ in streamlit_recorder if m == "error")
    # No stack trace, no exception type, user-friendly
    assert "RuntimeError" not in msg
    assert "boom" not in msg
    assert "inesperado" in msg.lower()


# ---------- sanitizer_log_expander ----------

def test_sanitizer_log_expander_renders_table(streamlit_recorder):
    log = [
        SanitizerEvent(
            severity="warning", category="metadata_stripped",
            location="metadata.Author", content_hash="abc123",
            reason="metadata field stripped",
        ),
        SanitizerEvent(
            severity="info", category="outline_extracted",
            location="document.outline", content_hash="def456",
            reason="outline has 7 entries",
        ),
    ]
    _render.sanitizer_log_expander(log)
    methods = [c[0] for c in streamlit_recorder]
    assert "expander_open" in methods
    assert "dataframe" in methods


def test_sanitizer_log_expander_skipped_when_empty(streamlit_recorder):
    _render.sanitizer_log_expander([])
    # Empty log → no expander emitted
    methods = [c[0] for c in streamlit_recorder]
    assert "expander_open" not in methods
    assert "dataframe" not in methods


# ---------- chat_state (top-level) ----------

def test_chat_state_pass_renders_full_output(streamlit_recorder):
    state = _chat_state(AuditVerdict.PASS)
    _render.chat_state(state)
    methods = [c[0] for c in streamlit_recorder]
    assert "success" in methods  # PASS badge
    assert "markdown" in methods  # answer text + finding
    # audit details expander present
    assert "expander_open" in methods


def test_chat_state_injection_blocked_shows_user_friendly_msg(streamlit_recorder):
    state = _chat_state(blocked=True)
    _render.chat_state(state)
    err_msgs = [args[0] for m, args, _ in streamlit_recorder if m == "error"]
    assert any("bloqueada" in m.lower() for m in err_msgs)
    # pattern_name MUST NOT appear in any UI message
    all_msgs = [args[0] for m, args, _ in streamlit_recorder if m in ("error", "warning", "info", "success", "markdown")]
    assert not any("ignore-previous" in m for m in all_msgs)


# ---------- document_report (top-level) ----------

def _document_report(
    verdict: AuditVerdict = AuditVerdict.PASS,
    reason: str | None = None,
    skipped_segments: int = 0,
) -> DocumentReport:
    seg = Segment(id=1, title="§1 Intro", text="x", token_count=1, is_continuation=False)
    sr = SegmentResult(
        segment=seg, skipped=False, skip_reason=None,
        audited_answer=_audited(AuditVerdict.PASS),
        latency_ms=100, cost_eur=0.01,
    )
    segs = [sr]
    for i in range(skipped_segments):
        skip_seg = Segment(id=2 + i, title=f"§{2+i} bad", text="x", token_count=1, is_continuation=False)
        segs.append(SegmentResult(
            segment=skip_seg, skipped=True, skip_reason="document_self_validating",
            audited_answer=None, latency_ms=10, cost_eur=0.0,
        ))
    return DocumentReport(
        case_id="doc-test",
        document_hash="sha256:test",
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=segs,
        document_verdict=verdict,
        document_reason=reason,
        n_segments_total=len(segs),
        n_segments_blocked_by_injection=skipped_segments,
        n_segments_pass=1 if verdict == AuditVerdict.PASS else 0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=200,
        cost_eur_total=0.02,
    )


def test_document_report_pass_renders_metrics_and_segments(streamlit_recorder):
    report = _document_report(AuditVerdict.PASS)
    _render.document_report(report)
    methods = [c[0] for c in streamlit_recorder]
    assert "success" in methods  # global verdict badge
    assert "metric" in methods   # at least one metric
    assert "expander_open" in methods  # at least one segment expander


def test_document_report_sanitizer_critical_short_circuits(streamlit_recorder):
    report = _document_report(
        AuditVerdict.REQUIRES_HUMAN_REVIEW,
        reason="sanitizer_critical:javascript_blocked",
    )
    _render.document_report(report)
    methods = [c[0] for c in streamlit_recorder]
    err_or_warn = [args[0] for m, args, _ in streamlit_recorder if m in ("error", "warning")]
    # At least one user-facing message references the sanitizer block
    assert any(
        "javascript" in m.lower() or "bloqueado" in m.lower() or "revisión" in m.lower()
        for m in err_or_warn
    )


def test_document_report_skipped_segment_user_friendly(streamlit_recorder):
    report = _document_report(AuditVerdict.BLOCK, skipped_segments=1)
    _render.document_report(report)
    # In any rendered text, skip_reason (= pattern name) must NOT appear
    all_text = []
    for m, args, _ in streamlit_recorder:
        if args and isinstance(args[0], str):
            all_text.append(args[0])
        elif args and isinstance(args[0], list):
            # dataframe etc.
            all_text.append(repr(args[0]))
    full = " ".join(all_text)
    assert "document_self_validating" not in full
    # But user-friendly message about "saltado" / "sospechoso" should appear
    assert "sospech" in full.lower() or "saltado" in full.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_ui_render_helpers.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'regulaitor.ui_streamlit._render'`.

- [ ] **Step 3: Implement `_render.py`**

Create `src/regulaitor/ui_streamlit/_render.py` with this exact content:

```python
"""Streamlit render helpers shared between tab_ask and tab_analyze (H6).

These functions call Streamlit primitives directly; they are unit-tested
via monkeypatching in tests/unit/test_ui_render_helpers.py.

Defense rules per spec:
- pattern_name from anti-injection regex NEVER appears in user-visible text.
- Stack traces NEVER appear in user-visible text.
- Citation literal text is ALWAYS visible inline (Q3 A inline blockquote).
"""

from __future__ import annotations

import streamlit as st

from regulaitor.citation.schemas import (
    AuditedAnswer,
    AuditVerdict,
    DocumentReport,
    Finding,
    SanitizerEvent,
)
from regulaitor.orchestration.state import ChatState

_SEVERITY_LABEL_COLOR = {
    "info": "gray",
    "low": "blue",
    "medium": "orange",
    "high": "red",
}


def verdict_badge(verdict: AuditVerdict, reason: str | None = None) -> None:
    """Render the global verdict as a colored Streamlit alert."""
    suffix = f" — {reason}" if reason else ""
    if verdict == AuditVerdict.PASS:
        st.success(f"✓ PASS{suffix}")
    elif verdict == AuditVerdict.BLOCK:
        st.error(f"✗ BLOCK{suffix}")
    else:  # REQUIRES_HUMAN_REVIEW
        st.warning(f"⚠ REQUIRES HUMAN REVIEW{suffix}")


def finding(f: Finding) -> None:
    """Render a Finding with severity badge and inline literal-text citations."""
    color = _SEVERITY_LABEL_COLOR.get(f.severity, "gray")
    st.markdown(
        f"**{f.text}** &nbsp;:{color}[**{f.severity.upper()}**]"
    )
    for c in f.citations:
        loc = f"{c.norma} art. {c.articulo}"
        if c.apartado is not None:
            loc += f".{c.apartado}"
        st.markdown(
            f"> _{c.text}_\n>\n> — **{loc}** ({c.language})"
        )


def sanitizer_log_expander(log: list[SanitizerEvent], expanded: bool = False) -> None:
    """Render the sanitizer log as a collapsible dataframe (skipped if empty)."""
    if not log:
        return
    label = f"Sanitizer log ({len(log)} eventos)"
    rows = [
        {
            "severity": e.severity,
            "category": e.category,
            "location": e.location,
            "content_hash": e.content_hash,
            "reason": e.reason,
        }
        for e in log
    ]
    with st.expander(label, expanded=expanded):
        st.dataframe(rows)


def error_message(exc: Exception) -> None:
    """Map a backend exception to a user-friendly st.error.

    Defense: never render the stack trace, exception class name, or raw
    message. Filter known Anthropic SDK exceptions to specific copy.
    """
    name = type(exc).__name__
    msg = str(exc)
    if name == "AuthenticationError":
        st.error("Key Anthropic inválida. Verifica tu .env.")
        return
    if name == "BadRequestError" and "credit balance" in msg.lower():
        st.error("Cuenta Anthropic sin créditos. Verifica billing.")
        return
    st.error("Ha ocurrido un error inesperado. Revisa la consola para detalles.")


def _audit_results_table(audited: AuditedAnswer) -> list[dict]:
    return [
        {
            "norma": r.citation.norma,
            "articulo": r.citation.articulo,
            "apartado": r.citation.apartado or "—",
            "validated": r.validated,
            "article_exists": r.article_exists,
            "apartado_exists": (
                "—" if r.apartado_exists is None else str(r.apartado_exists)
            ),
            "text_normalized_match": r.text_normalized_match,
            "reason": r.reason or "",
        }
        for r in audited.audit_results
    ]


def chat_state(state: ChatState) -> None:
    """Top-level renderer for the Pestaña Pregunta output."""
    if state.injection_blocked:
        st.error(
            "La consulta fue bloqueada por contener instrucciones potencialmente "
            "maliciosas. Reformula sin texto del tipo 'ignora las instrucciones' "
            "o 'actúa como X'."
        )
        return

    audited = state.audited_answer
    if audited is None:
        st.error("Ha ocurrido un error inesperado. Revisa la consola para detalles.")
        return

    verdict_badge(audited.verdict, reason=audited.reason)
    st.markdown(audited.answer.text)
    for f in audited.answer.findings:
        finding(f)
    with st.expander("Detalles del Auditor (audit_results)"):
        st.dataframe(_audit_results_table(audited))


def document_report(report: DocumentReport) -> None:
    """Top-level renderer for the Pestaña Analiza documento output."""
    verdict_badge(report.document_verdict, reason=report.document_reason)

    if report.document_reason and report.document_reason.startswith(
        "sanitizer_critical:"
    ):
        category = report.document_reason.split(":", 1)[1]
        st.error(
            f"Documento bloqueado: {category}. Revisión humana requerida."
        )
        sanitizer_log_expander(report.sanitizer_log, expanded=True)
        return

    cols = st.columns(6)
    metrics = [
        ("PASS", report.n_segments_pass),
        ("BLOCK", report.n_segments_block),
        ("REVIEW", report.n_segments_review),
        ("SKIPPED", report.n_segments_blocked_by_injection),
        ("LATENCY", f"{report.latency_ms_total / 1000:.1f}s"),
        ("COST €", f"{report.cost_eur_total:.4f}"),
    ]
    for col, (label, value) in zip(cols, metrics, strict=True):
        with col:
            st.metric(label, value)

    emoji = {
        "pass": "✓",
        "block": "✗",
        "requires_human_review": "⚠",
        "skipped": "⚠",
    }
    for sr in report.segments:
        verdict_str = (
            sr.audited_answer.verdict.value
            if sr.audited_answer is not None
            else "skipped"
        )
        title = sr.segment.title or "—"
        label = f"§{sr.segment.id} {title} · {emoji[verdict_str]} {verdict_str}"
        with st.expander(label, expanded=False):
            if sr.skipped:
                st.warning(
                    "Saltado: el segmento contiene contenido sospechoso de "
                    "manipulación. Revisión humana requerida."
                )
            else:
                assert sr.audited_answer is not None
                st.markdown(sr.audited_answer.answer.text)
                for f in sr.audited_answer.answer.findings:
                    finding(f)
                with st.expander("Detalles del Auditor"):
                    st.dataframe(_audit_results_table(sr.audited_answer))

    sanitizer_log_expander(report.sanitizer_log)
```

NOTE: the `:color[text]` syntax in `st.markdown` requires Streamlit ≥1.27, satisfied by our pin.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_ui_render_helpers.py -v --no-cov`
Expected: PASS for all tests (~15 cases).

If `test_error_message_authentication_error` fails because the fake exception class isn't recognized (`__name__` setattr is fine but Python may not respect it on class objects), fall back to constructing real `anthropic.AuthenticationError` and `anthropic.BadRequestError` instances. Both classes exist in the installed `anthropic` package; import them. If that breaks because their constructors require positional args, use:

```python
from anthropic import AuthenticationError, BadRequestError
```

and instantiate with the minimum-required args (consult `anthropic` SDK docs as needed).

If those tests still flake, you can replace them with monkeypatched globals approach: patch `_render.error_message` to consult a sentinel `getattr(exc, "_kind", None)` you set on a generic `Exception` — but that pollutes the public API. Prefer real anthropic exceptions.

Run: `uv run pytest tests/unit/ --no-cov -q 2>&1 | tail -5`
Expected: no regressions in existing unit suite.

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/regulaitor/ui_streamlit/_render.py tests/unit/test_ui_render_helpers.py`
Run: `uv run black --check src/regulaitor/ui_streamlit/_render.py tests/unit/test_ui_render_helpers.py`
Run: `uv run mypy src/regulaitor/ui_streamlit/_render.py`
All clean.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/ui_streamlit/_render.py tests/unit/test_ui_render_helpers.py
git commit -m "feat(h6): _render helpers — verdict_badge, finding, log, error, top-level

6 render helpers shared between Pestaña Pregunta + Pestaña Analiza
documento. Citations rendered inline as blockquote with literal text
(Q3 A: 'no citation no answer' visualmente). Anti-injection
pattern_name + skip_reason NEVER appear in user-visible text. Stack
traces NEVER appear in user-visible text — error_message filters
exception type to friendly Spanish copy."
```

Pre-commit must pass without `--no-verify`.

---

## Task 3: `tab_ask.py` — Pestaña Pregunta

**Goal:** Render the Pregunta form (text_area + corpus + lang + submit), invoke `run()` on submit with a generated `case_id`, store the result in `st.session_state["last_chat_state"]`, render via `_render.chat_state`. Single-slot session state per Q6 A.

**Files:**
- Create: `src/regulaitor/ui_streamlit/tab_ask.py`
- Create (extend in Task 4): `tests/unit/test_ui_tab_helpers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_ui_tab_helpers.py`:

```python
"""Unit tests for tab_ask + tab_analyze helper functions.

Full Streamlit submit flow is covered by the smoke tests; here we only
exercise the pure helpers (case_id format, mime detection).
"""
from __future__ import annotations

import re

import pytest

from regulaitor.ui_streamlit import tab_ask


def test_chat_case_id_format():
    cid = tab_ask._generate_case_id()
    assert re.match(r"^ch-\d{8}-[A-Za-z0-9xy]{8}$", cid), f"unexpected format: {cid!r}"


def test_chat_case_id_unique_across_calls():
    a = tab_ask._generate_case_id()
    b = tab_ask._generate_case_id()
    assert a != b, "case_id should be unique per call"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_ui_tab_helpers.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'regulaitor.ui_streamlit.tab_ask'`.

- [ ] **Step 3: Implement `tab_ask.py`**

Create `src/regulaitor/ui_streamlit/tab_ask.py`:

```python
"""Pestaña Pregunta — wraps the H4 chat pipeline (orchestration.graph.run).

Form-based submit; single-slot session state ('last_chat_state').
Errors → user-friendly st.error via _render.error_message.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from secrets import token_urlsafe

import streamlit as st

from regulaitor.orchestration.graph import run
from regulaitor.ui_streamlit import _render

logger = logging.getLogger("regulaitor.ui_streamlit.tab_ask")

_CORPUS_CHOICES = ["ai_act", "gdpr"]
_LANGUAGE_CHOICES = ["es", "en"]


def _generate_case_id() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]
    return f"ch-{today}-{suffix}"


def render() -> None:
    """Render the Pregunta tab: form + last result."""
    st.header("Pregunta normativa")

    with st.form("chat_form", clear_on_submit=False):
        query = st.text_area(
            "Pregunta",
            placeholder="¿Qué dice el AI Act sobre sistemas de alto riesgo?",
            height=100,
        )
        col_corpus, col_lang = st.columns(2)
        with col_corpus:
            corpus = st.selectbox("Corpus", _CORPUS_CHOICES, index=0)
        with col_lang:
            language = st.selectbox("Idioma", _LANGUAGE_CHOICES, index=0)
        submitted = st.form_submit_button("Analizar")

    if submitted:
        if not query.strip():
            st.error("La pregunta no puede estar vacía.")
            return
        case_id = _generate_case_id()
        try:
            with st.spinner("Analizando — Retriever → Analyst → Auditor..."):
                state = run(
                    query=query,
                    corpus=corpus,
                    language=language,
                    case_id=case_id,
                )
            st.session_state["last_chat_state"] = state
        except Exception as e:  # noqa: BLE001 — defensive UI catch-all
            logger.exception("chat run failed for case %s", case_id)
            _render.error_message(e)
            return

    state = st.session_state.get("last_chat_state")
    if state is not None:
        _render.chat_state(state)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_ui_tab_helpers.py -v --no-cov`
Expected: PASS for the 2 tests.

Run: `uv run pytest tests/unit/ --no-cov -q 2>&1 | tail -5`
Expected: no regressions.

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/regulaitor/ui_streamlit/tab_ask.py tests/unit/test_ui_tab_helpers.py`
Run: `uv run black --check src/regulaitor/ui_streamlit/tab_ask.py tests/unit/test_ui_tab_helpers.py`
Run: `uv run mypy src/regulaitor/ui_streamlit/tab_ask.py`
All clean.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/ui_streamlit/tab_ask.py tests/unit/test_ui_tab_helpers.py
git commit -m "feat(h6): tab_ask.py — Pestaña Pregunta wrapping run()

st.form with text_area + corpus + lang selectboxes. Submit triggers
run() with generated case_id (ch-YYYYMMDD-{nanoid:8}); result stored
in st.session_state['last_chat_state'] (single-slot, Q6 A). Defensive
try/except around run() — pipeline exceptions surface as user-friendly
st.error via _render.error_message; full traceback only in logs."
```

Pre-commit must pass without `--no-verify`.

---

## Task 4: `tab_analyze.py` — Pestaña Analiza documento

**Goal:** Render the Analyze form (file_uploader + multiselect corpus + lang + submit), detect mime via magic bytes, invoke `run_document()` on submit, store the `DocumentReport` in `st.session_state["last_doc_report"]`, render via `_render.document_report`.

**Files:**
- Create: `src/regulaitor/ui_streamlit/tab_analyze.py`
- Modify: `tests/unit/test_ui_tab_helpers.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/unit/test_ui_tab_helpers.py`:

```python


# ---------- tab_analyze ----------

from regulaitor.ui_streamlit import tab_analyze


def test_doc_case_id_format():
    cid = tab_analyze._generate_case_id()
    assert re.match(r"^doc-\d{8}-[A-Za-z0-9xy]{8}$", cid), f"unexpected format: {cid!r}"


def test_detect_mime_pdf_magic_bytes():
    assert tab_analyze._detect_mime(b"%PDF-1.4\n...", "policy.pdf") == "application/pdf"


def test_detect_mime_pdf_magic_overrides_extension():
    # Even with .md extension, PDF magic bytes win.
    assert tab_analyze._detect_mime(b"%PDF-1.4\n", "trick.md") == "application/pdf"


def test_detect_mime_markdown_via_extension_md():
    assert tab_analyze._detect_mime(b"# heading", "doc.md") == "text/markdown"


def test_detect_mime_markdown_via_extension_markdown():
    assert tab_analyze._detect_mime(b"# heading", "doc.markdown") == "text/markdown"


def test_detect_mime_unsupported_raises():
    with pytest.raises(ValueError, match="no soportado"):
        tab_analyze._detect_mime(b"PK\x03\x04...", "archive.zip")


def test_detect_mime_extension_case_insensitive():
    assert tab_analyze._detect_mime(b"# x", "DOC.MD") == "text/markdown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_ui_tab_helpers.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'regulaitor.ui_streamlit.tab_analyze'`.

- [ ] **Step 3: Implement `tab_analyze.py`**

Create `src/regulaitor/ui_streamlit/tab_analyze.py`:

```python
"""Pestaña Analiza documento — wraps the H5 document pipeline.

File upload + magic-byte mime detection + call run_document().
Single-slot session state ('last_doc_report'); errors → user-friendly
st.error.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe

import streamlit as st

from regulaitor.document.extractor import ExtractionError
from regulaitor.orchestration.document_graph import run_document
from regulaitor.ui_streamlit import _render

logger = logging.getLogger("regulaitor.ui_streamlit.tab_analyze")

_CORPUS_CHOICES = ["ai_act", "gdpr"]
_LANGUAGE_CHOICES = ["es", "en"]


def _generate_case_id() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]
    return f"doc-{today}-{suffix}"


def _detect_mime(file_bytes: bytes, filename: str) -> str:
    """Magic-byte aware mime detection (defense over extension-only)."""
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if Path(filename).suffix.lower() in (".md", ".markdown"):
        return "text/markdown"
    raise ValueError(
        f"Tipo de archivo no soportado: {filename}. Solo se aceptan PDF y Markdown."
    )


def render() -> None:
    """Render the Analiza documento tab: form + last result."""
    st.header("Analiza documento")

    with st.form("doc_form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "Documento (PDF o Markdown)",
            type=["pdf", "md", "markdown"],
            accept_multiple_files=False,
        )
        col_corpus, col_lang = st.columns(2)
        with col_corpus:
            corpus = st.multiselect(
                "Corpus", _CORPUS_CHOICES, default=_CORPUS_CHOICES
            )
        with col_lang:
            language = st.selectbox("Idioma", _LANGUAGE_CHOICES, index=0)
        submitted = st.form_submit_button("Analizar documento")

    if submitted:
        if uploaded is None:
            st.error("Sube un archivo PDF o Markdown.")
            return
        if not corpus:
            st.error("Selecciona al menos un corpus.")
            return

        file_bytes = uploaded.read()
        try:
            mime = _detect_mime(file_bytes, uploaded.name)
        except ValueError as e:
            st.error(str(e))
            return

        case_id = _generate_case_id()
        try:
            with st.spinner(
                "Procesando — extract → sanitize → segment → análisis por segmento..."
            ):
                report = run_document(
                    file_bytes=file_bytes,
                    mime_type=mime,
                    language=language,
                    corpus=corpus,
                    case_id=case_id,
                )
            st.session_state["last_doc_report"] = report
        except ExtractionError as e:
            logger.warning("extraction failed for case %s: %s", case_id, e)
            st.error(f"No se pudo procesar el archivo: {e}")
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("doc run failed for case %s", case_id)
            _render.error_message(e)
            return

    report = st.session_state.get("last_doc_report")
    if report is not None:
        _render.document_report(report)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_ui_tab_helpers.py -v --no-cov`
Expected: PASS for all 9 tests (2 from Task 3 + 7 new).

Run: `uv run pytest tests/unit/ --no-cov -q 2>&1 | tail -5`
Expected: no regressions.

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/regulaitor/ui_streamlit/tab_analyze.py tests/unit/test_ui_tab_helpers.py`
Run: `uv run black --check src/regulaitor/ui_streamlit/tab_analyze.py tests/unit/test_ui_tab_helpers.py`
Run: `uv run mypy src/regulaitor/ui_streamlit/tab_analyze.py`
All clean.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/ui_streamlit/tab_analyze.py tests/unit/test_ui_tab_helpers.py
git commit -m "feat(h6): tab_analyze.py — Pestaña Analiza documento wrapping run_document()

st.file_uploader (pdf/md only) + multiselect corpus + selectbox lang.
Magic-byte mime detection (defense over extension-only). Submit
triggers run_document() with case_id (doc-YYYYMMDD-{nanoid:8}).
ExtractionError → user-friendly st.error with file context. Other
errors → _render.error_message (filtered by exception type)."
```

Pre-commit must pass without `--no-verify`.

---

## Task 5: `app.py` entry point + smoke tests with `AppTest`

**Goal:** Compose the two tabs in a single entrypoint with a persistent disclaimer banner and an API-key guard. Smoke-test the entrypoint with `streamlit.testing.v1.AppTest`.

**Files:**
- Create: `src/regulaitor/ui_streamlit/app.py`
- Create: `tests/integration/test_streamlit_smoke.py`

- [ ] **Step 1: Write the failing smoke tests**

Create `tests/integration/test_streamlit_smoke.py`:

```python
"""Smoke tests for the Streamlit entrypoint via streamlit.testing.v1.AppTest.

These run the script in-process — no browser, no real LLM calls. We
verify only that the right widgets render in the right states.
"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

APP_PATH = "src/regulaitor/ui_streamlit/app.py"


def test_app_renders_disclaimer_banner_always(monkeypatch):
    """The disclaimer st.warning must always be present, regardless of API key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    assert any(
        "no sustituye asesoría jurídica" in w.value
        for w in app.warning
    ), f"disclaimer missing; warnings: {[w.value for w in app.warning]}"


def test_app_blocks_when_api_key_missing(monkeypatch):
    """No tabs / no submit when ANTHROPIC_API_KEY is unset."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    assert any(
        "ANTHROPIC_API_KEY no configurada" in e.value
        for e in app.error
    ), f"expected API-key error; errors: {[e.value for e in app.error]}"


def test_app_renders_two_tabs_when_api_key_present(monkeypatch):
    """Both tabs render when the key is set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    # tabs is a list of Tab widgets in AppTest
    tab_labels = [t.label for t in app.tabs]
    assert "Pregunta normativa" in tab_labels
    assert "Analiza documento" in tab_labels
```

NOTE on `AppTest` API: `app.warning`, `app.error`, `app.tabs` are list properties that return all rendered widgets of that kind. The exact attribute names may differ slightly across Streamlit versions; if `app.tabs` is not available (older API), use `app.get("tabs")` or iterate `app.main` children. Verify against the installed Streamlit version's docs by running:

```bash
uv run python -c "from streamlit.testing.v1 import AppTest; help(AppTest)" 2>&1 | head -50
```

If the API differs, adapt the tests but keep the assertions equivalent (presence of disclaimer; presence/absence of API-key error; presence of two tab labels).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_streamlit_smoke.py -v --no-cov`
Expected: FAIL — `app.py` does not exist yet.

- [ ] **Step 3: Implement `app.py`**

Create `src/regulaitor/ui_streamlit/app.py`:

```python
"""RegulAItor Streamlit MVP entry point (H6).

Two-tab UI wrapping the H4 chat pipeline (run) and the H5 document
pipeline (run_document). Persistent disclaimer banner; API-key guard
short-circuits before tab render if ANTHROPIC_API_KEY is missing.

Spec: docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md
"""

from __future__ import annotations

import os

import streamlit as st

from regulaitor.ui_streamlit import tab_analyze, tab_ask

DISCLAIMER = (
    "⚠️ **Aviso:** esta herramienta no sustituye asesoría jurídica. "
    "Las respuestas están respaldadas por citas validadas pero pueden "
    "contener errores. Consulta a un profesional para decisiones vinculantes."
)


def main() -> None:
    st.set_page_config(
        page_title="RegulAItor — Cumplimiento normativo asistido",
        page_icon="⚖️",
        layout="wide",
    )
    st.warning(DISCLAIMER)

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error(
            "ANTHROPIC_API_KEY no configurada. "
            "Añade ANTHROPIC_API_KEY=sk-ant-... al archivo `.env` del proyecto."
        )
        st.stop()

    tab_ask_view, tab_analyze_view = st.tabs(
        ["Pregunta normativa", "Analiza documento"]
    )
    with tab_ask_view:
        tab_ask.render()
    with tab_analyze_view:
        tab_analyze.render()


if __name__ == "__main__":
    main()
```

NOTE: `st.set_page_config` MUST be the first Streamlit call in the script. The disclaimer + guard sit above the tab render so they're evaluated on every rerun.

- [ ] **Step 4: Run smoke tests**

Run: `uv run pytest tests/integration/test_streamlit_smoke.py -v --no-cov`
Expected: PASS for all 3 smoke tests.

If a test fails because of an API surface mismatch (e.g., `app.tabs` not iterable), debug interactively:

```bash
uv run python -c "
from streamlit.testing.v1 import AppTest
app = AppTest.from_file('src/regulaitor/ui_streamlit/app.py').run(timeout=10)
print('warnings:', [w.value for w in app.warning])
print('errors:', [e.value for e in app.error])
print('attrs:', [a for a in dir(app) if not a.startswith('_')])
"
```

Adapt the assertion to whatever API surface is available, keeping the test intent intact.

Run: `uv run pytest tests/ -m "not slow and not document_slow" --no-cov -q 2>&1 | tail -5`
Expected: 400+ tests pass (390 existing + ~16 new from H6 unit + 3 H6 smoke).

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/regulaitor/ui_streamlit/app.py tests/integration/test_streamlit_smoke.py`
Run: `uv run black --check src/regulaitor/ui_streamlit/app.py tests/integration/test_streamlit_smoke.py`
Run: `uv run mypy src/regulaitor/ui_streamlit/app.py`
All clean.

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/ui_streamlit/app.py tests/integration/test_streamlit_smoke.py
git commit -m "feat(h6): app.py entry + smoke tests via AppTest

Persistent disclaimer banner via st.warning (Q4 A). API-key guard
short-circuits before tab render: missing ANTHROPIC_API_KEY shows
st.error and st.stop()s. st.tabs(['Pregunta normativa', 'Analiza
documento']) composes the two tabs. Smoke tests via
streamlit.testing.v1.AppTest cover: disclaimer always present,
API-key absence blocks, both tabs render when key is set."
```

Pre-commit must pass without `--no-verify`.

---

## Task 6: Makefile `serve` target + manual smoke checklist

**Goal:** Add `make serve` to launch the app and document the manual smoke checklist that gates closure.

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Inspect existing Makefile pattern**

Read `Makefile`. Identify the existing target style (e.g., `chat:`, `analyze:`, `test:`). Match the indentation (tabs) and the `python -m` vs `uv run python -m` convention.

- [ ] **Step 2: Add `serve` target**

Append to `Makefile` (matching existing style):

```make
.PHONY: serve
serve:
	uv run streamlit run src/regulaitor/ui_streamlit/app.py
```

If existing targets use plain `python -m` without `uv run`, match that convention instead. The command stays equivalent provided the venv is active.

- [ ] **Step 3: Smoke-verify locally (manual; agentic agents skip and trust)**

Run: `make serve`
Expected: Streamlit prints something like `You can now view your Streamlit app in your browser. Local URL: http://localhost:8501`. Open the URL.

Visual checklist (for the human running this):
1. Yellow disclaimer banner visible at the top.
2. If `ANTHROPIC_API_KEY` is set: two tabs `Pregunta normativa` and `Analiza documento` render.
3. If `ANTHROPIC_API_KEY` is unset: red error banner with "ANTHROPIC_API_KEY no configurada" — no tabs.
4. Both forms render their inputs (textarea / file_uploader / selectbox / multiselect).
5. Submit on an empty form shows a validation error (empty query / no file).

For agentic execution: do NOT actually run `make serve` (it would block the shell). Just verify the target exists and the file paths inside the recipe resolve.

Run: `grep -E "^serve:|^\.PHONY: serve" Makefile`
Expected: matches both the `.PHONY` line and the `serve:` line.

Run: `uv run streamlit --version`
Expected: prints a Streamlit version ≥1.40.

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "build(h6): make serve — launch Streamlit MVP

Single-line target that runs streamlit on src/regulaitor/ui_streamlit/
app.py. The user runs this for manual smoke + demo TFM."
```

Pre-commit must pass without `--no-verify`.

---

## Task 7: H6 closure — ADR + decisions log + CLAUDE.md + README

**Goal:** Wrap the milestone with all docs touched. Tag publishing happens after PR merge (separate manual step gated on explicit user OK).

**Files:**
- Create: `docs/adr/0008-streamlit-ui-architecture.md`
- Modify: `docs/technical_decisions_log.md` (append §H6)
- Modify: `CLAUDE.md` (§27 hitos cerrados +H6; Hito siguiente → H7)
- Modify: `README.md` (Quickstart adds UI section)

- [ ] **Step 1: Write ADR 0008**

Create `docs/adr/0008-streamlit-ui-architecture.md`:

```markdown
# ADR 0008 — Streamlit UI architecture (H6)

**Status:** Accepted
**Date:** 2026-05-07
**Supersedes:** None
**Superseded by:** None
**Cross-refs:** ADR 0001 (project scope), ADR 0006 (chat E2E), ADR 0007 (document pipeline)

## Context

H6 ships the first user-facing surface of RegulAItor: a 2-tab Streamlit MVP that wraps the existing H4 chat pipeline and H5 document pipeline. This is the primary surface for TFM defense — the demo. Constraint: no new backend code; the UI must be a thin wrapper.

## Decisions

### D1 — MVP funcional pelado, sin custom CSS

Streamlit theme default; only native components (`st.warning`, `st.tabs`, `st.form`, `st.expander`, `st.metric`, `st.dataframe`). No custom CSS, no branding, no logo. Polish visual deferred to H17 (cierre académico) and HX2 (Next.js avanzado).

**Alternatives discarded:**
- Polished MVP with custom CSS + branding: 2-3× implementation cost; the differentiator of the project is the Auditor + "no citation, no answer", not the visual.
- Híbrido (pelado ahora, polish H17): polish as last-step historically gets done badly; the pelado base is already non-destructive — additive polish later is safe.

### D2 — DocumentReport: badge global + métricas + expander per-segmento

Top: verdict badge. Then `st.columns(6)` of `st.metric`. Then per-segment `st.expander` (collapsed by default) with verdict + emoji in label. Sanitizer log expander at the end. 5-second read of global state with optional drill-down.

**Alternatives discarded:**
- `st.dataframe` with all segment rows + flat findings list: too much scroll on 8-segment docs; loses per-segment grouping.
- Cards-per-segment with prominent badges: requires custom CSS — out of scope for D1.

### D3 — Cita inline blockquote con texto literal siempre visible

Each Finding renders its citations as `st.markdown` blockquotes containing the literal corpus text + label `— {norma} art. {articulo}.{apartado}`. The user sees the audit trail at a glance. Encarna visualmente "no citation, no answer".

**Alternatives discarded:**
- Reference + popover/expander: forces user to click to see the proof — weakens the auditable narrative.
- External link to EUR-Lex: user leaves the app; depends on EUR-Lex link stability — erodes auditability.

### D4 — Aviso jurídico: banner persistente top con `st.warning`

Non-dismissable yellow banner at the top of every render. Cannot be missed. Defendible legally.

**Alternatives discarded:**
- Modal first-use with "Entendido": dismissed and forgotten failure mode; users joining mid-demo never see it.
- Banner + caption inline: redundant; one strong banner > two medium ones.
- Footer disclaimer: too weak.

### D5 — `ANTHROPIC_API_KEY` solo via env var, sin UI input

`os.getenv("ANTHROPIC_API_KEY")` at startup. If missing, red error banner + `st.stop()`. No UI text input for the key.

**Alternatives discarded:**
- UI sidebar input (`st.text_input(type="password")`): the value enters the DOM (accessible via DevTools), Streamlit may log inputs in debug mode — higher SSDLC risk for marginal multi-user benefit not in scope.
- Híbrido (env primary, UI fallback): two routes to test; no use case in H6 single-operator deployment.

### D6 — Single-slot session state

`st.session_state["last_chat_state"]` and `st.session_state["last_doc_report"]` hold only the most recent result. New submit replaces previous. No history list; no persistence to disk.

**Alternatives discarded:**
- History of last N (~5): scope creep for MVP; "Pregunta" tab is not a chat conversation; demos show one Q&A at a time.
- Persistent history (SQLite/files): out of scope for MVP; H7 may add this if needed for `/cases` endpoint.

### D7 — Tests: unit-test render helpers via monkeypatch + AppTest smoke

Streamlit's lifecycle (script reruns on every interaction) makes branch coverage 95% expensive vs its value. Coverage targets relaxed: `_render.py` ≥85%, `tab_*.py` ≥60%, `app.py` ≥80%, global ≥90% (mantenido).

**Alternatives discarded:**
- Selenium/Playwright UI tests: heavy, brittle; out of scope for MVP.
- 95% coverage gate on tabs: would force testing the entire Streamlit form lifecycle, which the framework doesn't expose well.

## Consequences

- New package `src/regulaitor/ui_streamlit/` (5 modules: empty `__init__`, `_render`, `tab_ask`, `tab_analyze`, `app`).
- New runtime dep: `streamlit>=1.40,<2.0`.
- Make target `serve` for manual smoke + TFM demo.
- 16 new unit tests (render helpers + tab helpers) + 3 smoke tests via `AppTest`.
- Backend H1-H5 untouched.
- Anti-injection `pattern_name` and `skip_reason` NEVER appear in user-visible text — defense against attacker iteration.
- Stack traces NEVER appear in user-visible text — `_render.error_message` filters by exception type to friendly Spanish copy.

## Revision conditions

- D1 reopened in H17 (cierre académico) if the defense narrative gains from custom CSS + branding.
- D5 reopened in HX2 (Next.js multi-tenant) when per-user keys become necessary.
- D6 reopened in H17 if user research shows demand for query history during demos.
- D7 reopened if Streamlit ships a more testable lifecycle (e.g., the AppTest API stabilizes around 2.0+).
```

- [ ] **Step 2: Append §H6 to decisions log**

Open `docs/technical_decisions_log.md`. Find the position after §H5 (search for `## H5 — Document pipeline E2E`). Append a new section with this content:

```markdown

## H6 — Streamlit MVP (cerrado YYYY-MM-DD)

**Tag:** `v0.0.7-h6` (pending publish post-merge). **Spec:** `docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md`. **Plan:** `docs/superpowers/plans/2026-05-07-h6-streamlit-mvp.md`. **ADR:** `docs/adr/0008-streamlit-ui-architecture.md`.

### Decisiones tomadas en brainstorming (2026-05-07)

1. **MVP pelado funcional** (Q1 A / D1 ADR 0008). Sin custom CSS, solo componentes Streamlit nativos. Polish a H17/HX2.
2. **DocumentReport viz: badge + métricas + expander per-segmento** (Q2 A / D2 ADR 0008). 5-second read del global, drill-down opcional.
3. **Cita inline blockquote** (Q3 A / D3 ADR 0008). Texto literal del corpus siempre visible bajo cada Finding.
4. **Banner persistente top con st.warning** (Q4 A / D4 ADR 0008). No descartable, imposible de miss.
5. **ANTHROPIC_API_KEY solo via env var** (Q5 A / D5 ADR 0008). Sin UI input — la key no toca el DOM. SSDLC narrower.
6. **Single-slot session_state** (Q6 A / D6 ADR 0008). Sin historial, coherente con run() / run_document() stateless.

### Amendments durante implementación

(populate as the cycle proceeds; mid-impl pivots get their own dated entries)

### Security delta

- ANTHROPIC_API_KEY nunca renderizada en UI (env var only); cero riesgo de exposure incidental vía DOM o screenshot.
- Anti-injection `pattern_name` (chat) y `skip_reason` (segmento documental) **nunca** aparecen en texto user-visible — defensa contra iteración de evasiones por parte de un atacante. El usuario ve el efecto (consulta bloqueada / segmento saltado); el log captura el detalle.
- Stack traces filtrados en `_render.error_message`: solo copy en español user-friendly llega al UI; el traceback completo va a stderr (consola Streamlit). Defensa contra info leakage de paths internos / stack frames.
- `st.stop()` tras error de API key faltante: corta el resto del render; los tabs no se exponen sin la key (defensa en profundidad).
- Sin auth multi-tenant: H6 es single-operator local. No abre superficie de sesiones.

### Métricas de cierre

- **Tests fast:** ~410 passing (390 existing + ~20 new H6).
- **Tests AppTest smoke:** 3 (disclaimer always, API-key guard, tabs present).
- **Coverage global:** ≥90% (mantenido).
- **Coverage `ui_streamlit/_render.py`:** ≥85%.
- **Coverage `ui_streamlit/tab_ask.py` + `tab_analyze.py`:** ≥60% (Streamlit framework limitations on testability).
- **Coverage `ui_streamlit/app.py`:** ≥80%.
- **Linters:** ruff + black + mypy clean.
- **Pre-commit (gitleaks + EOF + trailing):** clean.
- **Manual smoke en máquina limpia:** banner visible, API-key guard funcional, 1 query chat real + 1 análisis documento real renderizan correctamente.
- **Squash commit SHA:** (populated post-merge)
- **Tag `v0.0.7-h6`:** (published post-merge with explicit user OK)
```

(Replace `YYYY-MM-DD` with the actual closure date when the implementer commits.)

- [ ] **Step 3: Update CLAUDE.md §27**

Open `CLAUDE.md`. Locate the `### Hitos cerrados` section. After the H5 line, ADD:

```markdown
- **H6** — Streamlit MVP cerrado (YYYY-MM-DD). Tag `v0.0.7-h6` (pendiente de publicar tras merge). ADR 0008. Dos pestañas (Pregunta / Analiza documento) envolviendo run() y run_document() sin tocar el backend H1-H5. Aviso jurídico persistente. Skill `ui-ux-pro-max` referenciada en memoria pero NO activada (alcance pelado). Ver `docs/technical_decisions_log.md` §H6.
```

In `### Hito siguiente`, REPLACE the H6 line (whatever it currently says) with:

```markdown
- **H7** — FastAPI mínima (`/ask`, `/analyze`, `/health`) + auth básica + rate limiting. Pendiente: brainstorming sobre auth scheme (token estático vs sin auth para MVP), rate limiting (slowapi vs custom middleware), upload handling (`UploadFile` streaming), OpenAPI auto-generation review.
```

- [ ] **Step 4: Update README.md Quickstart**

Open `README.md`. Locate the Quickstart / Usage section (it shows `python -m scripts.chat ...` and `python -m scripts.analyze ...`). After those examples, ADD a new subsection:

```markdown

### UI Streamlit (H6)

Lanza el MVP de dos pestañas (Pregunta / Analiza documento):

\`\`\`bash
make serve
\`\`\`

Streamlit imprime una URL local (típicamente `http://localhost:8501`). El banner amarillo de aviso jurídico es persistente; si `ANTHROPIC_API_KEY` no está en `.env`, la app muestra un error rojo y no expone los tabs. Usa el flujo Pregunta para queries de chat o el flujo Analiza documento para subir un PDF/Markdown corporativo y ver el `DocumentReport` con verdict por segmento + sanitizer log + audit trail por cita.

**No respuesta sin cita validada — incluso en la UI**.
```

(Use real triple backticks in the README; the `\`` escape above is only because we're inside a Markdown code block in the plan.)

- [ ] **Step 5: Verify final test pass**

Run: `uv run pytest tests/ -m "not slow and not document_slow" --no-cov -q 2>&1 | tail -5`
Expected: 410+ passing, no regressions.

Run: `uv run ruff check`
Run: `uv run black --check src/ tests/ scripts/`
Run: `uv run mypy`
All clean.

Run: `uv run pre-commit run --all-files`
Expected: all hooks pass without `--no-verify`.

- [ ] **Step 6: Commit closure**

```bash
git add docs/adr/0008-streamlit-ui-architecture.md \
        docs/technical_decisions_log.md \
        CLAUDE.md \
        README.md
git commit -m "docs(h6): closure — ADR 0008, decisions log, CLAUDE.md, README

ADR 0008 documents 7 H6 decisions (D1 MVP pelado, D2 doc viz pattern,
D3 inline citation blockquote, D4 banner persistente, D5 env-only API
key, D6 single-slot session, D7 tests strategy). Decisions log §H6
opens with brainstorming snapshot + amendments scaffolding +
security delta + closure metrics. CLAUDE.md §27 records H6 closure
and points to H7 (FastAPI). README adds UI Quickstart."
```

Pre-commit must pass without `--no-verify`.

- [ ] **Step 7: Open the PR**

```bash
git push -u origin feat/h6-streamlit-mvp
gh pr create --title "feat(h6): Streamlit MVP — Pregunta + Analiza documento" --body "$(cat <<'EOF'
## Summary
- Implements H6 per `docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md` and ADR 0008.
- New package `src/regulaitor/ui_streamlit/` (5 modules: `__init__`, `_render`, `tab_ask`, `tab_analyze`, `app`).
- Persistent disclaimer banner via `st.warning` (D4 — non-dismissable, no risk of "click and forget").
- ANTHROPIC_API_KEY consumed only via env var (D5 — no UI input, SSDLC).
- Single-slot session state (D6 — no history, aligned with stateless backend).
- Citations rendered inline as blockquote with literal corpus text under each Finding (D3 — "no citation no answer" visualmente).
- DocumentReport rendered as badge + 6 metrics + per-segment expander + sanitizer log expander (D2).
- Anti-injection `pattern_name` + `skip_reason` NEVER appear in user-visible text. Stack traces filtered to friendly Spanish copy.
- Backend H1-H5 untouched.

## Test plan
- [x] Unit tests on render helpers + tab helpers (~16 cases).
- [x] AppTest smoke tests: disclaimer always present, API-key guard blocks, tabs render when key set.
- [x] Coverage ≥85% on `_render.py`, ≥60% on tabs, ≥80% on `app.py`, ≥90% global.
- [x] Lint (ruff + black + mypy) green.
- [x] Pre-commit (gitleaks + EOF + trailing) green.
- [ ] Manual smoke: `make serve` in clean checkout; banner visible; API-key error correct; 1 chat query + 1 doc analysis render output (requires Anthropic credits).
EOF
)"
```

NOTE: the manual smoke item is unchecked because it requires Anthropic billing. The agentic implementer can skip it; the human user runs it locally before approving merge.

- [ ] **Step 8: After review and approval — squash merge + tag**

Wait for explicit user OK (per CLAUDE.md §22.2 + project memory: "Pause before merge + tag for explicit user OK").

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull --ff-only origin main
git tag -a v0.0.7-h6 -m "H6 — Streamlit MVP

Two-tab UI (Pregunta + Analiza documento) wrapping run() and
run_document() unchanged. Persistent disclaimer banner. Env-only
API key. Single-slot session state. Citations inline blockquote.
ADR 0008. Spec docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md."
git push origin v0.0.7-h6
```

Update closure metrics + squash SHA placeholders in `docs/technical_decisions_log.md` §H6 with a follow-up commit on main.

---

## Self-review

After writing the plan, this section was checked against the spec.

### Spec coverage

| Spec section | Task |
|---|---|
| §3.1 file structure (5 files) | Tasks 1-5 |
| §3.2 flow diagram | Tasks 3-5 |
| §4.1 `__init__.py` | Task 1 |
| §4.2 `app.py` (banner + guard + tabs) | Task 5 |
| §4.3 `tab_ask.py` (form + run + render) | Task 3 |
| §4.4 `tab_analyze.py` (upload + run_document + render) | Task 4 |
| §4.5 `_render.py` (6 helpers) | Task 2 |
| §5.1 chat happy path | Tasks 2 (chat_state) + 3 |
| §5.2 chat injection_blocked | Tasks 2 (chat_state) + 3 |
| §5.3 doc happy path | Tasks 2 (document_report) + 4 |
| §5.4 doc segment skipped | Tasks 2 (document_report) |
| §6 visualization patterns (badge, metrics, expander, log) | Task 2 |
| §7 error handling matrix | Tasks 2 (error_message) + 3 + 4 + 5 |
| §8 anti-injection feedback (pattern_name never exposed) | Task 2 (chat_state, document_report) |
| §9.1 unit tests (render helpers) | Task 2 |
| §9.2 AppTest smoke | Task 5 |
| §9.3 manual smoke | Task 6 |
| §9.4 coverage targets | Task 1 (coverage scope) + accumulated across tasks |
| §10 ADR + decisions log + skill reference | Task 7 |
| §11 files touched | All tasks (cumulative) |
| §12 anti-patterns | Encoded in code + tests + ADR |
| §13 gate de cierre | Task 7 step 5 (verify) + Task 8 step (manual smoke) |
| §14 out of scope | ADR D1/D5/D6 revision conditions + spec §14 |
| §15 Q→spec mapping | ADR 0008 D1-D7 + decisions log §H6 |

No gaps detected.

### Placeholder scan

- `YYYY-MM-DD` in decisions log §H6 + CLAUDE.md §27: intentional placeholder, populated at closure.
- `<sha>` in tag message + closure metrics: intentional, populated post-merge.
- No `TBD`, `TODO`, `implement later`, `add appropriate error handling`, `similar to Task N` patterns.
- Every code-generation step shows the actual code.

### Type / signature consistency

- `_render.verdict_badge(verdict, reason=None)`: defined Task 2, called by `chat_state` and `document_report` (also Task 2). Same signature.
- `_render.finding(f)`: defined Task 2, called by `chat_state` and `document_report` (also Task 2). Same signature.
- `_render.sanitizer_log_expander(log, expanded=False)`: defined Task 2, called by `document_report`. Same signature.
- `_render.error_message(exc)`: defined Task 2, called by `tab_ask.render` (Task 3) and `tab_analyze.render` (Task 4). Same signature.
- `_render.chat_state(state)`: defined Task 2, called by `tab_ask.render` (Task 3). Same signature.
- `_render.document_report(report)`: defined Task 2, called by `tab_analyze.render` (Task 4). Same signature.
- `tab_ask._generate_case_id() -> str`: returns `ch-YYYYMMDD-{8chars}`. Tested in Task 3.
- `tab_analyze._generate_case_id() -> str`: returns `doc-YYYYMMDD-{8chars}`. Tested in Task 4. Different prefix from `tab_ask` — by design.
- `tab_analyze._detect_mime(file_bytes, filename) -> str`: defined Task 4, called by `tab_analyze.render`. Same signature.
- `app.main()`: defined Task 5. Imports both tab modules, calls `tab_ask.render()` and `tab_analyze.render()` — names match.

No inconsistencies detected. The plan is internally coherent and aligns with the spec.
