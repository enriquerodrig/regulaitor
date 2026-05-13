"""H9 — Generate adversarial PDFs from redteam/_pdf_specs.jsonl.

One-shot script: reads _pdf_specs.jsonl, generates each PDF via ReportLab,
writes to redteam/documents/<id>.pdf. Idempotent — re-run produces identical
bytes (deterministic seed).

PDF specs schema:
  {
    "id": "attack-001",
    "kind": "ignore-instructions" | "hidden-text" | "metadata-malicious" |
            "contradictions" | "nonexistent-article" | "auditor-bypass",
    "visible_text": "...",
    "hidden_text": "...",        # optional, for hidden-text attacks
    "metadata": {"Author": "..."} # optional, for metadata attacks
  }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

_SPECS_PATH = Path("redteam/_pdf_specs.jsonl")
_OUTPUT_DIR = Path("redteam/documents")


def _load_specs(path: Path) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                specs.append(json.loads(stripped))
    return specs


def _make_pdf(spec: dict[str, Any], output_path: Path) -> None:
    """Generate one PDF based on spec.kind."""
    c = canvas.Canvas(str(output_path), pagesize=A4)

    # Metadata (some attacks rely on malicious metadata)
    metadata = spec.get("metadata", {})
    for key, value in metadata.items():
        if key == "Author":
            c.setAuthor(value)
        elif key == "Title":
            c.setTitle(value)
        elif key == "Subject":
            c.setSubject(value)
        elif key == "Keywords":
            c.setKeywords(value)

    # Visible text
    visible = spec.get("visible_text", "")
    if visible:
        text_obj = c.beginText(72, 800)
        text_obj.setFont("Helvetica", 11)
        for line in visible.split("\n"):
            text_obj.textLine(line)
        c.drawText(text_obj)

    # Hidden text (white on white, off-page, etc.)
    kind = spec.get("kind", "")
    if kind == "hidden-text" and spec.get("hidden_text"):
        c.setFillColorRGB(1, 1, 1)  # white on white background
        text_obj = c.beginText(72, 400)
        text_obj.setFont("Helvetica", 11)
        for line in spec["hidden_text"].split("\n"):
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.setFillColorRGB(0, 0, 0)  # restore

    c.save()


def main() -> None:
    if not _SPECS_PATH.exists():
        raise SystemExit(f"missing {_SPECS_PATH}")
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    specs = _load_specs(_SPECS_PATH)
    for spec in specs:
        output = _OUTPUT_DIR / f"{spec['id']}.pdf"
        _make_pdf(spec, output)
        print(f"wrote {output}")


if __name__ == "__main__":
    main()
