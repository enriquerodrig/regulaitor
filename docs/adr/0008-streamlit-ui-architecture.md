# ADR 0008 — Streamlit UI architecture (H6)

- **Status:** Accepted
- **Date:** 2026-05-07 (H6 closure)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0006 (chat E2E architecture), 0007 (document pipeline architecture).

## Context

H6 ships the first user-facing surface of RegulAItor: a 2-tab Streamlit MVP
that wraps the existing H4 chat pipeline (`run()`) and H5 document pipeline
(`run_document()`). This is the primary surface for TFM defense — the demo.
Constraint: no new backend code; the UI must be a thin wrapper that does not
touch H1-H5.

## Decision

Seven design decisions taken at brainstorming (2026-05-07) and preserved
through implementation, organized as follows:

| Layer | Module |
|---|---|
| Entry point | `src/regulaitor/ui_streamlit/app.py` |
| Tab — chat | `src/regulaitor/ui_streamlit/tab_ask.py` |
| Tab — document | `src/regulaitor/ui_streamlit/tab_analyze.py` |
| Render helpers | `src/regulaitor/ui_streamlit/_render.py` |
| Make target | `serve` |

### D1 — MVP funcional pelado, sin custom CSS

Streamlit theme default; only native components (`st.warning`, `st.tabs`,
`st.form`, `st.expander`, `st.metric`, `st.dataframe`). No custom CSS, no
branding, no logo. Polish visual deferred to H17 (cierre académico) and
HX2 (Next.js avanzado).

### D2 — DocumentReport: badge global + métricas + expander per-segmento

Top: verdict badge. Then `st.columns(6)` of `st.metric` (PASS / BLOCK /
REVIEW / SKIPPED / LATENCY / COST €). Then per-segment `st.expander`
(collapsed by default) with verdict + emoji in label. Sanitizer log
expander at the end. 5-second read of global state with optional
drill-down.

### D3 — Cita inline blockquote con texto literal siempre visible

Each Finding renders its citations as `st.markdown` blockquotes containing
the literal corpus text + label `— {norma} art. {articulo}.{apartado}`.
The user sees the audit trail at a glance. Encarna visualmente
"no citation, no answer".

### D4 — Aviso jurídico: banner persistente top con `st.warning`

Non-dismissable yellow banner at the top of every render. Cannot be missed.
Defendible legally.

### D5 — `ANTHROPIC_API_KEY` solo via env var, sin UI input

`os.getenv("ANTHROPIC_API_KEY")` at startup. If missing, red error banner
+ `st.stop()`. No UI text input for the key. Error message points at
`.env` directly (`.env.example` was removed pre-implementation since keys
live in `.env` only — single-operator local).

### D6 — Single-slot session state

`st.session_state["last_chat_state"]` and
`st.session_state["last_doc_report"]` hold only the most recent result.
New submit replaces previous. No history list; no persistence to disk.

### D7 — Tests: unit-test render helpers via monkeypatch + AppTest smoke

Streamlit's lifecycle (script reruns on every interaction) makes branch
coverage 95% expensive vs its value. Coverage targets relaxed:
`_render.py` ≥85%, `tab_*.py` ≥60%, `app.py` ≥80%, global ≥90%
(mantenido). `AppTest.from_file()` resolves relative paths against the
test file's parent dir, not CWD — use `Path(__file__).resolve().parents[2]`
to compute the absolute repo-relative path. Cold-start timeout for the
smoke tests is 60s on Windows (importing `tab_analyze` pulls the H5 doc
pipeline lazily).

## Alternatives considered

- **Polished MVP with custom CSS + branding** (D1): 2-3× implementation
  cost; the differentiator of the project is the Auditor + "no citation,
  no answer", not the visual.
- **Híbrido (pelado ahora, polish H17)** (D1): polish as last-step
  historically gets done badly; the pelado base is already non-destructive
  — additive polish later is safe.
- **`st.dataframe` with all segment rows + flat findings list** (D2): too
  much scroll on 8-segment docs; loses per-segment grouping.
- **Cards-per-segment with prominent badges** (D2): requires custom CSS —
  out of scope for D1.
- **Reference + popover/expander** (D3): forces user to click to see the
  proof — weakens the auditable narrative.
- **External link to EUR-Lex** (D3): user leaves the app; depends on
  EUR-Lex link stability — erodes auditability.
- **Modal first-use with "Entendido"** (D4): dismissed and forgotten
  failure mode; users joining mid-demo never see it.
- **Banner + caption inline** (D4): redundant; one strong banner > two
  medium ones.
- **Footer disclaimer** (D4): too weak.
- **UI sidebar input** (`st.text_input(type="password")`) (D5): the value
  enters the DOM (accessible via DevTools), Streamlit may log inputs in
  debug mode — higher SSDLC risk for marginal multi-user benefit not in
  scope.
- **Híbrido (env primary, UI fallback)** (D5): two routes to test; no use
  case in H6 single-operator deployment.
- **History of last N (~5)** (D6): scope creep for MVP; "Pregunta" tab is
  not a chat conversation; demos show one Q&A at a time.
- **Persistent history (SQLite/files)** (D6): out of scope for MVP; H7
  may add this if needed for `/cases` endpoint.
- **Selenium/Playwright UI tests** (D7): heavy, brittle; out of scope for
  MVP.
- **95% coverage gate on tabs** (D7): would force testing the entire
  Streamlit form lifecycle, which the framework doesn't expose well.

## Consequences

### Positive

- New package `src/regulaitor/ui_streamlit/` (5 modules: empty `__init__`,
  `_render`, `tab_ask`, `tab_analyze`, `app`).
- New runtime dep: `streamlit>=1.40,<2.0` (resolved to 1.57.0 at impl
  date).
- Make target `serve` for manual smoke + TFM demo.
- New unit tests on render helpers + tab helpers (~24 cases) + 3 smoke
  tests via `AppTest`.
- Backend H1-H5 untouched.

### Negative / risks mitigated

- Anti-injection `pattern_name` (chat) and `skip_reason` (segmento
  documental) NEVER appear in user-visible text — defense against
  attacker iteration.
- Stack traces NEVER appear in user-visible text — `_render.error_message`
  filters by exception type to friendly Spanish copy.
- `Language = Literal["es", "en"]` cast added in `tab_analyze.py` because
  `run_document()` is strictly typed (`tab_ask.py` does not need this —
  `graph.run()` accepts plain `str`).

## Revision conditions

- **D1** reopened in H17 (cierre académico) if the defense narrative gains
  from custom CSS + branding.
- **D5** reopened in HX2 (Next.js multi-tenant) when per-user keys become
  necessary.
- **D6** reopened in H17 if user research shows demand for query history
  during demos.
- **D7** reopened if Streamlit ships a more testable lifecycle (e.g., the
  AppTest API stabilizes around 2.0+).

## References

- `docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md` — H6 spec.
- `docs/superpowers/plans/2026-05-07-h6-streamlit-mvp.md` — H6 plan.
- `docs/technical_decisions_log.md` H6 section.
- `docs/adr/0006-chat-e2e-architecture.md` — backend wrapped (chat).
- `docs/adr/0007-document-pipeline-architecture.md` — backend wrapped (document).
- `src/regulaitor/ui_streamlit/` — concrete output.
