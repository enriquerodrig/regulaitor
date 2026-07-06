"""CouncilAgent + aggregation policies (H13 → v0.1.19).

Advisory layer (H13): the Council records evidence. Under
``AdvisoryMajorityPolicy`` (H13 default; still available, used by callers
that pass it explicitly) the Council never mutates the deterministic
verdict — its review is recorded as ``council_review`` only.

Binding layer (v0.1.19, ADR-0025): the H15 promotion seam — module
constant ``_COUNCIL_BINDING`` together with ``MonotonicEscalatePolicy`` —
is now ON. ``CouncilAgent`` defaults to ``MonotonicEscalatePolicy`` and
the ``bind_verdict()`` helper below consumes ``would_escalate()`` to
promote PASS → RHR on a unanimous (3/3 ok) BLOCK vote. The policy never
relaxes BLOCK or RHR (conservative-only direction). The production-side
citation validator (``citation/validator.py``) and the Auditor's
Lenient-Finding + Strict-Answer aggregation (``agents/auditor.py``) are
byte-unchanged in v0.1.19; the §6 "no citation, no answer" invariant
operates at those layers and is unaffected.

Post-v0.1.25 / v0.1.29 note: the v0.1.25 D2 partial-routing softening and
the v0.1.29 D Mirror all-blocked routing softening (both in ``auditor.py``)
operate on the Auditor's Layer (c) turn-level aggregation policy and do
NOT remove Council's binding role. The Council still escalates PASS → RHR
on a unanimous (3/3 ok) BLOCK vote regardless of the partial / all-blocked
sub-route Auditor took to reach its mechanical verdict. The two layers are
orthogonal: aggregation softening (auditor.py) targets paraphrase-only
false-RHR/BLOCK; Council binding (this file) targets Auditor-PASS cases
that the panel unanimously disagrees with.
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

# H15 promotion seam, FLIPPED ON in v0.1.19 / ADR-0025. Production now uses
# MonotonicEscalatePolicy as the CouncilAgent default + the bind_verdict()
# helper below consumes would_escalate() to escalate PASS -> RHR on unanimous
# (3/3 ok) BLOCK vote. Never relaxes BLOCK or RHR (conservative-only direction;
# §6 invariant ROCK-SOLID).
_COUNCIL_BINDING: bool = True


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
_JUDGE_MODES: tuple[router.ModelChoice, router.ModelChoice, router.ModelChoice] = (
    "judge",
    "evaluation",
    "cost",
)

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
        # v0.1.19 / ADR-0025 D4: default policy changes from AdvisoryMajorityPolicy
        # to MonotonicEscalatePolicy. aggregate() behavior IDENTICAL (verified by
        # test_monotonic_aggregate_matches_advisory); the would_escalate() method
        # becomes available for bind_verdict() to consume.
        self._policy: AggregationPolicy = policy or MonotonicEscalatePolicy()
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

    def _one_judge(self, mode: router.ModelChoice, payload: str) -> JudgeVote:
        target = router._MODE_MAP[mode]
        # Sovereign profile (docs/sovereign_deploy.md §4 G2): skip a judge whose
        # (override-aware) provider has no API key — e.g. the US judge modes when
        # a sovereign deploy omits ANTHROPIC/OPENAI/GROQ keys. A skipped judge is
        # a not-ok vote, so the degrade-safe aggregation is unchanged (the
        # Auditor's mechanical verdict stands), but there is no doomed call nor an
        # ERROR-level traceback per turn for an expected, benign condition.
        eff_provider = router.effective_provider(mode)
        if not router.provider_key_present(eff_provider):
            # Label with the EFFECTIVE provider (not the nominal judge's) so an
            # operator sees WHICH key is actually missing — under the global
            # self_hosted override that is `selfhost`, not anthropic/openai/groq.
            logger.debug("council judge %s skipped: %s key absent", mode, eff_provider)
            return JudgeVote(
                model_id=target.model_id,
                provider=eff_provider,
                vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                reason=f"judge_skipped_no_key:{eff_provider}",
                ok=False,
                error_category="provider_key_absent",
            )
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
            # Deep-review minor (code-quality): logger.exception() preserves the
            # full traceback (vs warning(type(e).__name__) which dropped both
            # the message and traceback). error_category in the returned JudgeVote
            # keeps the class name available for downstream callers.
            logger.exception("council judge %s failed", mode)
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


# ---------------------------------------------------------------------------
# v0.1.19 / ADR-0025 — Council binding helper
# ---------------------------------------------------------------------------


def bind_verdict(
    audited: AuditedAnswer,
    review: CouncilReview,
    council: CouncilAgent,
) -> AuditedAnswer | None:
    """Apply Council binding to the audited verdict (v0.1.19 / ADR-0025).

    Returns a new AuditedAnswer with the escalated verdict + a
    "COUNCIL_BIND:"-prefixed reason iff:
    1. _COUNCIL_BINDING is True (module flag; True in v0.1.19+).
    2. The CouncilAgent's policy exposes a would_escalate(audited_verdict,
       judges) -> AuditVerdict method (MonotonicEscalatePolicy in v0.1.19).
    3. The policy's would_escalate returns a verdict that differs from the
       current audited.verdict.

    Returns None when no binding fires (the common case — Auditor verdict
    stands). The orchestration node uses None to mean "keep the existing
    audited_answer".

    Per ADR-0025 D1: the MonotonicEscalatePolicy is conservative-only
    (PASS -> RHR on unanimous BLOCK; NEVER relaxes BLOCK or RHR), so this
    helper can never WEAKEN a verdict — only escalate.

    Signature design (ADR-0025 D3 / brainstorming Q5): takes the
    CouncilAgent (not the policy directly). Keeps the private-access
    concern (council._policy) INTERNAL to council.py. Orchestration's
    call site is fully public-API.
    """
    if not _COUNCIL_BINDING:
        return None
    policy = council._policy  # private access INSIDE same module — clean
    would_escalate_fn = getattr(policy, "would_escalate", None)
    if would_escalate_fn is None:
        return None
    new_verdict = would_escalate_fn(audited.verdict, review.judges)
    if new_verdict == audited.verdict:
        return None
    # Binding fires. Build a new reason that preserves the original auditor
    # reason (if any) for audit-trail clarity.
    n_block = sum(1 for v in review.judges if v.ok and v.vote == AuditVerdict.BLOCK)
    n_ok = sum(1 for v in review.judges if v.ok)
    original_reason = audited.reason if audited.reason else "None"
    new_reason = (
        f"COUNCIL_BIND: {n_block}/{n_ok} judges voted BLOCK; "
        f"promoted {audited.verdict.value} -> {new_verdict.value}. "
        f"Original auditor reason: {original_reason}."
    )
    return AuditedAnswer(
        answer=audited.answer,
        verdict=new_verdict,
        audit_results=audited.audit_results,
        reason=new_reason,
    )
