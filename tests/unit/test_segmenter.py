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


# ---------------------------------------------------------------------------
# v0.1.14 — numbered-section heading detection (Spanish compliance docs pattern)
#
# Motivation: H15 doc-mode probe found doc fixtures producing 1 giant segment
# instead of expected ~5 segments. Root cause: the heading regex only matched
# ALL-CAPS or markdown `#` lines, ignoring the typical Spanish compliance-doc
# pattern "1. Introducción / 2. Riesgos / 2.1 Subsección". v0.1.14 extends
# the regex to detect numbered sections without breaking existing patterns.
# ---------------------------------------------------------------------------


def test_numbered_sections_spanish_style_are_detected_as_headings():
    """Real-world compliance doc pattern: "1. Introducción" / "2. Riesgos" /
    "3. Política aplicable". Single-level numbering, Spanish accents in title."""
    text = (
        "1. Introducción\n\n"
        "Esta política establece el marco de gobernanza para sistemas de IA "
        "en la organización suficiente para llenar la primera sección.\n\n"
        "2. Riesgos identificados\n\n"
        "Los principales riesgos contemplados incluyen sesgo algorítmico y "
        "tratamiento inadecuado de datos personales en las decisiones.\n\n"
        "3. Política aplicable\n\n"
        "Todos los sistemas de IA deben cumplir con el marco descrito en "
        "este documento y someterse a auditoría anual.\n"
    )
    segs = segmenter.segment(_sanitized(text))
    titles = [s.title for s in segs]
    assert "1. Introducción" in titles, f"numbered section not detected; titles={titles}"
    assert "2. Riesgos identificados" in titles
    assert "3. Política aplicable" in titles
    assert len(segs) == 3


def test_nested_numbered_sections_are_detected_as_headings():
    """Multi-level numbering: '2.1 Subsección', '3.1.1 Detalle'."""
    text = (
        "1. Principal\n\n"
        "Texto suficientemente largo para llenar la sección principal con "
        "detalle relevante para el contexto operativo de la organización.\n\n"
        "2.1 Subsección operativa\n\n"
        "Detalle de la subsección con información complementaria que "
        "describe los procesos operativos involucrados en el cumplimiento.\n\n"
        "3.1.1 Detalle específico\n\n"
        "Información granular sobre el detalle específico aplicable al "
        "caso particular descrito en las secciones anteriores.\n"
    )
    segs = segmenter.segment(_sanitized(text))
    titles = [s.title for s in segs]
    assert any("1. Principal" in (t or "") for t in titles), f"titles={titles}"
    assert any("2.1 Subsección operativa" in (t or "") for t in titles)
    assert any("3.1.1 Detalle específico" in (t or "") for t in titles)


def test_two_numbered_sections_trigger_heuristic_split():
    """The current threshold requires ≥2 headings to trigger heuristic split.
    Verify that 2 numbered sections (smallest interesting case) split correctly."""
    text = (
        "1. Alcance\n\n"
        "Esta sección describe el alcance del documento de manera completa "
        "incluyendo todos los aspectos relevantes para su aplicación.\n\n"
        "2. Definiciones\n\n"
        "Las definiciones aplicables a este documento se establecen en esta "
        "sección con suficiente detalle para evitar ambigüedades.\n"
    )
    segs = segmenter.segment(_sanitized(text))
    assert len(segs) == 2
    titles = [s.title for s in segs]
    assert "1. Alcance" in titles
    assert "2. Definiciones" in titles


def test_numbered_section_does_not_match_sentence_with_period():
    """Sentences like '1. Esta es una frase normal que termina con punto.' should
    NOT be classified as headings even though they start with a number. The
    existing `not stripped.endswith('.')` filter must continue to work."""
    text = (
        "1. Esta es una frase normal que termina con un punto al final.\n\n"
        "2. Esta también es una frase ordinaria que termina con un punto.\n\n"
        "3. Y esta es otra frase más para confirmar el patrón completo.\n"
    )
    # No real headings → token-windowed fallback → 1 untitled segment.
    segs = segmenter.segment(_sanitized(text))
    assert len(segs) == 1
    assert segs[0].title is None


def test_real_fixture_doc_001_produces_multiple_segments():
    """v0.1.14 regression: the doc-001 fixture (política IA con secciones
    numeradas "1. Introducción", "2. Sistemas adoptados", etc.) MUST produce
    multiple segments after the v0.1.14 regex fix. Before the fix it produced
    1 giant segment because the heading regex didn't match numbered sections.

    Loaded synthetically (not from PDF) to avoid the slow PDF extraction in
    a unit test — the relevant text structure is preserved."""
    text = (
        "Política de Inteligencia Artificial Empresarial\n\n"
        "1. Introducción\n\n"
        "Esta política establece el marco de gobernanza para el uso de "
        "sistemas de inteligencia artificial en nuestra organización. "
        "La empresa ha adoptado varios sistemas de IA.\n\n"
        "2. Sistemas adoptados\n\n"
        "Los sistemas en uso incluyen clasificación documental, asistentes "
        "virtuales y análisis predictivo de comportamiento de clientes.\n\n"
        "3. Riesgos identificados\n\n"
        "Los principales riesgos contemplados incluyen sesgo algorítmico, "
        "decisiones automatizadas no supervisadas y tratamiento inadecuado.\n\n"
        "4. Medidas de mitigación\n\n"
        "Se aplicarán evaluaciones de impacto, auditorías regulares y "
        "revisión humana en decisiones de alto impacto.\n\n"
        "5. Gobernanza\n\n"
        "Un comité interdisciplinario supervisará el cumplimiento y "
        "responderá ante incidentes según el procedimiento establecido.\n"
    )
    segs = segmenter.segment(_sanitized(text))
    assert len(segs) >= 3, (
        f"v0.1.14 regression: doc-001-shaped text produced {len(segs)} segment(s); "
        f"expected ≥3 (pre-fix produced 1 because regex missed numbered sections)"
    )
