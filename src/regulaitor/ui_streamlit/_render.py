"""Streamlit render helpers shared between tab_ask and tab_analyze (H6).

These functions call Streamlit primitives directly; they are unit-tested
via monkeypatching in tests/unit/test_ui_render_helpers.py.

Defense rules per spec §8:
- pattern_name from anti-injection regex NEVER appears in user-visible text.
- Stack traces NEVER appear in user-visible text.
- Citation literal text is ALWAYS visible inline (Q3 A inline blockquote).
"""

from __future__ import annotations

import streamlit as st

from regulaitor.citation.schemas import (
    AuditedAnswer,
    AuditVerdict,
    DocumentReport,
    Finding,
    SanitizerEvent,
)
from regulaitor.orchestration.state import ChatState

_SEVERITY_LABEL_COLOR = {
    "info": "gray",
    "low": "blue",
    "medium": "orange",
    "high": "red",
}


def verdict_badge(verdict: AuditVerdict, reason: str | None = None) -> None:
    """Render the global verdict as a colored Streamlit alert."""
    suffix = f" — {reason}" if reason else ""
    if verdict == AuditVerdict.PASS:
        st.success(f"✓ PASS{suffix}")
    elif verdict == AuditVerdict.BLOCK:
        st.error(f"✗ BLOCK{suffix}")
    else:  # REQUIRES_HUMAN_REVIEW
        st.warning(f"⚠ REQUIRES HUMAN REVIEW{suffix}")


def finding(f: Finding) -> None:
    """Render a Finding with severity badge and inline literal-text citations."""
    color = _SEVERITY_LABEL_COLOR.get(f.severity, "gray")
    st.markdown(f"**{f.text}** &nbsp;:{color}[**{f.severity.upper()}**]")
    for c in f.citations:
        loc = f"{c.norma} art. {c.articulo}"
        if c.apartado is not None:
            loc += f".{c.apartado}"
        st.markdown(f"> _{c.text}_\n>\n> — **{loc}** ({c.language})")


def sanitizer_log_expander(log: list[SanitizerEvent], expanded: bool = False) -> None:
    """Render the sanitizer log as a collapsible dataframe (skipped if empty)."""
    if not log:
        return
    label = f"Sanitizer log ({len(log)} eventos)"
    rows = [
        {
            "severity": e.severity,
            "category": e.category,
            "location": e.location,
            "content_hash": e.content_hash,
            "reason": e.reason,
        }
        for e in log
    ]
    with st.expander(label, expanded=expanded):
        st.dataframe(rows)


def error_message(exc: Exception) -> None:
    """Map a backend exception to a user-friendly st.error.

    Defense: never render the stack trace, exception class name, or raw
    message. Filter known Anthropic SDK exceptions to specific copy.
    """
    name = type(exc).__name__
    msg = str(exc)
    if name == "AuthenticationError":
        st.error("Key Anthropic inválida. Verifica tu .env.")
        return
    if name == "BadRequestError" and "credit balance" in msg.lower():
        st.error("Cuenta Anthropic sin créditos. Verifica billing.")
        return
    st.error("Ha ocurrido un error inesperado. Revisa la consola para detalles.")


def _audit_results_table(audited: AuditedAnswer) -> list[dict]:
    return [
        {
            "norma": r.citation.norma,
            "articulo": r.citation.articulo,
            "apartado": r.citation.apartado or "—",
            "validated": r.validated,
            "article_exists": r.article_exists,
            "apartado_exists": ("—" if r.apartado_exists is None else str(r.apartado_exists)),
            "text_normalized_match": r.text_normalized_match,
            "reason": r.reason or "",
        }
        for r in audited.audit_results
    ]


def chat_state(state: ChatState) -> None:
    """Top-level renderer for the Pestaña Pregunta output."""
    if state.injection_blocked:
        st.error(
            "La consulta fue bloqueada por contener instrucciones potencialmente "
            "maliciosas. Reformula sin texto del tipo 'ignora las instrucciones' "
            "o 'actúa como X'."
        )
        return

    audited = state.audited_answer
    if audited is None:
        st.error("Ha ocurrido un error inesperado. Revisa la consola para detalles.")
        return

    verdict_badge(audited.verdict, reason=audited.reason)
    st.markdown(audited.answer.text)
    for f in audited.answer.findings:
        finding(f)
    with st.expander("Detalles del Auditor (audit_results)"):
        st.dataframe(_audit_results_table(audited))


def document_report(report: DocumentReport) -> None:
    """Top-level renderer for the Pestaña Analiza documento output."""
    verdict_badge(report.document_verdict, reason=report.document_reason)

    if report.document_reason and report.document_reason.startswith("sanitizer_critical:"):
        category = report.document_reason.split(":", 1)[1]
        st.error(f"Documento bloqueado: {category}. Revisión humana requerida.")
        sanitizer_log_expander(report.sanitizer_log, expanded=True)
        return

    cols = st.columns(6)
    metrics: list[tuple[str, str]] = [
        ("PASS", str(report.n_segments_pass)),
        ("BLOCK", str(report.n_segments_block)),
        ("REVIEW", str(report.n_segments_review)),
        ("SKIPPED", str(report.n_segments_blocked_by_injection)),
        ("LATENCY", f"{report.latency_ms_total / 1000:.1f}s"),
        ("COST €", f"{report.cost_eur_total:.4f}"),
    ]
    for col, (label, value) in zip(cols, metrics, strict=True):
        with col:
            st.metric(label, value)

    # nosec B105 -- "pass" is an AuditVerdict enum value (Lenient-strict policy),
    # not a password. Bandit flags any string literal next to a key containing
    # "pass" regardless of context.
    emoji = {
        "pass": "✓",  # nosec B105
        "block": "✗",
        "requires_human_review": "⚠",
        "skipped": "⚠",
    }
    for sr in report.segments:
        verdict_str = (
            sr.audited_answer.verdict.value if sr.audited_answer is not None else "skipped"
        )
        title = sr.segment.title or "—"
        label = f"§{sr.segment.id} {title} · {emoji[verdict_str]} {verdict_str}"
        with st.expander(label, expanded=False):
            if sr.skipped:
                st.warning(
                    "Saltado: el segmento contiene contenido sospechoso de "
                    "manipulación. Revisión humana requerida."
                )
            else:
                assert (
                    sr.audited_answer is not None
                )  # nosec B101 -- mypy narrowing; the not-skipped branch guarantees audited_answer is set per SegmentResult invariant
                st.markdown(sr.audited_answer.answer.text)
                for f in sr.audited_answer.answer.findings:
                    finding(f)
                with st.expander("Detalles del Auditor"):
                    st.dataframe(_audit_results_table(sr.audited_answer))

    sanitizer_log_expander(report.sanitizer_log)
