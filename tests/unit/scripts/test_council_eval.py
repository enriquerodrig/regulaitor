from __future__ import annotations

from scripts.council_eval import summarize_divergence

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote


def _row(auditor, council, diverges, triggered_auto):
    cr = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr" if triggered_auto else "api_override",
        judges=[
            JudgeVote(
                model_id="m",
                provider="p",
                vote=council,
                reason="r",
                ok=True,
                error_category=None,
            )
        ],
        council_verdict=council,
        agreement="degraded",
        diverges_from_auditor=diverges,
        reason="x",
    )
    return {"auditor_verdict": auditor, "council": cr}


def test_summarize_counts_subset_and_divergence():
    rows = [
        _row(AuditVerdict.PASS, AuditVerdict.BLOCK, True, True),
        _row(AuditVerdict.PASS, AuditVerdict.PASS, False, False),
        _row(AuditVerdict.REQUIRES_HUMAN_REVIEW, AuditVerdict.BLOCK, True, True),
    ]
    s = summarize_divergence(rows)
    assert s["n_total"] == 3
    assert s["n_auto_triggered"] == 2
    assert s["n_diverged"] == 2
    assert s["n_auditor_pass_council_flagged"] == 1
    assert s["n_selected"] == 3  # default: len(rows) when not passed
    assert s["n_skipped"] == 0


def test_summarize_empty_rows_all_zero():
    s = summarize_divergence([])
    assert s["n_total"] == 0
    assert s["n_auto_triggered"] == 0
    assert s["n_diverged"] == 0
    assert s["n_auditor_pass_council_flagged"] == 0
    assert s["n_selected"] == 0
    assert s["n_skipped"] == 0

    # explicit n_selected/n_skipped when all cases were skipped
    s2 = summarize_divergence([], n_selected=5, n_skipped=5)
    assert s2["n_total"] == 0
    assert s2["n_selected"] == 5
    assert s2["n_skipped"] == 5


def test_rhr_auditor_pass_council_not_flagged():
    """Flagged-count is gated on auditor==PASS; an RHR auditor must NOT increment it."""
    row = _row(AuditVerdict.REQUIRES_HUMAN_REVIEW, AuditVerdict.PASS, True, True)
    s = summarize_divergence([row])
    assert s["n_auditor_pass_council_flagged"] == 0
