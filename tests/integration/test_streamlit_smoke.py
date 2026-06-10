"""Smoke tests for the Streamlit entrypoint via streamlit.testing.v1.AppTest.

These run the script in-process — no browser, no real LLM calls. We
verify only that the right widgets render in the right states.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

# AppTest.from_file resolves relative paths against the test file's parent;
# use an absolute path so the test works regardless of CWD or invocation dir.
APP_PATH = str(
    Path(__file__).resolve().parents[2] / "src" / "regulaitor" / "ui_streamlit" / "app.py"
)


def test_app_renders_disclaimer_banner_always(monkeypatch):
    """The disclaimer must always be present, regardless of API key.

    R3 polish: disclaimer rendered as subtle st.markdown HTML box (not the
    loud st.warning yellow alert it used to be); check app.markdown bodies.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    # Cold-start imports (tab_analyze pulls the document pipeline) can take
    # ~20s on Windows; use 60s to absorb that without flakiness.
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    assert any(
        "no sustituye asesoría jurídica" in m.value for m in app.markdown
    ), f"disclaimer missing; markdown bodies: {[m.value for m in app.markdown]}"


def test_app_blocks_when_api_key_missing(monkeypatch):
    """No tabs / no submit when ANTHROPIC_API_KEY is unset."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    assert any(
        "ANTHROPIC_API_KEY no configurada" in e.value for e in app.error
    ), f"expected API-key error; errors: {[e.value for e in app.error]}"


def test_app_renders_two_tabs_when_api_key_present(monkeypatch):
    """Both tabs render when the key is set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    # tabs is a list of Tab widgets in AppTest
    tab_labels = [t.label for t in app.tabs]
    assert "Pregunta normativa" in tab_labels
    assert "Analiza documento" in tab_labels


def test_app_renders_when_self_hosted_keys_present_no_anthropic(monkeypatch):
    """Sovereign demo: self_hosted + SELFHOST endpoint/key render the UI WITHOUT
    ANTHROPIC_API_KEY (the H6 guard wrongly hard-required it; sovereign-demo fix)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("REGULAITOR_ANALYST_MODEL_CHOICE", "self_hosted")
    monkeypatch.setenv("REGULAITOR_SELFHOST_BASE_URL", "https://api.mistral.ai/v1")
    monkeypatch.setenv("REGULAITOR_SELFHOST_API_KEY", "stub-mistral-key")
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    tab_labels = [t.label for t in app.tabs]
    assert "Pregunta normativa" in tab_labels
    assert not app.error, f"unexpected error: {[e.value for e in app.error]}"


def test_app_blocks_when_self_hosted_endpoint_missing(monkeypatch):
    """self_hosted mode without the SELFHOST endpoint/key -> sovereign config
    error, no tabs (and it must NOT fall back to demanding ANTHROPIC_API_KEY)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("REGULAITOR_ANALYST_MODEL_CHOICE", "self_hosted")
    monkeypatch.delenv("REGULAITOR_SELFHOST_BASE_URL", raising=False)
    monkeypatch.delenv("REGULAITOR_SELFHOST_API_KEY", raising=False)
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    assert any(
        "self-hosted" in e.value.lower() for e in app.error
    ), f"expected self-hosted config error; errors: {[e.value for e in app.error]}"


def test_app_renders_intro_and_sovereignty_footer(monkeypatch):
    """Demo polish: the intro (what it is + the §6 rule) and the EU-sovereignty
    footer render alongside the disclaimer."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    md = " ".join(m.value for m in app.markdown)
    assert "Sin cita verificable, no hay respuesta" in md
    captions = " ".join(c.value for c in app.caption)
    assert "salen de la Unión Europea" in captions


def test_app_example_buttons_prefill_chat_query(monkeypatch):
    """Demo polish: example buttons render and clicking one pre-fills the query."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    labels = [b.label for b in app.button]
    assert "AI Act · alto riesgo" in labels, f"example buttons missing; buttons: {labels}"
    target = next(b for b in app.button if b.label == "AI Act · alto riesgo")
    target.click().run(timeout=60)
    assert "alto riesgo" in app.session_state["chat_query"]


def test_app_chat_warns_on_pii_in_query(monkeypatch):
    """§18.5 (Fase 2): a query containing PII shows the alert and holds the
    result behind a continue/cancel gate (does NOT auto-process — no backend
    call). We do not click 'Continuar' here to avoid st.rerun() in AppTest."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stub-for-smoke")
    app = AppTest.from_file(APP_PATH).run(timeout=60)
    ta = next(t for t in app.text_area if t.label == "Pregunta")
    ta.set_value("Mi email es ana@test.com; ¿qué dice el RGPD sobre brechas?")
    submit = next(b for b in app.button if b.label == "Analizar")
    submit.click().run(timeout=60)
    assert any(
        "datos personales" in w.value for w in app.warning
    ), f"expected PII warning; warnings: {[w.value for w in app.warning]}"
    # the continue/cancel gate is present
    labels = [b.label for b in app.button]
    assert "Continuar de todos modos" in labels and "Cancelar" in labels
