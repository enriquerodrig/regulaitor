"""Unit tests for security/pii.py (Fase 2 — PII detection + redaction, §18.5)."""

from __future__ import annotations

import pytest

from regulaitor.security.pii import (
    detect_pii,
    has_pii,
    pii_kinds,
    redact,
)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Contacto: maria.lopez@empresa.es", "email"),
        ("Llámame al 612 345 678", "phone"),
        ("El DNI 12345678Z del responsable", "dni_nif"),
        ("NIE X1234567L del trabajador", "nie"),
        ("IBAN ES91 2100 0418 4502 0005 1332", "iban"),
        ("Tarjeta 4111 1111 1111 1111", "card"),  # Luhn-valid Visa test number
    ],
)
def test_detect_each_pii_kind(text: str, kind: str) -> None:
    kinds = pii_kinds(text)
    assert kind in kinds, f"expected {kind} in {kinds} for {text!r}"


def test_clean_normative_text_has_no_pii() -> None:
    """A normative question must NOT trip any detector (no false positives)."""
    clean = "¿Qué obligaciones impone el AI Act a los sistemas de IA de alto riesgo?"
    assert detect_pii(clean) == []
    assert has_pii(clean) is False


def test_card_requires_luhn() -> None:
    """A 16-digit run that fails the Luhn checksum is NOT flagged as a card."""
    assert "card" not in pii_kinds("Referencia 1111 1111 1111 1111")  # Luhn-fail
    assert "card" in pii_kinds("Tarjeta 4111 1111 1111 1111")  # Luhn-pass


def test_redact_replaces_with_placeholders() -> None:
    text = "Mi email es ana@test.com y mi DNI 12345678Z"
    out = redact(text)
    assert "ana@test.com" not in out
    assert "12345678Z" not in out
    assert "[EMAIL]" in out
    assert "[DNI]" in out


def test_redact_clean_text_is_unchanged() -> None:
    clean = "¿Qué dice el RGPD sobre las DPIA?"
    assert redact(clean) == clean


def test_detect_multiple_kinds_in_one_text() -> None:
    text = "email pepe@x.es, teléfono 698765432, IBAN ES91 2100 0418 4502 0005 1332"
    kinds = pii_kinds(text)
    assert {"email", "phone", "iban"} <= set(kinds)


def test_matches_are_non_overlapping_and_positioned() -> None:
    text = "DNI 12345678Z"
    matches = detect_pii(text)
    assert len(matches) == 1
    m = matches[0]
    assert m.kind == "dni_nif"
    assert text[m.start : m.end] == "12345678Z"


def test_redact_preserves_offsets_with_multiple_matches() -> None:
    text = "a@b.com mid 87654321A end c@d.org"
    out = redact(text)
    assert out == "[EMAIL] mid [DNI] end [EMAIL]"
