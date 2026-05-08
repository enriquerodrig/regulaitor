"""H5 slow E2E: clean synthesized policy → document_verdict=PASS.

Requires ANTHROPIC_API_KEY; loads BGE-M3 + reranker + LanceDB. Skipped
when the API key is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from regulaitor.citation.schemas import AuditVerdict
from regulaitor.orchestration.document_graph import run_document

_FIXTURE = Path("evals/document_cases/synthesized_policy_clean.pdf")


@pytest.mark.document_slow
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
@pytest.mark.skipif(
    not _FIXTURE.exists(),
    reason="run `make regenerate-fixtures` first",
)
def test_e2e_clean_policy_pass():
    file_bytes = _FIXTURE.read_bytes()
    report = run_document(
        file_bytes=file_bytes,
        mime_type="application/pdf",
        language="es",
        corpus=["ai_act", "gdpr"],
    )
    assert report.n_segments_total >= 3
    assert report.document_verdict in (
        AuditVerdict.PASS,
        AuditVerdict.REQUIRES_HUMAN_REVIEW,
    )
    assert report.latency_ms_total < 90_000
    assert not any(e.severity == "critical" for e in report.sanitizer_log)
