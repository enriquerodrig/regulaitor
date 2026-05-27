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


def _all_blocked_findings_paraphrase_only(
    finding_verdicts: list[Literal["pass", "blocked"]],
    per_finding_results: list[list[AuditResult]],
) -> bool:
    """v0.1.25 (ADR-0032 Design H D2) + v0.1.29 (ADR-0034 Design D Mirror):
    True iff every blocked Finding has all its invalid citations with
    failed_check==3 (paraphrase mismatch only). Used by BOTH:
    - v0.1.25 partial-Findings routing (PASS-Finding + blocked-Finding mix):
      PASS if True else RHR
    - v0.1.29 all-blocked-Findings routing (every Finding blocked):
      PASS if True else BLOCK

    Returns False if ANY blocked Finding has ANY invalid citation with
    failed_check==1 (article fabrication) or failed_check==2 (apartado
    fabrication) — those indicate true §6-relevant fabrication and must
    preserve the original BLOCK/RHR routing.

    Pre-v0.1.24 cached AuditResults have failed_check=None (Pydantic v2
    default); those are treated as 'unknown' and the function returns
    False (conservative; preserves pre-v0.1.25 routing for legacy data).
    """
    blocked_indices = [i for i, v in enumerate(finding_verdicts) if v == "blocked"]
    for i in blocked_indices:
        for r in per_finding_results[i]:
            if r.validated:
                continue  # pass-citations don't count for blocked-Finding analysis
            if r.failed_check != 3:
                return False  # any non-Check-3 invalid → fabrication evidence
    return True


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

        # Strict: Answer aggregates.
        # v0.1.21 (ADR-0027 D1): per-citation RHR quorum semantics. Count
        # invalid citations across ALL citations in the answer; only escalate
        # to turn-level RHR when >=2 per-citation validations failed.
        # A single isolated invalid citation no longer forces turn-RHR —
        # addresses the dominant v0.1.20 T6.5 "nonempty-RHR-still-RHR" pattern
        # (42% of v1.0 RHR cases) without weakening §6 (per-citation
        # validation in citation/validator.py is byte-unchanged).
        # v0.1.23 ADR-0030 Design B (LENIENT quorum-counting based on
        # article+apartado existence only) was ACCEPTED then REVERTED post-T6
        # empirical refutation (verdict_match regressed -0.03 vs predicted
        # +0.10; 0/10 H1-predicted cases flipped RHR -> PASS; 2/10 unexpectedly
        # moved RHR -> BLOCK). §6 invariant HELD throughout (validator + Finding-
        # Lenient unchanged) but Design B failed outcome equivalence — Tier 1
        # quorum was NOT the bottleneck for H1 cases as the v0.1.22.1 diagnostic
        # had inferred. See ADR-0030 §REVERT for the empirical narrative.
        n_invalid_citations = sum(1 for r in all_results if not r.validated)
        verdict: AuditVerdict
        reason: str | None
        if not finding_verdicts or all(v == "pass" for v in finding_verdicts):
            # Tier 1 quorum branch (ADR-0027 D1, v0.1.21).
            # All findings pass at the Finding level (Lenient-Finding was generous).
            # But if >=2 citations are invalid even within passing Findings,
            # escalate to RHR via quorum logic.
            if n_invalid_citations >= 2:
                verdict = AuditVerdict.REQUIRES_HUMAN_REVIEW
                reason = _aggregate_reason(
                    answer, all_results, per_finding_results, "REQUIRES_HUMAN_REVIEW"
                )
            else:
                verdict, reason = AuditVerdict.PASS, None
        elif all(v == "blocked" for v in finding_verdicts):
            # All-blocked routing branch (ADR-0034 D Mirror, v0.1.29).
            # v0.1.29 (ADR-0034, Design D Mirror of v0.1.25 D2): all-blocked
            # routing softening. Relax all-blocked → PASS only when ALL blocked
            # Findings have all-invalid citations failed_check==3 (paraphrase
            # mismatch only; ZERO fabrication evidence — article + apartado
            # exist in corpus, only text-match differs). Any blocked Finding
            # with at least one Check 1 (article fab) or Check 2 (apartado fab)
            # failure → preserve pre-v0.1.29 all-blocked → BLOCK routing
            # (fabrication still caught by construction). Targets v0.1.25 paid
            # chat-016 pattern (gold=pass, actual=BLOCK; 3/3 citations failed
            # validator with paraphrase-only Check 3 failures) + Bucket B
            # similar cases. §6 invariant: validator + Finding-Lenient layers
            # BYTE-UNCHANGED; only Turn-level all-blocked sub-route modified.
            if _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results):
                verdict = AuditVerdict.PASS
                reason = None
            else:
                verdict = AuditVerdict.BLOCK
                reason = _aggregate_reason(answer, all_results, per_finding_results, "BLOCK")
        else:
            # Partial-Findings routing branch (ADR-0032 D2, v0.1.25).
            # v0.1.25 (ADR-0032, Design H D2): partial-Findings routing softening.
            # Relax partial → PASS only when ALL blocked Findings have all-invalid
            # citations failed_check==3 (paraphrase mismatch only; ZERO fabrication
            # evidence). Any blocked Finding with at least one Check 1 (article
            # fab) or Check 2 (apartado fab) failure → preserve pre-v0.1.25
            # partial→RHR routing. Targets v0.1.24.1 Path B DOMINANT finding
            # (Strict-Answer routing is empirical gatekeeper for 8/10 H1.C cases).
            if _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results):
                verdict = AuditVerdict.PASS
                reason = None
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
