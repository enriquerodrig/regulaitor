"""P1.3b (Layer b/c): CI guard for the Auditor §6-routing mutation audit.

Companion to tests/unit/citation/test_sec6_mutation_audit.py (Layer a). Asserts
every §6-routing weakening of auditor.py (softening fabrication, lenient-always-pass,
loosened quorum, misrouted branches) is caught by the routing-invariant battery. A
future change that weakens the Auditor OR its tests so a mutation survives fails here.
Fast + $0 (exec's auditor.py in-process with a fake validator; no model, no LanceDB).
"""

from __future__ import annotations

from scripts.sec6_auditor_mutation_audit import run_audit


def test_sec6_auditor_mutation_audit_all_routing_weakenings_killed() -> None:
    rep = run_audit()
    assert rep["baseline_ok"], f"baseline battery failed at case {rep['baseline_fail']!r}"
    assert rep["errors"] == [], f"stale mutation targets (source refactor?): {rep['errors']}"
    assert rep["unexpected"] == [], f"unexpected mutation outcomes: {rep['unexpected']}"
    # Kills must be genuine routing-invariant mismatches, not incidental crashes
    # (§6 review, low): a crash-kill would mask that the invariant was never exercised.
    assert (
        rep["crashed"] == []
    ), f"mutations killed by crash, not routing mismatch: {rep['crashed']}"
    assert rep["killed"] == rep["total"] - rep["equivalent_documented"]
    assert rep["killed"] >= 8  # regression anchor (§6-review-strengthened: + FAB2 blocked-path)
