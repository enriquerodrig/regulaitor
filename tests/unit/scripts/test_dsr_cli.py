"""P3.3: the DSR operator CLI (scripts/dsr.py) — export / erase / purge."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.dsr import main

from regulaitor.observability import audit_store


@pytest.fixture
def enabled_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("REGULAITOR_AUDIT_DB", str(tmp_path / "audit.db"))
    return tmp_path


def _seed(tenant: str) -> None:
    audit_store.record(case_id="c", tenant_id=tenant, mode="chat", verdict="pass", query="q")


def test_export_prints_json(enabled_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed("t1")
    assert main(["export", "t1"]) == 0
    out = capsys.readouterr()
    assert '"tenant_id": "t1"' in out.out  # JSON on stdout
    assert "exported 1 row" in out.err  # summary on stderr


def test_erase_requires_yes(enabled_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed("t1")
    assert main(["erase", "t1"]) == 2  # refuses without --yes
    assert audit_store.count_turns("t1") == 1  # nothing deleted
    assert "refusing to erase" in capsys.readouterr().err


def test_erase_with_yes_deletes(enabled_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed("t1")
    assert main(["erase", "t1", "--yes"]) == 0
    assert audit_store.count_turns("t1") == 0
    assert "erased 1 row" in capsys.readouterr().err


def test_purge_reports_window(enabled_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed("t1")
    assert main(["purge", "--days", "-1"]) == 0  # future cutoff → deletes all
    assert audit_store.count_turns("t1") == 0
    assert "older than -1 day" in capsys.readouterr().err


def test_commands_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("REGULAITOR_AUDIT_DB", raising=False)
    assert main(["export", "t1"]) == 0
    assert "audit store disabled" in capsys.readouterr().err


def test_default_tenant_maps_to_null(enabled_db: Path) -> None:
    audit_store.record(case_id="c", tenant_id=None, mode="chat", verdict="pass", query="q")
    assert main(["erase", "default", "--yes"]) == 0
    assert audit_store.count_turns(None) == 0
