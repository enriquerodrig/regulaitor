"""Anti-injection regex heuristic on raw user queries (H4 chat mode).

Curated initial set; H9 redteam will expand based on empirical attacks.
Multilingual ES+EN, case-insensitive.

Coverage: ~70-80% of trivial chat injection attacks. Heavy defense (document
sanitization, semantic injection classifier) belongs to H5 + H9.
Decisions log 2026-05-05 entry "Auditor lean en H4".
"""

from __future__ import annotations

import re

INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ignore (?:all )?previous instructions?", re.I), "ignore-previous"),
    (re.compile(r"olvida (?:todas las )?instrucciones? anteriores?", re.I), "olvida-anteriores"),
    (re.compile(r"</?(?:system|instructions?|prompt)>", re.I), "fake-tag"),
    (re.compile(r"new instructions?:", re.I), "new-instructions"),
    (re.compile(r"nuevas instrucciones?:", re.I), "nuevas-instrucciones"),
    (re.compile(r"you are now (?:a |an )?", re.I), "role-override-en"),
    (re.compile(r"ahora eres (?:un |una )?", re.I), "role-override-es"),
    (re.compile(r"reveal (?:your |the )?(?:system )?prompt", re.I), "reveal-prompt"),
    (re.compile(r"jailbreak|DAN", re.I), "jailbreak-keyword"),
    (re.compile(r"###[\s_]*(?:end|fin)[\s_]*###", re.I), "fake-delimiter"),
]


def is_injection(query: str) -> tuple[bool, str | None]:
    """Return (True, pattern_name) on first match; (False, None) otherwise."""
    for pattern, name in INJECTION_PATTERNS:
        if pattern.search(query):
            return True, name
    return False, None
