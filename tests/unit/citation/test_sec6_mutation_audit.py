"""P1.3b: CI guard for the §6 mutation audit.

Runs the in-process mutation audit (scripts/sec6_mutation_audit.py) and asserts
that every §6-weakening mutation of citation/validator.py is caught by the
validator's invariant battery. A future edit that weakens the validator OR the
battery — so that a mutation survives unexpectedly — fails here. Fast + $0
(exec's the validator source in-process; no model, no LanceDB).
"""

from __future__ import annotations

from scripts.sec6_mutation_audit import run_audit


def test_sec6_mutation_audit_all_weakenings_killed() -> None:
    rep = run_audit()
    assert rep["baseline_ok"], f"baseline battery failed at case {rep['baseline_fail']!r}"
    assert rep["errors"] == [], f"stale mutation targets (source refactor?): {rep['errors']}"
    assert rep["unexpected"] == [], f"unexpected mutation outcomes: {rep['unexpected']}"
    # Every non-equivalent mutation must be killed by the battery.
    assert rep["killed"] == rep["total"] - rep["equivalent_documented"]
    assert rep["killed"] >= 11  # regression anchor (§6-review-strengthened mutation set)
