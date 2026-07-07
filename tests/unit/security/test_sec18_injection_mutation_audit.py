"""§18: CI guard for the prompt-injection detection mutation audit.

Asserts every detection-weakening mutation of security/injection.py (disabled mode
dispatch, dropped case-insensitivity, removed pattern alternatives, regex typos,
over-detection) is caught by the §18 invariant battery — known attacks detected,
benign queries not. A future change that weakens the detector OR its coverage so a
mutation survives fails here. Fast + $0 (exec's injection.py in-process; no model).
"""

from __future__ import annotations

from scripts.sec18_injection_mutation_audit import run_audit


def test_sec18_injection_mutation_audit_all_weakenings_killed() -> None:
    rep = run_audit()
    assert rep["baseline_ok"], f"baseline battery failed at case {rep['baseline_fail']!r}"
    assert rep["errors"] == [], f"stale mutation targets (source refactor?): {rep['errors']}"
    assert rep["unexpected"] == [], f"unexpected mutation outcomes: {rep['unexpected']}"
    assert (
        rep["crashed"] == []
    ), f"mutations killed by crash, not detection mismatch: {rep['crashed']}"
    # Full per-pattern coverage (§18 review, high): every named pattern must have a
    # payload — else a mutation neutering it survives untested, and a newly-added
    # pattern could ship with no test.
    assert (
        rep["uncovered_patterns"] == []
    ), f"patterns with no battery payload: {rep['uncovered_patterns']}"
    assert rep["killed"] == rep["total"] - rep["equivalent_documented"]
    assert rep["killed"] >= 9  # regression anchor on the detection mutation set
