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


def test_audit_answer_with_no_findings_rejected_at_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.21 (Capa B): Answer with empty findings is no longer constructible.
    This test's original intent (no findings -> PASS verdict) is now moot
    because the schema forbids empty findings. Renamed post-final-review
    (C2 M3) to match v0.1.21 actual behavior: empty findings is REJECTED at
    schema level, never reaches the Auditor at all. Pinning that _answer()
    rejects empty input.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _answer([])


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


# v0.1.25 (ADR-0032 D2): tests for partial-Findings routing softening
# _all_blocked_findings_paraphrase_only helper + integration tests


def test_all_blocked_findings_paraphrase_only_returns_true_when_all_check3() -> None:
    """v0.1.25 (ADR-0032 D2): partial-Findings with blocked-Finding all-citations
    failed_check==3 → helper returns True (paraphrase-only blocked Findings)."""
    from regulaitor.agents.auditor import _all_blocked_findings_paraphrase_only
    from regulaitor.citation.schemas import AuditResult, Citation

    cite = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    pass_result = AuditResult(
        citation=cite,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    paraphrase_result = AuditResult(
        citation=cite,
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
        failed_check=3,
    )

    finding_verdicts = ["pass", "blocked"]
    per_finding_results = [[pass_result], [paraphrase_result]]

    assert _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results) is True


def test_all_blocked_findings_paraphrase_only_returns_false_when_any_check1() -> None:
    """v0.1.25 (ADR-0032 D2): any Check 1 fail in blocked Finding → False (fabrication)."""
    from regulaitor.agents.auditor import _all_blocked_findings_paraphrase_only
    from regulaitor.citation.schemas import AuditResult, Citation

    cite = Citation(norma="ai_act", articulo="999", apartado="1", language="es", text="fake")
    pass_cite = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    pass_result = AuditResult(
        citation=pass_cite,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    fab_result = AuditResult(
        citation=cite,
        validated=False,
        article_exists=False,
        apartado_exists=False,
        text_normalized_match=False,
        reason="article_not_found",
        failed_check=1,
    )

    finding_verdicts = ["pass", "blocked"]
    per_finding_results = [[pass_result], [fab_result]]

    assert _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results) is False


def test_all_blocked_findings_paraphrase_only_returns_false_when_any_check2() -> None:
    """v0.1.25 (ADR-0032 D2): any Check 2 fail in blocked Finding → False (apartado fab)."""
    from regulaitor.agents.auditor import _all_blocked_findings_paraphrase_only
    from regulaitor.citation.schemas import AuditResult, Citation

    cite = Citation(norma="ai_act", articulo="6", apartado="99", language="es", text="fake")
    pass_cite = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    pass_result = AuditResult(
        citation=pass_cite,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    fab_result = AuditResult(
        citation=cite,
        validated=False,
        article_exists=True,
        apartado_exists=False,
        text_normalized_match=False,
        reason="apartado_not_found",
        failed_check=2,
    )

    finding_verdicts = ["pass", "blocked"]
    per_finding_results = [[pass_result], [fab_result]]

    assert _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results) is False


def test_all_blocked_findings_paraphrase_only_returns_false_when_failed_check_none() -> None:
    """v0.1.25 (ADR-0032 D2): pre-v0.1.24 cached data (failed_check=None) → False conservative."""
    from regulaitor.agents.auditor import _all_blocked_findings_paraphrase_only
    from regulaitor.citation.schemas import AuditResult, Citation

    cite = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    pass_cite = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    pass_result = AuditResult(
        citation=pass_cite,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    invalid_result = AuditResult(
        citation=cite,
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
        failed_check=None,  # None = pre-v0.1.24 cached data
    )

    finding_verdicts = ["pass", "blocked"]
    per_finding_results = [[pass_result], [invalid_result]]

    assert _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results) is False


def test_auditor_partial_routing_pass_when_blocked_findings_all_paraphrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.25 D2: integration partial-Findings (1 pass + 1 paraphrase-blocked) → PASS."""
    from regulaitor.agents import auditor as auditor_module
    from regulaitor.agents.auditor import AuditorAgent
    from regulaitor.citation.schemas import (
        Answer,
        AuditResult,
        AuditVerdict,
        Citation,
        Finding,
    )

    cite_pass = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t_pass")
    cite_para = Citation(
        norma="ai_act", articulo="7", apartado="1", language="es", text="t_paraphrase"
    )

    result_pass = AuditResult(
        citation=cite_pass,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    result_para = AuditResult(
        citation=cite_para,
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
        failed_check=3,
    )

    results_by_citation = {id(cite_pass): result_pass, id(cite_para): result_para}

    def mock_validate(citation: Citation, **kwargs: object) -> AuditResult:
        return results_by_citation[id(citation)]

    monkeypatch.setattr(auditor_module.validator, "validate", mock_validate)

    finding_pass = Finding(text="claim_pass", citations=[cite_pass], severity="info")
    finding_para = Finding(text="claim_para", citations=[cite_para], severity="info")
    answer = Answer(query="q", language="es", text="t", findings=[finding_pass, finding_para])

    audited = AuditorAgent().audit(answer)

    # v0.1.25 D2 expected: PASS (partial with all-paraphrase-only blocked Finding)
    # Pre-v0.1.25: would be RHR (partial → always RHR)
    assert (
        audited.verdict == AuditVerdict.PASS
    ), f"Expected PASS post-v0.1.25 D2 partial-routing but got {audited.verdict}"


def test_auditor_partial_routing_rhr_when_blocked_findings_have_fabrication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.25 D2: partial with Check 1 fab in blocked Finding -> RHR (preserves pre-v0.1.25)."""
    from regulaitor.agents import auditor as auditor_module
    from regulaitor.agents.auditor import AuditorAgent
    from regulaitor.citation.schemas import (
        Answer,
        AuditResult,
        AuditVerdict,
        Citation,
        Finding,
    )

    cite_pass = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t_pass")
    cite_fab = Citation(norma="ai_act", articulo="999", apartado="1", language="es", text="t_fab")

    result_pass = AuditResult(
        citation=cite_pass,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    result_fab = AuditResult(
        citation=cite_fab,
        validated=False,
        article_exists=False,
        apartado_exists=False,
        text_normalized_match=False,
        reason="article_not_found",
        failed_check=1,
    )

    results_by_citation = {id(cite_pass): result_pass, id(cite_fab): result_fab}

    def mock_validate(citation: Citation, **kwargs: object) -> AuditResult:
        return results_by_citation[id(citation)]

    monkeypatch.setattr(auditor_module.validator, "validate", mock_validate)

    finding_pass = Finding(text="claim_pass", citations=[cite_pass], severity="info")
    finding_fab = Finding(text="claim_fab", citations=[cite_fab], severity="info")
    answer = Answer(query="q", language="es", text="t", findings=[finding_pass, finding_fab])

    audited = AuditorAgent().audit(answer)

    # v0.1.25 D2 expected: RHR (fabrication blocks partial-routing softening)
    assert (
        audited.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    ), f"Expected RHR (fabrication detection preserved) but got {audited.verdict}"


def test_auditor_partial_routing_rhr_when_blocked_findings_failed_check_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1.25 D2: partial with failed_check=None blocked → RHR conservative."""
    from regulaitor.agents import auditor as auditor_module
    from regulaitor.agents.auditor import AuditorAgent
    from regulaitor.citation.schemas import (
        Answer,
        AuditResult,
        AuditVerdict,
        Citation,
        Finding,
    )

    cite_pass = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t_pass")
    cite_unknown = Citation(norma="ai_act", articulo="7", apartado="1", language="es", text="t_u")

    result_pass = AuditResult(
        citation=cite_pass,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
        failed_check=None,
    )
    result_unknown = AuditResult(
        citation=cite_unknown,
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
        failed_check=None,  # None = pre-v0.1.24 cached data
    )

    results_by_citation = {id(cite_pass): result_pass, id(cite_unknown): result_unknown}

    def mock_validate(citation: Citation, **kwargs: object) -> AuditResult:
        return results_by_citation[id(citation)]

    monkeypatch.setattr(auditor_module.validator, "validate", mock_validate)

    finding_pass = Finding(text="claim_pass", citations=[cite_pass], severity="info")
    finding_unknown = Finding(text="claim_unknown", citations=[cite_unknown], severity="info")
    answer = Answer(query="q", language="es", text="t", findings=[finding_pass, finding_unknown])

    audited = AuditorAgent().audit(answer)

    # v0.1.25 D2 expected: RHR (failed_check=None → conservative preserves pre-v0.1.25)
    assert (
        audited.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    ), f"Expected RHR (failed_check=None conservative) but got {audited.verdict}"
