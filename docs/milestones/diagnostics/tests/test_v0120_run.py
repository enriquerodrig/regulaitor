"""$0 unit tests for scripts/v0120_run.py — verify env routing + isolation contract.

Mirrors tests/unit/scripts/test_h15_run.py if it exists; otherwise these tests
provide the same coverage shape: id loader, env set/restore, isolate stubbed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from scripts import v0120_run


def test_load_case_ids_strips_comments_and_blanks(tmp_path: Path) -> None:
    f = tmp_path / "ids.txt"
    f.write_text(
        "# header\nchat-001\n\nchat-002\n  # indented comment\nchat-003\n", encoding="utf-8"
    )
    ids = v0120_run._load_case_ids(f)
    assert ids == {"chat-001", "chat-002", "chat-003"}


def test_load_case_ids_handles_utf8_bom(tmp_path: Path) -> None:
    f = tmp_path / "ids.txt"
    # UTF-8 BOM + ids
    f.write_bytes(b"\xef\xbb\xbf# header\nchat-001\nchat-002\n")
    ids = v0120_run._load_case_ids(f)
    assert ids == {"chat-001", "chat-002"}


def test_run_sets_env_then_restores_prior(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prior env value: ensure it's restored, not lost.
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v1.3")
    # Mock the harness + isolation to no-ops; we test ONLY the env contract.
    observed: dict[str, str | None] = {}

    def fake_harness(*, subset: int | None, case_ids: set[str] | None) -> None:
        observed["during_run"] = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")

    monkeypatch.setattr(v0120_run, "_harness_main", fake_harness)
    monkeypatch.setattr(v0120_run, "_isolate_report", lambda tag: None)

    cases_file = tmp_path / "ids.txt"
    cases_file.write_text("chat-001\n", encoding="utf-8")

    v0120_run.run(version="v1.4", cases_file=cases_file, tag="test-tag")

    assert observed["during_run"] == "v1.4"  # env was set during harness call
    # Env was restored to prior value, not lost or set to v1.4.
    assert os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION") == "v1.3"


def test_run_sets_env_then_unsets_when_prior_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Prior env value: UNSET. After run, env must remain UNSET (not stuck at v1.4).
    monkeypatch.delenv("REGULAITOR_ANALYST_PROMPT_VERSION", raising=False)

    monkeypatch.setattr(v0120_run, "_harness_main", lambda *, subset, case_ids: None)
    monkeypatch.setattr(v0120_run, "_isolate_report", lambda tag: None)

    cases_file = tmp_path / "ids.txt"
    cases_file.write_text("chat-001\n", encoding="utf-8")

    v0120_run.run(version="v1.0", cases_file=cases_file, tag="test-tag")

    assert "REGULAITOR_ANALYST_PROMPT_VERSION" not in os.environ


def test_run_restores_env_even_on_harness_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REGULAITOR_ANALYST_PROMPT_VERSION", "v1.2")

    def crashy_harness(*, subset: int | None, case_ids: set[str] | None) -> None:
        raise RuntimeError("simulated mid-run crash")

    monkeypatch.setattr(v0120_run, "_harness_main", crashy_harness)
    # _isolate_report still called per finally; mock it to no-op so it doesn't
    # try to git-checkout in the test.
    monkeypatch.setattr(v0120_run, "_isolate_report", lambda tag: None)

    cases_file = tmp_path / "ids.txt"
    cases_file.write_text("chat-001\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="simulated mid-run crash"):
        v0120_run.run(version="v1.4", cases_file=cases_file, tag="test-tag")

    # Env STILL restored even though harness raised.
    assert os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION") == "v1.2"
