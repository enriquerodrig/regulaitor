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

_CORPUS_CHOICES = ["auto", "ai_act", "gdpr", "nis2", "dora"]
_LANGUAGE_CHOICES = ["es", "en"]


def _generate_case_id() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]
    return f"ch-{today}-{suffix}"


_EXAMPLES = [
    (
        "AI Act · alto riesgo",
        "¿Qué obligaciones impone el AI Act a los sistemas de IA de alto riesgo?",
    ),
    (
        "RGPD · brecha de datos",
        "¿En qué plazo debo notificar una brecha de datos personales bajo el RGPD?",
    ),
    (
        "Fintech · DORA + NIS2",
        "Soy una fintech regulada: ¿qué exigen DORA y NIS2 sobre la notificación de incidentes?",
    ),
]


def render() -> None:
    """Render the Pregunta tab: examples + form + last result."""
    st.header("Pregunta normativa")

    if "chat_query" not in st.session_state:
        st.session_state["chat_query"] = ""

    st.caption("Ejemplos — pulsa uno para probar:")
    ex_cols = st.columns(len(_EXAMPLES))
    for col, (label, example_query) in zip(ex_cols, _EXAMPLES, strict=False):
        if col.button(label, key=f"ex_{label}", use_container_width=True):
            # Set BEFORE the form's text_area (key="chat_query") instantiates so
            # it pre-fills in this same run — no st.rerun() needed (and st.rerun
            # pollutes AppTest isolation under random test order).
            st.session_state["chat_query"] = example_query

    with st.form("chat_form", clear_on_submit=False):
        query = st.text_area(
            "Pregunta",
            key="chat_query",
            placeholder="¿Qué dice el AI Act sobre sistemas de alto riesgo?",
            height=100,
        )
        col_corpus, col_lang = st.columns(2)
        with col_corpus:
            corpus = st.selectbox("Corpus", _CORPUS_CHOICES, index=0)
        with col_lang:
            language = st.selectbox("Idioma", _LANGUAGE_CHOICES, index=0)
        submitted = st.form_submit_button("Analizar", type="primary")

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
