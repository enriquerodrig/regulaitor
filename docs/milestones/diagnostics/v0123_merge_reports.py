#!/usr/bin/env python
"""T1 Deliverable: Merge v0.1.23 probe (5 cases) + main (25 cases) into v0.1.23-prod.md

Reads:
  - evals/reports/v0.1.23/probe.md (chat-001..005)
  - evals/reports/v0.1.23/v0.1.23-prod-main.md (chat-006..030)

Merges into:
  - evals/reports/v0.1.23/v0.1.23-prod.md (30 cases combined)

Pattern mirrors v0.1.22 merge (if exists); otherwise simple Markdown concat with unified header.

No API calls; $0 script.
"""

import re
from pathlib import Path


def extract_header(markdown_path: str) -> str:
    """Extract the header section (before first ### case heading)."""
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    # Find position of first "### " heading
    match = re.search(r"^### ", text, re.MULTILINE)
    if match:
        return text[: match.start()].rstrip()
    return text


def extract_cases(markdown_path: str) -> str:
    """Extract the per-case appendix section (from first ### onward)."""
    with open(markdown_path, encoding="utf-8") as f:
        text = f.read()

    # Find position of first "### " heading
    match = re.search(r"^### ", text, re.MULTILINE)
    if match:
        return text[match.start() :]
    return ""


def main():
    """Merge probe + main reports."""
    probe_path = Path("evals/reports/v0.1.23/probe.md")
    main_path = Path("evals/reports/v0.1.23/v0.1.23-prod-main.md")
    output_path = Path("evals/reports/v0.1.23/v0.1.23-prod.md")

    if not probe_path.exists():
        raise FileNotFoundError(f"Probe report not found: {probe_path}")
    if not main_path.exists():
        raise FileNotFoundError(f"Main report not found: {main_path}")

    # Extract header from probe (use as canonical header)
    header = extract_header(str(probe_path))

    # Extract cases from both
    probe_cases = extract_cases(str(probe_path))
    main_cases = extract_cases(str(main_path))

    # Merge: header + probe cases + main cases
    merged = f"{header}\n\n{probe_cases}\n\n{main_cases}"

    # Write output
    output_path.write_text(merged.strip() + "\n", encoding="utf-8")
    print(f"OK: Merged report written to {output_path}")
    print("    Combined 5 probe + 25 main = 30 total cases")


if __name__ == "__main__":
    main()
