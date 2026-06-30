"""dos-01: an over-segmented document short-circuits to REQUIRES_HUMAN_REVIEW
before the per-segment CPU-reranker loop (DoS guard), never a silent pass."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import AuditVerdict, Segment
from regulaitor.document import segmenter
from regulaitor.orchestration import document_graph
from regulaitor.orchestration.document_graph import run_document


def _seg(i: int) -> Segment:
    return Segment(id=i, title=None, text=f"clause {i}", token_count=2, is_continuation=False)


def test_too_many_segments_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_MAX_SEGMENTS", "2")
    # 3 > cap of 2. The fake segmenter avoids needing a pathological real document;
    # the agents are never constructed/called (we return before the loop) → $0.
    monkeypatch.setattr(segmenter, "segment", lambda _doc: [_seg(1), _seg(2), _seg(3)])

    # A markdown that survives sanitization (non-empty clean_text), so we reach the
    # segmenter and exercise the cap rather than the sanitizer-empty short-circuit.
    md = (
        b"# Seccion A\n\n"
        b"Primera seccion con contenido suficiente para procesarse correctamente.\n\n"
        b"# Seccion B\n\n"
        b"Segunda seccion con contenido suficiente para procesarse correctamente.\n"
    )
    report = run_document(
        file_bytes=md,
        mime_type="text/markdown",
        language="es",
        corpus=["ai_act"],
        case_id="doc-cap-test",
    )

    assert report.document_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert report.segments == []
    assert (report.document_reason or "").startswith("too_many_segments:")
    assert report.n_segments_total == 0
    assert report.cost_eur_total == 0.0


def test_default_cap_is_generous(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression anchor: the default must comfortably clear legitimate long contracts.
    monkeypatch.delenv("REGULAITOR_MAX_SEGMENTS", raising=False)
    assert document_graph._max_segments() >= 300


def test_invalid_cap_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    default = document_graph._DEFAULT_MAX_SEGMENTS
    monkeypatch.setenv("REGULAITOR_MAX_SEGMENTS", "not-a-number")
    assert document_graph._max_segments() == default
    monkeypatch.setenv("REGULAITOR_MAX_SEGMENTS", "0")  # non-positive rejected
    assert document_graph._max_segments() == default
