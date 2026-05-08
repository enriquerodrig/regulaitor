"""H5 property tests — pipeline invariants under arbitrary inputs."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.citation.schemas import (
    AuditVerdict,
    DocumentBlockedError,
    Page,
    RawDocument,
    SanitizedDocument,
)
from regulaitor.document import sanitizer, segmenter

_TEXT_STRATEGY = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=60,
    max_size=2000,
)


def _raw_md(text: str, metadata: dict[str, str] | None = None) -> RawDocument:
    return RawDocument(
        document_hash="sha256:f",
        mime_type="text/markdown",
        language="es",
        pages=[
            Page(
                number=1,
                text=text,
                fonts=[],
                annotations=[],
                hidden_text_candidates=[],
                likely_scanned=False,
            )
        ],
        metadata=metadata or {},
        attachments=[],
        outline=None,
        has_javascript=False,
        has_form_actions=False,
        uri_actions=[],
    )


@given(text=_TEXT_STRATEGY)
@settings(max_examples=50, deadline=2000)
def test_sanitize_returns_doc_or_raises(text: str) -> None:
    """For any text >=60 chars, sanitize either returns a SanitizedDocument
    or raises DocumentBlockedError. Never returns a malformed result.
    """
    raw = _raw_md(text)
    try:
        sd = sanitizer.sanitize(raw)
    except DocumentBlockedError:
        return
    assert isinstance(sd, SanitizedDocument)
    assert len(sd.clean_text) >= 50


@given(text=_TEXT_STRATEGY)
@settings(max_examples=20, deadline=2000)
def test_segment_covers_at_least_50pct_of_text(text: str) -> None:
    """Segmenter never silently loses input — the joined token text covers
    at least half the original character count (allowing for whitespace
    normalization and paragraph splitting).
    """
    raw = _raw_md(text)
    try:
        sd = sanitizer.sanitize(raw)
    except DocumentBlockedError:
        return
    segs = segmenter.segment(sd)
    assert len(segs) >= 1
    total_chars = sum(len(s.text) for s in segs)
    assert total_chars >= len(sd.clean_text) * 0.5


@pytest.mark.parametrize(
    "verdicts,expected_doc",
    [
        (("pass", "pass"), AuditVerdict.PASS),
        (("pass", "block"), AuditVerdict.BLOCK),
        (("pass", "requires_human_review"), AuditVerdict.REQUIRES_HUMAN_REVIEW),
        (("block", "requires_human_review"), AuditVerdict.BLOCK),
        (
            ("requires_human_review", "requires_human_review"),
            AuditVerdict.REQUIRES_HUMAN_REVIEW,
        ),
    ],
)
def test_aggregation_matrix(verdicts: tuple[str, ...], expected_doc: AuditVerdict) -> None:
    """Verdict aggregation matrix from spec §7."""
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        AuditResult,
        Citation,
        Finding,
        Segment,
        SegmentResult,
    )
    from regulaitor.orchestration.document_graph import _aggregate_document

    citation = Citation(
        norma="ai_act",
        articulo="1",
        apartado="1",
        language="es",
        text="t",
    )
    finding = Finding(text="x", citations=[citation])
    answer = Answer(query="q", language="es", text="t", findings=[finding])
    audit_result = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )

    segs = []
    for i, v in enumerate(verdicts, start=1):
        seg = Segment(id=i, title=f"S{i}", text="x", token_count=1, is_continuation=False)
        audited = AuditedAnswer(
            answer=answer,
            verdict=AuditVerdict(v),
            audit_results=[audit_result],
            reason=None,
        )
        segs.append(
            SegmentResult(
                segment=seg,
                skipped=False,
                skip_reason=None,
                audited_answer=audited,
                latency_ms=1,
                cost_eur=0.0,
            )
        )
    verdict, _, _, _, _, _ = _aggregate_document(segs, [])
    assert verdict == expected_doc
