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
