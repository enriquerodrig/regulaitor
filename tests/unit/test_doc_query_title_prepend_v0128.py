"""v0.1.28 T4-bis (Option B) — pin tests for title-prepended retrieval query.

Hypothesis: doc segments have descriptive body text ("Nuestro sistema puntúa
candidatos sin supervisión") that BGE-M3 embeddings rarely match against
corpus obligation-article text ("Los proveedores establecerán supervisión
efectiva..."). Section titles ("Supervisión Humana", "Gestión de Riesgos")
bridge that gap if segmenter v0.1.14 detected them.

Pins:
- When seg.title is non-None: retriever query = f"{title}\n{text}"
- When seg.title is None: retriever query = seg.text (fallback to body-only)
- Chat-mode retriever calls unchanged (this only fires inside doc_graph)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from regulaitor.citation.schemas import Segment


def test_segment_with_title_prepends_to_query(monkeypatch):
    """Segment with non-None title: retriever query = f'{title}\\n{text}'."""
    from regulaitor.orchestration import document_graph

    seg = Segment(
        id=1,
        title="Supervisión Humana",
        text="Nuestro sistema puntúa candidatos sin revisión.",
        token_count=10,
        is_continuation=False,
    )
    fake_retriever = MagicMock()
    fake_retriever.retrieve = MagicMock(return_value=MagicMock(chunks=[]))
    fake_analyst = MagicMock()
    fake_analyst.analyze = MagicMock(return_value=MagicMock())
    fake_auditor = MagicMock()
    fake_auditor.audit = MagicMock(return_value=MagicMock())

    monkeypatch.setattr(document_graph, "_retriever", lambda: fake_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: fake_analyst)
    monkeypatch.setattr(document_graph, "_auditor", lambda: fake_auditor)
    monkeypatch.setattr(document_graph.injection, "is_injection", lambda *a, **k: (False, None))

    # SegmentResult Pydantic validation will fail because fake_auditor returns
    # a MagicMock instead of a real AuditedAnswer; we don't care — we only
    # need to verify that retriever.retrieve was called with the right query
    # BEFORE the SegmentResult construction. Suppress the ValidationError.
    with patch.object(document_graph, "SegmentResult", MagicMock()):
        document_graph._process_segment(seg, "ai_act", "es")

    args, kwargs = fake_retriever.retrieve.call_args
    query_arg = args[0] if args else kwargs.get("query")
    # The full prepended query should contain BOTH the title and the body.
    assert "Supervisión Humana" in query_arg
    assert "Nuestro sistema puntúa candidatos sin revisión." in query_arg
    # And the title must come BEFORE the body text.
    assert query_arg.index("Supervisión Humana") < query_arg.index("Nuestro sistema")


def test_segment_without_title_uses_body_only(monkeypatch):
    """Segment with None title: retriever query = seg.text (no prepend)."""
    from regulaitor.orchestration import document_graph

    seg = Segment(
        id=1,
        title=None,
        text="Body without any title.",
        token_count=5,
        is_continuation=False,
    )
    fake_retriever = MagicMock()
    fake_retriever.retrieve = MagicMock(return_value=MagicMock(chunks=[]))
    fake_analyst = MagicMock()
    fake_analyst.analyze = MagicMock(return_value=MagicMock())
    fake_auditor = MagicMock()
    fake_auditor.audit = MagicMock(return_value=MagicMock())

    monkeypatch.setattr(document_graph, "_retriever", lambda: fake_retriever)
    monkeypatch.setattr(document_graph, "_analyst_doc", lambda: fake_analyst)
    monkeypatch.setattr(document_graph, "_auditor", lambda: fake_auditor)
    monkeypatch.setattr(document_graph.injection, "is_injection", lambda *a, **k: (False, None))

    # SegmentResult Pydantic validation will fail because fake_auditor returns
    # a MagicMock instead of a real AuditedAnswer; we don't care — we only
    # need to verify that retriever.retrieve was called with the right query
    # BEFORE the SegmentResult construction. Suppress the ValidationError.
    with patch.object(document_graph, "SegmentResult", MagicMock()):
        document_graph._process_segment(seg, "ai_act", "es")

    args, kwargs = fake_retriever.retrieve.call_args
    query_arg = args[0] if args else kwargs.get("query")
    # No title to prepend; query is just the body text (no leading newlines).
    assert query_arg == "Body without any title."
