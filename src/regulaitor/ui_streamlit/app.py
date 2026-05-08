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

    tab_ask_view, tab_analyze_view = st.tabs(["Pregunta normativa", "Analiza documento"])
    with tab_ask_view:
        tab_ask.render()
    with tab_analyze_view:
        tab_analyze.render()


if __name__ == "__main__":
    main()
