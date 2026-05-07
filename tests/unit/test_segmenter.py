"""Tests for document.segmenter — structural + token-cap fallback."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import OutlineEntry, SanitizedDocument
from regulaitor.document import segmenter


def _sanitized(text: str, outline: list[OutlineEntry] | None = None) -> SanitizedDocument:
    return SanitizedDocument(
        document_hash="sha256:f",
        language="es",
        clean_text=text,
        outline=outline,
        sanitizer_log=[],
    )


def test_split_by_outline_when_present():
    text = (
        "\n\n--- p1 ---\n\n"
        "# Introducción\n\nTexto de la sección 1 con detalle relevante para el contexto.\n\n"
        "# Política de IA\n\nDescripción de la política aplicable.\n"
    )
    outline = [
        OutlineEntry(title="Introducción", level=1, page_number=1),
        OutlineEntry(title="Política de IA", level=1, page_number=1),
    ]
    segs = segmenter.segment(_sanitized(text, outline=outline))
    assert len(segs) == 2
    assert segs[0].title == "Introducción"
    assert segs[1].title == "Política de IA"
    assert all(s.token_count >= 1 for s in segs)
    assert all(not s.is_continuation for s in segs)


def test_token_cap_splits_long_section():
    big = "palabra " * 800  # forces over a 1500-token cap when chunking by paragraph
    text = "# Larga\n\n" + big + "\n"
    outline = [OutlineEntry(title="Larga", level=1, page_number=1)]
    segs = segmenter.segment(_sanitized(text, outline=outline), max_tokens=300)
    assert len(segs) >= 2
    assert segs[0].is_continuation is False
    assert all(s.is_continuation for s in segs[1:])
    assert all(s.title == "Larga" for s in segs)


def test_token_windowed_fallback_when_no_outline_no_headings():
    text = "Plain prose " * 200
    segs = segmenter.segment(_sanitized(text), max_tokens=200)
    assert len(segs) >= 1
    assert segs[0].title is None  # no structural title


def test_heading_heuristic_when_no_outline():
    text = (
        "INTRODUCCION\n\n"
        "Texto suficientemente largo para llenar la primera sección de manera holgada.\n\n"
        "POLITICA\n\n"
        "Texto suficientemente largo para llenar la segunda sección de manera holgada.\n"
    )
    segs = segmenter.segment(_sanitized(text))
    titles = [s.title for s in segs]
    assert "INTRODUCCION" in titles
    assert "POLITICA" in titles


def test_empty_clean_text_raises():
    sd = SanitizedDocument(
        document_hash="sha256:f",
        language="es",
        clean_text="x" * 50,  # min_length=50
        outline=None,
        sanitizer_log=[],
    )
    sd_ws = sd.model_copy(update={"clean_text": " " * 80})
    with pytest.raises(ValueError, match="cannot segment"):
        segmenter.segment(sd_ws)


def test_segment_ids_are_contiguous_starting_at_1():
    text = "Sección uno con texto suficiente.\n\nSección dos con texto suficiente.\n"
    outline = [
        OutlineEntry(title="A", level=1, page_number=1),
        OutlineEntry(title="B", level=1, page_number=1),
    ]
    segs = segmenter.segment(_sanitized(text, outline=outline))
    ids = [s.id for s in segs]
    assert ids == list(range(1, len(segs) + 1))
