"""Unit tests for agents/auditor.py — Lenient-strict aggregation over H3 validator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.agents.auditor import AuditorAgent
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)


def _citation(articulo: str = "6", apartado: str | None = "1", text: str = "t") -> Citation:
    return Citation(norma="ai_act", articulo=articulo, apartado=apartado, language="es", text=text)


def _audit_result(citation: Citation, *, validated: bool, reason: str | None) -> AuditResult:
    return AuditResult(
        citation=citation,
        validated=validated,
        article_exists=validated,
        apartado_exists=validated if citation.apartado else None,
        text_normalized_match=validated,
        reason=reason,
    )


def _answer(findings: list[Finding]) -> Answer:
    return Answer(query="q", language="es", text="response", findings=findings)


def test_audit_pass_all_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.agents import auditor

    c1 = _citation("6", "1", "t1")
    c2 = _citation("7", "2", "t2")
    finding = Finding(text="f1", citations=[c1, c2])
    answer = _answer([finding])

    validate_mock = MagicMock(
        side_effect=[
            _audit_result(c1, validated=True, reason=None),
            _audit_result(c2, validated=True, reason=None),
        ]
    )
    monkeypatch.setattr(auditor.validator, "validate", validate_mock)

    result = AuditorAgent().audit(answer)

    assert isinstance(result, AuditedAnswer)
    assert result.verdict == AuditVerdict.PASS
    assert result.reason is None
    assert len(result.audit_results) == 2


def test_audit_block_all_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    from regulaitor.agents import auditor

    c1 = _citation("999", None, "t1")
    finding = Finding(text="f1", citations=[c1])
    answer = _answer([finding])

    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            return_value=_audit_result(
                c1, validated=False, reason="article_not_found: ai_act art. 999"
            )
        ),
    )

    result = AuditorAgent().audit(answer)

    assert result.verdict == AuditVerdict.BLOCK
    assert result.reason is not None
    assert "BLOCK" in result.reason
    assert "article_not_found" in result.reason


def test_audit_requires_human_review_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """One Finding all-valid + one Finding all-invalid -> REQUIRES_HUMAN_REVIEW."""
    from regulaitor.agents import auditor

    c_good = _citation("6", "1", "good")
    c_bad = _citation("999", None, "bad")
    finding_good = Finding(text="good finding", citations=[c_good])
    finding_bad = Finding(text="bad finding", citations=[c_bad])
    answer = _answer([finding_good, finding_bad])

    validate_mock = MagicMock(
        side_effect=[
            _audit_result(c_good, validated=True, reason=None),
            _audit_result(c_bad, validated=False, reason="article_not_found"),
        ]
    )
    monkeypatch.setattr(auditor.validator, "validate", validate_mock)

    result = AuditorAgent().audit(answer)

    assert result.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert result.reason is not None
    assert "REQUIRES_HUMAN_REVIEW" in result.reason


def test_audit_lenient_finding_passes_with_one_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Finding with 1 valid + 1 invalid citation should still PASS the Finding."""
    from regulaitor.agents import auditor

    c1 = _citation("6", "1", "t1")
    c2 = _citation("999", None, "t2")
    finding = Finding(text="f1", citations=[c1, c2])
    answer = _answer([finding])

    validate_mock = MagicMock(
        side_effect=[
            _audit_result(c1, validated=True, reason=None),
            _audit_result(c2, validated=False, reason="article_not_found"),
        ]
    )
    monkeypatch.setattr(auditor.validator, "validate", validate_mock)

    result = AuditorAgent().audit(answer)

    # Lenient: Finding passes because >=1 citation valid
    # Strict aggregate: all Findings passed -> PASS overall
    assert result.verdict == AuditVerdict.PASS


def test_audit_audit_results_flat_across_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from regulaitor.agents import auditor

    c1 = _citation("6", "1", "t1")
    c2 = _citation("7", "1", "t2")
    c3 = _citation("8", "1", "t3")
    f1 = Finding(text="f1", citations=[c1, c2])
    f2 = Finding(text="f2", citations=[c3])
    answer = _answer([f1, f2])

    validate_mock = MagicMock(
        side_effect=[
            _audit_result(c1, validated=True, reason=None),
            _audit_result(c2, validated=True, reason=None),
            _audit_result(c3, validated=True, reason=None),
        ]
    )
    monkeypatch.setattr(auditor.validator, "validate", validate_mock)

    result = AuditorAgent().audit(answer)

    assert len(result.audit_results) == 3


def test_audit_answer_with_no_findings_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Analyst emits empty findings (corpus doesn't support answer), verdict=PASS."""
    from regulaitor.agents import auditor

    answer = _answer([])
    monkeypatch.setattr(auditor.validator, "validate", MagicMock())  # never called

    result = AuditorAgent().audit(answer)

    assert result.verdict == AuditVerdict.PASS
    assert len(result.audit_results) == 0


def test_audit_reason_uses_pipe_separator_not_semicolon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validator reasons embed ';' so Auditor must join per-Finding reasons with ' | '.

    Example validator reason: 'text_not_in_apartado: ai_act art. 6.2; cited text
    not found...'. Downstream parsers must split unambiguously, so the Auditor's
    inter-reason separator must be a string the validator never emits.
    """
    from regulaitor.agents import auditor

    c1 = _citation("6", "2", "t1")
    c2 = _citation("999", None, "t2")
    finding = Finding(text="f", citations=[c1, c2])
    answer = _answer([finding])

    # Real-format reasons containing ';' (matching validator's actual output)
    reason_with_semicolon = (
        "text_not_in_apartado: ai_act art. 6.2 es; cited text not found "
        "after normalization (12 chars vs 800 chars apartado)."
    )
    monkeypatch.setattr(
        auditor.validator,
        "validate",
        MagicMock(
            side_effect=[
                _audit_result(c1, validated=False, reason=reason_with_semicolon),
                _audit_result(
                    c2,
                    validated=False,
                    reason="article_not_found: ai_act has no articulo 999 in language es",
                ),
            ]
        ),
    )

    result = AuditorAgent().audit(answer)

    # The 2 reasons should be joined with " | ", not ";"
    assert result.reason is not None
    assert " | " in result.reason
    # Both reasons must appear in the output
    assert "text_not_in_apartado" in result.reason
    assert "article_not_found" in result.reason
