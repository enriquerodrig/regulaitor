"""H5 slow E2E: adversarial synthesized policy → REQUIRES_HUMAN_REVIEW.

The sanitizer short-circuits on embedded JavaScript before any LLM
call, so this test does NOT require ANTHROPIC_API_KEY. Only the
fixture-existence guard is kept — this lets the H5 closure gate be
verified in any environment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaitor.citation.schemas import AuditVerdict
from regulaitor.orchestration.document_graph import run_document

_FIXTURE = Path("evals/document_cases/synthesized_policy_adversarial.pdf")


@pytest.mark.document_slow
@pytest.mark.skipif(
    not _FIXTURE.exists(),
    reason="run `make regenerate-fixtures` first",
)
def test_e2e_adversarial_policy_review_or_block():
    file_bytes = _FIXTURE.read_bytes()
    report = run_document(
        file_bytes=file_bytes,
        mime_type="application/pdf",
        language="es",
        corpus=["ai_act", "gdpr"],
    )
    assert report.document_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert any(
        e.severity == "critical" and e.category == "javascript_blocked"
        for e in report.sanitizer_log
    )
    assert "sanitizer_critical:javascript_blocked" in (report.document_reason or "")
