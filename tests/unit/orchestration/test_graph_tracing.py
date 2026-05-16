"""H11 — chat graph tracing regression: behaviour identical without keys,
metadata emitted with keys. Backend graph is mocked (no LLM)."""

from __future__ import annotations

import pytest

from regulaitor.orchestration import graph as g


def _fake_final_dict() -> dict:
    return {
        "case_id": "c1",
        "query": "test query",
        "corpus": "ai_act",
        "language": "es",
        "errors": [],
        "injection_blocked": False,
        "audited_answer": None,
    }


def test_run_without_keys_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)

    class _Compiled:
        def invoke(self, _initial: object) -> dict:
            return _fake_final_dict()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _Compiled())
    state = g.run(query="test query", corpus="ai_act", language="es", case_id="c1")
    assert state.case_id == "c1"
    assert state.corpus == "ai_act"


def test_run_emits_trace_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _TT:
        def set_root(self, **kw: object) -> None:
            captured.update(kw)

        def span(self, name: str, **kw: object) -> None:
            captured[f"span:{name}"] = kw

    import contextlib

    @contextlib.contextmanager
    def _fake_trace_turn(**_kw: object):
        yield _TT()

    monkeypatch.setattr(g, "trace_turn", _fake_trace_turn)

    class _Compiled:
        def invoke(self, _initial: object) -> dict:
            return _fake_final_dict()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _Compiled())
    g.run(query="test query", corpus="ai_act", language="es", case_id="c1")
    assert "verdict" in captured
    assert "latency_ms_total" in captured
    assert "query_sha256_12" in captured
    # Chat emits a root summary only — no per-span calls.
    assert not any(str(k).startswith("span:") for k in captured)
    # Redaction: only the sha256[:12] prefix leaves the process, never
    # the raw query (pin the primitive end-to-end, not just absence).
    from regulaitor.observability.langfuse_client import hash12

    assert captured["query_sha256_12"] == hash12("test query")
    assert "test query" not in repr(captured)


# ---------------------------------------------------------------------------
# Document-pipeline tracing tests (Task 5, H11)
# ---------------------------------------------------------------------------


def _stub_doc_pipeline(monkeypatch: pytest.MonkeyPatch, *, doc_hash: str) -> None:
    """Patch extractor/sanitizer/segmenter so run_document reaches a clean
    `return report` with no LLM/network: empty segments → PASS aggregate."""
    from regulaitor.citation.schemas import SanitizedDocument
    from regulaitor.orchestration import document_graph as dg

    fake_raw = type(
        "_FakeRaw",
        (),
        {"document_hash": doc_hash, "text": "stub", "mime_type": "text/plain"},
    )()
    fake_sanitized = SanitizedDocument(
        document_hash=doc_hash,
        language="es",
        clean_text="stub clean text for testing purposes only - padded to meet minimum length",
        outline=None,
        sanitizer_log=[],
    )
    monkeypatch.setattr(dg.extractor, "extract", lambda *_a, **_kw: fake_raw)
    monkeypatch.setattr(dg.sanitizer, "sanitize", lambda _raw: fake_sanitized)
    monkeypatch.setattr(dg.segmenter, "segment", lambda _san: [])


def test_run_document_emits_trace_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from regulaitor.citation.schemas import AuditVerdict
    from regulaitor.orchestration import document_graph as dg

    captured: dict = {}

    class _TT:
        def set_root(self, **kw: object) -> None:
            captured.update(kw)

        def span(self, name: str, **kw: object) -> None:
            captured[f"span:{name}"] = kw

    import contextlib

    @contextlib.contextmanager
    def _fake_trace_turn(**_kw: object):
        yield _TT()

    monkeypatch.setattr(dg, "trace_turn", _fake_trace_turn)
    _stub_doc_pipeline(monkeypatch, doc_hash="0" * 64)

    result = dg.run_document(
        file_bytes=b"%PDF-1.4 stub",
        mime_type="application/pdf",
        language="es",
        corpus=["ai_act"],
        case_id="d1",
    )

    # Trace wiring assertions
    assert "document_verdict" in captured
    assert captured["document_verdict"] == AuditVerdict.PASS.value  # no segments → PASS
    # ("0"*64)[:12] — slice of the all-zeros sha256 sentinel
    assert captured["document_sha256_12"] == ("0" * 64)[:12]
    assert captured["case_id"] == "d1"
    assert captured["language"] == "es"
    assert captured["corpus"] == "ai_act"
    assert captured["n_segments_total"] == 0
    assert captured["cost_eur_total"] == 0.0
    # Redaction: raw bytes and document text must never appear in trace metadata
    assert "%PDF" not in repr(captured)
    assert "stub" not in repr(captured)
    # No per-span calls for the document pipeline (root summary only)
    assert not any(str(k).startswith("span:") for k in captured)
    # Sanity: run_document returned the correct report
    assert result.case_id == "d1"
    assert result.document_verdict == AuditVerdict.PASS


def test_run_document_without_keys_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression-zero: without LANGFUSE_* env vars the document pipeline
    returns an unchanged DocumentReport and no tracing overhead is added."""
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)

    from regulaitor.citation.schemas import AuditVerdict
    from regulaitor.orchestration import document_graph as dg

    _stub_doc_pipeline(monkeypatch, doc_hash="a" * 64)

    result = dg.run_document(
        file_bytes=b"stub bytes",
        mime_type="application/pdf",
        language="es",
        corpus=["rgpd"],
        case_id="d2",
    )

    assert result.case_id == "d2"
    assert result.corpus == ["rgpd"]
    assert result.document_verdict == AuditVerdict.PASS
    assert result.document_hash == "a" * 64
