"""§18.8: CI guard for the document-sanitizer mutation audit.

Asserts every block-weakening mutation of document/sanitizer.py (disabled JS /
attachment / form-action / URI / metadata-injection / metadata-URL blocks, disabled
content floor, disabled unicode-trick strip) is caught by the §18.8 invariant battery
— a malicious RawDocument raises DocumentBlockedError with the right reason, a clean
one returns a SanitizedDocument, tricks are stripped. A future change that weakens the
sanitizer OR its coverage so a mutation survives fails here. Fast + $0.
"""

from __future__ import annotations

from scripts.sec18_sanitizer_mutation_audit import run_audit


def test_sec18_sanitizer_mutation_audit_all_block_weakenings_killed() -> None:
    rep = run_audit()
    assert rep["baseline_ok"], f"baseline battery failed at case {rep['baseline_fail']!r}"
    assert rep["errors"] == [], f"stale mutation targets (source refactor?): {rep['errors']}"
    assert rep["unexpected"] == [], f"unexpected mutation outcomes: {rep['unexpected']}"
    assert (
        rep["crashed"] == []
    ), f"mutations killed by crash, not a §18.8 mismatch: {rep['crashed']}"
    # Per-member unicode-trick coverage (§18.8 review, high): every trick-set member
    # needs a strip case, else dropping it (e.g. the RLO bidi-override) survives.
    assert (
        rep["uncovered_tricks"] == []
    ), f"_UNICODE_TRICKS members with no strip case: {rep['uncovered_tricks']}"
    assert rep["killed"] == rep["total"] - rep["equivalent_documented"]
    assert rep["killed"] >= 11  # block-weakening + per-member trick + audit-log mutations
