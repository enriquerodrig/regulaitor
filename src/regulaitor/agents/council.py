"""CouncilAgent + aggregation policies (H13).

Advisory layer: the Council records evidence and NEVER mutates the
deterministic verdict in H13. The H15 promotion seam is the module
constant ``_COUNCIL_BINDING`` (kept False here) together with
``MonotonicEscalatePolicy`` (added in a later task): while the seam is
off, the graph node only records the Council outcome and never lets it
change the verdict.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Literal, Protocol

from regulaitor.citation.schemas import (
    AuditedAnswer,
    AuditVerdict,
    Context,
    CouncilReview,
    Finding,
    JudgeVote,
)
from regulaitor.models import router

AgreementLabel = Literal["unanimous", "majority", "split", "degraded"]

# H15 promotion seam. Flipping this True + selecting MonotonicEscalatePolicy
# is the entire promotion to a binding gate (see decisions log §H13).
_COUNCIL_BINDING: bool = False


class AggregationPolicy(Protocol):
    def aggregate(self, votes: list[JudgeVote]) -> tuple[AuditVerdict, AgreementLabel]: ...


def _modal_verdict(ok_votes: list[JudgeVote]) -> tuple[AuditVerdict, int]:
    """Most common vote among ok votes + its count. Empty -> (RHR, 0)."""
    if not ok_votes:
        return AuditVerdict.REQUIRES_HUMAN_REVIEW, 0
    counts = Counter(v.vote for v in ok_votes)
    verdict, n = counts.most_common(1)[0]
    return verdict, n


class AdvisoryMajorityPolicy:
    """Default H13 policy. Verdict = modal vote iff >=2 ok votes agree,
    else REQUIRES_HUMAN_REVIEW. Label precedence: degraded if <3 ok;
    else unanimous if all 3 agree; else majority if exactly 2 agree;
    else split."""

    def aggregate(self, votes: list[JudgeVote]) -> tuple[AuditVerdict, AgreementLabel]:
        ok = [v for v in votes if v.ok]
        modal, n_modal = _modal_verdict(ok)
        verdict = modal if n_modal >= 2 else AuditVerdict.REQUIRES_HUMAN_REVIEW
        if len(ok) < 3:
            return verdict, "degraded"
        if n_modal == 3:
            return modal, "unanimous"
        if n_modal == 2:
            return modal, "majority"
        return AuditVerdict.REQUIRES_HUMAN_REVIEW, "split"


class MonotonicEscalatePolicy:
    """H15 promotion seam (implemented + tested, NOT wired in H13).

    `aggregate` is identical to AdvisoryMajorityPolicy. `would_escalate`
    is the future binding rule: escalate PASS->REQUIRES_HUMAN_REVIEW only
    on a unanimous (all-ok, >=3) BLOCK vote; NEVER relax a BLOCK. The
    graph node never calls would_escalate while _COUNCIL_BINDING is False.
    """

    def aggregate(self, votes: list[JudgeVote]) -> tuple[AuditVerdict, AgreementLabel]:
        return AdvisoryMajorityPolicy().aggregate(votes)

    def would_escalate(self, audited_verdict: AuditVerdict, votes: list[JudgeVote]) -> AuditVerdict:
        if audited_verdict != AuditVerdict.PASS:
            return audited_verdict  # never relax BLOCK / RHR
        ok = [v for v in votes if v.ok]
        if len(ok) >= 3 and all(v.vote == AuditVerdict.BLOCK for v in ok):
            return AuditVerdict.REQUIRES_HUMAN_REVIEW
        return AuditVerdict.PASS


# ---------------------------------------------------------------------------
# T7 — CouncilAgent (3-judge advisory, degrade-safe)
# ---------------------------------------------------------------------------

logger = logging.getLogger("regulaitor.agents.council")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "council" / "judge.v1.0.md"
_JUDGE_MODES: tuple[str, str, str] = ("judge", "evaluation", "cost")

_VOTE_TOOL = {
    "name": "cast_vote",
    "description": "Cast the judge's single global vote on the findings under review.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "vote": {
                "type": "string",
                "enum": ["valid", "invalid", "requires_human_review"],
            },
            "reason": {"type": "string"},
        },
        "required": ["vote", "reason"],
    },
}

# Judge vote vocabulary -> AuditVerdict.
_VOTE_MAP = {
    "valid": AuditVerdict.PASS,
    "invalid": AuditVerdict.BLOCK,
    "requires_human_review": AuditVerdict.REQUIRES_HUMAN_REVIEW,
}


class CouncilAgent:
    """Advisory 3-judge council. Never mutates the verdict in H13."""

    def __init__(self, policy: AggregationPolicy | None = None) -> None:
        self._policy: AggregationPolicy = policy or AdvisoryMajorityPolicy()
        self._system = _PROMPT_PATH.read_text(encoding="utf-8")

    def _findings_under_review(self, audited: AuditedAnswer) -> list[Finding]:
        invalid_citations = {r.citation for r in audited.audit_results if not r.validated}
        selected = [
            f
            for f in audited.answer.findings
            if f.severity == "high"
            or (
                audited.verdict != AuditVerdict.PASS
                and any(c in invalid_citations for c in f.citations)
            )
        ]
        return selected or list(audited.answer.findings)

    def _user_payload(self, audited: AuditedAnswer, context: Context) -> str:
        findings = self._findings_under_review(audited)
        return json.dumps(
            {
                "answer_text": audited.answer.text,
                "findings_under_review": [
                    {
                        "text": f.text,
                        "citations": [
                            {
                                "norma": str(c.norma),
                                "articulo": c.articulo,
                                "apartado": c.apartado,
                                "text": c.text,
                            }
                            for c in f.citations
                        ],
                        "severity": f.severity,
                    }
                    for f in findings
                ],
                "audit_results": [
                    {"validated": r.validated, "reason": r.reason} for r in audited.audit_results
                ],
                "retrieved_context": [
                    {
                        "articulo": ch.articulo,
                        "apartado": ch.apartado,
                        "text": ch.text,
                    }
                    for ch in context.chunks
                ],
            },
            ensure_ascii=False,
        )

    def _one_judge(self, mode: str, payload: str) -> JudgeVote:
        target = router._MODE_MAP[mode]
        try:
            result = router.complete(
                messages=[{"role": "user", "content": payload}],
                system=self._system,
                tools=[_VOTE_TOOL],
                tool_choice={"type": "tool", "name": "cast_vote"},
                model_choice=mode,
                max_tokens=600,
            )
            data = result.tool_use_input
            if not isinstance(data, dict) or data.get("vote") not in _VOTE_MAP:
                raise ValueError(f"judge {mode} emitted no valid vote")
            return JudgeVote(
                model_id=result.model_id,
                provider=target.provider,
                vote=_VOTE_MAP[data["vote"]],
                reason=str(data.get("reason", ""))[:500],
                ok=True,
                error_category=None,
            )
        except Exception as e:  # advisory: never break the turn
            logger.warning("council judge %s failed: %s", mode, type(e).__name__)
            return JudgeVote(
                model_id=target.model_id,
                provider=target.provider,
                vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                reason="judge_failed",
                ok=False,
                error_category=type(e).__name__,
            )

    def review(
        self,
        audited: AuditedAnswer,
        context: Context,
        *,
        trigger_reason: Literal["auditor_rhr", "high_severity", "api_override"],
    ) -> CouncilReview:
        payload = self._user_payload(audited, context)
        votes = [self._one_judge(m, payload) for m in _JUDGE_MODES]
        verdict, label = self._policy.aggregate(votes)
        n_ok = sum(1 for v in votes if v.ok)
        reason = (
            "council_unavailable: 0/3 judges responded"
            if n_ok == 0
            else f"{n_ok}/3 judges ok; {label} -> {verdict.value}"
        )
        return CouncilReview(
            triggered=True,
            trigger_reason=trigger_reason,
            judges=votes,
            council_verdict=verdict,
            agreement=label,
            diverges_from_auditor=verdict != audited.verdict,
            reason=reason,
        )
