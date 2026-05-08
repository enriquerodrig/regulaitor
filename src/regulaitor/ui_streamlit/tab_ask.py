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

    last_state = st.session_state.get("last_chat_state")
    if last_state is not None:
        _render.chat_state(last_state)
