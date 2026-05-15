"""H5 document E2E orchestration.

Sequential per-segment loop. NOT a LangGraph compiled graph — the control
flow is linear and a Python loop is more auditable. The chat graph in
`graph.py` (LangGraph-based) is separate and untouched.

Spec docs/superpowers/specs/2026-05-06-h5-document-pipeline-design.md §4.8.
"""

from __future__ import annotations

import functools
import json
import logging
import time
from collections import Counter
from datetime import datetime
from secrets import token_urlsafe
from typing import cast

from regulaitor.agents.analyst import AnalystAgent
from regulaitor.agents.auditor import AuditorAgent
from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditVerdict,
    DocumentBlockedError,
    DocumentReport,
    SanitizedDocument,
    SanitizerEvent,
    Segment,
    SegmentResult,
)
from regulaitor.corpus.schemas import Language, Norma
from regulaitor.document import extractor, sanitizer, segmenter
from regulaitor.observability.langfuse_client import trace_turn
from regulaitor.security import injection

logger = logging.getLogger("regulaitor.orchestration.document_graph")


# Lazy-init agent helpers. Same pattern as orchestration.graph: avoid
# import-time I/O so a missing prompt only fails at first use, and so each
# agent is constructed at most once per process.
@functools.lru_cache(maxsize=1)
def _retriever() -> RetrieverAgent:
    return RetrieverAgent()


@functools.lru_cache(maxsize=1)
def _analyst_doc() -> AnalystAgent:
    return AnalystAgent(prompt_role="document_analyst")


@functools.lru_cache(maxsize=1)
def _auditor() -> AuditorAgent:
    return AuditorAgent()


def _generate_case_id() -> str:
    """Build a deterministic-shape case_id with a random suffix.

    Format: ``doc-YYYYMMDD-<8 url-safe chars>``. Suffix uses ``secrets``
    rather than ``random`` so external observers cannot guess upcoming ids.
    """
    today = datetime.utcnow().strftime("%Y%m%d")  # noqa: DTZ005
    suffix = token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]
    return f"doc-{today}-{suffix}"


def _aggregate_document(
    segment_results: list[SegmentResult],
    sanitizer_log: list[SanitizerEvent],  # noqa: ARG001 — kept for symmetry with caller
) -> tuple[AuditVerdict, str | None, int, int, int, int]:
    """Per-document Lenient-strict aggregation.

    Returns ``(verdict, reason, n_pass, n_block, n_review, n_blocked_by_injection)``.

    Rules (spec §7):
      * Any segment skipped by anti-injection counts as a BLOCK contributor.
      * Any segment whose AuditedAnswer.verdict is BLOCK contributes to BLOCK.
      * Any non-PASS / non-BLOCK segment (i.e. REQUIRES_HUMAN_REVIEW)
        contributes to REVIEW.
      * Document verdict: PASS only if everyone passes. Otherwise BLOCK if
        any contributor is BLOCK or injection-skipped; else REQUIRES_HUMAN_REVIEW.
    """
    n_pass = 0
    n_block = 0
    n_review = 0
    n_inj = 0
    block_ids: list[int] = []
    review_ids: list[int] = []
    inj_ids: list[int] = []

    for sr in segment_results:
        if sr.skipped:
            n_inj += 1
            inj_ids.append(sr.segment.id)
            continue
        if sr.audited_answer is None:
            # Defensive: a non-skipped segment must carry an audited_answer.
            # We treat it as REVIEW so the document doesn't silently PASS.
            n_review += 1
            review_ids.append(sr.segment.id)
            continue
        v = sr.audited_answer.verdict
        if v == AuditVerdict.PASS:
            n_pass += 1
        elif v == AuditVerdict.BLOCK:
            n_block += 1
            block_ids.append(sr.segment.id)
        else:  # REQUIRES_HUMAN_REVIEW
            n_review += 1
            review_ids.append(sr.segment.id)

    if n_block == 0 and n_inj == 0 and n_review == 0:
        return AuditVerdict.PASS, None, n_pass, n_block, n_review, n_inj

    parts: list[str] = []
    if block_ids:
        parts.append(f"block_in_segments:{block_ids}")
    if inj_ids:
        parts.append(f"injection_skipped:{inj_ids}")
    if review_ids and n_block == 0 and n_inj == 0:
        parts.append(f"review_in_segments:{review_ids}")

    reason = " | ".join(parts) if parts else None

    if n_block > 0 or n_inj > 0:
        return AuditVerdict.BLOCK, reason, n_pass, n_block, n_review, n_inj
    return AuditVerdict.REQUIRES_HUMAN_REVIEW, reason, n_pass, n_block, n_review, n_inj


def _process_segment(
    seg: Segment,
    corpus: Norma,
    language: Language,
) -> SegmentResult:
    """Run anti-injection -> Retriever -> Analyst -> Auditor for one segment."""
    t0 = time.monotonic()
    blocked, pattern = injection.is_injection(seg.text, mode="document")
    if blocked:
        latency = int((time.monotonic() - t0) * 1000)
        return SegmentResult(
            segment=seg,
            skipped=True,
            skip_reason=pattern,
            audited_answer=None,
            latency_ms=latency,
            cost_eur=0.0,
        )
    ctx = _retriever().retrieve(seg.text, corpus, language)
    answer: Answer = _analyst_doc().analyze(seg.text, ctx)
    audited: AuditedAnswer = _auditor().audit(answer)
    latency = int((time.monotonic() - t0) * 1000)
    return SegmentResult(
        segment=seg,
        skipped=False,
        skip_reason=None,
        audited_answer=audited,
        latency_ms=latency,
        cost_eur=0.0,
    )


def _log_document_turn(report: DocumentReport) -> None:
    """Emit a single structured JSON log line. No PII; counters + hashes only."""
    cats = Counter(e.category for e in report.sanitizer_log)
    record = {
        "case_id": report.case_id,
        "document_hash": report.document_hash,
        "language": report.language,
        "corpus": report.corpus,
        "document_verdict": report.document_verdict.value,
        "n_segments_total": report.n_segments_total,
        "n_segments_pass": report.n_segments_pass,
        "n_segments_block": report.n_segments_block,
        "n_segments_review": report.n_segments_review,
        "n_segments_blocked_by_injection": report.n_segments_blocked_by_injection,
        "sanitizer_event_categories": dict(cats),
        "latency_ms_total": report.latency_ms_total,
        "cost_eur_total": report.cost_eur_total,
    }
    logger.info("document_turn: %s", json.dumps(record, ensure_ascii=False))


def _doc_trace_record(report: DocumentReport) -> dict[str, object]:
    """Metadata-only summary of a document turn. NO raw document text —
    only a sha256[:12] prefix. Mirrors the allowlist-safe subset of the
    JSON log line; see observability.langfuse_client redaction allowlist."""
    return {
        "case_id": report.case_id,
        "document_sha256_12": report.document_hash[:12],
        "corpus": ",".join(report.corpus),
        "language": report.language,
        "document_verdict": report.document_verdict.value,
        "n_segments_total": report.n_segments_total,
        "n_segments_pass": report.n_segments_pass,
        "n_segments_block": report.n_segments_block,
        "n_segments_review": report.n_segments_review,
        "n_segments_blocked_by_injection": report.n_segments_blocked_by_injection,
        "latency_ms_total": report.latency_ms_total,
        "cost_eur_total": report.cost_eur_total,
    }


def run_document(
    *,
    file_bytes: bytes,
    mime_type: str,
    language: Language,
    corpus: list[str],
    case_id: str | None = None,
) -> DocumentReport:
    """Run the H5 document pipeline E2E and return a DocumentReport.

    Pipeline:
        extract -> sanitize -> segment -> (per-segment: anti-injection ->
        retrieve -> analyze -> audit) -> aggregate.

    Sanitizer critical-block (DocumentBlockedError) short-circuits before
    segmentation; the resulting DocumentReport carries verdict
    REQUIRES_HUMAN_REVIEW, ``segments=[]`` and the partial sanitizer_log.
    """
    case_id = case_id or _generate_case_id()
    with trace_turn(
        kind="document",
        case_id=case_id,
        corpus=",".join(corpus),
        language=language,
    ) as tt:
        t0 = time.monotonic()

        raw = extractor.extract(file_bytes, mime_type=mime_type)
        try:
            sanitized: SanitizedDocument = sanitizer.sanitize(raw)
        except DocumentBlockedError as e:
            latency = int((time.monotonic() - t0) * 1000)
            report = DocumentReport(
                case_id=case_id,
                document_hash=raw.document_hash,
                language=language,
                corpus=corpus,
                sanitizer_log=e.sanitizer_log,
                segments=[],
                document_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                document_reason=f"sanitizer_critical:{e.reason}",
                n_segments_total=0,
                n_segments_blocked_by_injection=0,
                n_segments_pass=0,
                n_segments_block=0,
                n_segments_review=0,
                latency_ms_total=latency,
                cost_eur_total=0.0,
            )
            _log_document_turn(report)
            tt.set_root(**_doc_trace_record(report))
            return report

        segs = segmenter.segment(sanitized)
        primary_corpus = cast(Norma, corpus[0])
        segment_results: list[SegmentResult] = []
        for seg in segs:
            sr = _process_segment(seg, primary_corpus, language)
            segment_results.append(sr)

        verdict, reason, n_pass, n_block, n_review, n_inj = _aggregate_document(
            segment_results, sanitized.sanitizer_log
        )
        latency = int((time.monotonic() - t0) * 1000)

        report = DocumentReport(
            case_id=case_id,
            document_hash=sanitized.document_hash,
            language=language,
            corpus=corpus,
            sanitizer_log=sanitized.sanitizer_log,
            segments=segment_results,
            document_verdict=verdict,
            document_reason=reason,
            n_segments_total=len(segment_results),
            n_segments_blocked_by_injection=n_inj,
            n_segments_pass=n_pass,
            n_segments_block=n_block,
            n_segments_review=n_review,
            latency_ms_total=latency,
            cost_eur_total=sum(sr.cost_eur for sr in segment_results),
        )
        _log_document_turn(report)
        tt.set_root(**_doc_trace_record(report))
        return report
