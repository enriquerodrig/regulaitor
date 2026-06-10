"""RegulAItor Streamlit MVP entry point (H6).

Two-tab UI wrapping the H4 chat pipeline (run) and the H5 document
pipeline (run_document). Persistent disclaimer banner; API-key guard
short-circuits before tab render if ANTHROPIC_API_KEY is missing.

Spec: docs/superpowers/specs/2026-05-07-h6-streamlit-mvp-design.md
"""

from __future__ import annotations

import os

import streamlit as st

from regulaitor.corpus import loader as corpus_loader
from regulaitor.ui_streamlit import tab_analyze, tab_ask

DISCLAIMER = (
    "**Aviso.** Esta herramienta no sustituye asesoría jurídica. "
    "Las respuestas están respaldadas por citas validadas pero pueden "
    "contener errores. Consulta a un profesional para decisiones vinculantes."
)

INTRO = (
    "**RegulAItor** — inteligencia normativa europea con cita verificable. "
    "Consulta el AI Act, el RGPD, NIS2 y DORA: cada respuesta va respaldada por "
    "una cita textual validada contra el corpus oficial de EUR-Lex. "
    "**Sin cita verificable, no hay respuesta.**"
)

FOOTER = (
    "Corre sobre un modelo de IA europeo open-source (Mistral): ni tus datos ni "
    "el modelo de inferencia salen de la Unión Europea. Demo en fase temprana."
)

# Vercel Web Interface Guidelines: tabular-nums for numeric columns
# (regulatory reporting, metrics, audit-result tables). Applied to common
# Streamlit selectors via single small <style> block; no web-font fetched.
_GLOBAL_STYLES = """
<style>
  [data-testid="stMetricValue"],
  [data-testid="stMetricDelta"],
  table, .stCode, code {
    font-variant-numeric: tabular-nums;
  }
  h1, h2, h3, h4 {
    text-wrap: balance;
  }
</style>
"""


def _missing_key_error() -> str | None:
    """Return a config error message if the configured Analyst backend lacks its
    key, else None. Model-choice-aware: the self_hosted (sovereign open-model)
    path needs REGULAITOR_SELFHOST_BASE_URL + REGULAITOR_SELFHOST_API_KEY; the
    default Anthropic path needs ANTHROPIC_API_KEY. Pre-sovereign-demo this guard
    only checked ANTHROPIC_API_KEY, which blocked a fully self-hosted deploy
    (no US key) from ever rendering the UI.
    """
    if os.getenv("REGULAITOR_ANALYST_MODEL_CHOICE", "default") == "self_hosted":
        if not os.getenv("REGULAITOR_SELFHOST_BASE_URL") or not os.getenv(
            "REGULAITOR_SELFHOST_API_KEY"
        ):
            return (
                "Modo self-hosted: configura REGULAITOR_SELFHOST_BASE_URL + "
                "REGULAITOR_SELFHOST_API_KEY (endpoint open-source soberano)."
            )
        return None
    if not os.getenv("ANTHROPIC_API_KEY"):
        return (
            "ANTHROPIC_API_KEY no configurada. "
            "Añade ANTHROPIC_API_KEY=sk-ant-... al archivo `.env` del proyecto."
        )
    return None


def main() -> None:
    st.set_page_config(
        page_title="RegulAItor — Cumplimiento normativo asistido",
        layout="wide",
    )
    corpus_loader.warmup()
    st.markdown(_GLOBAL_STYLES, unsafe_allow_html=True)
    st.markdown(
        f"""<div style="padding: 12px 16px; background: #F8FAFC; border-left: 3px solid #94A3B8;
        border-radius: 4px; color: #475569; font-size: 14px; margin-bottom: 16px;">
        {DISCLAIMER}</div>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""<div style="padding: 12px 16px; background: #F1F5F9; border-left: 3px solid #1E3A5F;
        border-radius: 4px; color: #334155; font-size: 14px; margin-bottom: 20px;">
        {INTRO}</div>""",
        unsafe_allow_html=True,
    )

    _key_error = _missing_key_error()
    if _key_error:
        st.error(_key_error)
        st.stop()

    tab_ask_view, tab_analyze_view = st.tabs(["Pregunta normativa", "Analiza documento"])
    with tab_ask_view:
        tab_ask.render()
    with tab_analyze_view:
        tab_analyze.render()

    st.divider()
    st.caption(FOOTER)


if __name__ == "__main__":
    main()
