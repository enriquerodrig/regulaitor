# H6 — Streamlit MVP (Pestaña Pregunta + Pestaña Analiza documento) — Design

**Status:** approved (brainstorming closed 2026-05-07)
**Milestone:** H6
**Predecessor:** H5 (document pipeline E2E, tag `v0.0.6-h5`, squash `415d269`)
**Successor:** H7 (FastAPI mínima)
**ADR:** 0008 (to be created during implementation)

---

## 1. Goal

Cerrar H6 entregando un Streamlit MVP de dos pestañas — Pregunta (chat) y Analiza documento — que envuelve sin tocar los pipelines existentes H4 (`orchestration.graph.run`) y H5 (`orchestration.document_graph.run_document`), con un aviso jurídico persistente y la regla "no citation, no answer" visible y auditable en cada output.

**Narrativa ancla** (CLAUDE.md §2): la UI es la primera superficie por la que un humano externo (tutor TFM, evaluador) ve RegulAItor en funcionamiento. Debe transmitir trazabilidad y seriedad jurídica sin pretensión visual; el diferencial es el Auditor, no el polish.

## 2. Context

### 2.1 Estado heredado de H5

- Document E2E operativo: `scripts/analyze.py` y `run_document(file_bytes, mime_type, language, corpus, case_id) -> DocumentReport`. Pipeline secuencial: extract (pypdfium2 + magic bytes) → sanitize (strip+log + critical-block vía pikepdf deep scan) → segment (estructural-by-outline + token-cap fallback) → loop por segmento (anti-injection mode="document" → Retriever → Analyst con `prompt_role="document_analyst"` → Auditor) → agregación.
- Chat E2E operativo (H4): `scripts/chat.py` y `run(query, corpus, language, case_id) -> ChatState`. LangGraph: `injection_check → retriever → analyst → auditor`.
- Schemas estables: `Citation`, `Finding`, `Answer`, `AuditedAnswer`, `AuditVerdict`, `Context`, `RawDocument`, `SanitizedDocument`, `Segment`, `SegmentResult`, `DocumentReport`, `SanitizerEvent`. Todos `frozen=True, extra="forbid"`.
- 391 tests fast + 2 slow `document_slow` + (1 ya determinístico sin API key, 1 esperando billing Anthropic).
- `.env` con `ANTHROPIC_API_KEY` slot (cuenta sin créditos al cierre H5; carga prevista pre-H8).
- 5 dominios en `security/allowlist.py`. Skill `document-analysis` activa.

### 2.2 H6 deliverables (per CLAUDE.md §16.1 + §11)

1. `src/regulaitor/ui_streamlit/app.py` — entry point con banner aviso + tabs.
2. `src/regulaitor/ui_streamlit/tab_ask.py` — pestaña Pregunta envolviendo `run()`.
3. `src/regulaitor/ui_streamlit/tab_analyze.py` — pestaña Analiza documento envolviendo `run_document()`.
4. `src/regulaitor/ui_streamlit/_render.py` — render helpers compartidos (verdict badge, finding, sanitizer log).
5. Tests unitarios sobre los render helpers + smoke tests con `streamlit.testing.v1.AppTest`.
6. Make target `serve` para arrancar la app.
7. ADR 0008 + decisions log §H6 + CLAUDE.md §27 + README Quickstart UI.

## 3. Architecture overview

### 3.1 Estructura de archivos

```
src/regulaitor/ui_streamlit/
├── __init__.py             (empty)
├── app.py                  (entry: banner + API key guard + tabs)
├── tab_ask.py              (Pestaña Pregunta — wraps run())
├── tab_analyze.py          (Pestaña Analiza documento — wraps run_document())
└── _render.py              (helpers compartidos: verdict_badge, finding, sanitizer_log)

tests/unit/test_ui_render_helpers.py
tests/integration/test_streamlit_smoke.py
```

### 3.2 Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────┐
│ app.py                                                            │
│  ├─ st.warning(persistent disclaimer — Q4 A)                     │
│  ├─ guard: ANTHROPIC_API_KEY → st.error + disable submits        │
│  └─ st.tabs(["Pregunta", "Analiza documento"])                    │
└──────┬─────────────────────────────────────────┬─────────────────┘
       │                                         │
       ▼                                         ▼
┌──────────────────────────┐           ┌────────────────────────────┐
│ tab_ask.py               │           │ tab_analyze.py             │
│ - st.form                │           │ - st.form                  │
│   - text_area            │           │   - file_uploader (pdf/md) │
│   - selectbox(corpus)    │           │   - multiselect(corpus)    │
│   - selectbox(lang)      │           │   - selectbox(lang)        │
│   - submit_button        │           │   - submit_button          │
│ - on_submit:             │           │ - on_submit:               │
│   - case_id ch-...       │           │   - case_id doc-...        │
│   - st.spinner           │           │   - mime detect (magic)    │
│   - run(...)             │           │   - st.spinner             │
│   - session_state slot   │           │   - run_document(...)      │
│ - render output via      │           │   - session_state slot     │
│   _render helpers        │           │ - render output via        │
└──────────────────────────┘           │   _render helpers          │
                                        └────────────────────────────┘
                │                                       │
                ▼                                       ▼
       H4 chat pipeline                       H5 document pipeline
       (untouched)                            (untouched)
```

**Componentes nuevos:** 5 archivos en `src/regulaitor/ui_streamlit/` + 2 archivos de test. **Reusados sin tocar:** todo el backend H1-H5. **Cero modificación de pipelines existentes.**

## 4. Components

### 4.1 `src/regulaitor/ui_streamlit/__init__.py` (NEW)

Empty package marker.

### 4.2 `src/regulaitor/ui_streamlit/app.py` (NEW)

**Responsabilidad:** entry point Streamlit. Setup global de la página, banner aviso jurídico, guard de API key, render de tabs.

**Estructura mínima:**

```python
import os
import streamlit as st

from regulaitor.ui_streamlit import tab_ask, tab_analyze

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

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.error(
            "ANTHROPIC_API_KEY no configurada. Copia `.env.example` a `.env` y añade tu clave."
        )
        st.stop()

    tab1, tab2 = st.tabs(["Pregunta normativa", "Analiza documento"])
    with tab1:
        tab_ask.render()
    with tab2:
        tab_analyze.render()


if __name__ == "__main__":
    main()
```

**Notas:**
- `st.warning` es persistente (cada rerun lo vuelve a renderizar arriba) y no descartable — exactamente lo que Q4 A pide.
- `st.stop()` tras error de API key: corta el resto del render. El usuario ve el banner amarillo + el error rojo, sin tabs.
- `layout="wide"` para que las métricas + expanders del DocumentReport tengan espacio.

### 4.3 `src/regulaitor/ui_streamlit/tab_ask.py` (NEW)

**Responsabilidad:** Pestaña Pregunta. Form con query/corpus/lang, submit, render del `ChatState`.

**API pública:**
```python
def render() -> None: ...
```

**Comportamiento:**

```python
import logging
from datetime import datetime, UTC
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
    st.header("Pregunta normativa")
    with st.form("chat_form", clear_on_submit=False):
        query = st.text_area(
            "Pregunta",
            placeholder="¿Qué dice el AI Act sobre sistemas de alto riesgo?",
            height=100,
        )
        col1, col2 = st.columns(2)
        with col1:
            corpus = st.selectbox("Corpus", _CORPUS_CHOICES, index=0)
        with col2:
            language = st.selectbox("Idioma", _LANGUAGE_CHOICES, index=0)
        submitted = st.form_submit_button(
            "Analizar", disabled=False, use_container_width=False
        )

    if submitted:
        if not query.strip():
            st.error("La pregunta no puede estar vacía.")
            return
        case_id = _generate_case_id()
        try:
            with st.spinner("Analizando — Retriever → Analyst → Auditor..."):
                state = run(
                    query=query, corpus=corpus, language=language, case_id=case_id
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

### 4.4 `src/regulaitor/ui_streamlit/tab_analyze.py` (NEW)

**Responsabilidad:** Pestaña Analiza documento. File uploader + form, submit, render del `DocumentReport`.

**API pública:**
```python
def render() -> None: ...
```

**Comportamiento:**

```python
import logging
from datetime import datetime, UTC
from pathlib import Path
from secrets import token_urlsafe

import streamlit as st

from regulaitor.orchestration.document_graph import run_document
from regulaitor.document.extractor import ExtractionError
from regulaitor.ui_streamlit import _render

logger = logging.getLogger("regulaitor.ui_streamlit.tab_analyze")

_CORPUS_CHOICES = ["ai_act", "gdpr"]
_LANGUAGE_CHOICES = ["es", "en"]


def _generate_case_id() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]
    return f"doc-{today}-{suffix}"


def _detect_mime(file_bytes: bytes, filename: str) -> str:
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if Path(filename).suffix.lower() in (".md", ".markdown"):
        return "text/markdown"
    raise ValueError(f"tipo de archivo no soportado: {filename}")


def render() -> None:
    st.header("Analiza documento")
    with st.form("doc_form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "Documento (PDF o Markdown)",
            type=["pdf", "md", "markdown"],
            accept_multiple_files=False,
        )
        col1, col2 = st.columns(2)
        with col1:
            corpus = st.multiselect(
                "Corpus", _CORPUS_CHOICES, default=_CORPUS_CHOICES
            )
        with col2:
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

### 4.5 `src/regulaitor/ui_streamlit/_render.py` (NEW)

**Responsabilidad:** helpers de render compartidos entre tabs. Funciones puras que llaman primitivas Streamlit.

**API pública:**
```python
def chat_state(state: ChatState) -> None: ...
def document_report(report: DocumentReport) -> None: ...
def verdict_badge(verdict: AuditVerdict, reason: str | None = None) -> None: ...
def finding(f: Finding) -> None: ...
def sanitizer_log_expander(log: list[SanitizerEvent], expanded: bool = False) -> None: ...
def error_message(exc: Exception) -> None: ...
```

**Implementación clave (`finding` con citas inline blockquote — Q3 A):**

```python
SEVERITY_COLORS = {
    "info": "gray", "low": "blue",
    "medium": "orange", "high": "red",
}


def finding(f: Finding) -> None:
    severity_color = SEVERITY_COLORS.get(f.severity, "gray")
    st.markdown(
        f"**{f.text}** &nbsp;:{severity_color}[{f.severity.upper()}]"
    )
    for c in f.citations:
        loc = f"{c.norma} art. {c.articulo}"
        if c.apartado is not None:
            loc += f".{c.apartado}"
        st.markdown(
            f"> _{c.text}_\n>\n> — **{loc}** ({c.language})"
        )
```

**`error_message`** filtra el detalle de la excepción según tipo:
- `anthropic.AuthenticationError`: *"Key Anthropic inválida. Verifica tu .env."*
- `anthropic.BadRequestError` con "credit balance": *"Cuenta Anthropic sin créditos. Verifica billing."*
- Otros: *"Ha ocurrido un error inesperado. Revisa la consola para detalles."*

**Anti-injection feedback** (CLAUDE.md §22 + Q4 spec): cuando `state.injection_blocked` es True, `chat_state` muestra `st.error("La consulta fue bloqueada por contener instrucciones potencialmente maliciosas. Reformula sin texto del tipo 'ignora las instrucciones' o 'actúa como X'.")` SIN exponer `state.injection_reason` (queda en log).

Mismo patrón en `document_report`: cuando un `SegmentResult.skipped is True`, dentro del expander del segmento aparece *"Saltado: el segmento contiene contenido sospechoso de manipulación. Revisión humana requerida."* Sin `skip_reason` visible.

## 5. UI flows

### 5.1 Pestaña Pregunta — happy path

1. Usuario teclea query, selecciona corpus + lang, click "Analizar".
2. Spinner mientras `run()` corre (típicamente 5-15s con BGE-M3 caliente).
3. Output debajo del form:
   - `verdict_badge(state.audited_answer.verdict, state.audited_answer.reason)`.
   - `st.markdown(state.audited_answer.answer.text)` como párrafo de respuesta.
   - Por cada `finding`, render con citas blockquote inline.
   - `st.expander("Detalles del Auditor")` con tabla de `audit_results`.

### 5.2 Pestaña Pregunta — injection blocked

1. Submit con query "ignora las instrucciones anteriores".
2. `run()` retorna `ChatState(injection_blocked=True, audited_answer=None, injection_reason="ignore-previous")`.
3. Output: solo el `st.error` user-friendly. Sin exposición del `pattern_name`.

### 5.3 Pestaña Analiza documento — happy path

1. Usuario sube PDF, selecciona corpus + lang, click "Analizar documento".
2. Spinner mientras `run_document()` corre (30-90s con BGE-M3 caliente).
3. Output:
   - `verdict_badge(report.document_verdict, report.document_reason)`.
   - Si critical-block (`report.document_reason` empieza con `sanitizer_critical:`): solo el badge rojo + sanitizer_log expandido. Sin segmentos.
   - Si flujo normal: fila de 6 `st.metric`, expander por segmento (colapsado), sanitizer_log expander al final si tiene entradas.

### 5.4 Pestaña Analiza documento — segment skipped por injection

Dentro del expander de segmento `§N {title}`: badge `st.warning` con texto user-friendly, sin findings (el segmento no llegó al Analyst).

## 6. Visualization patterns

### 6.1 Verdict badge

| Verdict | Streamlit primitive | Texto |
|---|---|---|
| `PASS` | `st.success` | `✓ {verdict_label} — {n_segments_pass} de {n_segments_total} validados` (doc) o `✓ Respuesta validada` (chat) |
| `BLOCK` | `st.error` | `✗ Bloqueado — {reason}` |
| `REQUIRES_HUMAN_REVIEW` | `st.warning` | `⚠ Requiere revisión humana — {reason}` |

### 6.2 Métricas (DocumentReport)

`st.columns(6)` con `st.metric` en cada uno:
- PASS, BLOCK, REVIEW, INJECTION_SKIPPED, LATENCY (en `s` formateado), COST (€ con 4 decimales).

### 6.3 Per-segment expander

```python
emoji = {"pass": "✓", "block": "✗", "requires_human_review": "⚠"}
verdict_str = (
    sr.audited_answer.verdict.value if sr.audited_answer
    else "skipped"
)
label = f"§{sr.segment.id} {sr.segment.title or '—'} · {emoji[verdict_str]} {verdict_str}"
with st.expander(label, expanded=False):
    if sr.skipped:
        st.warning("Saltado: el segmento contiene contenido sospechoso de manipulación. Revisión humana requerida.")
    else:
        st.markdown(sr.audited_answer.answer.text)
        for f in sr.audited_answer.answer.findings:
            _render.finding(f)
        with st.expander("Detalles del Auditor"):
            st.dataframe(_audit_table(sr.audited_answer.audit_results))
```

### 6.4 Sanitizer log expander

```python
with st.expander(f"Sanitizer log ({len(log)} eventos)", expanded=expanded):
    st.dataframe([
        {"severity": e.severity, "category": e.category,
         "location": e.location, "content_hash": e.content_hash,
         "reason": e.reason}
        for e in log
    ])
```

## 7. Error handling

| Error | Detección | Mensaje al usuario |
|---|---|---|
| API key faltante | `os.getenv` returns None at startup | Banner rojo + `st.stop()`. Texto: *"ANTHROPIC_API_KEY no configurada. Copia `.env.example` a `.env` y añade tu clave."* |
| API key inválida | `anthropic.AuthenticationError` durante run | `st.error("Key Anthropic inválida. Verifica tu .env.")` + log con detalle. |
| Sin créditos | `anthropic.BadRequestError` con "credit balance" en mensaje | `st.error("Cuenta Anthropic sin créditos. Verifica billing.")` + log. |
| PDF corrupto / mime mismatch | `ExtractionError` | `st.error(f"No se pudo procesar el archivo: {e}")`. |
| `DocumentBlockedError` propagado (defensa) | catch genérico | `st.error("Documento bloqueado por seguridad. Detalles en el log de sanitización.")`. |
| Cualquier otra | `Exception` catch en submit | `st.error("Ha ocurrido un error inesperado. Revisa la consola.")` + `logger.exception(...)` a stderr. **Stack trace nunca aparece en UI** (defensa contra info leakage). |

## 8. Anti-injection feedback (UX side)

Política inviolable: **el usuario ve el efecto, nunca el `pattern_name`**.

| Evento | UI muestra | UI NO muestra | Log captura |
|---|---|---|---|
| Chat injection_blocked | "Consulta bloqueada por contener instrucciones potencialmente maliciosas. Reformula sin..." | el nombre del patrón regex | `pattern_name` + `query_hash` (no query en claro) |
| Doc segment skipped | "Saltado: contenido sospechoso. Revisión humana requerida." | el `skip_reason` (= `pattern_name`) | mismo log estructurado de `run_document` ya implementado en H5 |
| Sanitizer critical-block | "Documento bloqueado: {category}. Revisión humana requerida." | content_hash, reason detallada (sigue en log estructurado) | sanitizer_log JSON con severity/category |

Razón SSDLC: exponer el `pattern_name` da al atacante señal para iterar evasiones del regex. Un usuario legítimo cuya query es benigna pero matchea por accidente puede reformular sin saber el patrón exacto; un atacante no debe tener telemetry de cuál se disparó.

## 9. Testing strategy

### 9.1 Unit tests (`tests/unit/test_ui_render_helpers.py`)

Funciones puras o llamadas Streamlit verificables vía mock:

```python
def test_verdict_badge_pass(monkeypatch):
    calls = []
    monkeypatch.setattr("streamlit.success", lambda msg: calls.append(("success", msg)))
    _render.verdict_badge(AuditVerdict.PASS)
    assert len(calls) == 1
    assert calls[0][0] == "success"
    assert "✓" in calls[0][1]


def test_finding_with_one_citation(monkeypatch):
    md_calls = []
    monkeypatch.setattr("streamlit.markdown", lambda s, **kw: md_calls.append(s))
    citation = Citation(norma="ai_act", articulo="6", apartado="1",
                        language="es", text="texto literal")
    f = Finding(text="hallazgo X", citations=[citation], severity="medium")
    _render.finding(f)
    # 1 markdown for finding text + 1 markdown for citation blockquote
    assert len(md_calls) == 2
    assert "hallazgo X" in md_calls[0]
    assert "MEDIUM" in md_calls[0]
    assert "texto literal" in md_calls[1]
    assert "ai_act art. 6.1" in md_calls[1]


def test_detect_mime_pdf():
    assert tab_analyze._detect_mime(b"%PDF-1.4\n...", "x.pdf") == "application/pdf"


def test_detect_mime_markdown():
    assert tab_analyze._detect_mime(b"# heading", "x.md") == "text/markdown"


def test_detect_mime_unsupported_raises():
    with pytest.raises(ValueError, match="tipo de archivo no soportado"):
        tab_analyze._detect_mime(b"PK...", "x.zip")
```

Coverage objetivo en `_render.py`: ≥85%. En `tab_ask.py` / `tab_analyze.py`: ≥60% (los flujos completos requieren `AppTest`).

### 9.2 Smoke tests con `AppTest` (`tests/integration/test_streamlit_smoke.py`)

```python
from streamlit.testing.v1 import AppTest


def test_app_renders_disclaimer_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = AppTest.from_file("src/regulaitor/ui_streamlit/app.py").run()
    assert any("no sustituye asesoría jurídica" in w.value for w in app.warning)
    assert any("ANTHROPIC_API_KEY no configurada" in e.value for e in app.error)


def test_app_renders_tabs_when_api_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-stub")
    app = AppTest.from_file("src/regulaitor/ui_streamlit/app.py").run()
    # No error block; tabs present
    assert not app.error
    # Disclaimer always present
    assert any("asesoría jurídica" in w.value for w in app.warning)
```

Test integración que mockea `run()` y `run_document()` para verificar el render del output:

```python
def test_chat_submit_renders_audited_answer(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub")
    fake_state = ChatState(...)  # construir manualmente con fixtures
    monkeypatch.setattr(
        "regulaitor.orchestration.graph.run", lambda **kw: fake_state
    )
    app = AppTest.from_file("src/regulaitor/ui_streamlit/app.py").run()
    # Set form inputs and submit (AppTest API)
    # ...
    # Assert verdict badge renders correctly
```

### 9.3 Manual smoke obligatorio (gate de cierre)

`make serve` en máquina limpia, abrir browser:
- ✅ Banner aviso visible.
- ✅ Sin API key → error correcto.
- ✅ Con API key + créditos → 1 query chat + 1 análisis doc real renderizan output.
- ✅ Refresh de browser no rompe (session_state se reinicia limpio).
- ✅ Captura de pantalla evidencia para `docs/architecture.md` o defensa TFM.

### 9.4 Coverage gate

- Global: ≥90% (mantenido).
- `ui_streamlit/_render.py`: ≥85%.
- `ui_streamlit/tab_ask.py` / `tab_analyze.py`: ≥60% (Streamlit limitations).
- `ui_streamlit/app.py`: ≥80% (entry simple).

Justificación de la relajación per-módulo: Streamlit's lifecycle (script reruns on every interaction) hace que branch coverage 95% sea costoso vs su valor real. El gate global ≥90% se mantiene porque H1-H5 contribuyen mucho coverage.

## 10. ADR + decisions log + skill

### 10.1 ADR 0008 — `streamlit-ui-architecture.md`

Captura las 6 decisiones brainstorming Q1-Q6:
- D1: MVP pelado funcional (Q1 A). Custom CSS / branding deferido a H17.
- D2: DocumentReport viz métricas resumen + expander per-segmento (Q2 A).
- D3: Citation inline blockquote con texto literal (Q3 A).
- D4: Banner persistente top con `st.warning` (Q4 A).
- D5: API key solo via env var (Q5 A). Sin UI input.
- D6: Single-slot session state (Q6 A). Sin historial.
- D7 (técnica): Streamlit `AppTest` para smoke tests + unit tests con mock de primitivas Streamlit. Coverage ≥60% per módulo de tab justificado por limitaciones del framework.

Alternativas descartadas + revisión condiciones (cuándo reabrir cada una).

### 10.2 Decisions log §H6

Apertura post-spec con las 6 decisiones + tabla mapping Q→spec. Security delta: ANTHROPIC_API_KEY no expuesta a UI; anti-injection `pattern_name` no expuesto al usuario; sin auth multi-tenant (out of scope explícito). Closure metrics post-merge.

### 10.3 Skills

- **No se introduce skill nueva en H6.**
- `reference_ui_skills.md` (memoria) ya apunta a `ui-ux-pro-max` para H17/HX2 cuando aplique.
- Skills activas mantienen estado (prompt-versioning, document-analysis, citation-validator, rag-ingest).

## 11. Files touched

### 11.1 Created (7)

```
src/regulaitor/ui_streamlit/__init__.py
src/regulaitor/ui_streamlit/app.py
src/regulaitor/ui_streamlit/tab_ask.py
src/regulaitor/ui_streamlit/tab_analyze.py
src/regulaitor/ui_streamlit/_render.py

tests/unit/test_ui_render_helpers.py
tests/integration/test_streamlit_smoke.py

docs/adr/0008-streamlit-ui-architecture.md
```

### 11.2 Modified (5)

```
pyproject.toml                          (+streamlit>=1.40,<2.0; coverage scope: ui_streamlit/)
Makefile                                (+serve target)
docs/technical_decisions_log.md         (+§H6 entries)
CLAUDE.md                               (§27 hitos cerrados +H6; Hito siguiente → H7)
README.md                               (Quickstart +sección "UI: make serve")
```

## 12. Anti-patterns to avoid

Heredados de H1-H5 + nuevos H6:

- **No tocar el backend H1-H5** — H6 es solo presentación. Si surge necesidad de cambiar `run()` o `run_document()` durante implementación, parar y volver a brainstorming.
- **No exponer `pattern_name` / `skip_reason` al usuario** — defensa SSDLC contra iteración de evasiones.
- **No mostrar stack traces en UI** — `st.exception()` solo si flag debug; producción usa `st.error` con texto user-friendly + log a stderr.
- **No persistir sesiones a disco** — single-slot in-memory only. Sin SQLite, sin pickle, sin archivos temporales.
- **No introducir custom CSS** — alcance pelado Q1 A. Streamlit theme default.
- **No introducir auth / multi-tenant** — out of scope. Single operator local.
- **No bypassear `st.spinner`** — el usuario debe saber que algo corre durante 30-90s.
- **No paralelizar segmentos** (ya prohibido en H5; aquí también — la UI es síncrona).
- **No mockear el backend en tests** — los tests UI mockean `run()` y `run_document()` (signatures externas) pero NUNCA mockean Auditor / sanitizer / validator.

## 13. Gate de cierre H6

1. Tests unitarios verdes (~10 nuevos en `test_ui_render_helpers.py`).
2. Smoke tests `AppTest` verdes (~3 en `test_streamlit_smoke.py`).
3. Manual smoke en máquina limpia: 1 query chat real + 1 análisis doc real (clean fixture H5) renderizan correctamente.
4. ruff + black + mypy clean en `ui_streamlit/`.
5. Banner aviso jurídico verificado en captura de pantalla → archivada en `docs/architecture.md` o `docs/evidence_matrix.md`.
6. ADR 0008 commiteado.
7. Decisions log §H6 cerrado.
8. CLAUDE.md §27 actualizado.
9. README Quickstart con sección UI.
10. Tag `v0.0.7-h6` publicado tras merge + OK explícito del usuario.

**Gates relajados vs H4/H5** (justificados por limitaciones Streamlit):
- Coverage `ui_streamlit/` ≥60% per-módulo en tabs (vs ≥95% típico H4/H5).
- Sin slow E2E con LLM real (smoke con mock cubre el flujo; LLM real ya validado en H4/H5).
- Sin property tests hypothesis (UI no tiene invariantes hypothesis-amigables).

## 14. Out of scope (deferred consciente)

- **Persistencia de historial** (Q6 B/C): defer a H17 si la defensa lo pide.
- **Custom CSS / branding visual / paleta**: defer a H17 / HX2.
- **Skill ui-ux-pro-max activa**: defer; MVP pelado no la justifica. Disponible cuando llegue H17 o HX2.
- **Multi-tenant / auth**: API key viene de env, no hay sesiones de usuario. Defer a H7 (FastAPI puede añadir auth básica) o HX2.
- **Streaming de respuestas**: el router H4 tiene la opción deferida; UI no la consume aún. Defer a H6 v2 si hay quejas de latencia percibida.
- **Per-segment progress en Analiza documento**: defer; spinner único es suficiente para 4-8 segmentos.
- **Internacionalización i18n UI**: la UI está en español (target users CLAUDE.md §4). EN UI defer a HX si llega.
- **Mobile responsive**: Streamlit `layout="wide"` ya es razonable en tablet; mobile-first no aplica para herramienta de cumplimiento corporativo.
- **Charts / dashboards** (verdict trends, cost over time, etc.): H11 observabilidad lo cubre con LangFuse + Grafana; UI Streamlit no es el lugar.

## 15. Decisiones brainstorming → spec mapping

| Q | Decisión | Spec section |
|---|---|---|
| Q1 | MVP pelado funcional (sin custom CSS, componentes nativos) | §1, §3, §4, §12 |
| Q2 | DocumentReport: métricas resumen + expander per-segmento | §6.2, §6.3, §4.5 |
| Q3 | Citation: inline blockquote con texto literal siempre visible | §4.5 (`finding`), §6 |
| Q4 | Aviso jurídico: banner persistente top con `st.warning` | §4.2 (`app.py`), §5 |
| Q5 | API key: solo env var, sin UI input | §4.2 (guard), §7, §12 |
| Q6 | Session state: single-slot, sin historial | §4.3, §4.4, §14 |

---

**End of design document.** Implementation plan to follow via `superpowers:writing-plans`.
