"""§6 mutation audit — prove the citation validator's tests kill §6-breaking changes.

Mutation testing normally mutates a source file and re-runs the test suite per
mutant. Here that is impractical: importing the app (torch/transformers/lancedb)
costs ~60s, so a subprocess pytest per mutant would take hours. Instead this is an
IN-PROCESS, dependency-free audit scoped to `citation/validator.py`'s decision
logic: it exec()s each mutated source once and runs a curated §6-invariant battery
against it. A mutant that any battery case catches is KILLED; one that none catch
SURVIVES (a test gap — or a documented equivalent mutant).

The battery mirrors the §6 invariants the real suite pins (fabricated article/
apartado -> invalid; text-not-in-corpus -> invalid; too-short -> invalid; empty ->
invalid; a real substring -> valid, incl. the boundary length). Run as a script for
the report; `tests/unit/citation/test_sec6_mutation_audit.py` asserts every
non-equivalent mutant is killed so a future weakening surfaces in CI.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from regulaitor.citation.schemas import Citation

_VALIDATOR_SRC = pathlib.Path(__file__).resolve().parents[1] / (
    "src/regulaitor/citation/validator.py"
)

# A corpus segment long enough to clear the floor; the battery citations are
# substrings (or not) of its normalized form.
_TARGET = "The providers of high-risk AI systems shall establish a risk-management system"
_VALID_TEXT = "providers of high-risk AI systems shall establish"  # substring, 49 norm chars
_NOT_IN_TEXT = "this exact phrase is absent from every official corpus segment entirely"
_SHORT_SUBSTR = "systems"  # substring, 7 norm chars < floor
_BOUNDARY_20 = "the providers of hig"  # substring prefix, exactly 20 norm chars
# Superset: the real target text PLUS an appended fabricated conclusion. A citation
# is a superset of the article, not a substring of it → must stay INVALID (defends
# the classic "quote real text + append a fabricated legal conclusion" §6 attack).
_SUPERSET = _TARGET + ", and therefore ALL such systems are exempt from every obligation"
_PADDED_SHORT = "systems" + " " * 20  # raw len 27, but normalizes to 7 chars < floor


class _FakeLoader:
    """Minimal loader satisfying validator.LoaderProtocol."""

    def __init__(self, *, target: str, article_exists: bool = True, apartado_exists: bool = True):
        self._target = target
        self._ae = article_exists
        self._pe = apartado_exists

    def get_article(self, norma: str, articulo: str, language: str) -> object:
        if not self._ae:
            raise KeyError("no such article")
        return object()

    def get_paragraph(self, norma: str, articulo: str, apartado: str, language: str) -> str:
        if not self._pe:
            raise KeyError("no such apartado")
        return self._target

    def get_article_text(self, norma: str, articulo: str, language: str) -> str:
        return self._target

    def list_apartados(self, norma: str, articulo: str, language: str) -> list[str]:
        return ["1"]


def _cit(text: str, apartado: str | None = "1") -> Citation:
    return Citation(norma="ai_act", articulo="6", apartado=apartado, language="es", text=text)


def _cit_bypass(text: str) -> Citation:
    """A whitespace citation that bypasses the schema field_validator (models a
    deserialization / injection edge case) — the empty-guard's raison d'être."""
    c = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="real text")
    object.__setattr__(c, "text", text)
    return c


@dataclass(frozen=True)
class _Case:
    name: str
    citation: Citation
    loader: _FakeLoader
    check: Callable[[Any], bool]  # AuditResult -> ok


# The §6 invariant battery. `check` returns True when the validator behaved
# correctly; a mutant that makes ANY check return False (or raise) is killed.
def _battery() -> list[_Case]:
    tgt = _FakeLoader(target=_TARGET)
    return [
        _Case(
            "B1_fabricated_article",
            _cit(_VALID_TEXT),
            _FakeLoader(target=_TARGET, article_exists=False),
            lambda r: (not r.validated) and r.failed_check == 1,
        ),
        _Case(
            "B2_fabricated_apartado",
            _cit(_VALID_TEXT, apartado="99"),
            _FakeLoader(target=_TARGET, apartado_exists=False),
            lambda r: (not r.validated) and r.failed_check == 2,
        ),
        _Case(
            "B3_text_not_in_corpus",
            _cit(_NOT_IN_TEXT),
            tgt,
            lambda r: (not r.validated) and r.failed_check == 3,
        ),
        _Case(
            "B4_too_short",
            _cit(_SHORT_SUBSTR),
            tgt,
            lambda r: (not r.validated) and r.failed_check == 4,
        ),
        _Case(
            "B5_empty_after_normalize",
            _cit_bypass("   "),
            tgt,
            lambda r: (not r.validated) and r.failed_check == 4,  # sec6-01b: strict, not 3
        ),
        _Case(
            "B6_valid_long",
            _cit(_VALID_TEXT),
            tgt,
            lambda r: r.validated and r.failed_check is None,
        ),
        _Case(
            "B7_valid_boundary_20",
            _cit(_BOUNDARY_20),
            tgt,
            lambda r: r.validated and r.failed_check is None,
        ),
        _Case(
            "B8_superset_of_article",
            _cit(_SUPERSET),
            tgt,
            lambda r: (not r.validated) and r.failed_check == 3,  # catches bidirectional match
        ),
        _Case(
            "B9_article_level_valid",
            _cit(_VALID_TEXT, apartado=None),  # apartado=None → article-text branch
            tgt,
            lambda r: r.validated and r.failed_check is None,
        ),
        _Case(
            "B10_article_level_fabricated",
            _cit(_NOT_IN_TEXT, apartado=None),
            tgt,
            lambda r: (not r.validated) and r.failed_check == 3,  # exercises the apartado=None path
        ),
        _Case(
            "B11_raw_padded_short",
            _cit(_PADDED_SHORT),
            tgt,
            lambda r: (not r.validated) and r.failed_check == 4,  # floor must key on NORMALIZED len
        ),
    ]


@dataclass(frozen=True)
class _Mutation:
    name: str
    old: str
    new: str
    expected: str  # "killed" | "equivalent"
    rationale: str


# Each mutation is a realistic §6 weakening of one decision point. `old` must occur
# exactly once (a stale audit = a source refactor that moved the target = an error).
_MUTATIONS: list[_Mutation] = [
    _Mutation(
        "floor_const_zero",
        "_MIN_CITATION_CHARS = 20",
        "_MIN_CITATION_CHARS = 0",
        "killed",
        "Disabling the length floor lets a trivial token validate -> B4 catches it.",
    ),
    _Mutation(
        "floor_boundary_lte",
        "< _MIN_CITATION_CHARS:",
        "<= _MIN_CITATION_CHARS:",
        "killed",
        "Off-by-one at the floor rejects a boundary-length valid citation -> B7.",
    ),
    _Mutation(
        "substring_always_true",
        "citation_norm in target_norm",
        "citation_norm in target_norm or True",
        "killed",
        "Forcing the substring test true validates fabricated text -> B3.",
    ),
    _Mutation(
        "textmatch_invert",
        "if not text_match:",
        "if text_match:",
        "killed",
        "Inverting the match branch flips valid<->invalid -> B3 and B6.",
    ),
    _Mutation(
        "empty_guard_disabled",
        "if len(citation_norm) == 0:",
        "if len(citation_norm) == -1:",
        "equivalent",
        "The floor subsumes the empty guard (empty is len 0 < 20 -> also failed_check=4); "
        "disabling the guard leaves the reject + code unchanged. Kept for the precise "
        "reason string + defense-in-depth clarity (sec6-01b).",
    ),
    _Mutation(
        "check1_code",
        "failed_check=1,",
        "failed_check=3,",
        "killed",
        "Mislabelling article fabrication as paraphrase (softenable) -> B1.",
    ),
    _Mutation(
        "check2_code",
        "failed_check=2,",
        "failed_check=3,",
        "killed",
        "Mislabelling apartado fabrication as paraphrase (softenable) -> B2.",
    ),
    _Mutation(
        "pass_validated_flip",
        "validated=True,",
        "validated=False,",
        "killed",
        "Flipping the pass return invalidates a real citation -> B6 and B7.",
    ),
    _Mutation(
        "apartado_branch_skip",
        "if citation.apartado is not None:",
        "if citation.apartado is None:",
        "killed",
        "Skipping the apartado check validates a fabricated-apartado citation -> B2.",
    ),
    _Mutation(
        "substring_bidirectional",
        "citation_norm in target_norm",
        "citation_norm in target_norm or target_norm in citation_norm",
        "killed",
        "Superset match (target in citation) validates 'real text + appended fabrication' -> B8.",
    ),
    _Mutation(
        "floor_raw_length",
        "len(citation_norm) < _MIN_CITATION_CHARS",
        "len(citation.text) < _MIN_CITATION_CHARS",
        "killed",
        "Keying the floor on RAW length lets a whitespace-padded short token clear it -> B11.",
    ),
    _Mutation(
        "article_self_match",
        "target_text = ld.get_article_text(citation.norma, citation.articulo, citation.language)",
        "target_text = citation.text",
        "killed",
        "apartado=None branch self-match validates fabricated whole-article text -> B10.",
    ),
]


def _run_battery(validate: Callable[..., Any], battery: list[_Case]) -> str | None:
    """Return the name of the first battery case the validate() fn fails, or None."""
    for case in battery:
        try:
            result = validate(case.citation, loader=case.loader)
        except Exception:  # a mutant that crashes on a valid input is killed
            return case.name
        if not case.check(result):
            return case.name
    return None


def _load_validate(src: str) -> Callable[..., Any]:
    ns: dict[str, Any] = {}
    exec(compile(src, "<sec6_mutant>", "exec"), ns)  # noqa: S102 — auditing our own source
    return ns["validate"]


def run_audit() -> dict[str, Any]:
    """Exec the baseline + every mutant, running the battery against each."""
    src = _VALIDATOR_SRC.read_text(encoding="utf-8")
    battery = _battery()

    baseline_fail = _run_battery(_load_validate(src), battery)
    results: list[dict[str, Any]] = []
    for mut in _MUTATIONS:
        count = src.count(mut.old)
        if count != 1:
            results.append({"name": mut.name, "outcome": "ERROR", "detail": f"old x{count}"})
            continue
        mutant_src = src.replace(mut.old, mut.new)
        killed_by = _run_battery(_load_validate(mutant_src), battery)
        outcome = "killed" if killed_by is not None else "survived"
        results.append(
            {
                "name": mut.name,
                "outcome": outcome,
                "expected": mut.expected,
                "killed_by": killed_by,
                "match": (outcome == "killed") == (mut.expected == "killed"),
                "rationale": mut.rationale,
            }
        )

    killed = [r for r in results if r["outcome"] == "killed"]
    survived = [r for r in results if r["outcome"] == "survived"]
    equivalent = [r for r in results if r.get("expected") == "equivalent"]
    unexpected = [r for r in results if not r.get("match", False) and r["outcome"] != "ERROR"]
    errors = [r for r in results if r["outcome"] == "ERROR"]
    return {
        "baseline_ok": baseline_fail is None,
        "baseline_fail": baseline_fail,
        "total": len(_MUTATIONS),
        "killed": len(killed),
        "survived": len(survived),
        "equivalent_documented": len(equivalent),
        "unexpected": unexpected,
        "errors": errors,
        "results": results,
    }


def _render(report: dict[str, Any]) -> str:
    lines = ["# §6 mutation audit — citation/validator.py", ""]
    lines.append(f"Baseline battery passes: **{report['baseline_ok']}**")
    lines.append(
        f"Mutations: **{report['total']}** | killed: **{report['killed']}** | "
        f"survived: **{report['survived']}** (documented equivalents: "
        f"{report['equivalent_documented']}) | unexpected: **{len(report['unexpected'])}** | "
        f"errors: **{len(report['errors'])}**"
    )
    lines.append("")
    lines.append("| mutation | outcome | expected | killed_by | note |")
    lines.append("|---|---|---|---|---|")
    for r in report["results"]:
        lines.append(
            f"| `{r['name']}` | {r['outcome']} | {r.get('expected', '-')} | "
            f"{r.get('killed_by') or '-'} | {r.get('rationale', r.get('detail', ''))} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    rep = run_audit()
    out = _VALIDATOR_SRC.parents[3] / "docs" / "sec6_mutation_audit.md"
    out.write_text(_render(rep), encoding="utf-8")
    print(_render(rep))
    print(f"\nWrote {out}")
