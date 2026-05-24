"""v0.1.21 — Tier 2 Capa B: Pydantic min_length=1 on Answer.findings.

Pins that the schema rejects empty findings at validation time. This is the
server-side defense-in-depth that complements Capa A (Anthropic strict mode)
and Capa C (aggressive retry with feedback).

ADR-0027 / spec D3.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import Answer, Citation, Finding


def _make_finding() -> Finding:
    citation = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="text")
    return Finding(text="finding text", citations=[citation])


def test_answer_with_one_finding_validates() -> None:
    """Single Finding is the new minimum; instantiation succeeds."""
    a = Answer(query="q", language="es", text="response", findings=[_make_finding()])
    assert len(a.findings) == 1


def test_answer_with_empty_findings_raises_validation_error() -> None:
    """Empty findings list is now invalid (Capa B Pydantic min_length=1)."""
    with pytest.raises(ValidationError) as exc_info:
        Answer(query="q", language="es", text="No findings here.", findings=[])
    # Sanity-check the error attaches to the `findings` field.
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("findings",) for err in errors)


def test_answer_with_multiple_findings_validates() -> None:
    """Multiple Findings (typical case) still validate."""
    a = Answer(
        query="q",
        language="es",
        text="response",
        findings=[_make_finding(), _make_finding(), _make_finding()],
    )
    assert len(a.findings) == 3
