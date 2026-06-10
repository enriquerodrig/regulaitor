"""Unit tests for security/pii.py (Fase 2 — PII detection + redaction, §18.5)."""

from __future__ import annotations

import pytest

from regulaitor.security.pii import (
    count_pii,
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


# ---------- count_pii (Fase 2.1: doc-mode summary, counts only) ----------


def test_count_pii_counts_occurrences_per_kind() -> None:
    counts = count_pii("a@b.com, c@d.com y DNI 12345678Z")
    assert counts == {"dni_nif": 1, "email": 2}


def test_count_pii_empty_for_clean_text() -> None:
    assert count_pii("¿Qué dice el RGPD sobre las DPIA?") == {}


def test_count_pii_keys_sorted() -> None:
    counts = count_pii("IBAN ES91 2100 0418 4502 0005 1332, email z@z.es")
    assert list(counts.keys()) == sorted(counts.keys())


def test_count_pii_carries_no_raw_values() -> None:
    """§18.8: the summary must expose counts/kinds only — never the values."""
    counts = count_pii("Contacto maria.lopez@empresa.es")
    assert counts == {"email": 1}
    # keys are kinds, values are ints — no PII string anywhere in the mapping
    assert all(isinstance(k, str) and isinstance(v, int) for k, v in counts.items())
    assert "maria.lopez@empresa.es" not in counts


def test_count_pii_normative_digits_do_not_false_positive() -> None:
    """§22.22 characterization of the documented recall-favoring tradeoff
    (pii.py module docstring): CELEX ids, 4-digit years and short article
    numbers do NOT match the phone/card patterns — only a bare 9-digit run
    starting 6-9 does. Pins the TRUE false-positive surface so any regex change
    is intentional (corrects the over-broad 'dates/CELEX/ranges trigger' premise)."""
    # Dense normative prose: regulation refs, CELEX id, year, article numbers.
    normative = "Reglamento (UE) 2022/2554, CELEX 32022R2554, arts. 33 y 34"
    assert count_pii(normative) == {}
    # The actual (acknowledged) false positive: a bare 9-digit run starting 6-9.
    assert count_pii("Expediente 698765432 del registro interno") == {"phone": 1}
