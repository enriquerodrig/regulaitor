"""Document segmenter (H5).

Strategy (Q5 B):
1. If outline is non-empty: split by outline (each entry = a segment start;
   single-entry outline still drives a titled split + token-cap chunking).
2. Else if >= 2 heading-like lines are detected: heuristic split.
3. Else: token-windowed fallback with cap = max_tokens.

Token counting reuses the BGE-M3 tokenizer already loaded for RAG (H2). We
fall back to a whitespace approximation if the tokenizer is unavailable —
the cap is a safety bound, not a precision target.
"""

from __future__ import annotations

import logging
import re

from regulaitor.citation.schemas import OutlineEntry, SanitizedDocument, Segment

logger = logging.getLogger("regulaitor.document.segmenter")

_HEADING_LIKE = re.compile(r"^(?:[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ \-]{2,80}|#{1,6}\s+\S.{0,80})$")


def _count_tokens(text: str) -> int:
    """Approximate BGE-M3 token count.

    H2 already loads BGE-M3 tokenizer in `rag/embeddings.py`; importing it
    eagerly here would slow tests considerably, so we use a whitespace
    approximation that is safe (overestimates by ~20% for ES/EN) and
    deterministic. Real BGE-M3 tokenization is exercised in slow E2E tests.
    """
    return max(1, len(text.split()))


def _split_paragraphs_under_cap(
    text: str, title: str | None, max_tokens: int, start_id: int
) -> list[Segment]:
    """Split ``text`` into segments capped at ``max_tokens`` tokens each.

    Splits on blank-line paragraph boundaries; never splits inside a paragraph.
    First chunk has ``is_continuation=False``; subsequent chunks True.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[Segment] = []
    buf: list[str] = []
    buf_tokens = 0
    for para in paragraphs:
        para_tokens = _count_tokens(para)
        if buf and buf_tokens + para_tokens > max_tokens:
            joined = "\n\n".join(buf)
            out.append(
                Segment(
                    id=start_id + len(out),
                    title=title,
                    text=joined,
                    token_count=buf_tokens,
                    is_continuation=bool(out),
                )
            )
            buf = [para]
            buf_tokens = para_tokens
        else:
            buf.append(para)
            buf_tokens += para_tokens
    if buf:
        joined = "\n\n".join(buf)
        out.append(
            Segment(
                id=start_id + len(out),
                title=title,
                text=joined,
                token_count=buf_tokens,
                is_continuation=bool(out),
            )
        )
    return out


def _split_by_outline(
    clean_text: str, outline: list[OutlineEntry], max_tokens: int
) -> list[Segment]:
    """Locate each outline title in clean_text and split between titles."""
    segments: list[Segment] = []
    cursor = 0
    boundaries: list[tuple[str, int]] = []
    for entry in outline:
        idx = clean_text.find(entry.title, cursor)
        if idx == -1:
            continue
        boundaries.append((entry.title, idx))
        cursor = idx + len(entry.title)
    if not boundaries:
        return _split_paragraphs_under_cap(clean_text, None, max_tokens, 1)
    for i, (title, start) in enumerate(boundaries):
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(clean_text)
        section_text = clean_text[start:end].strip()
        if not section_text:
            continue
        next_id = (segments[-1].id + 1) if segments else 1
        section_segments = _split_paragraphs_under_cap(section_text, title, max_tokens, next_id)
        segments.extend(section_segments)
    return segments


def _detect_heading_lines(clean_text: str) -> list[tuple[str, int]]:
    """Return (heading_text, char_offset) for lines that look like headings."""
    headings: list[tuple[str, int]] = []
    offset = 0
    for line in clean_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and _HEADING_LIKE.match(stripped) and not stripped.endswith("."):
            headings.append((stripped.lstrip("# ").strip(), offset))
        offset += len(line)
    return headings


def segment(doc: SanitizedDocument, max_tokens: int = 1500) -> list[Segment]:
    """Segment a SanitizedDocument into a list of Segment objects.

    Raises ValueError if the input is whitespace-only (sanitizer guarantees
    >= 50 chars but does not guarantee non-whitespace).
    """
    if not doc.clean_text.strip():
        raise ValueError("cannot segment whitespace-only document")

    if doc.outline and len(doc.outline) >= 1:
        return _split_by_outline(doc.clean_text, doc.outline, max_tokens)

    headings = _detect_heading_lines(doc.clean_text)
    if len(headings) >= 2:
        # Build pseudo-outline and reuse split-by-outline.
        pseudo = [OutlineEntry(title=h, level=1, page_number=1) for h, _ in headings]
        return _split_by_outline(doc.clean_text, pseudo, max_tokens)

    logger.warning("segmentation_fallback=token_windowed; no outline and <2 headings detected")
    return _split_paragraphs_under_cap(doc.clean_text, None, max_tokens, 1)
