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
from typing import cast

import streamlit as st

from regulaitor.corpus.schemas import Language
from regulaitor.document.extractor import ExtractionError
from regulaitor.orchestration.document_graph import run_document
from regulaitor.ui_streamlit import _render

logger = logging.getLogger("regulaitor.ui_streamlit.tab_analyze")

_CORPUS_CHOICES = ["ai_act", "gdpr", "nis2", "dora", "dora_rts_incident", "dora_rts_class"]
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
    raise ValueError(f"Tipo de archivo no soportado: {filename}. Solo se aceptan PDF y Markdown.")


def render() -> None:
    """Render the Analiza documento tab: form + last result."""
    st.header("Analiza documento")

    # Demo-public latency advisory: HF Spaces free tier runs on CPU (cpu-basic
    # = 2 vCPU, no GPU). BGE-M3 reranker takes ~15-30s per segment query;
    # a doc with 80 segments can take ~1h. For real workloads use GPU deploy
    # or local. Frontend-only note, no backend behavior change.
    st.info(
        "**Demo público (HF Spaces CPU)**: el análisis documental tarda "
        "~30-60s por sección. Recomendado: PDFs ≤ 5 páginas para esta demo. "
        "Documentos extensos: deploy GPU o ejecutar localmente."
    )
    st.caption(
        "Privacidad: anonimiza los datos personales antes de subir un documento; "
        "los registros internos solo guardan recuentos, nunca los valores detectados."
    )

    with st.form("doc_form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "Documento (PDF o Markdown)",
            type=["pdf", "md", "markdown"],
            accept_multiple_files=False,
        )
        col_corpus, col_lang = st.columns(2)
        with col_corpus:
            corpus = st.multiselect("Corpus", _CORPUS_CHOICES, default=_CORPUS_CHOICES)
        with col_lang:
            language = st.selectbox("Idioma", _LANGUAGE_CHOICES, index=0)
        submitted = st.form_submit_button("Analizar documento", type="primary")

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
            with st.spinner("Procesando — extract → sanitize → segment → análisis por segmento..."):
                report = run_document(
                    file_bytes=file_bytes,
                    mime_type=mime,
                    language=cast(Language, language),
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

    last_report = st.session_state.get("last_doc_report")
    if last_report is not None:
        _render.document_report(last_report)
