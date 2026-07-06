"""Unit tests for citation/validator.py — 3 strict checks against the corpus."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import Citation
from regulaitor.citation.validator import validate


class _FakeLoader:
    """Minimal loader stub that satisfies LoaderProtocol for unit tests."""

    def __init__(self, articles: dict[tuple[str, str, str], str]) -> None:
        # key: (norma, articulo, language) -> full article text
        self._articles = articles
        # key: (norma, articulo, apartado, language) -> paragraph text
        self._paragraphs: dict[tuple[str, str, str, str], str] = {}

    def add_paragraph(
        self,
        norma: str,
        articulo: str,
        apartado: str,
        language: str,
        text: str,
    ) -> None:
        self._paragraphs[(norma, articulo, apartado, language)] = text

    def get_article(self, norma: str, articulo: str, language: str) -> object:
        # The validator only uses get_article as an existence probe; the
        # returned object is intentionally opaque (no .text attribute) so the
        # validator must go through get_article_text for the no-apartado path.
        if (norma, articulo, language) not in self._articles:
            raise KeyError(f"{norma} has no articulo {articulo} in language {language}")
        return object()

    def get_paragraph(self, norma: str, articulo: str, apartado: str, language: str) -> str:
        key = (norma, articulo, apartado, language)
        if key not in self._paragraphs:
            raise KeyError(f"no apartado {apartado}")
        return self._paragraphs[key]

    def get_article_text(self, norma: str, articulo: str, language: str) -> str:
        key = (norma, articulo, language)
        if key not in self._articles:
            raise KeyError(f"{norma} has no articulo {articulo} in language {language}")
        return self._articles[key]

    def list_apartados(self, norma: str, articulo: str, language: str) -> list[str]:
        return [
            ap
            for (n, a, ap, lang) in self._paragraphs
            if n == norma and a == articulo and lang == language
        ]


@pytest.fixture
def loader_with_data() -> _FakeLoader:
    full_text = "El Artículo 6 establece reglas — incluido el apartado 1."
    apartado_1 = "El apartado 1 fija el ámbito"
    fl = _FakeLoader({("ai_act", "6", "es"): full_text})
    fl.add_paragraph("ai_act", "6", "1", "es", apartado_1)
    return fl


def test_validate_happy_path_with_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is True
    assert r.reason is None


def test_validate_happy_path_without_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="el artículo 6 establece reglas",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.apartado_exists is None  # no apartado given => check skipped
    assert r.text_normalized_match is True


def test_validate_article_not_found(loader_with_data: _FakeLoader) -> None:
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is False
    assert r.reason is not None
    assert "article_not_found" in r.reason


def test_trivial_substring_citation_rejected_by_length_floor(
    loader_with_data: _FakeLoader,
) -> None:
    """sec6-01 (pre-pilot audit; ADR-0043) — the length floor closes the gap.

    Check 3 is a substring test, so before the floor a trivial token (here the
    stopword "el", which occurs in the article) validated True with zero evidence.
    The _MIN_CITATION_CHARS floor (20) now rejects it as failed_check=4 (too-short,
    distinct from paraphrase=3 so the Auditor routes it strictly). Calibrated so it
    cannot reject a legitimate citation (shortest real validated citation 53 chars;
    shortest citable corpus segment 42 chars). §6-safe: strict-tightening.
    """
    c = Citation(norma="ai_act", articulo="6", language="es", text="el")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    # failed_check=4 (too-short), distinct from 3 (paraphrase) so the Auditor routes
    # it strictly (BLOCK/RHR) instead of softening to PASS — see test_auditor.
    assert r.failed_check == 4
    assert r.reason is not None and "too_short" in r.reason


def test_citation_at_length_floor_still_evaluated_on_match(loader_with_data: _FakeLoader) -> None:
    """A citation at/above the floor is evaluated normally by the substring match
    (the floor only short-circuits BELOW the threshold)."""
    # 'el artículo 6 establece reglas' is >20 chars and is a substring of the article.
    c = Citation(norma="ai_act", articulo="6", language="es", text="el artículo 6 establece reglas")
    r = validate(c, loader=loader_with_data)
    assert r.validated is True


def test_validate_apartado_not_found(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="99",
        language="es",
        text="text",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is False
    assert r.reason is not None
    assert "apartado_not_found" in r.reason


def test_validate_text_not_in_apartado(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason


def test_validate_text_not_in_article(loader_with_data: _FakeLoader) -> None:
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_article" in r.reason


def test_validate_normalizes_accents_and_case(loader_with_data: _FakeLoader) -> None:
    # Citation has caps + missing accents; corpus has lowercase + accents
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="EL APARTADO 1 FIJA EL AMBITO",  # no acento on "ambito"
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True


def test_validate_normalizes_dashes(loader_with_data: _FakeLoader) -> None:
    # Corpus has em-dash —; citation uses ascii -
    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text="el artículo 6 establece reglas - incluido el apartado 1",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True


def test_validate_text_from_other_apartado_rejected() -> None:
    """Text that matches a DIFFERENT apartado of the same article must be rejected.

    Regression: ensures the validator scopes the substring search to the
    claimed apartado, not the whole article. Citation claims apartado 1 but
    quotes the text of apartado 2; must fail.
    """
    # Passages are >20 chars so they exercise the substring-scoping logic, not the
    # sec6-01 length floor (which short-circuits below the threshold).
    apartado_1 = "El ámbito material del primer apartado es el que se describe aquí."
    apartado_2 = "Las obligaciones del segundo apartado son completamente distintas."
    fl = _FakeLoader({("ai_act", "6", "es"): f"{apartado_1}\n\n{apartado_2}"})
    fl.add_paragraph("ai_act", "6", "1", "es", apartado_1)
    fl.add_paragraph("ai_act", "6", "2", "es", apartado_2)

    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text=apartado_2,  # claims apartado 1 but quotes apartado 2
    )
    r = validate(c, loader=fl)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_apartado" in r.reason


def test_validate_text_from_other_article_rejected() -> None:
    """Text that matches a DIFFERENT article must be rejected.

    Regression: ensures the no-apartado path scopes the substring search to
    the claimed article, not the whole corpus. Citation claims article 6 but
    quotes the text of article 7; must fail.
    """
    # Passages are >20 chars so they exercise article scoping, not the length floor.
    art_6 = "El artículo seis regula el ámbito material de aplicación."
    art_7 = "El artículo siete regula obligaciones de transparencia distintas."
    fl = _FakeLoader(
        {
            ("ai_act", "6", "es"): art_6,
            ("ai_act", "7", "es"): art_7,
        }
    )

    c = Citation(
        norma="ai_act",
        articulo="6",
        language="es",
        text=art_7,  # claims article 6 but quotes article 7
    )
    r = validate(c, loader=fl)
    assert r.validated is False
    assert r.article_exists is True
    assert r.text_normalized_match is False
    assert r.reason is not None
    assert "text_not_in_article" in r.reason


# ---------------------------------------------------------------------------
# v0.1.24 (ADR-0031): failed_check field tests
# ---------------------------------------------------------------------------


def test_audit_result_failed_check_optional_field_default_none(
    loader_with_data: _FakeLoader,
) -> None:
    """AuditResult.failed_check defaults to None (backward-compat)."""
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.failed_check is None


def test_validator_populates_failed_check_1_when_article_not_exists(
    loader_with_data: _FakeLoader,
) -> None:
    """When Check 1 fails (article not found), failed_check=1."""
    c = Citation(norma="ai_act", articulo="999", language="es", text="text")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is False
    assert r.failed_check == 1


def test_validator_populates_failed_check_2_when_apartado_not_exists(
    loader_with_data: _FakeLoader,
) -> None:
    """When Check 2 fails (apartado not found), failed_check=2."""
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="99",
        language="es",
        text="text",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is False
    assert r.failed_check == 2


def test_validator_populates_failed_check_3_when_text_not_match(
    loader_with_data: _FakeLoader,
) -> None:
    """When Check 3 fails (text not found), failed_check=3."""
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="texto que no aparece nunca",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.article_exists is True
    assert r.apartado_exists is True
    assert r.text_normalized_match is False
    assert r.failed_check == 3


def test_validator_failed_check_none_when_all_checks_pass(
    loader_with_data: _FakeLoader,
) -> None:
    """When all checks pass, failed_check=None."""
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="el apartado 1 fija el ámbito",
    )
    r = validate(c, loader=loader_with_data)
    assert r.validated is True
    assert r.failed_check is None


# ---------------------------------------------------------------------------
# v0.1.32-post §6 invariant tightening: whitespace-only Citation.text bypass
# ---------------------------------------------------------------------------
# H17 deep-review finding C1: Pydantic Field(min_length=1) on Citation.text
# accepts " ", "\t", "\n", " ". _normalize collapses these to "" and
# "" in any_string == True. Result: AuditResult(validated=True), §6 PASS.
# Reproducible end-to-end against the live corpus. Two-layer fix:
#  (a) schema: @field_validator on Citation.text rejects whitespace-only;
#  (b) defense-in-depth in validator.py: if citation_norm == "" treat as
#      Check 3 failure (failed_check=3) so a future schema bypass still
#      cannot route to PASS.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ws_text", [" ", "  ", "\t", "\n", "\t \n ", "\xa0"])
def test_citation_schema_rejects_whitespace_only_text(ws_text: str) -> None:
    """Layer (a) — schema validator rejects whitespace-only text at construction."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="whitespace-only"):
        Citation(
            norma="ai_act",
            articulo="1",
            apartado="1",
            language="es",
            text=ws_text,
        )


def test_validator_rejects_empty_after_normalization_defense_in_depth(
    loader_with_data: _FakeLoader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer (b) — even if a Citation with whitespace text bypasses the schema
    (Pydantic field_validator), validator.py defense-in-depth catches the
    empty-after-normalization case and returns failed_check=4.

    sec6-01b: failed_check is 4 (non-citation), NOT 3 (paraphrase). An empty
    citation is the extreme non-citation; emitting 4 keeps the Auditor's
    paraphrase-softening `!= 3` guard routing it strict (BLOCK/RHR), consistent
    with the length floor. See validator.py sec6-01b note + ADR-0043 lineage.
    """
    # Construct a valid Citation, then mutate-bypass to whitespace via
    # model_copy + frozen-bypass. Use object.__setattr__ to skip the schema.
    c = Citation(
        norma="ai_act",
        articulo="6",
        apartado="1",
        language="es",
        text="real text",
    )
    object.__setattr__(c, "text", "   ")
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.failed_check == 4  # sec6-01b: non-citation, routes strict (not softenable 3)
    assert r.text_normalized_match is False
    assert "empty_citation_text_after_normalization" in (r.reason or "")


@pytest.mark.parametrize("combining_text", ["́", "️", "́̀"])
def test_validator_rejects_combining_mark_only_citation(
    loader_with_data: _FakeLoader,
    combining_text: str,
) -> None:
    """sec6-01b reachability (§6 review, medium): a Citation.text of bare combining
    marks / variation selectors PASSES the schema field_validator (str.strip() keeps
    non-whitespace Mn chars) but _normalize() collapses it to "" — so the empty-guard
    is reachable via the NORMAL production path (Answer.model_validate of the Analyst's
    tool_use), NOT only via a schema bypass. It MUST be rejected with failed_check=4
    (strict); pre-sec6-01b it was 3 (softenable) → a single-such-citation turn could be
    softened to PASS by the Auditor = a real §6 bypass this closes.
    """
    # Constructed the NORMAL way — no schema bypass; this is the production path.
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text=combining_text)
    r = validate(c, loader=loader_with_data)
    assert r.validated is False
    assert r.failed_check == 4
    assert "empty_citation_text_after_normalization" in (r.reason or "")


def test_citation_schema_accepts_legitimate_text() -> None:
    """Regression anchor: legitimate non-empty text remains valid post-fix."""
    c = Citation(
        norma="ai_act",
        articulo="1",
        apartado="1",
        language="es",
        text="el presente Reglamento es mejorar el funcionamiento",
    )
    assert c.text == "el presente Reglamento es mejorar el funcionamiento"
