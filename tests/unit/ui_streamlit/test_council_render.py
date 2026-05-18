"""H13 — tests for the real per-judge projection seam in _render.py.

Pure unit tests for _council_judge_rows; no Streamlit runtime required.
Verifies redaction contract (exact key set) and auditable-evidence retention
(reason + error_category round-trip).
"""

from __future__ import annotations

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote
from regulaitor.ui_streamlit._render import _council_judge_rows

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_JUDGE_OK = JudgeVote(
    model_id="claude-haiku-4-5",
    provider="anthropic",
    vote=AuditVerdict.BLOCK,
    reason="no soporta",
    ok=True,
    error_category=None,
)

_JUDGE_FAIL = JudgeVote(
    model_id="gpt-4o-mini",
    provider="openai",
    vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
    reason="judge_failed",
    ok=False,
    error_category="RuntimeError",
)

_REVIEW_TWO = CouncilReview(
    triggered=True,
    trigger_reason="auditor_rhr",
    judges=[_JUDGE_OK, _JUDGE_FAIL],
    council_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
    agreement="split",
    diverges_from_auditor=True,
    reason="split vote",
)

_REVIEW_EMPTY = CouncilReview(
    triggered=False,
    trigger_reason="not_triggered",
    judges=[],
    council_verdict=AuditVerdict.PASS,
    agreement="unanimous",
    diverges_from_auditor=False,
    reason="not triggered",
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_EXPECTED_KEYS = {"model_id", "provider", "vote", "ok", "error_category", "reason"}


def test_judge_rows_redacted_field_set() -> None:
    """Each row exposes EXACTLY the declared keys — no extra/leaking fields."""
    rows = _council_judge_rows(_REVIEW_TWO)
    assert len(rows) == 2
    for row in rows:
        assert set(row.keys()) == _EXPECTED_KEYS, f"Unexpected keys: {set(row.keys())}"


def test_judge_rows_retains_reason_and_error_category() -> None:
    """Auditable evidence: reason strings are present; error_category round-trips."""
    rows = _council_judge_rows(_REVIEW_TWO)

    ok_row = rows[0]
    assert ok_row["vote"] == "block", "vote must be the StrEnum .value string"
    assert ok_row["reason"] == "no soporta"
    assert ok_row["error_category"] is None
    assert ok_row["ok"] is True

    fail_row = rows[1]
    assert fail_row["vote"] == "requires_human_review"
    assert fail_row["reason"] == "judge_failed"
    assert fail_row["error_category"] == "RuntimeError"
    assert fail_row["ok"] is False


def test_judge_rows_empty() -> None:
    """CouncilReview with no judges returns an empty list."""
    assert _council_judge_rows(_REVIEW_EMPTY) == []
