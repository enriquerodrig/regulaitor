"""§6 mutation audit — the Auditor's aggregation (Layer b/c), companion to
scripts/sec6_mutation_audit.py (Layer a, the per-citation validator).

The Auditor turns per-citation AuditResults into a turn verdict: Finding-Lenient
(a Finding passes if >=1 citation validates) + turn routing (quorum, all-blocked,
partial) gated by `_all_blocked_findings_paraphrase_only` (softens to PASS ONLY
when every blocked Finding's invalid citations are all failed_check==3). Every
routing milestone (v0.1.21/25/29) claims "§6-safe by construction" here. This audit
proves those claims are TESTED: it exec()s mutated copies of auditor.py and asserts
a battery of §6-routing invariants (fabrication/too-short/empty NEVER PASS;
paraphrase-only MAY soften; Lenient + quorum behave as specified).

In-process + $0: exec once, inject a FAKE validator into the mutant's namespace so
each citation's failed_check is controlled by its text prefix (VALID / FAB1 / FAB2 /
PARA / SHORT), then run AuditorAgent().audit(answer) and check the verdict.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Literal

from regulaitor.citation.schemas import (
    Answer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)

_AUDITOR_SRC = pathlib.Path(__file__).resolve().parents[1] / "src/regulaitor/agents/auditor.py"

# citation text prefix -> per-citation outcome (failed_check). The fake validator
# reads the prefix so the audit controls exactly what the Auditor aggregates.
_CODE: dict[str, Literal[1, 2, 3, 4]] = {
    "FAB1": 1,
    "FAB2": 2,
    "PARA": 3,
    "SHORT": 4,
}  # VALID->valid


def _fake_validate(citation: Citation, *, loader: object | None = None) -> AuditResult:
    kind = citation.text.split(":", 1)[0]
    if kind == "VALID":
        return AuditResult(
            citation=citation,
            validated=True,
            article_exists=True,
            apartado_exists=True,
            text_normalized_match=True,
            reason=None,
            failed_check=None,
        )
    code = _CODE[kind]
    return AuditResult(
        citation=citation,
        validated=False,
        article_exists=code != 1,
        apartado_exists=code not in (1, 2),
        text_normalized_match=False,
        reason=f"fake:{kind}",
        failed_check=code,
    )


def _c(text: str) -> Citation:
    return Citation(norma="ai_act", articulo="6", apartado="1", language="es", text=text)


def _finding(*texts: str, severity: Literal["info", "low", "medium", "high"] = "high") -> Finding:
    return Finding(text="claim", citations=[_c(t) for t in texts], severity=severity)


def _answer(*findings: Finding) -> Answer:
    return Answer(query="q", language="es", text="t", findings=list(findings))


@dataclass(frozen=True)
class _Case:
    name: str
    answer: Answer
    expect: AuditVerdict


def _battery() -> list[_Case]:
    p, b, r = AuditVerdict.PASS, AuditVerdict.BLOCK, AuditVerdict.REQUIRES_HUMAN_REVIEW
    return [
        # Fabrication / too-short must NEVER route to PASS (the §6 invariant).
        _Case("R1_single_fabricated_article", _answer(_finding("FAB1:a")), b),
        _Case("R2_single_too_short", _answer(_finding("SHORT:a")), b),
        _Case("R6_two_fabricated", _answer(_finding("FAB1:a"), _finding("FAB1:b")), b),
        _Case("R7_partial_fabrication", _answer(_finding("VALID:a"), _finding("FAB1:b")), r),
        _Case("R10_allblocked_mixed_fab", _answer(_finding("PARA:a"), _finding("FAB1:b")), b),
        # FAB2 (apartado fabrication) MUST reach the helper via a BLOCKED Finding
        # — else a mutation softening only check 2 survives (§6 review, high).
        _Case("R11_allblocked_apartado_fab", _answer(_finding("FAB2:a")), b),
        _Case("R12_partial_apartado_fab", _answer(_finding("VALID:a"), _finding("FAB2:b")), r),
        # Paraphrase-only MAY soften (the intended v0.1.25/29 behaviour).
        _Case("R3_single_paraphrase", _answer(_finding("PARA:a")), p),
        _Case("R8_partial_paraphrase", _answer(_finding("VALID:a"), _finding("PARA:b")), p),
        # Lenient-Finding + quorum.
        _Case("R4_single_valid", _answer(_finding("VALID:a")), p),
        _Case("R5_lenient_valid_plus_fab", _answer(_finding("VALID:a", "FAB1:b")), p),
        _Case(
            "R9_quorum_two_invalid",
            _answer(_finding("VALID:a", "FAB1:b"), _finding("VALID:c", "FAB2:d")),
            r,
        ),
    ]


@dataclass(frozen=True)
class _Mutation:
    name: str
    old: str
    new: str
    expected: str  # "killed" | "equivalent"
    rationale: str


_MUTATIONS: list[_Mutation] = [
    _Mutation(
        "helper_softens_fabrication",
        "if r.failed_check != 3:",
        "if r.failed_check == 3:",
        "killed",
        "Inverting the paraphrase gate softens FABRICATION to PASS -> R1.",
    ),
    _Mutation(
        "helper_skips_wrong_citations",
        "if r.validated:",
        "if not r.validated:",
        "killed",
        "Skipping invalid (not valid) citations makes the helper always True -> R1.",
    ),
    _Mutation(
        "finding_lenient_always_pass",
        "any(r.validated for r in this_finding_results)",
        "True",
        "killed",
        "Marking every Finding passed hides a fabricated-only Finding via the quorum -> R1.",
    ),
    _Mutation(
        "quorum_loosened",
        "n_invalid_citations >= 2",
        "n_invalid_citations >= 3",
        "killed",
        "Raising the quorum lets two invalid citations PASS instead of RHR -> R9.",
    ),
    _Mutation(
        "allblocked_else_pass",
        "verdict = AuditVerdict.BLOCK",
        "verdict = AuditVerdict.PASS",
        "killed",
        "Softening the all-blocked fallback passes fabricated all-blocked turns -> R1.",
    ),
    _Mutation(
        "allpass_condition_any",
        'all(v == "pass" for v in finding_verdicts)',
        'any(v == "pass" for v in finding_verdicts)',
        "killed",
        "Any-pass routes a partial fabrication turn through the lenient quorum -> R7.",
    ),
    _Mutation(
        "allblocked_condition_any",
        'all(v == "blocked" for v in finding_verdicts)',
        'any(v == "blocked" for v in finding_verdicts)',
        "killed",
        "Any-blocked misroutes a partial turn into the all-blocked branch -> R7.",
    ),
    _Mutation(
        "helper_softens_apartado_fab",
        "if r.failed_check != 3:",
        "if r.failed_check not in (3, 2):",
        "killed",
        "Softening ONLY apartado fabrication (check 2) to PASS while keeping 1/4 strict -> R11.",
    ),
]


def _load_auditor(src: str) -> Any:
    ns: dict[str, Any] = {}
    exec(compile(src, "<sec6_auditor_mutant>", "exec"), ns)  # noqa: S102 — auditing our own source

    class _FakeValidator:
        validate = staticmethod(_fake_validate)

    ns["validator"] = _FakeValidator  # audit() resolves `validator` from its module globals (=ns)
    return ns["AuditorAgent"]


def _run_battery(auditor_cls: Any, battery: list[_Case]) -> tuple[str, str] | None:
    """Return (case_name, kind) of the first case a mutant fails, or None if all
    pass. kind is 'mismatch' (the routing invariant caught it — the intended §6
    signal) or 'crash' (audit() raised — caught, but not via a routing mismatch),
    so a §6 review can require kills to be genuine routing mismatches."""
    for case in battery:
        try:
            result = auditor_cls().audit(case.answer)
        except Exception:
            return case.name, "crash"
        if result.verdict != case.expect:
            return case.name, "mismatch"
    return None


def run_audit() -> dict[str, Any]:
    src = _AUDITOR_SRC.read_text(encoding="utf-8")
    battery = _battery()

    baseline_res = _run_battery(_load_auditor(src), battery)
    results: list[dict[str, Any]] = []
    for mut in _MUTATIONS:
        count = src.count(mut.old)
        if count != 1:
            results.append({"name": mut.name, "outcome": "ERROR", "detail": f"old x{count}"})
            continue
        kill = _run_battery(_load_auditor(src.replace(mut.old, mut.new)), battery)
        outcome = "killed" if kill is not None else "survived"
        results.append(
            {
                "name": mut.name,
                "outcome": outcome,
                "expected": mut.expected,
                "killed_by": kill[0] if kill else None,
                "kill_kind": kill[1] if kill else None,
                "match": (outcome == "killed") == (mut.expected == "killed"),
                "rationale": mut.rationale,
            }
        )

    killed = [r for r in results if r["outcome"] == "killed"]
    equivalent = [r for r in results if r.get("expected") == "equivalent"]
    unexpected = [r for r in results if not r.get("match", False) and r["outcome"] != "ERROR"]
    errors = [r for r in results if r["outcome"] == "ERROR"]
    crashed = [
        r for r in results if r.get("kill_kind") == "crash"
    ]  # kills not via routing mismatch
    return {
        "baseline_ok": baseline_res is None,
        "baseline_fail": baseline_res[0] if baseline_res else None,
        "total": len(_MUTATIONS),
        "killed": len(killed),
        "survived": len([r for r in results if r["outcome"] == "survived"]),
        "equivalent_documented": len(equivalent),
        "unexpected": unexpected,
        "errors": errors,
        "crashed": crashed,
        "results": results,
    }


def _render(report: dict[str, Any]) -> str:
    lines = ["# §6 mutation audit — agents/auditor.py (Layer b/c routing)", ""]
    lines.append(f"Baseline battery passes: **{report['baseline_ok']}**")
    lines.append(
        f"Mutations: **{report['total']}** | killed: **{report['killed']}** | "
        f"survived: **{report['survived']}** | unexpected: **{len(report['unexpected'])}** | "
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
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover
    rep = run_audit()
    out = _AUDITOR_SRC.parents[3] / "docs" / "sec6_auditor_mutation_audit.md"
    out.write_text(_render(rep), encoding="utf-8")
    print(_render(rep))
    print(f"Wrote {out}")
