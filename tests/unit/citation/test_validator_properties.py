"""Property/fuzz tests for the §6 citation validator (roadmap P1.3).

The two §6 bypasses shipped-then-patched (substring "el" — sec6-01/ADR-0043; and
whitespace-only — v0.1.32-post) were both found by MANUAL review, not by tests. These
Hypothesis properties assert the §6 invariant across fuzzed inputs so the moat's tests
PIN behaviour rather than merely touching enumerated examples. They ASSERT the
invariant only — they do NOT edit validator.py (the sacred file stays byte-unchanged).

The load-bearing property is `test_non_substring_text_never_validates`: no citation
whose normalized text is absent from the corpus paragraph may ever validate. That is
"no citation, no answer" stated as a universally-quantified property.
"""

from __future__ import annotations

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import _MIN_CITATION_CHARS, validate
from regulaitor.rag.chunking import _normalize

_REAL_ART = "6"
_ARTICLE_TEXT = (
    "El artículo 6 establece las reglas de clasificación de sistemas de IA de alto "
    "riesgo conforme al presente Reglamento y sus anexos correspondientes."
)
_NORM_ARTICLE = _normalize(_ARTICLE_TEXT)


class _Loader:
    """Minimal LoaderProtocol impl exposing exactly one real article (no apartados)."""

    def __init__(self, articulo: str, text: str) -> None:
        self._articulo = articulo
        self._text = text

    def get_article(self, norma: str, articulo: str, language: str) -> object:
        if articulo != self._articulo:
            raise KeyError(articulo)
        return object()

    def get_article_text(self, norma: str, articulo: str, language: str) -> str:
        if articulo != self._articulo:
            raise KeyError(articulo)
        return self._text

    def get_paragraph(self, norma: str, articulo: str, apartado: str, language: str) -> str:
        raise KeyError(apartado)

    def list_apartados(self, norma: str, articulo: str, language: str) -> list[str]:
        return []


_LOADER = _Loader(_REAL_ART, _ARTICLE_TEXT)

# Broad alphabet EXCLUDING surrogates (which can't be UTF-8 encoded) — but keeping the
# §6-interesting classes (zero-width, combining marks, fullwidth) where normalization
# bypasses would hide.
_TEXT_CHARS = st.characters(blacklist_categories=("Cs",))
_SETTINGS = settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@given(articulo=st.text(min_size=1, max_size=6).filter(lambda s: s != _REAL_ART))
@_SETTINGS
def test_fabricated_article_never_validates(articulo: str) -> None:
    """Check 1: a citation for an article the corpus does not contain never validates
    (fabrication is blocked regardless of the cited text)."""
    c = Citation(norma="ai_act", articulo=articulo, language="es", text="x" * 40)
    assert validate(c, loader=_LOADER).validated is False


@given(txt=st.text(alphabet=_TEXT_CHARS, min_size=_MIN_CITATION_CHARS, max_size=120))
@_SETTINGS
def test_non_substring_text_never_validates(txt: str) -> None:
    """THE §6 property: for a real article, any text whose normalized form is NOT a
    substring of the article's normalized text can never validate."""
    assume(txt.strip())  # the schema rejects whitespace-only Citation.text
    assume(_normalize(txt) not in _NORM_ARTICLE)
    c = Citation(norma="ai_act", articulo=_REAL_ART, language="es", text=txt)
    assert validate(c, loader=_LOADER).validated is False


@given(txt=st.text(alphabet=_TEXT_CHARS, min_size=1, max_size=_MIN_CITATION_CHARS - 1))
@_SETTINGS
def test_too_short_text_never_validates(txt: str) -> None:
    """sec6-01: a citation whose normalized text is below the length floor never
    validates (a trivial token carries no evidentiary weight)."""
    assume(txt.strip())
    c = Citation(norma="ai_act", articulo=_REAL_ART, language="es", text=txt)
    assert validate(c, loader=_LOADER).validated is False


@given(start=st.integers(min_value=0, max_value=len(_ARTICLE_TEXT) - _MIN_CITATION_CHARS))
@_SETTINGS
def test_real_substring_at_or_above_floor_validates(start: str) -> None:
    """Positive direction: a genuine fragment of the article, at/above the floor and a
    real normalized-substring, DOES validate — the floor/substring guard is not so
    aggressive that it rejects legitimate quotes."""
    frag = _ARTICLE_TEXT[start : start + _MIN_CITATION_CHARS + 15]
    assume(len(_normalize(frag)) >= _MIN_CITATION_CHARS)
    assume(_normalize(frag) in _NORM_ARTICLE)  # keep only true normalized-substrings
    c = Citation(norma="ai_act", articulo=_REAL_ART, language="es", text=frag)
    assert validate(c, loader=_LOADER).validated is True
