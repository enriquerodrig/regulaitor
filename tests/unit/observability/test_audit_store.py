"""Unit tests for observability/audit_store (Fase 6 hardening, ADR-0041)."""

from __future__ import annotations

import hashlib

import pytest

from regulaitor.observability import audit_store


def _enable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> object:
    path = tmp_path / "audit.db"
    monkeypatch.setenv("REGULAITOR_AUDIT_DB", str(path))
    return path


def test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_AUDIT_DB", raising=False)
    assert audit_store.is_enabled() is False
    # All operations are no-ops when unconfigured (never raise).
    audit_store.record(case_id="c1", tenant_id="acme", mode="chat", query="secret query")
    assert audit_store.recent() == []
    assert audit_store.count_turns("acme") == 0


def test_enabled_when_path_set(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    assert audit_store.is_enabled() is True


def test_record_and_recent_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    audit_store.record(
        case_id="c1",
        tenant_id="acme",
        mode="chat",
        corpus="ai_act",
        language="es",
        verdict="pass",
        query="q",
        n_findings=2,
        n_citations=3,
        n_validated=1,
        latency_ms=120,
    )
    rows = audit_store.recent()
    assert len(rows) == 1
    row = rows[0]
    assert row["case_id"] == "c1"
    assert row["tenant_id"] == "acme"
    assert row["mode"] == "chat"
    assert row["verdict"] == "pass"
    assert row["n_findings"] == 2
    assert row["n_validated"] == 1
    assert row["ts"] is not None


def test_query_stored_as_sha256_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """§18.8: the raw query is NEVER persisted — only its SHA-256."""
    path = _enable(monkeypatch, tmp_path)
    secret = "¿cuál es mi número de DNI 12345678Z?"
    audit_store.record(case_id="c1", tenant_id="acme", mode="chat", query=secret)
    row = audit_store.recent()[0]
    assert row["query_sha256"] == hashlib.sha256(secret.encode("utf-8")).hexdigest()
    # The raw query bytes must not appear anywhere in the DB file.
    raw = path.read_bytes()
    assert secret.encode("utf-8") not in raw
    assert b"12345678Z" not in raw


def test_record_without_query_has_null_hash(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    audit_store.record(case_id="d1", tenant_id=None, mode="document", n_segments=4, latency_ms=5)
    row = audit_store.recent()[0]
    assert row["query_sha256"] is None
    assert row["mode"] == "document"
    assert row["n_segments"] == 4
    assert row["tenant_id"] is None


def test_count_turns_per_tenant(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    for _ in range(3):
        audit_store.record(case_id="c", tenant_id="acme", mode="chat", query="q")
    audit_store.record(case_id="c", tenant_id="globex", mode="chat", query="q")
    audit_store.record(case_id="c", tenant_id=None, mode="chat", query="q")
    assert audit_store.count_turns("acme") == 3
    assert audit_store.count_turns("globex") == 1
    assert audit_store.count_turns(None) == 1  # NULL tenant matched via IS


def test_count_turns_since_filter(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """The `since` branch filters by ISO-8601 ts with a lexicographic >= compare."""
    _enable(monkeypatch, tmp_path)
    audit_store.record(case_id="c1", tenant_id="acme", mode="chat", query="q")
    audit_store.record(case_id="c2", tenant_id="acme", mode="chat", query="q")
    # far-future `since` excludes everything; far-past `since` includes all.
    assert audit_store.count_turns("acme", since="2999-01-01T00:00:00+00:00") == 0
    assert audit_store.count_turns("acme", since="2000-01-01T00:00:00+00:00") == 2


def test_recent_filter_and_limit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    for i in range(5):
        audit_store.record(case_id=f"c{i}", tenant_id="acme", mode="chat", query="q")
    audit_store.record(case_id="other", tenant_id="globex", mode="chat", query="q")
    acme = audit_store.recent(tenant_id="acme")
    assert len(acme) == 5
    assert all(r["tenant_id"] == "acme" for r in acme)
    newest = audit_store.recent(limit=2)
    assert len(newest) == 2
    assert newest[0]["case_id"] == "other"  # id DESC -> newest first


def test_record_never_raises_on_bad_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Parent directory does not exist -> sqlite connect fails -> swallowed (WARNING).
    monkeypatch.setenv("REGULAITOR_AUDIT_DB", str(tmp_path / "nope" / "audit.db"))
    audit_store.record(case_id="c", tenant_id="acme", mode="chat", query="q")
    assert audit_store.count_turns("acme") == 0


def test_schema_idempotent_across_calls(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    audit_store.record(case_id="c1", tenant_id="acme", mode="chat", query="q")
    audit_store.record(case_id="c2", tenant_id="acme", mode="chat", query="q")
    assert audit_store.count_turns("acme") == 2
