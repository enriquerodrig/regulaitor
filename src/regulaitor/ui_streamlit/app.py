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

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error(
            "ANTHROPIC_API_KEY no configurada. "
            "Añade ANTHROPIC_API_KEY=sk-ant-... al archivo `.env` del proyecto."
        )
        st.stop()

    tab_ask_view, tab_analyze_view = st.tabs(["Pregunta normativa", "Analiza documento"])
    with tab_ask_view:
        tab_ask.render()
    with tab_analyze_view:
        tab_analyze.render()


if __name__ == "__main__":
    main()
