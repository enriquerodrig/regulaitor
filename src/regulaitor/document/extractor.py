"""Document extraction (PDF + Markdown). H5 — pre-sanitization stage.

PDF path uses pypdfium2 (no OCR per Q2). Markdown path uses markdown-it-py
to walk the token stream and recover headings as outline entries.

See spec docs/superpowers/specs/2026-05-06-h5-document-pipeline-design.md §4.2.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import pypdfium2 as pdfium
from markdown_it import MarkdownIt

from regulaitor.citation.schemas import (
    OutlineEntry,
    Page,
    RawDocument,
)
from regulaitor.corpus.schemas import Language

_SPANISH_CHARS = re.compile(r"[áéíóúñ¿¡ÁÉÍÓÚÑ]")
_PDF_MAGIC = b"%PDF-"


class ExtractionError(Exception):
    """Raised when extraction fails for a structurally invalid document."""


def _detect_language(text: str) -> Language:
    """Lightweight heuristic: any ES-only character → es, else en.

    Real systems would call a language detector. Documents in our target
    corpus are always ES or EN; this binary heuristic is intentionally simple
    and deterministic for tests.
    """
    return "es" if _SPANISH_CHARS.search(text) else "en"


def _hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _extract_markdown(file_bytes: bytes) -> RawDocument:
    text = file_bytes.decode("utf-8", errors="replace")
    md = MarkdownIt("commonmark")
    tokens = md.parse(text)

    outline: list[OutlineEntry] = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            level = int(tok.tag[1])  # "h1" -> 1
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            title = (inline.content if inline is not None else "").strip()
            if title:
                outline.append(OutlineEntry(title=title, level=level, page_number=1))

    page = Page(
        number=1,
        text=text,
        fonts=[],
        annotations=[],
        hidden_text_candidates=[],
        likely_scanned=False,
    )
    return RawDocument(
        document_hash=_hash_bytes(file_bytes),
        mime_type="text/markdown",
        language=_detect_language(text),
        pages=[page],
        metadata={},
        attachments=[],
        outline=outline if outline else None,
        has_javascript=False,
        has_form_actions=False,
        uri_actions=[],
    )


def extract(file_bytes: bytes, mime_type: str) -> RawDocument:
    """Convert raw bytes into a RawDocument.

    Supported mime types: 'application/pdf', 'text/markdown'.
    Other types raise ValueError (no fallback inference).
    """
    if mime_type == "text/markdown":
        return _extract_markdown(file_bytes)
    if mime_type == "application/pdf":
        return _extract_pdf(file_bytes)
    raise ValueError(f"unsupported mime_type: {mime_type!r}")


def _validate_pdf_magic(file_bytes: bytes) -> None:
    if not file_bytes.startswith(_PDF_MAGIC):
        raise ValueError("magic bytes do not match declared mime_type=application/pdf")


def _read_pdf_metadata(pdf: Any) -> dict[str, str]:
    md: dict[str, str] = {}
    try:
        for key in ("Title", "Author", "Subject", "Keywords", "Creator", "Producer"):
            value = pdf.get_metadata_value(key)
            if value:
                md[key] = str(value)
    except Exception:
        # Conservative: if metadata API surface differs across pypdfium2 versions,
        # we degrade gracefully — sanitizer treats missing metadata as "none".
        pass
    return md


def _read_pdf_pages(pdf: Any) -> list[Page]:
    pages: list[Page] = []
    for i in range(len(pdf)):
        page = pdf[i]
        try:
            textpage = page.get_textpage()
            text = textpage.get_text_bounded()
        except Exception:
            text = ""
        likely_scanned = len(text.strip()) < 10
        pages.append(
            Page(
                number=i + 1,
                text=text,
                fonts=[],
                annotations=[],
                hidden_text_candidates=[],
                likely_scanned=likely_scanned,
            )
        )
    return pages


def _read_pdf_outline(pdf: Any) -> list[OutlineEntry]:
    out: list[OutlineEntry] = []
    try:
        for entry in pdf.get_toc():
            page_number = int(entry.page_index) + 1 if entry.page_index is not None else 1
            out.append(
                OutlineEntry(
                    title=str(entry.title),
                    level=int(entry.level) + 1,
                    page_number=page_number,
                )
            )
    except Exception:
        # If pypdfium2 surface differs / outline is malformed, skip.
        pass
    return out


def _extract_pdf(file_bytes: bytes) -> RawDocument:
    _validate_pdf_magic(file_bytes)
    try:
        pdf = pdfium.PdfDocument(file_bytes)
    except pdfium.PdfiumError as e:
        raise ExtractionError(f"pypdfium2 failed to load PDF: {e}") from e

    metadata = _read_pdf_metadata(pdf)
    pages = _read_pdf_pages(pdf)
    outline = _read_pdf_outline(pdf)

    full_text = "\n".join(p.text for p in pages)
    return RawDocument(
        document_hash=_hash_bytes(file_bytes),
        mime_type="application/pdf",
        language=_detect_language(full_text),
        pages=pages,
        metadata=metadata,
        attachments=[],
        outline=outline if outline else None,
        has_javascript=False,
        has_form_actions=False,
        uri_actions=[],
    )
