"""Contract tests for MCP tool extract_document."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import RawDocument
from regulaitor.mcp_server import tools


def test_extract_document_markdown():
    md = b"# T\n\nText body.\n"
    result = tools.extract_document(file_bytes=md, mime_type="text/markdown")
    assert isinstance(result, RawDocument)
    assert result.mime_type == "text/markdown"


def test_extract_document_unsupported_mime_raises():
    with pytest.raises(ValueError):
        tools.extract_document(file_bytes=b"x", mime_type="application/exe")
