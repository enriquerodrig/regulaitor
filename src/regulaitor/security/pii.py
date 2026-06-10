"""Centralized PII detection + redaction (CLAUDE.md §18.5; Fase 2 HX).

Regex-based MVP for common EU/Spain personal data: email, Spanish phone,
DNI/NIF, NIE, IBAN, payment card (Luhn-validated). Detection-grade, NOT
validation-grade — it favors recall for the §18.5 "alert + redact + cancel"
UX, so some false positives are acceptable (the user is warned, not blocked).

§22.22: regex MVP. False positives possible (notably phone-shaped 9-digit
runs); NER-based detection (spaCy/Presidio) is HX. This module does NOT touch
the §6 citation pipeline — it is a pre-pipeline / logging-egress security layer.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class PIIMatch(NamedTuple):
    kind: str  # email | phone | dni_nif | nie | iban | card
    value: str
    start: int
    end: int


# Order matters: more-specific / longer patterns first so dedupe keeps them.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("iban", re.compile(r"\bES\d{2}(?:[ ]?\d{4}){5}\b", re.IGNORECASE)),
    ("nie", re.compile(r"\b[XYZ]\d{7}[A-Z]\b", re.IGNORECASE)),
    ("dni_nif", re.compile(r"\b\d{8}[A-Z]\b", re.IGNORECASE)),
    # card: candidate 13-19 digit runs (grouped with spaces/hyphens); Luhn-filtered below.
    ("card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    # ES phone: optional +34 / 0034, then 9 digits starting 6/7/8/9, optional separators.
    ("phone", re.compile(r"(?:(?:\+|00)34[ .\-]?)?\b[6-9]\d{2}[ .\-]?\d{3}[ .\-]?\d{3}\b")),
]

_REDACTION = {
    "email": "[EMAIL]",
    "phone": "[TELÉFONO]",
    "dni_nif": "[DNI]",
    "nie": "[NIE]",
    "iban": "[IBAN]",
    "card": "[TARJETA]",
}


def _luhn_ok(text: str) -> bool:
    """Luhn checksum on the digits of *text* (drops separators). Used to keep
    only plausible payment cards and reject arbitrary long digit runs."""
    nums = [int(c) for c in text if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(nums)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _dedupe_overlapping(matches: list[PIIMatch]) -> list[PIIMatch]:
    """Keep matches that do not overlap an already-kept (earlier-starting,
    then longer) match, so redaction never double-replaces a span."""
    kept: list[PIIMatch] = []
    last_end = -1
    for m in sorted(matches, key=lambda x: (x.start, -(x.end - x.start))):
        if m.start >= last_end:
            kept.append(m)
            last_end = m.end
    return kept


def detect_pii(text: str) -> list[PIIMatch]:
    """Return non-overlapping PII matches in *text*, sorted by position."""
    found: list[PIIMatch] = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if kind == "card" and not _luhn_ok(m.group()):
                continue
            found.append(PIIMatch(kind, m.group(), m.start(), m.end()))
    return _dedupe_overlapping(found)


def redact(text: str) -> str:
    """Replace every detected PII span with its placeholder ([EMAIL], [DNI], ...).
    Replaces from the end so earlier offsets stay valid."""
    out = text
    for m in sorted(detect_pii(text), key=lambda x: x.start, reverse=True):
        out = out[: m.start] + _REDACTION.get(m.kind, "[PII]") + out[m.end :]
    return out


def pii_kinds(text: str) -> list[str]:
    """Distinct PII kinds present (for the user-facing alert), sorted."""
    return sorted({m.kind for m in detect_pii(text)})


def has_pii(text: str) -> bool:
    return bool(detect_pii(text))
