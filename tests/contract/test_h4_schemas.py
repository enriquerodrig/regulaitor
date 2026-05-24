"""Hypothesis round-trip contract tests for H4 schemas: Finding, Answer, AuditedAnswer."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)

pytestmark = pytest.mark.contract


_NORMA = st.sampled_from(["ai_act", "gdpr", "nis2", "dora"])
_LANG = st.sampled_from(["es", "en"])
_NON_EMPTY = st.text(min_size=1, max_size=200)
_SEVERITY = st.sampled_from(["info", "low", "medium", "high"])


def _citation_strategy() -> st.SearchStrategy[Citation]:
    return st.builds(
        Citation,
        norma=_NORMA,
        articulo=_NON_EMPTY,
        apartado=st.one_of(st.none(), _NON_EMPTY),
        language=_LANG,
        text=_NON_EMPTY,
    )


def _finding_strategy() -> st.SearchStrategy[Finding]:
    return st.builds(
        Finding,
        text=_NON_EMPTY,
        citations=st.lists(_citation_strategy(), min_size=1, max_size=3),
        severity=_SEVERITY,
    )


@given(finding=_finding_strategy())
@settings(max_examples=50)
def test_finding_round_trip(finding: Finding) -> None:
    parsed = Finding.model_validate_json(finding.model_dump_json())
    assert parsed == finding


@given(
    query=_NON_EMPTY,
    language=_LANG,
    text=_NON_EMPTY,
    findings=st.lists(_finding_strategy(), min_size=1, max_size=3),  # v0.1.21: min_size=1
)
@settings(max_examples=30)
def test_answer_round_trip(query: str, language: str, text: str, findings: list[Finding]) -> None:
    a = Answer(query=query, language=language, text=text, findings=findings)  # type: ignore[arg-type]
    parsed = Answer.model_validate_json(a.model_dump_json())
    assert parsed == a


def test_audited_answer_round_trip_minimal() -> None:
    citation = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    finding = Finding(text="t", citations=[citation])
    answer = Answer(query="q", language="es", text="t", findings=[finding])
    audit_result = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    aa = AuditedAnswer(
        answer=answer,
        verdict=AuditVerdict.PASS,
        audit_results=[audit_result],
        reason=None,
    )
    parsed = AuditedAnswer.model_validate_json(aa.model_dump_json())
    assert parsed == aa
