"""Parse Formex 4 XML (EUR-Lex Office of Publications schema) into ParsedArticle.

Synthetic fixtures live in tests/fixtures/formex/. Real EUR-Lex Formex documents
have additional namespaces and elements; the parser uses tolerant XPath that
ignores unknown elements while requiring the structural minimum (ARTICLE with
NO.ARTICLE and at least one PARAG/TXT).

Design notes:
- ARTICLE_XPATH is descendant-axis (".//ARTICLE") so we capture articles wherever
  they nest within the document tree. validate.py is the downstream guard that
  enforces the expected article count per corpus, catching any inflation from
  annex/appendix articles that share the ARTICLE element name.
- Title and article-number text are extracted via _text_content() rather than
  lxml's .text attribute, so inline markup like <HT TYPE="BOLD"> inside TI.ART
  is preserved.
- The fallback path (PARAG without NO.P) deliberately collects text only from
  PARAG/TXT children, never from the ARTICLE root, to keep NO.ARTICLE and
  TI.ART content out of the article body that downstream RAG embeds.
- Root element is validated against VALID_ROOTS; this guards against an HTML
  page being fed to the Formex parser by mistake (EUR-Lex sometimes returns
  HTML on format negotiation failure).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree


class FormexValidationError(Exception):
    """Raised when the input is not parseable Formex 4 or fails structural checks."""


@dataclass(frozen=True)
class ParsedParagraph:
    apartado: str
    text: str


@dataclass
class ParsedArticle:
    articulo: str
    title: str | None
    text: str
    paragraphs: list[ParsedParagraph] = field(default_factory=list)


_WS_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _text_content(node: etree._Element) -> str:
    """Concatenate all text inside the node (including nested tags) and normalise."""
    return _normalise("".join(node.itertext()))


class FormexParser:
    """Parse Formex 4 byte content into ParsedArticle list."""

    VALID_ROOTS = frozenset({"CONS.ACT", "ACT"})

    ARTICLE_XPATH = ".//ARTICLE"
    NO_ARTICLE_XPATH = "./NO.ARTICLE"
    TITLE_XPATH = "./TI.ART"
    PARAG_XPATH = "./PARAG"
    NO_P_XPATH = "./NO.P"
    TXT_XPATH = "./TXT"

    def parse(self, xml_bytes: bytes) -> list[ParsedArticle]:
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise FormexValidationError(f"invalid XML: {exc}") from exc

        if root.tag not in self.VALID_ROOTS:
            valid = sorted(self.VALID_ROOTS)
            raise FormexValidationError(
                f"unexpected root element: {root.tag!r} (expected one of {valid})"
            )

        articles_nodes = root.xpath(self.ARTICLE_XPATH)
        if not articles_nodes:
            raise FormexValidationError("zero ARTICLE nodes found")

        out: list[ParsedArticle] = []
        for node in articles_nodes:
            num_nodes = node.xpath(self.NO_ARTICLE_XPATH)
            if not num_nodes:
                raise FormexValidationError("ARTICLE without NO.ARTICLE")
            articulo = _text_content(num_nodes[0])
            if not articulo:
                raise FormexValidationError("ARTICLE NO.ARTICLE is empty")

            title_nodes = node.xpath(self.TITLE_XPATH)
            if title_nodes:
                raw_title = _text_content(title_nodes[0])
                title: str | None = raw_title if raw_title else None
            else:
                title = None

            paragraphs: list[ParsedParagraph] = []
            for p_node in node.xpath(self.PARAG_XPATH):
                num_p_nodes = p_node.xpath(self.NO_P_XPATH)
                txt_nodes = p_node.xpath(self.TXT_XPATH)
                if not num_p_nodes or not txt_nodes:
                    continue  # tolerate; some PARAGs lack numbering
                apartado = _normalise(num_p_nodes[0].text or "")
                paragraph_text = _text_content(txt_nodes[0])
                if apartado and paragraph_text:
                    paragraphs.append(ParsedParagraph(apartado=apartado, text=paragraph_text))

            article_text = " ".join(p.text for p in paragraphs)
            if not article_text:
                # Fallback: collect raw text from PARAG/TXT, ignoring missing NO.P.
                # Deliberately skips NO.ARTICLE and TI.ART so structural metadata
                # never contaminates the article body that downstream RAG embeds.
                fallback_parts = [
                    _text_content(txt)
                    for p_node in node.xpath(self.PARAG_XPATH)
                    for txt in p_node.xpath(self.TXT_XPATH)
                ]
                article_text = " ".join(t for t in fallback_parts if t)
                if not article_text:
                    raise FormexValidationError(f"ARTICLE {articulo} has empty text")

            out.append(
                ParsedArticle(
                    articulo=articulo,
                    title=title,
                    text=article_text,
                    paragraphs=paragraphs,
                )
            )
        return out
