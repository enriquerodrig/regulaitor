"""Streamlit render helpers shared between tab_ask and tab_analyze (H6).

These functions call Streamlit primitives directly; they are unit-tested
via monkeypatching in tests/unit/test_ui_render_helpers.py.

Defense rules per spec §8:
- pattern_name from anti-injection regex NEVER appears in user-visible text.
- Stack traces NEVER appear in user-visible text.
- Citation literal text is ALWAYS visible inline (Q3 A inline blockquote).
"""

from __future__ import annotations

import os

import streamlit as st

from regulaitor.api.schemas import _council_notice
from regulaitor.citation.schemas import (
    AuditedAnswer,
    AuditVerdict,
    CouncilReview,
    DocumentReport,
    Finding,
    PIISummary,
    SanitizerEvent,
)
from regulaitor.orchestration.state import ChatState

_SEVERITY_LABEL_COLOR = {
    "info": "gray",
    "low": "blue",
    "medium": "orange",
    "high": "red",
}

# Corpus chip palette — one accent color per norma, distinct enough to scan
# at a glance but all desaturated to stay subordinate to the verdict badge.
# Labels are the human-readable forms (uppercase, official acronyms).
_NORMA_STYLE: dict[str, tuple[str, str]] = {
    "ai_act": ("AI Act", "#1E40AF"),  # blue-800 (matches theme primaryColor)
    "gdpr": ("GDPR", "#047857"),  # emerald-700
    "nis2": ("NIS2", "#6D28D9"),  # violet-700
    "dora": ("DORA", "#B45309"),  # amber-700
    "dora_rts_incident": ("DORA RTS Plazos", "#0F766E"),  # teal-700 (Fase 3)
    "dora_rts_class": ("DORA RTS Clasif.", "#A21CAF"),  # fuchsia-700 (Fase 3)
}


def _norma_chip(norma: str) -> str:
    """Return HTML for a small colored corpus chip (e.g. "AI Act"). Inline."""
    label, color = _NORMA_STYLE.get(norma, (norma.upper(), "#475569"))
    return (
        f'<span style="background: {color}; color: #FFFFFF; padding: 2px 8px; '
        f"border-radius: 10px; font-size: 11px; font-weight: 700; "
        f'letter-spacing: 0.4px; vertical-align: middle;">{label}</span>'
    )


def _sources_summary(audited: AuditedAnswer) -> None:
    """Render small "Fuentes consultadas" line with corpus chips above the
    findings block. Surfaces multi-corpus reach (cross-corpus intelligence)
    automatically: 1 chip if single norma, N chips if auto resolved to many.
    """
    seen: list[str] = []
    for r in audited.audit_results:
        if r.citation.norma not in seen:
            seen.append(r.citation.norma)
    if not seen:
        return
    chips = " ".join(_norma_chip(n) for n in seen)
    st.markdown(
        f'<div style="margin: 4px 0 16px 0; font-size: 12px; color: #64748B;">'
        f"Fuentes consultadas: {chips}</div>",
        unsafe_allow_html=True,
    )


def _council_judge_rows(cr: CouncilReview) -> list[dict[str, object]]:
    """Per-judge projection shown in the Council expander. Redacted subset of
    CouncilReview/JudgeVote: judge `reason` is retained as auditable Council
    evidence (consistent with the T11 JudgeVoteDTO SSDLC decision — judge
    rationale over corpus text, not user PII, truncated upstream). NO raw
    user/ChatState text is exposed (only the explicit JudgeVote fields)."""
    return [
        {
            "model_id": j.model_id,
            "provider": j.provider,
            "vote": j.vote.value,
            "ok": j.ok,
            "error_category": j.error_category,
            "reason": j.reason,
        }
        for j in cr.judges
    ]


# Verdict badge colors — semantic Tailwind palette (NOT theme primaryColor).
# emerald-700 / rose-700 / amber-700 chosen for ≥4.5:1 contrast vs the *-50
# tinted backgrounds; matches the Vercel/shadcn alert pattern (subtle pill,
# border-left, never a full-width loud st.success/error/warning block).
_VERDICT_STYLE: dict[AuditVerdict, tuple[str, str, str]] = {
    AuditVerdict.PASS: ("PASS", "#047857", "#ECFDF5"),  # emerald-700, emerald-50
    AuditVerdict.BLOCK: ("BLOCK", "#BE123C", "#FFF1F2"),  # rose-700, rose-50
    AuditVerdict.REQUIRES_HUMAN_REVIEW: (
        "REQUIRES HUMAN REVIEW",
        "#B45309",  # amber-700
        "#FFFBEB",  # amber-50
    ),
}


def verdict_badge(verdict: AuditVerdict, reason: str | None = None) -> None:
    """Render the global verdict as a prominent pill with strong color accent.

    Structure: solid color pill on the left (label only) + tinted background
    panel on the right (reason text). Pill stays restrained per Vercel guideline
    (no emojis; semantic color used only as accent) but gains visual weight
    appropriate for the most important signal on the page.
    """
    label, color, bg = _VERDICT_STYLE[verdict]
    suffix_html = (
        f"""<span style="color: #475569; font-weight: 500; font-size: 13px;
        margin-left: 12px;">{reason}</span>"""
        if reason
        else ""
    )
    st.markdown(
        f"""<div role="status" aria-live="polite" style="display: flex;
        align-items: center; padding: 12px 16px; background: {bg};
        border-left: 4px solid {color}; border-radius: 6px; margin-bottom: 16px;">
        <span style="background: {color}; color: #FFFFFF; padding: 4px 12px;
        border-radius: 12px; font-weight: 700; font-size: 13px;
        letter-spacing: 0.6px;">{label}</span>{suffix_html}</div>""",
        unsafe_allow_html=True,
    )


def finding(f: Finding) -> None:
    """Render a Finding with severity badge and inline literal-text citations.

    Each citation is prefixed with a colored corpus chip (AI Act / GDPR / NIS2
    / DORA) for instant scanability and visual hierarchy. The chip uses HTML
    + unsafe_allow_html (markdown `:color[...]` can't render rounded pills).
    """
    color = _SEVERITY_LABEL_COLOR.get(f.severity, "gray")
    st.markdown(f"**{f.text}** &nbsp;:{color}[**{f.severity.upper()}**]")
    for c in f.citations:
        apartado = f".{c.apartado}" if c.apartado is not None else ""
        # Quote first (literal text), then attribution line with corpus chip.
        st.markdown(f"> _{c.text}_", unsafe_allow_html=True)
        st.markdown(
            f'<div style="margin: -8px 0 12px 14px; font-size: 13px; color: #475569;">'
            f"{_norma_chip(c.norma)} &nbsp; "
            f'<span style="font-weight: 600;">art. {c.articulo}{apartado}</span> '
            f'<span style="color: #94A3B8;">({c.language})</span></div>',
            unsafe_allow_html=True,
        )


# Human-readable Spanish labels for the PII kinds emitted by security.pii.
_PII_KIND_LABEL = {
    "email": "email",
    "phone": "teléfono",
    "dni_nif": "DNI/NIF",
    "nie": "NIE",
    "iban": "IBAN",
    "card": "tarjeta",
}


def pii_banner(summary: PIISummary) -> None:
    """Advisory banner: personal data detected in the document (counts only).

    The document is analyzed regardless — this only warns the user (§18.5). No
    raw values are ever shown (the summary carries counts/kinds only, §18.8).
    """
    kinds_label = ", ".join(
        f"{_PII_KIND_LABEL.get(kind, kind)} ({n})" for kind, n in summary.counts.items()
    )
    st.warning(
        f"Se detectaron datos personales en el documento "
        f"({summary.total}: {kinds_label}). El análisis se realiza igualmente; "
        "los registros internos solo guardan recuentos, nunca los valores "
        "detectados. Anonimiza antes de compartir el informe."
    )


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
    _sources_summary(audited)

    # Advisory Council notice (H13): show prominently if diverges from Auditor
    notice = _council_notice(state.council_review, state.audited_answer)
    cr = state.council_review
    if notice and cr is not None:
        st.warning(notice)
        with st.expander("Council (evidencia) — votos de los jueces"):
            st.json(_council_judge_rows(cr))

    st.markdown(audited.answer.text)
    for f in audited.answer.findings:
        finding(f)
    # Auditor details: gated by REGULAITOR_SHOW_AUDIT_DETAILS env (default true).
    # TFM/HF Space demo leaves visible — shows §6 invariant working;
    # production deploy can flip to false to hide internal validation flags.
    if os.getenv("REGULAITOR_SHOW_AUDIT_DETAILS", "true").lower() != "false":
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

    # Fase 2.1 (§18.5): advisory PII banner when the document carries personal data.
    if report.pii_summary is not None:
        pii_banner(report.pii_summary)

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

    emoji = {
        "pass": "✓",  # nosec B105 -- U+2713 checkmark, not a password
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
