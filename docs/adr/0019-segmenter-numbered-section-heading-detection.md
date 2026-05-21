# ADR 0019 — Segmenter heading regex extension for numbered-section detection (v0.1.14)

- **Status:** Accepted — 2026-05-21 — squash `<squash-sha>`, tag `v0.1.14`
- **Deciders:** Project owner.
- **Companion ADRs:** 0007 (H5 document pipeline — the segmenter design this extends), 0016 (H15 Auditor calibration — surfaced the "1 giant segment" failure mode on the doc-mode probe).

## Context

H15 calibration (ADR 0016) ran a 1-doc probe through the document analysis pipeline (extractor → sanitizer → segmenter → Analyst → Auditor) and observed that the segmenter produced **1 giant segment per document** instead of the expected per-section granularity. This made doc-mode A/B uncomputable for H15 and was carried forward as a deferred microhito.

Diagnostic in v0.1.14 (on the real `evals/document_cases/case_doc-001_politica-ia-empresarial-con-si.pdf` fixture):

- Extraction: OK (1 page, 1507 chars).
- Sanitization: OK (1519 chars clean_text, metadata stripped per §18.8).
- Segmentation: **1 segment of 1519 chars** (`token_count=225`, well below `max_tokens=1500` default).
- Gold expectation for this fixture: `expected_n_segments=5, tolerance=±2` — i.e. 3-7 segments.

Root cause: the `_HEADING_LIKE` regex in `src/regulaitor/document/segmenter.py` matched only two patterns:

```python
_HEADING_LIKE = re.compile(r"^(?:[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ \-]{2,80}|#{1,6}\s+\S.{0,80})$")
```

1. ALL-CAPS lines (e.g. "INTRODUCCIÓN", "POLÍTICA")
2. Markdown headings (e.g. "# Título")

But the compliance-doc fixtures use the standard Spanish numbered-section pattern: "1. Introducción", "2. Sistemas adoptados", "3. Riesgos identificados". This pattern matches NEITHER alternative — neither is ALL-CAPS nor a markdown heading. The segmenter therefore detected 0 headings, fell through to the token-windowed fallback, and (because every fixture's full text was under `max_tokens=1500`) returned 1 segment per doc.

This is the actual mechanism behind H15's "1 giant segment" observation — NOT a sanitizer issue, NOT an extractor issue, NOT a max_tokens issue. A regex blind spot.

All 8 testable fixtures in `evals/document_cases/` use the numbered-section pattern (2 of the 10 fixtures are blocked-by-design redteam cases for javascript injection and don't reach the segmenter). Without v0.1.14, ALL 8 would silently fail the gold's `expected_n_segments` invariant. The doc-mode evaluation therefore was never operationally measurable since H5.

## Decision

Extend `_HEADING_LIKE` with a third alternative for numbered sections, matching one or more dot-separated digit groups followed by ≥3 chars of title text. The existing downstream filter `not stripped.endswith(".")` in `_detect_heading_lines` continues to exclude ordinary sentences like "1. Esta es una frase normal." (which DO start with a number but end in a period after the title text).

```python
_HEADING_LIKE = re.compile(
    r"^(?:"
    r"[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ \-]{2,80}"  # ALL CAPS heading
    r"|#{1,6}\s+\S.{0,80}"               # Markdown heading
    r"|\d+(?:\.\d+)*\.?\s+\S.{2,100}"    # NEW: Numbered "1. Intro", "2.1 Sub", "3.1.1 Detail"
    r")$"
)
```

The third alternative matches:
- `1. Introducción` (one-level numbering, period after digit, title text ≥3 chars)
- `2.1 Subsección` (two-level numbering, no trailing period, title text)
- `3.1.1 Detalle específico` (three-level)
- `1. Introducción del marco` (multi-word title)

The third alternative does NOT match:
- `1.` alone (no title text after the number)
- `1. ab` (title text < 3 chars per `\S.{2,100}`)
- `1. Esta es una frase normal.` (filtered out by `not stripped.endswith(".")`)
- `1`, `1.` (no whitespace after, no title)

No other code change. The segmenter's overall strategy (split-by-outline > heuristic-headings > token-windowed-fallback) is preserved. `max_tokens` default stays at 1500. `_split_by_outline`, `_split_paragraphs_under_cap`, `segment()` entry point — all unchanged.

## Consequences

**Positive:**

- **Doc-mode evaluation now operationally measurable** — 8/8 testable fixtures (excluding 2 blocked-by-design redteam cases) now produce `actual_n_segments` within the gold's `expected_n_segments ± tolerance`. Before v0.1.14, all 8 were silently failing this invariant; H5 doc-mode A/B was therefore never meaningful.
- **Surgical change** — 1 regex alternative added, no other code touched. `_split_by_outline`, `_split_paragraphs_under_cap`, `segment()` strategy, `max_tokens` default all preserved. Backward-compat with non-numbered-section docs verified by full pytest gate (837 passed / 0 failed).
- **5 new unit tests** pin the new behavior + the downstream filter that excludes ordinary sentences. The existing 6 tests continue to pass.
- **Compliance-doc canonical pattern supported** — Spanish compliance documents (policies, procedures, contracts) overwhelmingly use the numbered-section convention. The fix aligns the segmenter with the actual document distribution it's expected to serve.
- **§6 invariant intact** — Auditor + citation validator byte-unchanged. The segmenter is upstream of retrieval/Analyst/Auditor; its output structure changes don't affect citation validation.

**Negative / accepted (documented honestly per §22.22):**

- **False-positive risk on academic-style documents** — papers and reports sometimes have numbered bullet lists ("1. First point", "2. Second point") within a single section that are NOT headings but bullet points. The third regex alternative would match these and produce over-segmentation. Mitigation: the existing `not stripped.endswith(".")` downstream filter catches the most common case (bullets that end in periods); if a future fixture surfaces this false-positive pattern legitimately, the regex can be tightened (e.g. require capitalized first character after the number, OR require the heading to be on its own line surrounded by blank lines).
- **No threshold change** — the existing `len(headings) >= 2` threshold for heuristic split is preserved. A document with exactly one numbered section ("1. Introducción") followed by prose would still fall through to the token-windowed fallback. This is conservative (avoids over-splitting on a single numbered list item appearing in body text) but means single-section short docs continue to produce 1 segment.
- **Doc-mode A/B paid validation still deferred** — v0.1.14 enables `expected_n_segments` to be met on real fixtures, but the END-TO-END doc-mode A/B (paid: extractor → sanitizer → segmenter → Analyst → Auditor → judge) is still deferred to the v0.1.20 paid bundle validation. v0.1.14 ships the SEGMENTATION primitive correctness; the integrated measurement is for v0.1.20.

## Alternatives considered

- **Lower `max_tokens` default 1500 → 400** — would cause the token-windowed fallback to produce more segments per doc. Rejected: would change behavior for all callers (including non-compliance-doc usage), would require updating every test that depends on segment count, and doesn't address the root cause (regex blindness). The surgical regex fix is preferred.
- **Add a separate `_NUMBERED_HEADING_LIKE` regex** with its own detection path — rejected as over-engineered. The existing `_HEADING_LIKE` pattern is a single regex with alternatives; adding a third alternative is consistent with the existing design.
- **Require `≥1 heading` instead of `≥2` for heuristic split** — would help in single-section docs but introduces false-positive risk for documents with one accidental numbered line in body text. The `≥2` threshold is preserved as a safety guard.
- **Replace the segmenter entirely** (e.g. with `unstructured` library's chunking) — large milestone, out of v0.1.14 scope. Listed for future consideration if v0.1.20 measurement reveals the surgical fix is insufficient for production-grade doc-mode quality.

## References

- Spec context: H5 document pipeline (ADR 0007).
- Source of fix: `src/regulaitor/document/segmenter.py:23` (regex line).
- New unit tests: `tests/unit/test_segmenter.py` (5 tests added for numbered-section detection + downstream filter).
- Real-fixture verification: all 8 testable fixtures in `evals/document_cases/` now within `expected_n_segments ± tolerance` (manually verified at v0.1.14 implementation).
- Predecessor finding context: H15 calibration study (`docs/auditor_calibration.md` notes "0 segments" probe; v0.1.14 diagnostic clarified that the actual behavior was "1 giant segment", not literal 0).
- Future paid validation: v0.1.20 paid bundle (doc-mode A/B with real Analyst + judge, when budget recharges).
