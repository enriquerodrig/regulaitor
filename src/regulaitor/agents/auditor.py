"""AuditorAgent — pure-Python Lenient-strict aggregator over H3 validator (lean H4).

Decisions log 2026-05-05 entries: "Auditor lean en H4" + "Aggregation policy: Lenient-strict".
H13 may add LLM-based Auditor for high-severity cases; H4 stays mechanical.
"""

from __future__ import annotations

from typing import Literal

from regulaitor.citation import validator
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
)


class AuditorAgent:
    """Validate every Citation in the Answer; aggregate verdict per Lenient-strict."""

    def audit(self, answer: Answer) -> AuditedAnswer:
        all_results: list[AuditResult] = []
        per_finding_results: list[list[AuditResult]] = []  # parallel to answer.findings
        finding_verdicts: list[Literal["pass", "blocked"]] = []

        for finding in answer.findings:
            this_finding_results = [validator.validate(c) for c in finding.citations]
            all_results.extend(this_finding_results)
            per_finding_results.append(this_finding_results)
            # Lenient: Finding passes if >=1 of its citations validates
            finding_verdicts.append(
                "pass" if any(r.validated for r in this_finding_results) else "blocked"
            )

        # Strict: Answer aggregates
        verdict: AuditVerdict
        reason: str | None
        if not finding_verdicts or all(v == "pass" for v in finding_verdicts):
            verdict, reason = AuditVerdict.PASS, None
        elif all(v == "blocked" for v in finding_verdicts):
            verdict = AuditVerdict.BLOCK
            reason = _aggregate_reason(answer, all_results, per_finding_results, "BLOCK")
        else:
            verdict = AuditVerdict.REQUIRES_HUMAN_REVIEW
            reason = _aggregate_reason(
                answer, all_results, per_finding_results, "REQUIRES_HUMAN_REVIEW"
            )

        return AuditedAnswer(
            answer=answer,
            verdict=verdict,
            audit_results=all_results,
            reason=reason,
        )


def _aggregate_reason(
    answer: Answer,
    all_results: list[AuditResult],
    per_finding_results: list[list[AuditResult]],
    verdict_prefix: str,
) -> str:
    """Build human-readable summary referencing per-Finding outcomes.

    Per-Finding citation reasons are joined with ' | ' (validator never emits this
    separator, ensuring downstream parsers can split unambiguously).

    Format example:
    "REQUIRES_HUMAN_REVIEW: 2 of 5 citations invalid. Finding #2: 2 of 2 citations
    invalid (text_not_in_apartado: ai_act art. 6.2 | text_not_in_apartado: ai_act art. 6.3)."
    """
    n_invalid = sum(1 for r in all_results if not r.validated)
    n_total = len(all_results)
    parts = [f"{verdict_prefix}: {n_invalid} of {n_total} citations invalid."]

    for idx, finding_results in enumerate(per_finding_results, start=1):
        bad = [r for r in finding_results if not r.validated]
        if bad:
            reasons_str = " | ".join(r.reason or "no-reason" for r in bad)
            parts.append(
                f"Finding #{idx}: {len(bad)} of {len(finding_results)} "
                f"citations invalid ({reasons_str})."
            )

    return " ".join(parts)
