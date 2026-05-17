"""Unit tests for scripts/ab_eval.py (no real LLM)."""

from __future__ import annotations

import os
from pathlib import Path

import scripts.ab_eval as ab


def test_arms_are_evaluation_and_cost_only() -> None:
    assert ab.AB_ARMS == [("evaluation", "gpt-4o"), ("cost", "llama-groq")]
    # Sonnet is intentionally NOT an arm (frozen baseline reused).
    assert all(arm[0] != "default" for arm in ab.AB_ARMS)


def test_run_arm_sets_and_clears_env(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def _fake_harness_main(**kwargs):
        seen["mode"] = os.environ.get("REGULAITOR_ROUTER_MODE")
        return None

    monkeypatch.setattr(ab, "_harness_main", _fake_harness_main)
    # Monkeypatch _isolate_report so no real git/filesystem mutation occurs in
    # this $0 env-contract unit test.
    monkeypatch.setattr(ab, "_isolate_report", lambda mode: None)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    ab.run_arm("evaluation", gold_set="evals/gold_set.jsonl", subset=2)
    assert seen["mode"] == "evaluation"
    # env restored after the arm
    assert os.environ.get("REGULAITOR_ROUTER_MODE") is None


def test_run_arm_restores_prior_env_value(monkeypatch) -> None:
    """If REGULAITOR_ROUTER_MODE was already set, run_arm restores that exact
    prior value (not just unset) after the arm."""
    monkeypatch.setattr(ab, "_harness_main", lambda **k: None)
    # Monkeypatch _isolate_report so no real git/filesystem mutation occurs in
    # this $0 env-contract unit test.
    monkeypatch.setattr(ab, "_isolate_report", lambda mode: None)
    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "quality")
    ab.run_arm("cost", gold_set="evals/gold_set.jsonl", subset=1)
    assert os.environ.get("REGULAITOR_ROUTER_MODE") == "quality"


def test_isolate_report_snapshots_and_restores_without_touching_repo(
    monkeypatch, tmp_path: Path
) -> None:
    """_isolate_report must copy latest.md to latest.<mode>.md and invoke the
    git baseline-restore command — with ZERO real git or out-of-tmp disk
    effects.

    Strategy:
    - Redirect _REPORT_PATH to a tmp_path file (no repo paths touched).
    - Replace subprocess.run with a call recorder (no real git executed).
    - Assert the per-arm snapshot was written with the correct bytes.
    - Assert the git baseline-restore was *invoked* with the right argv.
    """
    # Set up a fake latest.md in tmp_path.
    fake_report = tmp_path / "latest.md"
    fake_report.write_bytes(b"ARM REPORT")
    monkeypatch.setattr(ab, "_REPORT_PATH", fake_report)

    # Record subprocess calls instead of executing them.
    calls: list[tuple] = []

    def _record_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(ab.subprocess, "run", _record_run)

    ab._isolate_report("evaluation")

    # The per-arm snapshot must exist with the right content.
    arm_snapshot = tmp_path / "latest.evaluation.md"
    assert arm_snapshot.exists(), "per-arm snapshot file was not created"
    assert arm_snapshot.read_bytes() == b"ARM REPORT"

    # The git baseline-restore must have been invoked exactly once with the
    # correct argv (proves the call is made, without executing real git).
    assert len(calls) == 1, f"expected 1 subprocess call, got {len(calls)}"
    invocation_args = calls[0][0][0]  # first positional arg to subprocess.run
    assert invocation_args == [
        "git",
        "checkout",
        "HEAD",
        "--",
        str(ab._REPORT_PATH),
    ], f"unexpected git argv: {invocation_args}"


def test_isolate_report_no_snapshot_when_report_absent(monkeypatch, tmp_path: Path) -> None:
    """If the harness failed before writing latest.md, _isolate_report skips
    the per-arm snapshot but STILL invokes the baseline git-restore (defensive:
    leave the committed baseline clean regardless)."""
    missing_report = tmp_path / "latest.md"  # deliberately never created
    monkeypatch.setattr(ab, "_REPORT_PATH", missing_report)

    calls: list[tuple] = []
    monkeypatch.setattr(ab.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    ab._isolate_report("cost")

    assert not (
        tmp_path / "latest.cost.md"
    ).exists(), "no per-arm snapshot must be written when latest.md is absent"
    assert len(calls) == 1, "git baseline-restore must still be invoked exactly once"
    assert calls[0][0][0] == ["git", "checkout", "HEAD", "--", str(ab._REPORT_PATH)]
