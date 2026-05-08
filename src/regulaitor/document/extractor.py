"""Document extraction (PDF + Markdown). H5 — pre-sanitization stage.

PDF path uses pypdfium2 (no OCR per Q2). Markdown path uses markdown-it-py
to walk the token stream and recover headings as outline entries.

See spec docs/superpowers/specs/2026-05-06-h5-document-pipeline-design.md §4.2.
"""

from __future__ import annotations

import hashlib
import io
import re
from typing import Any

import pikepdf
import pypdfium2 as pdfium
from markdown_it import MarkdownIt

from regulaitor.citation.schemas import (
    Attachment,
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


def _deep_scan_pdf_bytes(
    file_bytes: bytes,
) -> tuple[bool, bool, list[str], list[Attachment]]:
    """Walk the PDF catalog with pikepdf for JS / forms / URIs / attachments.

    pypdfium2's high-level API does not enumerate these structures from
    Python; pikepdf owns a full QPDF binding and can. We accept the small
    dependency overhead in exchange for accurate critical-block detection.

    Returns (has_js, has_form_actions, uri_actions, attachments).

    Defensive contract: never raises. If pikepdf cannot open or traverse,
    returns conservative defaults (False/empty). The sanitizer + Auditor
    downstream provide deeper safety nets.
    """
    has_js = False
    has_form = False
    uri_actions: list[str] = []
    attachments: list[Attachment] = []

    try:
        with pikepdf.open(io.BytesIO(file_bytes)) as pdf:
            root = pdf.Root

            # JavaScript via /Names /JavaScript tree
            try:
                names = root.get(pikepdf.Name.Names)
                if names is not None and pikepdf.Name.JavaScript in names:
                    has_js = True
            except Exception:
                pass

            # Form actions: /AcroForm with /Fields and an action dictionary
            try:
                acro = root.get(pikepdf.Name.AcroForm)
                if acro is not None and pikepdf.Name.Fields in acro:
                    has_form = bool(acro[pikepdf.Name.Fields])
            except Exception:
                pass

            # URI actions in page annotations
            try:
                for page in pdf.pages:
                    annots = page.get(pikepdf.Name.Annots)
                    if annots is None:
                        continue
                    for annot in annots:  # type: ignore[attr-defined]
                        try:
                            action = annot.get(pikepdf.Name.A)
                            if action is None:
                                continue
                            if action.get(pikepdf.Name.S) == pikepdf.Name.URI:
                                uri = action.get(pikepdf.Name.URI)
                                if uri is not None:
                                    uri_actions.append(str(uri))
                        except Exception:
                            continue
            except Exception:
                pass

            # Attachments via /Names /EmbeddedFiles
            try:
                names = root.get(pikepdf.Name.Names)
                if names is not None and pikepdf.Name.EmbeddedFiles in names:
                    embedded = names[pikepdf.Name.EmbeddedFiles]
                    name_array = embedded.get(pikepdf.Name.Names)
                    if name_array is not None:
                        for i in range(0, len(name_array), 2):
                            try:
                                spec = name_array[i + 1]
                                ef = spec.get(pikepdf.Name.EF)
                                if ef is None:
                                    continue
                                stream = ef.get(pikepdf.Name.F)
                                if stream is None:
                                    continue
                                data = (
                                    bytes(stream.read_bytes())
                                    if hasattr(stream, "read_bytes")
                                    else b""
                                )
                                attachments.append(
                                    Attachment(
                                        name=str(
                                            spec.get(pikepdf.Name.UF)
                                            or spec.get(pikepdf.Name.F)
                                            or "unknown"
                                        ),
                                        mime=str(
                                            stream.get(pikepdf.Name.Subtype)
                                            or "application/octet-stream"
                                        ),
                                        size_bytes=len(data),
                                        hash="sha256:" + hashlib.sha256(data).hexdigest(),
                                    )
                                )
                            except Exception:
                                continue
            except Exception:
                pass
    except (pikepdf.PdfError, pikepdf.PasswordError):
        pass
    except Exception:
        # Last-resort defensive catch: any other pikepdf surface change should
        # degrade to conservative defaults rather than abort extraction.
        pass

    return has_js, has_form, uri_actions, attachments


def _extract_pdf(file_bytes: bytes) -> RawDocument:
    _validate_pdf_magic(file_bytes)
    try:
        pdf = pdfium.PdfDocument(file_bytes)
    except pdfium.PdfiumError as e:
        raise ExtractionError(f"pypdfium2 failed to load PDF: {e}") from e

    metadata = _read_pdf_metadata(pdf)
    pages = _read_pdf_pages(pdf)
    outline = _read_pdf_outline(pdf)
    has_js, has_form, uri_actions, attachments = _deep_scan_pdf_bytes(file_bytes)

    full_text = "\n".join(p.text for p in pages)
    return RawDocument(
        document_hash=_hash_bytes(file_bytes),
        mime_type="application/pdf",
        language=_detect_language(full_text),
        pages=pages,
        metadata=metadata,
        attachments=attachments,
        outline=outline if outline else None,
        has_javascript=has_js,
        has_form_actions=has_form,
        uri_actions=uri_actions,
    )
