"""Tests for document.extractor (Markdown path first; PDF added later)."""

from __future__ import annotations

import hashlib
import io

import pikepdf
import pytest
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

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


# ---------- PDF path ----------


def _make_pdf(text_per_page: list[str], metadata: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    if metadata:
        if "Author" in metadata:
            c.setAuthor(metadata["Author"])
        if "Title" in metadata:
            c.setTitle(metadata["Title"])
    for page_text in text_per_page:
        c.setFont("Helvetica", 12)
        c.drawString(72, 720, page_text)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_pdf_basic_extraction():
    pdf = _make_pdf(["Hello world page 1", "Page 2 content"])
    raw = extractor.extract(pdf, mime_type="application/pdf")
    assert raw.mime_type == "application/pdf"
    assert len(raw.pages) == 2
    assert "Hello world" in raw.pages[0].text
    assert "Page 2" in raw.pages[1].text


def test_pdf_metadata_captured():
    pdf = _make_pdf(["x"], metadata={"Author": "Acme Inc", "Title": "Policy"})
    raw = extractor.extract(pdf, mime_type="application/pdf")
    assert raw.metadata.get("Author") == "Acme Inc"
    assert raw.metadata.get("Title") == "Policy"


def test_pdf_magic_bytes_mismatch_raises():
    with pytest.raises(ValueError, match="magic bytes"):
        extractor.extract(b"NOT A PDF", mime_type="application/pdf")


def test_pdf_corrupted_raises():
    # Magic bytes ok but body garbage.
    bad = b"%PDF-1.4\n" + b"\x00" * 100
    with pytest.raises(extractor.ExtractionError):
        extractor.extract(bad, mime_type="application/pdf")


def test_pdf_no_javascript_no_forms_no_uris_in_simple_pdf():
    pdf = _make_pdf(["Plain content"])
    raw = extractor.extract(pdf, mime_type="application/pdf")
    assert raw.has_javascript is False
    assert raw.has_form_actions is False
    assert raw.uri_actions == []


def test_pdf_likely_scanned_when_no_text():
    # A PDF with no text drawn → all pages likely_scanned.
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.showPage()
    c.save()
    raw = extractor.extract(buf.getvalue(), mime_type="application/pdf")
    assert raw.pages[0].likely_scanned is True


# ---------- PDF deep-scan via pikepdf ----------


def _pdf_with_javascript() -> bytes:
    """Construct a minimal PDF that declares document-level JavaScript."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    js_action = pikepdf.Dictionary(
        S=pikepdf.Name.JavaScript,
        JS=pikepdf.String("app.alert('hi')"),
    )
    names_tree = pikepdf.Dictionary(
        Names=pikepdf.Array([pikepdf.String("attack"), js_action]),
    )
    pdf.Root[pikepdf.Name.Names] = pikepdf.Dictionary(JavaScript=names_tree)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _pdf_with_external_uri(domain: str = "attacker.example") -> bytes:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page()
    link_action = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name.Link,
        Rect=pikepdf.Array([0, 0, 100, 100]),
        A=pikepdf.Dictionary(
            S=pikepdf.Name.URI,
            URI=pikepdf.String(f"https://{domain}/payload"),
        ),
    )
    page.Annots = pikepdf.Array([link_action])
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_pdf_deep_scan_detects_javascript():
    pdf_bytes = _pdf_with_javascript()
    raw = extractor.extract(pdf_bytes, mime_type="application/pdf")
    assert raw.has_javascript is True


def test_pdf_deep_scan_detects_external_uri():
    pdf_bytes = _pdf_with_external_uri()
    raw = extractor.extract(pdf_bytes, mime_type="application/pdf")
    assert any("attacker.example" in u for u in raw.uri_actions)


def test_pdf_deep_scan_clean_pdf_has_no_flags():
    pdf = _make_pdf(["Plain content of a normal document."])
    raw = extractor.extract(pdf, mime_type="application/pdf")
    assert raw.has_javascript is False
    assert raw.has_form_actions is False
    assert raw.uri_actions == []
