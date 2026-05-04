"""Parse EUR-Lex consolidated regulation PDFs into ParsedArticle.

Pragmatic H1 fallback when EUR-Lex CloudFront WAF blocks Formex/HTML access.
Calibrated against AI Act (32024R1689) and GDPR (02016R0679-20160504)
consolidated PDFs fetched manually in May 2026.

Design notes:
- Article header detection uses a strict line-anchored regex. Matches lines
  that are JUST `Article N` or `Artículo N` (no trailing dots/page numbers),
  which excludes most Table-of-Contents entries automatically.
- Cross-references inside body text (e.g. "...in accordance with Article 49(1)")
  do not match the strict regex because they don't sit on their own line.
- When the same article number appears twice as a header (e.g. once in body,
  once in an Annex back-reference), KEEP-FIRST resolves it to the body
  occurrence: the body always comes earlier in the document than annexes.
- Paragraph extraction inside an article body uses a "1." / "2." line-anchored
  regex. Articles without numbered paragraphs collapse to a single apartado="1".
"""

from __future__ import annotations

import re
from io import BytesIO

import pdfplumber

from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph

# Strict article-header regex: line is JUST "Article N" or "Artículo N".
# This deliberately rejects ToC lines like "Article 1 — Subject matter ........ 12".
_HDR_RE = re.compile(
    r"^\s*(?:Article|Art[íi]culo)\s+(\d+)\s*$",
    re.MULTILINE,
)

# Numbered paragraph at line start: "1.", "2.", etc. followed by whitespace.
_PARA_RE = re.compile(r"^\s*(\d+)\.\s+", re.MULTILINE)


class PdfParseError(Exception):
    """Raised when no recognisable article markers are found in the PDF."""


class PdfParser:
    """Parse PDF bytes into ParsedArticle list using regex over extracted text."""

    def parse(self, pdf_bytes: bytes) -> list[ParsedArticle]:
        text = self._extract_text(pdf_bytes)
        return self._parse_text(text)

    @staticmethod
    def _extract_text(pdf_bytes: bytes) -> str:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    def _parse_text(self, text: str) -> list[ParsedArticle]:
        """Pure-text path, separated from PDF I/O so tests can inject strings."""
        matches = list(_HDR_RE.finditer(text))
        if not matches:
            raise PdfParseError(
                "no recognisable article markers (expected '^Article N$' or '^Artículo N$')"
            )

        # Keep-first per article number (deduplicates back-references in annexes).
        first_match: dict[str, re.Match[str]] = {}
        for m in matches:
            num = m.group(1)
            if num not in first_match:
                first_match[num] = m

        ordered = sorted(first_match.values(), key=lambda m: m.start())
        out: list[ParsedArticle] = []
        for i, m in enumerate(ordered):
            body_start = m.end()
            body_end = ordered[i + 1].start() if i + 1 < len(ordered) else len(text)
            body = text[body_start:body_end].strip()
            articulo = m.group(1)

            lines = [line.strip() for line in body.splitlines() if line.strip()]
            title = lines[0] if lines else None
            article_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if not article_text:
                # Single-line article (rare; keep title as the article text).
                article_text = title or ""
                title = None
            paragraphs = self._extract_paragraphs(article_text)
            out.append(
                ParsedArticle(
                    articulo=articulo,
                    title=title,
                    text=article_text,
                    paragraphs=paragraphs,
                )
            )
        return out

    @staticmethod
    def _extract_paragraphs(text: str) -> list[ParsedParagraph]:
        marks = list(_PARA_RE.finditer(text))
        if not marks:
            return [ParsedParagraph(apartado="1", text=text)] if text.strip() else []
        out: list[ParsedParagraph] = []
        for i, m in enumerate(marks):
            start = m.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[start:end].strip()
            if body:
                out.append(ParsedParagraph(apartado=m.group(1), text=body))
        return out
