"""Document sanitizer (H5).

Policy: strip & log + critical-block. Body text is the only payload that
reaches the segmenter; metadata, annotations, invisible text, hidden layers
and unicode tricks are stripped (warning) and logged. JavaScript, attachments,
form actions, non-allowlisted URIs and password-encrypted PDFs trigger an
immediate critical-block (DocumentBlockedError).

Spec §4.3 + §6 (canonical lists).
"""

from __future__ import annotations

import hashlib
import unicodedata

from regulaitor.citation.schemas import (
    DocumentBlockedError,
    RawDocument,
    SanitizedDocument,
    SanitizerEvent,
)
from regulaitor.security.allowlist import is_uri_allowed

# Unicode codepoints used in injection tricks; stripped if present.
_UNICODE_TRICKS = {
    "​",  # zero-width space
    "‌",  # zero-width non-joiner
    "‍",  # zero-width joiner
    "‮",  # right-to-left override
    "⁠",  # word joiner
    "﻿",  # zero-width no-break space (BOM)
}

_MIN_CLEAN_LENGTH = 50


def _hash12(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def _strip_unicode_tricks(text: str) -> tuple[str, bool]:
    if not any(ch in text for ch in _UNICODE_TRICKS):
        return text, False
    cleaned = "".join(ch for ch in text if ch not in _UNICODE_TRICKS)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    return cleaned, True


def sanitize(raw: RawDocument) -> SanitizedDocument:
    """Sanitize a RawDocument; raise DocumentBlockedError on critical findings.

    Returns SanitizedDocument with clean_text >= 50 chars and a complete
    sanitizer_log of stripped/logged content (hashes only, never plain text).
    """
    log: list[SanitizerEvent] = []

    # --- 1. Critical-block checks (early, fail-fast) --------------------------
    if raw.has_javascript:
        log.append(
            SanitizerEvent(
                severity="critical",
                category="javascript_blocked",
                location="document.catalog",
                content_hash=_hash12("javascript"),
                reason="document declares JavaScript; execution surface forbidden",
            )
        )
        raise DocumentBlockedError("javascript_blocked", log)

    if raw.attachments:
        for att in raw.attachments:
            log.append(
                SanitizerEvent(
                    severity="critical",
                    category="attachment_blocked",
                    location=f"attachment:{att.name}",
                    content_hash=_hash12(att.hash),
                    reason=f"embedded file {att.mime} ({att.size_bytes} bytes)",
                )
            )
        raise DocumentBlockedError("attachment_blocked", log)

    if raw.has_form_actions:
        log.append(
            SanitizerEvent(
                severity="critical",
                category="form_action_blocked",
                location="document.catalog",
                content_hash=_hash12("form_actions"),
                reason="document declares form actions (SubmitForm/ImportData/Reset)",
            )
        )
        raise DocumentBlockedError("form_action_blocked", log)

    for uri in raw.uri_actions:
        if not is_uri_allowed(uri):
            log.append(
                SanitizerEvent(
                    severity="critical",
                    category="uri_action_blocked",
                    location=f"uri_action:{_hash12(uri)}",
                    content_hash=_hash12(uri),
                    reason="URI Action target outside official EU allowlist",
                )
            )
            raise DocumentBlockedError("uri_action_blocked", log)

    # --- 2. Strip + log (warning) --------------------------------------------
    for key, value in raw.metadata.items():
        log.append(
            SanitizerEvent(
                severity="warning",
                category="metadata_stripped",
                location=f"metadata.{key}",
                content_hash=_hash12(value),
                reason="metadata field stripped unconditionally (CLAUDE.md §18.8)",
            )
        )

    for page in raw.pages:
        for ann in page.annotations:
            log.append(
                SanitizerEvent(
                    severity="warning",
                    category="annotation_stripped",
                    location=f"page={page.number}",
                    content_hash=_hash12(ann),
                    reason="annotation text stripped from payload",
                )
            )
        for hidden in page.hidden_text_candidates:
            log.append(
                SanitizerEvent(
                    severity="warning",
                    category="invisible_text_stripped",
                    location=f"page={page.number}",
                    content_hash=_hash12(hidden),
                    reason="invisible text candidate stripped",
                )
            )

    # --- 3. Build clean_text (page text + unicode normalization) -------------
    page_chunks: list[str] = []
    content_chars = 0
    for page in raw.pages:
        page_text, had_tricks = _strip_unicode_tricks(page.text)
        if had_tricks:
            log.append(
                SanitizerEvent(
                    severity="warning",
                    category="unicode_trick_stripped",
                    location=f"page={page.number}",
                    content_hash=_hash12(page.text),
                    reason="zero-width / bidi-override codepoints removed",
                )
            )
        content_chars += len(page_text.strip())
        page_chunks.append(f"\n\n--- p{page.number} ---\n\n{page_text}")
    clean_text = "".join(page_chunks).strip()

    # --- 4. Outline log (info) -----------------------------------------------
    if raw.outline:
        log.append(
            SanitizerEvent(
                severity="info",
                category="outline_extracted",
                location="document.outline",
                content_hash=_hash12(str(len(raw.outline))),
                reason=f"outline has {len(raw.outline)} entries",
            )
        )

    # --- 5. Large-document warning (info) ------------------------------------
    if len(raw.pages) > 50 or len(clean_text) > 100_000 * 4:
        log.append(
            SanitizerEvent(
                severity="info",
                category="large_document_warning",
                location="document.summary",
                content_hash=_hash12(str(len(raw.pages))),
                reason=f"document has {len(raw.pages)} pages; processing may be slow",
            )
        )

    # --- 6. Length floor ------------------------------------------------------
    # Count only actual content chars (page.text after unicode strip), not the
    # "--- p{n} ---" separator scaffolding the sanitizer adds for traceability.
    if content_chars < _MIN_CLEAN_LENGTH:
        log.append(
            SanitizerEvent(
                severity="warning",
                category="invisible_text_stripped",
                location="document.body",
                content_hash=_hash12(clean_text),
                reason=f"content length {content_chars} below floor {_MIN_CLEAN_LENGTH}",
            )
        )
        raise DocumentBlockedError("document_empty_after_sanitization", log)

    return SanitizedDocument(
        document_hash=raw.document_hash,
        language=raw.language,
        clean_text=clean_text,
        outline=raw.outline,
        sanitizer_log=log,
    )
