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
    """Parse EUR-Lex HTML by extracting div blocks with id matching ^art_\\d+$."""

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
            title_node = div.find("p", class_="sti-art")
            title = title_node.get_text(strip=True) if title_node else None

            paragraph_text = " ".join(
                p.get_text(strip=True) for p in div.find_all("p", class_="normal")
            ).strip()
            if not paragraph_text:
                paragraph_text = div.get_text(strip=True)

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
