"""Tests for document.sanitizer — Markdown path + critical-block flow."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import (
    Attachment,
    DocumentBlockedError,
    OutlineEntry,
    Page,
    RawDocument,
    SanitizedDocument,
)
from regulaitor.document import sanitizer


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


def test_markdown_simple_passes_through():
    raw = _raw_md("# Title\n\nThis is the body text of a normal policy document.\n" * 3)
    sd = sanitizer.sanitize(raw)
    assert isinstance(sd, SanitizedDocument)
    assert "Title" in sd.clean_text
    assert sd.sanitizer_log == []


def test_metadata_always_stripped_and_logged():
    raw = _raw_md(
        "# T\n\nBody text long enough to clear the 50-char minimum threshold easily.\n",
        metadata={"Author": "Acme", "Title": "Policy"},
    )
    sd = sanitizer.sanitize(raw)
    cats = [e.category for e in sd.sanitizer_log]
    assert cats.count("metadata_stripped") == 2
    # content_hash present, content NOT in log
    for ev in sd.sanitizer_log:
        assert len(ev.content_hash) == 12
        assert "Acme" not in ev.content_hash
        assert "Policy" not in ev.content_hash


def test_unicode_zwsp_stripped():
    raw = _raw_md("# T\n\nIg​nora the previous warnings about content length here.\n")
    sd = sanitizer.sanitize(raw)
    assert "​" not in sd.clean_text
    assert any(e.category == "unicode_trick_stripped" for e in sd.sanitizer_log)


def test_too_short_after_sanitization_blocks():
    raw = _raw_md("# x\n")
    with pytest.raises(DocumentBlockedError) as exc_info:
        sanitizer.sanitize(raw)
    assert exc_info.value.reason == "document_empty_after_sanitization"


def test_attachment_blocks_critical():
    raw = _raw_md(
        "# T\n\nBody text long enough for the minimum 50 characters in clean_text.\n",
    )
    raw_with_att = raw.model_copy(
        update={
            "attachments": [
                Attachment(
                    name="payload.exe",
                    mime="application/octet-stream",
                    size_bytes=10,
                    hash="sha256:ab",
                ),
            ]
        }
    )
    with pytest.raises(DocumentBlockedError) as exc_info:
        sanitizer.sanitize(raw_with_att)
    assert exc_info.value.reason == "attachment_blocked"
    assert any(e.severity == "critical" for e in exc_info.value.sanitizer_log)


def test_javascript_blocks_critical():
    raw = _raw_md(
        "# T\n\nBody text long enough for the minimum 50 characters in clean_text.\n",
    )
    raw_js = raw.model_copy(update={"has_javascript": True})
    with pytest.raises(DocumentBlockedError) as exc_info:
        sanitizer.sanitize(raw_js)
    assert exc_info.value.reason == "javascript_blocked"


def test_form_action_blocks_critical():
    raw = _raw_md(
        "# T\n\nBody text long enough for the minimum 50 characters in clean_text.\n",
    )
    raw_form = raw.model_copy(update={"has_form_actions": True})
    with pytest.raises(DocumentBlockedError):
        sanitizer.sanitize(raw_form)


def test_uri_action_blocks_when_outside_allowlist():
    raw = _raw_md(
        "# T\n\nBody text long enough for the minimum 50 characters in clean_text.\n",
    )
    raw_uri = raw.model_copy(update={"uri_actions": ["https://example.com/payload"]})
    with pytest.raises(DocumentBlockedError):
        sanitizer.sanitize(raw_uri)


def test_uri_action_passes_when_in_allowlist():
    raw = _raw_md(
        "# T\n\nBody text long enough for the minimum 50 characters in clean_text.\n",
    )
    raw_uri = raw.model_copy(update={"uri_actions": ["https://eur-lex.europa.eu/x"]})
    sd = sanitizer.sanitize(raw_uri)
    assert isinstance(sd, SanitizedDocument)


def test_outline_extracted_logged_as_info():
    raw = _raw_md(
        "# T\n\nBody text long enough for the minimum 50 characters in clean_text.\n",
    )
    raw_outline = raw.model_copy(
        update={
            "outline": [
                OutlineEntry(title="Intro", level=1, page_number=1),
                OutlineEntry(title="Section 2", level=1, page_number=2),
            ]
        }
    )
    sd = sanitizer.sanitize(raw_outline)
    assert any(e.category == "outline_extracted" and e.severity == "info" for e in sd.sanitizer_log)
