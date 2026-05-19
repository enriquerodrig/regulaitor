# tests/unit/test_h15_run.py
from __future__ import annotations

import os
from pathlib import Path

import pytest
import scripts.h15_run as h15


def test_env_seam_set_and_restored(tmp_path: Path, monkeypatch) -> None:
    cf = tmp_path / "ids.txt"
    cf.write_text("# header comment — must be skipped\n\nchat-001\n", encoding="utf-8")
    seen: dict[str, object] = {}

    def _fake_main(**kw: object) -> None:
        seen["env"] = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")
        seen["case_ids"] = kw.get("case_ids")
        seen["subset"] = kw.get("subset")

    monkeypatch.setattr(h15, "_harness_main", _fake_main)
    monkeypatch.setattr(h15, "_isolate_report", lambda tag: None)
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)
    h15.run(version="v1.1", cases_file=cf, tag="t", limit=3)
    assert seen["env"] == "v1.1"  # set during the run
    assert seen["case_ids"] == {"chat-001"}  # # header + blank line skipped
    assert seen["subset"] == 3  # --limit threaded to subset
    assert "REGULAITOR_ANALYST_PROMPT_VERSION" not in os.environ  # restored (was unset)


def test_env_restored_to_prior_value(tmp_path: Path, monkeypatch) -> None:
    cf = tmp_path / "ids.txt"
    cf.write_text("chat-001\n", encoding="utf-8")
    monkeypatch.setattr(h15, "_harness_main", lambda **kw: None)
    monkeypatch.setattr(h15, "_isolate_report", lambda tag: None)
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v0.9")
    h15.run(version="v1.1", cases_file=cf, tag="t", limit=None)
    assert os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] == "v0.9"  # prior restored


# ---------------------------------------------------------------------------
# C2 — Contract tests for the REAL _isolate_report (no subprocess, no git).
# Mirrors tests/unit/scripts/test_ab_eval.py's _isolate_report test structure.
# ---------------------------------------------------------------------------


def test_isolate_report_snapshots_then_restores(monkeypatch, tmp_path: Path) -> None:
    """_isolate_report must copy latest.md to h15/<tag>.md BEFORE invoking the
    git baseline-restore, with ZERO real git or out-of-tmp disk effects.

    Strategy:
    - Redirect _REPORT_PATH to a tmp file with known bytes.
    - Redirect _H15_DIR to a tmp dir.
    - Replace subprocess.run with a call recorder (no real git executed).
    - Assert the snapshot file was written with the correct bytes.
    - Assert git restore was invoked exactly once with the right argv.
    - Assert the snapshot path uses the .md extension (not .tag or other suffix).
    """
    fake_report = tmp_path / "latest.md"
    fake_report.write_bytes(b"H15 RUN REPORT")
    monkeypatch.setattr(h15, "_REPORT_PATH", fake_report)

    h15_dir = tmp_path / "h15"
    monkeypatch.setattr(h15, "_H15_DIR", h15_dir)

    calls: list[tuple] = []

    def _record_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(h15.subprocess, "run", _record_run)

    h15._isolate_report("baseline-v1.0")

    # Snapshot must exist at <_H15_DIR>/baseline-v1.0.md with correct bytes.
    snapshot = h15_dir / "baseline-v1.0.md"
    assert snapshot.exists(), "snapshot file was not created"
    assert snapshot.read_bytes() == b"H15 RUN REPORT", "snapshot bytes do not match"

    # git restore must have been invoked exactly once with the correct argv.
    assert len(calls) == 1, f"expected 1 subprocess call, got {len(calls)}"
    invocation_args = calls[0][0][0]  # first positional arg to subprocess.run
    assert invocation_args == [
        "git",
        "checkout",
        "HEAD",
        "--",
        str(fake_report),
    ], f"unexpected git argv: {invocation_args}"
    # Verify timeout=30 was passed (I1 fix).
    assert calls[0][1].get("timeout") == 30, "timeout=30 must be passed to subprocess.run"


def test_isolate_report_absent_report_still_restores(monkeypatch, tmp_path: Path) -> None:
    """If the harness failed before writing latest.md, _isolate_report skips
    the snapshot but STILL invokes the baseline git-restore (defensive: leave
    the committed baseline clean regardless). Mirrors ab_eval's equivalent test."""
    missing_report = tmp_path / "latest.md"  # deliberately never created
    monkeypatch.setattr(h15, "_REPORT_PATH", missing_report)

    h15_dir = tmp_path / "h15"
    monkeypatch.setattr(h15, "_H15_DIR", h15_dir)

    calls: list[tuple] = []
    monkeypatch.setattr(h15.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    h15._isolate_report("baseline-v1.0")

    # No snapshot file must be written when latest.md is absent.
    assert not (
        h15_dir / "baseline-v1.0.md"
    ).exists(), "no snapshot must be written when latest.md is absent"
    # git restore must still be invoked exactly once.
    assert len(calls) == 1, "git baseline-restore must still be invoked exactly once"
    assert calls[0][0][0] == ["git", "checkout", "HEAD", "--", str(missing_report)]


# ---------------------------------------------------------------------------
# C1-followup — Crash-safety behavioral test: _isolate_report fires even when
# _harness_main raises, and the env is still restored afterward.
# ---------------------------------------------------------------------------


def test_isolate_report_runs_even_when_harness_crashes(tmp_path: Path, monkeypatch) -> None:
    """C1 fix: when _harness_main raises, _isolate_report is still called (inner
    finally), the original exception propagates, and the env var is still restored
    (outer finally).  Would fail against the OLD try/except structure where
    _isolate_report was called inline after _harness_main (no finally guard)."""
    cf = tmp_path / "ids.txt"
    cf.write_text("chat-001\n", encoding="utf-8")

    def _crashing_main(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(h15, "_harness_main", _crashing_main)

    isolate_calls: list[str] = []
    monkeypatch.setattr(h15, "_isolate_report", lambda tag: isolate_calls.append(tag))
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v0.9")

    with pytest.raises(RuntimeError, match="boom"):
        h15.run(version="v1.1", cases_file=cf, tag="crash-tag", limit=None)

    # _isolate_report must have been called despite the crash.
    assert isolate_calls == [
        "crash-tag"
    ], "_isolate_report was NOT called after _harness_main crashed"
    # env must be restored to its prior value.
    assert (
        os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] == "v0.9"
    ), "env var was not restored after crash"


# ---------------------------------------------------------------------------
# M1 — BOM path: _load_case_ids must strip UTF-8 BOM and skip comments/blanks.
# ---------------------------------------------------------------------------


def test_load_case_ids_strips_bom_and_comments(tmp_path: Path) -> None:
    """_load_case_ids uses utf-8-sig which silently strips a leading BOM.
    This test pins that behaviour (Task-2-hardening rationale) and verifies
    that comment lines (#) and blank lines are also skipped."""
    cf = tmp_path / "ids.txt"
    # Write a BOM-prefixed file (the ﻿ BOM is preserved by utf-8 encoding
    # but stripped by utf-8-sig on read).
    cf.write_text("﻿chat-001\n# ignored comment\n\nchat-002\n", encoding="utf-8")
    result = h15._load_case_ids(cf)
    assert result == {
        "chat-001",
        "chat-002",
    }, f"BOM and/or comment stripping failed: got {result!r}"
