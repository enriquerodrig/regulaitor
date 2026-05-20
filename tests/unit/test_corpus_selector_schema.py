"""H15.1 — CorpusSelector type + Context.resolved_normas schema tests."""

# tests/unit/test_corpus_selector_schema.py
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import Context


def test_context_accepts_explicit_corpus_with_empty_resolved_normas() -> None:
    ctx = Context(
        query="q",
        corpus="gdpr",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="m",
        resolved_normas=[],
    )
    assert ctx.corpus == "gdpr"
    assert ctx.resolved_normas == []


def test_context_accepts_auto_and_multi_resolved_normas() -> None:
    ctx = Context(
        query="q",
        corpus="auto",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="m",
        resolved_normas=["nis2", "dora"],
    )
    assert ctx.corpus == "auto"
    assert ctx.resolved_normas == ["nis2", "dora"]


def test_context_rejects_unknown_corpus() -> None:
    with pytest.raises(ValidationError):
        Context(
            query="q",
            corpus="bogus",
            language="es",
            chunks=[],
            retrieved_at=datetime.now(tz=UTC),
            embedding_model="m",
            resolved_normas=[],
        )


def test_context_backward_compat_no_resolved_normas_kwarg() -> None:
    """Existing callers that omit resolved_normas must still construct cleanly."""
    ctx = Context(
        query="q",
        corpus="ai_act",
        language="en",
        chunks=[],
        retrieved_at=datetime.now(tz=UTC),
        embedding_model="m",
    )
    assert ctx.resolved_normas == []
