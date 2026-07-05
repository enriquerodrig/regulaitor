"""P3.2/P3.3: retention purge + GDPR DSR (access/erasure) over the audit store.

The store is opt-in; these tests point REGULAITOR_AUDIT_DB at a tmp DB. Personal
data in scope is minimal (tenant_id + query_sha256; the raw query is never
stored), so erasure/access operate on tenant_id.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from regulaitor.observability import audit_store


@pytest.fixture
def audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "audit.db"
    monkeypatch.setenv("REGULAITOR_AUDIT_DB", str(db))
    yield db


def _record(tenant: str | None, query: str = "consulta") -> None:
    audit_store.record(case_id="c", tenant_id=tenant, mode="chat", verdict="pass", query=query)


# --- retention_days config -------------------------------------------------


def test_retention_days_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_AUDIT_RETENTION_DAYS", raising=False)
    assert audit_store.retention_days() == 365


@pytest.mark.parametrize("bad", ["", "abc", "0", "-5"])
def test_retention_days_falls_back_on_bad_value(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv("REGULAITOR_AUDIT_RETENTION_DAYS", bad)
    assert audit_store.retention_days() == 365


def test_retention_days_honours_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGULAITOR_AUDIT_RETENTION_DAYS", "30")
    assert audit_store.retention_days() == 30


# --- DSR access (Art. 15) --------------------------------------------------


def test_export_returns_only_that_tenant(audit_db: Path) -> None:
    _record("t1")
    _record("t1")
    _record("t2")
    rows = audit_store.export_tenant("t1")
    assert len(rows) == 2
    assert {r["tenant_id"] for r in rows} == {"t1"}
    # raw query never present; only its hash
    assert "query" not in rows[0]
    assert rows[0]["query_sha256"] is not None


def test_export_disabled_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_AUDIT_DB", raising=False)
    assert audit_store.export_tenant("t1") == []


# --- DSR erasure (Art. 17) -------------------------------------------------


def test_erase_deletes_only_that_tenant_and_returns_count(audit_db: Path) -> None:
    _record("t1")
    _record("t1")
    _record("t2")
    deleted = audit_store.erase_tenant("t1")
    assert deleted == 2
    assert audit_store.export_tenant("t1") == []
    assert len(audit_store.export_tenant("t2")) == 1  # other tenant untouched


def test_erase_disabled_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_AUDIT_DB", raising=False)
    assert audit_store.erase_tenant("t1") == 0


# --- retention purge (P3.2) ------------------------------------------------


def test_purge_expired_removes_old_rows_only(audit_db: Path) -> None:
    _record("t1", query="recent")
    # Backdate one row 400 days into the past (past the 365-day default).
    conn = sqlite3.connect(str(audit_db))
    conn.execute(
        "INSERT INTO audit_log (ts, case_id, tenant_id, mode, verdict) "
        "VALUES ('2020-01-01T00:00:00+00:00', 'old', 't1', 'chat', 'pass')"
    )
    conn.commit()
    conn.close()

    deleted = audit_store.purge_expired()  # default 365 days
    assert deleted == 1
    remaining = audit_store.export_tenant("t1")
    assert len(remaining) == 1
    assert remaining[0]["case_id"] == "c"  # the recent row survived


def test_purge_honours_explicit_days(audit_db: Path) -> None:
    _record("t1")  # timestamp = now
    # A 0-day window would be invalid via retention_days(), but an explicit
    # negative window is a cutoff in the future → deletes everything.
    assert audit_store.purge_expired(days=-1) == 1


def test_purge_disabled_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_AUDIT_DB", raising=False)
    assert audit_store.purge_expired() == 0
