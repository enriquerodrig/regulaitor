"""Best-effort HTML fallback parser for EUR-Lex pages.

Used only when Formex 4 isn't available for a given consolidated version.
Brittle by design — EUR-Lex template changes will require updates here, not
in the upstream pipeline. Document any update in docs/technical_decisions_log.md.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from regulaitor.corpus.formex_parser import ParsedArticle, ParsedParagraph

_NUM_RE = re.compile(r"art[íi]culo\s+(\d+)", re.IGNORECASE)


class HtmlParseError(Exception):
    """Raised when no recognisable article markers are found in the HTML."""


class HtmlParser:
    """Parse EUR-Lex HTML by extracting div blocks with id matching ^art_\\d+$.

    Supports two class vocabularies: the pre-2024 EUR-Lex template
    (``sti-art`` / ``normal``) and the 2024+ Official Journal template
    (``oj-sti-art`` / ``oj-normal``, introduced with the new OJ layout —
    Fase 3, see docs/technical_decisions_log.md). The article designation
    (``oj-ti-art``/``ti-art``) is intentionally NOT part of the body — the
    article number comes from the ``div#art_N`` id.
    """

    # CSS selectors covering both the legacy and the 2024+ OJ class names.
    _TITLE_SEL = "p.sti-art, p.oj-sti-art"
    _BODY_SEL = "p.normal, p.oj-normal"
    # The OJ template occasionally leaks the article designation into the subtitle
    # (e.g. EN "Article Specific information..."); drop a leading designation token
    # when followed by a word (NOT a number — a real "Artículo 5" designation, if
    # it ever appeared here, must be preserved).
    _TITLE_DESIGNATION = re.compile(r"^(?:Art[íi]culo|Article|Artigo)\s+(?=\D)")

    @staticmethod
    def _clean(text: str) -> str:
        """Collapse whitespace runs. Uses get_text() WITHOUT strip upstream so
        inter-span spaces (e.g. "software, hardware") are preserved — strip=True
        would glue adjacent inline <span> tokens ("software,hardware")."""
        return " ".join(text.split())

    def parse(self, html_bytes: bytes) -> list[ParsedArticle]:
        soup = BeautifulSoup(html_bytes, "html.parser")
        article_divs = soup.find_all("div", id=re.compile(r"^art_\d+$"))
        if not article_divs:
            raise HtmlParseError("no recognisable article markers (expected div#art_N)")

        out: list[ParsedArticle] = []
        for div in article_divs:
            raw_id = div.get("id", "")
            div_id = raw_id if isinstance(raw_id, str) else str(raw_id)
            articulo = div_id.removeprefix("art_")
            title_node = div.select_one(self._TITLE_SEL)
            title = self._clean(title_node.get_text()) if title_node else None
            if title:
                title = self._TITLE_DESIGNATION.sub("", title) or None

            paragraph_text = self._clean(" ".join(p.get_text() for p in div.select(self._BODY_SEL)))
            if not paragraph_text:
                paragraph_text = self._clean(div.get_text())

            paragraphs = (
                [ParsedParagraph(apartado="1", text=paragraph_text)] if paragraph_text else []
            )
            out.append(
                ParsedArticle(
                    articulo=articulo,
                    title=title,
                    text=paragraph_text,
                    paragraphs=paragraphs,
                )
            )
        return out
