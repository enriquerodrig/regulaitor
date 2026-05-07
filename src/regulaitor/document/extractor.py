"""Document extraction (PDF + Markdown). H5 — pre-sanitization stage.

PDF path uses pypdfium2 (no OCR per Q2). Markdown path uses markdown-it-py
to walk the token stream and recover headings as outline entries.

See spec docs/superpowers/specs/2026-05-06-h5-document-pipeline-design.md §4.2.
"""

from __future__ import annotations

import hashlib
import re

from markdown_it import MarkdownIt

from regulaitor.citation.schemas import (
    OutlineEntry,
    Page,
    RawDocument,
)
from regulaitor.corpus.schemas import Language

_SPANISH_CHARS = re.compile(r"[áéíóúñ¿¡ÁÉÍÓÚÑ]")


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


def _extract_pdf(file_bytes: bytes) -> RawDocument:
    """Stub — implemented in Task 5."""
    raise NotImplementedError("PDF extraction implemented in Task 5")
