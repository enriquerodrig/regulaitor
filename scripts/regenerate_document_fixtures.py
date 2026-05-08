"""Regenerate evals/document_cases/*.pdf from their .source.md siblings.

Uses reportlab to render markdown to PDF (Windows-friendly: no system deps).
The adversarial fixture is post-processed with pikepdf to inject document-
level JavaScript so the sanitizer can detect it as critical.

This is intentionally a simple renderer: paragraph-level layout, no fancy
typography. The point is producing a deterministic test fixture, not a
beautiful document.

Backend choice: reportlab (chosen on 2026-05-07). WeasyPrint was attempted
first but fails at runtime on Windows hosts without system cairo/pango/
gdk-pixbuf libraries. Reportlab is pure Python and already a dev dep.
"""

from __future__ import annotations

import re
from pathlib import Path

import pikepdf
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "document_cases"


def _markdown_to_flowables(md_text: str) -> list:
    """Convert markdown text into a list of reportlab Flowables.

    Supports: # H1, ## H2, ### H3, paragraphs separated by blank lines.
    Inline HTML spans (used by adversarial fixture for white-on-white text)
    pass through to reportlab, which interprets a small subset of HTML in
    Paragraph contents.
    """
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=22, spaceAfter=28, spaceBefore=14)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=16, spaceAfter=20, spaceBefore=20)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=13, leading=24, spaceAfter=14)

    flowables: list = []
    h2_count = 0
    for raw_block in re.split(r"\n\s*\n", md_text):
        block = raw_block.strip()
        if not block:
            continue
        if block.startswith("# "):
            flowables.append(Paragraph(block[2:].strip(), h1))
        elif block.startswith("## "):
            # Force a page break every two top-level sections so the synthesized
            # policy fixture lands in the 4-page target window deterministically.
            if h2_count > 0 and h2_count % 2 == 0:
                flowables.append(PageBreak())
            flowables.append(Paragraph(block[3:].strip(), h2))
            h2_count += 1
        elif block.startswith("### "):
            flowables.append(Paragraph(block[4:].strip(), h2))
        else:
            text = block.replace("\n", " ")
            flowables.append(Paragraph(text, body))
        flowables.append(Spacer(1, 6))
    return flowables


def _render_pdf(md_path: Path, out_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    doc.build(_markdown_to_flowables(md_text))


def _inject_adversarial(out_path: Path) -> None:
    """Add document-level JavaScript so the sanitizer can detect critical."""
    with pikepdf.open(out_path, allow_overwriting_input=True) as pdf:
        js = pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript,
            JS=pikepdf.String("app.alert('hi')"),
        )
        pdf.Root[pikepdf.Name.Names] = pikepdf.Dictionary(
            JavaScript=pikepdf.Dictionary(Names=pikepdf.Array([pikepdf.String("attack"), js])),
        )
        pdf.save(out_path)


def main() -> None:
    clean_md = CASES / "synthesized_policy_clean.source.md"
    clean_pdf = CASES / "synthesized_policy_clean.pdf"
    if clean_md.exists():
        _render_pdf(clean_md, clean_pdf)
        print(f"wrote {clean_pdf}")
    else:
        print(f"WARN: {clean_md} not found; skipping clean fixture")

    adv_md = CASES / "synthesized_policy_adversarial.source.md"
    adv_pdf = CASES / "synthesized_policy_adversarial.pdf"
    if adv_md.exists():
        _render_pdf(adv_md, adv_pdf)
        _inject_adversarial(adv_pdf)
        print(f"wrote {adv_pdf} (with embedded JS)")
    else:
        print(f"WARN: {adv_md} not found; skipping adversarial fixture")


if __name__ == "__main__":
    main()
