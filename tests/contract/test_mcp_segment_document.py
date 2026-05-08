"""Contract tests for MCP tool segment_document."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import Segment
from regulaitor.mcp_server import tools


def test_segment_document_returns_segments():
    text = (
        "# Sec A\n\nContenido suficiente de la primera seccion para procesarse.\n\n"
        "# Sec B\n\nContenido suficiente de la segunda seccion para procesarse.\n"
    )
    segs = tools.segment_document(text=text, max_tokens=1500)
    assert isinstance(segs, list)
    assert len(segs) >= 1
    assert all(isinstance(s, Segment) for s in segs)


def test_segment_document_empty_text_raises():
    with pytest.raises(ValueError):
        tools.segment_document(text="    ", max_tokens=1500)
