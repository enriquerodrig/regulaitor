"""Anti-injection regex heuristics (H4 chat + H5 document mode).

Curated; H9 redteam will expand based on empirical attacks.
Multilingual ES+EN, case-insensitive.

Coverage:
- chat mode: ~70-80% trivial chat injection (the 10 H4 patterns).
- document mode: chat patterns + ~13 document-specific (instruction-to-evaluator,
  citation poisoning, self-validating, authorize-exception, meta-inject, role
  override, data exfiltration, jailbreak chains) targeting prompt injection
  embedded in policy / contract text.

Defense in depth: regex is the second of four layers (sanitizer 1, regex 2,
prompt 3, Auditor 4). Imperfect coverage is acceptable because the Analyst
prompt explicitly instructs "data not instructions" and the Auditor still
blocks fabricated citations.
"""

from __future__ import annotations

import re
from typing import Literal

# H4 chat patterns (unchanged).
_CHAT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ignore (?:all )?previous instructions?", re.I), "ignore-previous"),
    # H9: widened to cover "olvida (las|todas|mis|estas) instrucciones anteriores"
    # (previously required exactly "todas las"; attack-006 exposed the gap).
    (
        re.compile(
            r"olvida\s+(?:(?:todas\s+)?(?:las\s+)?|mis\s+|estas\s+)?instrucciones?\s+anteriores?",
            re.I,
        ),
        "olvida-anteriores",
    ),
    # H9: Spanish "ignora ... instrucciones anteriores" was an uncovered variant
    # (attack-011 metadata exposed the gap).
    (
        re.compile(
            r"ignora\s+(?:(?:todas\s+)?(?:las\s+)?|mis\s+|estas\s+)?instrucciones?\s+anteriores?",
            re.I,
        ),
        "ignora-anteriores",
    ),
    (re.compile(r"</?(?:system|instructions?|prompt)>", re.I), "fake-tag"),
    (re.compile(r"new instructions?:", re.I), "new-instructions"),
    (re.compile(r"nuevas instrucciones?:", re.I), "nuevas-instrucciones"),
    (re.compile(r"you are now (?:a |an )?", re.I), "role-override-en"),
    (re.compile(r"ahora eres (?:un |una )?", re.I), "role-override-es"),
    (re.compile(r"reveal (?:your |the )?(?:system )?prompt", re.I), "reveal-prompt"),
    (re.compile(r"jailbreak|DAN", re.I), "jailbreak-keyword"),
    (re.compile(r"###[\s_]*(?:end|fin)[\s_]*###", re.I), "fake-delimiter"),
]

# H5 document-only patterns. Each targets a vector that is realistic in policy
# / contract / report text but unusual in short chat queries.
_DOCUMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?:el|la)\s+(?:asesor|asesora|analista|evaluador|evaluadora|revisor|revisora|sistema)\s+"
            r"que\s+(?:eval[uú]e|revise|analice|consulte)\s+(?:esta|este)\s+"
            r"(?:pol[ií]tica|documento|contrato|informe)\s+debe",
            re.I | re.U,
        ),
        "document_instruction_to_evaluator",
    ),
    (
        # H9: catches "el sistema evaluador debe omitir/ignorar" without the
        # "que evalúe esta política" qualifier (attack-007 exposed the gap).
        re.compile(
            r"(?:el|la)\s+(?:asesor|asesora|analista|evaluador|evaluadora|revisor|revisora|sistema(?:\s+evaluador)?)\s+"
            r"(?:debe|deber[íi]a|tiene\s+que)\s+"
            r"(?:omitir|ignorar|saltarse|saltar|reportar|reportar\s+cumplimiento|concluir|confirmar)",
            re.I | re.U,
        ),
        "document_instruction_to_evaluator_direct",
    ),
    (
        re.compile(
            r"the\s+(?:advisor|reviewer|analyst|evaluator|system)\s+"
            r"(?:(?:reviewing|evaluating|analyzing|that\s+reviews)\s+this\s+"
            r"(?:policy|document|contract|report)\s+)?"
            r"(?:must|should|shall)\s+(?:conclude|state|respond|report|find|confirm)",
            re.I,
        ),
        "document_instruction_to_evaluator_en",
    ),
    (
        re.compile(
            r"esta\s+(?:pol[ií]tica|documento|contrato|informe)\s+cumple\s+plenamente\s+con",
            re.I | re.U,
        ),
        "document_self_validating",
    ),
    (
        re.compile(
            r"los\s+art[ií]culos?\s+[\d\sy]+(?:que\s+aparecen)?\s+aqu[ií]?\s+son\s+"
            r"interpretaciones\s+internas",
            re.I | re.U,
        ),
        "document_citation_poisoning_es",
    ),
    (
        re.compile(
            r"the\s+articles?\s+(?:cited|referenced|mentioned)\s+(?:here|above|below)?\s+are\s+"
            r"internal\s+interpretations",
            re.I,
        ),
        "document_citation_poisoning_en",
    ),
    (
        re.compile(
            r"se\s+autoriza\s+(?:expl[ií]citamente\s+)?la\s+excepci[oó]n\s+(?:del|al)?\s*"
            r"art[ií]culo",
            re.I | re.U,
        ),
        "document_authorize_exception",
    ),
    (
        re.compile(
            r"(?:this\s+document\s+)?explicitly\s+authorizes?\s+the\s+exception\s+to",
            re.I,
        ),
        "document_authorize_exception_en",
    ),
    (
        re.compile(
            r"(?:por\s+favor\s+)?ignora\s+(?:la\s+)?secci[oó]n\s+anterior",
            re.I | re.U,
        ),
        "document_meta_inject_es",
    ),
    (
        re.compile(
            r"(?:please\s+)?skip\s+the\s+previous\s+section",
            re.I,
        ),
        "document_meta_inject_en",
    ),
    (
        re.compile(
            r"act[uú]a\s+como\s+(?:un\s+)?abogado\s+(?:oficial|certificado)?",
            re.I | re.U,
        ),
        "document_role_override_es",
    ),
    (
        re.compile(
            r"act\s+as\s+a\s+lawyer\s+who\s+concludes",
            re.I,
        ),
        "document_role_override_en",
    ),
    (
        re.compile(
            r"env[ií]a\s+esta\s+informaci[oó]n\s+a\s+\S+@",
            re.I | re.U,
        ),
        "document_data_exfiltration",
    ),
    (
        re.compile(
            r"(?:activate|enable)\s+DAN\s+mode|developer\s+mode\s+(?:on|enabled)",
            re.I,
        ),
        "document_jailbreak_chain",
    ),
]


def is_injection(text: str, mode: Literal["chat", "document"] = "chat") -> tuple[bool, str | None]:
    """Return (True, pattern_name) on first match; (False, None) otherwise.

    mode='chat' (default, H4 backcompat) applies the 10 chat patterns only.
    mode='document' applies ~13 document-specific patterns first (more
    specific) and then the 10 chat patterns as a fallback. This ordering
    means a phrase like "Activate DAN mode" surfaces as
    'document_jailbreak_chain' instead of the broader 'jailbreak-keyword'
    when analysing document text, while a bare "DAN" still hits chat
    fallback. Chat-mode behaviour is unchanged.
    """
    if mode == "document":
        for pattern, name in _DOCUMENT_PATTERNS:
            if pattern.search(text):
                return True, name
    for pattern, name in _CHAT_PATTERNS:
        if pattern.search(text):
            return True, name
    return False, None
