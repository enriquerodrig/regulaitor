"""Tests for document.extractor (Markdown path first; PDF added later)."""

from __future__ import annotations

import hashlib

import pytest

from regulaitor.citation.schemas import RawDocument
from regulaitor.document import extractor


def _md(text: str) -> bytes:
    return text.encode("utf-8")


def test_markdown_basic_extraction():
    md = _md("# Title\n\nFirst paragraph.\n\n## Subtitle\n\nSecond paragraph.\n")
    raw = extractor.extract(md, mime_type="text/markdown")
    assert isinstance(raw, RawDocument)
    assert raw.mime_type == "text/markdown"
    assert raw.has_javascript is False
    assert raw.has_form_actions is False
    assert raw.uri_actions == []
    assert raw.attachments == []
    assert len(raw.pages) == 1
    assert "First paragraph" in raw.pages[0].text
    assert "Second paragraph" in raw.pages[0].text


def test_markdown_outline_from_headings():
    md = _md("# H1\n\np\n\n## H2\n\np\n\n### H3\n\np\n")
    raw = extractor.extract(md, mime_type="text/markdown")
    assert raw.outline is not None
    titles = [e.title for e in raw.outline]
    levels = [e.level for e in raw.outline]
    assert titles == ["H1", "H2", "H3"]
    assert levels == [1, 2, 3]


def test_markdown_no_headings_outline_none():
    md = _md("Plain text without any heading.\n")
    raw = extractor.extract(md, mime_type="text/markdown")
    assert raw.outline is None


def test_unsupported_mime_type_raises():
    with pytest.raises(ValueError, match="unsupported mime_type"):
        extractor.extract(b"x", mime_type="application/exe")


def test_document_hash_is_sha256_of_input():
    md = _md("# t\n")
    raw = extractor.extract(md, mime_type="text/markdown")
    expected = "sha256:" + hashlib.sha256(md).hexdigest()
    assert raw.document_hash == expected


def test_language_default_es_when_unspecified():
    md = _md("# Política\n\nTexto.\n")
    raw = extractor.extract(md, mime_type="text/markdown")
    # Default heuristic: ES if Spanish-typical chars detected, else EN.
    assert raw.language == "es"


def test_language_en_when_english_only():
    md = _md("# Title\n\nThis document is in English only.\n")
    raw = extractor.extract(md, mime_type="text/markdown")
    assert raw.language == "en"
