"""Unit tests for tab_ask + tab_analyze helper functions.

Full Streamlit submit flow is covered by the smoke tests; here we only
exercise the pure helpers (case_id format, mime detection).
"""

from __future__ import annotations

import re

import pytest

from regulaitor.ui_streamlit import tab_analyze, tab_ask


def test_chat_case_id_format():
    cid = tab_ask._generate_case_id()
    assert re.match(r"^ch-\d{8}-[A-Za-z0-9xy]{8}$", cid), f"unexpected format: {cid!r}"


def test_chat_case_id_unique_across_calls():
    a = tab_ask._generate_case_id()
    b = tab_ask._generate_case_id()
    assert a != b, "case_id should be unique per call"


# ---------- tab_analyze ----------


def test_doc_case_id_format():
    cid = tab_analyze._generate_case_id()
    assert re.match(r"^doc-\d{8}-[A-Za-z0-9xy]{8}$", cid), f"unexpected format: {cid!r}"


def test_detect_mime_pdf_magic_bytes():
    assert tab_analyze._detect_mime(b"%PDF-1.4\n...", "policy.pdf") == "application/pdf"


def test_detect_mime_pdf_magic_overrides_extension():
    # Even with .md extension, PDF magic bytes win.
    assert tab_analyze._detect_mime(b"%PDF-1.4\n", "trick.md") == "application/pdf"


def test_detect_mime_markdown_via_extension_md():
    assert tab_analyze._detect_mime(b"# heading", "doc.md") == "text/markdown"


def test_detect_mime_markdown_via_extension_markdown():
    assert tab_analyze._detect_mime(b"# heading", "doc.markdown") == "text/markdown"


def test_detect_mime_unsupported_raises():
    with pytest.raises(ValueError, match="no soportado"):
        tab_analyze._detect_mime(b"PK\x03\x04...", "archive.zip")


def test_detect_mime_extension_case_insensitive():
    assert tab_analyze._detect_mime(b"# x", "DOC.MD") == "text/markdown"
