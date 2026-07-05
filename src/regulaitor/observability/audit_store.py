"""Optional SQLite audit-trail persistence (Fase 6 hardening, ADR-0041).

Stateless-by-default: persistence is OPT-IN. With ``REGULAITOR_AUDIT_DB`` unset
(the default), every function here is a no-op and the system stays fully
ephemeral (ADR-0039). When the env var points at a writable path, exactly one
append-only row is persisted per completed ``/ask`` and ``/analyze`` turn —
serving the project's traceability-for-audit goal (problem #4) and laying the
foundation for per-tenant usage/quotas.

SSDLC / §18.8: the raw query is NEVER stored — only its SHA-256. Document text
is never stored. Rows hold non-sensitive metadata only (case id, tenant id,
verdict, counts, latency, cost) plus the query hash. Like
``observability/langfuse_client``, every failure is swallowed with a WARNING so
auditing can never break a request.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_ENV_PATH = "REGULAITOR_AUDIT_DB"
_ENV_RETENTION = "REGULAITOR_AUDIT_RETENTION_DAYS"
_DEFAULT_RETENTION_DAYS = 365

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    case_id TEXT NOT NULL,
    tenant_id TEXT,
    mode TEXT NOT NULL,
    corpus TEXT,
    language TEXT,
    verdict TEXT,
    query_sha256 TEXT,
    n_findings INTEGER,
    n_citations INTEGER,
    n_validated INTEGER,
    n_segments INTEGER,
    latency_ms INTEGER,
    cost_eur REAL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_ts ON audit_log (tenant_id, ts);
"""


def _db_path() -> str | None:
    raw = os.getenv(_ENV_PATH, "").strip()
    return raw or None


def is_enabled() -> bool:
    """True when REGULAITOR_AUDIT_DB points at a path (persistence is opt-in)."""
    return _db_path() is not None


def is_healthy() -> bool:
    """obs-08: True if the configured audit DB is reachable + writable, OR not
    configured (unconfigured is not a failure). A False means the operator pointed
    REGULAITOR_AUDIT_DB at a broken/unwritable path — surfaced as a non-fatal
    'degraded' sub-check by /health so a silently-broken trail is alertable. Opening
    the DB ensures the schema (a write), so this doubles as a writability probe."""
    path = _db_path()
    if path is None:
        return True
    try:
        conn = _open(path)
        try:
            conn.execute("SELECT 1")
            return True
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — health probe must never raise
        logger.warning("audit_store.is_healthy probe failed: %s", exc)
        return False


def _open(path: str) -> sqlite3.Connection:
    # A fresh connection per call, used only on the thread that opened it (never
    # shared across threads). Concurrent writers may briefly contend on the
    # SQLite file; the default 5s busy-timeout absorbs that, and any residual
    # error is swallowed by the caller — a single audit row may be dropped under
    # heavy contention, but a request is never broken.
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)  # idempotent (CREATE ... IF NOT EXISTS)
    return conn


def record(
    *,
    case_id: str,
    tenant_id: str | None,
    mode: str,
    corpus: str | None = None,
    language: str | None = None,
    verdict: str | None = None,
    query: str | None = None,  # hashed here; the raw text is NEVER persisted
    n_findings: int | None = None,
    n_citations: int | None = None,
    n_validated: int | None = None,
    n_segments: int | None = None,
    latency_ms: int | None = None,
    cost_eur: float | None = None,
) -> None:
    """Persist one audit row. No-op when REGULAITOR_AUDIT_DB is unset. Never raises."""
    path = _db_path()
    if path is None:
        return
    query_sha256 = hashlib.sha256(query.encode("utf-8")).hexdigest() if query else None
    ts = datetime.now(UTC).isoformat()
    try:
        conn = _open(path)
        try:
            conn.execute(
                "INSERT INTO audit_log (ts, case_id, tenant_id, mode, corpus, language, "
                "verdict, query_sha256, n_findings, n_citations, n_validated, n_segments, "
                "latency_ms, cost_eur) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts,
                    case_id,
                    tenant_id,
                    mode,
                    corpus,
                    language,
                    verdict,
                    query_sha256,
                    n_findings,
                    n_citations,
                    n_validated,
                    n_segments,
                    latency_ms,
                    cost_eur,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — auditing must never break a request
        logger.warning("audit_store.record failed: %s", exc)


def count_turns(tenant_id: str | None, *, since: str | None = None) -> int:
    """Count persisted turns for a tenant (quota foundation). 0 when disabled."""
    path = _db_path()
    if path is None:
        return 0
    try:
        conn = _open(path)
        try:
            if since is not None:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE tenant_id IS ? AND ts >= ?",
                    (tenant_id, since),
                )
            else:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE tenant_id IS ?",
                    (tenant_id,),
                )
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_store.count_turns failed: %s", exc)
        return 0


def retention_days() -> int:
    """Configured retention window (REGULAITOR_AUDIT_RETENTION_DAYS, default 365).
    Invalid or non-positive values fall back to the default with a WARNING."""
    raw = os.getenv(_ENV_RETENTION, "").strip()
    if not raw:
        return _DEFAULT_RETENTION_DAYS
    try:
        n = int(raw)
    except ValueError:
        logger.warning("invalid %s=%r; using %d", _ENV_RETENTION, raw, _DEFAULT_RETENTION_DAYS)
        return _DEFAULT_RETENTION_DAYS
    if n <= 0:
        logger.warning(
            "%s=%d is not positive; using %d", _ENV_RETENTION, n, _DEFAULT_RETENTION_DAYS
        )
        return _DEFAULT_RETENTION_DAYS
    return n


def export_tenant(tenant_id: str | None) -> list[dict[str, Any]]:
    """GDPR Art. 15 (access): ALL persisted rows for a tenant, oldest first.

    Returns [] when the store is disabled. Unlike the request-path helpers,
    DSR operations are operator-invoked (scripts/dsr.py) and DO NOT swallow DB
    errors — a silently-failed access request is a compliance defect.
    """
    path = _db_path()
    if path is None:
        return []
    conn = _open(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM audit_log WHERE tenant_id IS ? ORDER BY id ASC",
            (tenant_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def erase_tenant(tenant_id: str | None) -> int:
    """GDPR Art. 17 (erasure): delete ALL rows for a tenant; return the count.

    Returns 0 when the store is disabled. Raises on DB error (operator-facing):
    a silently-failed erasure would leave personal data the DPO believes gone.
    """
    path = _db_path()
    if path is None:
        return 0
    conn = _open(path)
    try:
        cur = conn.execute("DELETE FROM audit_log WHERE tenant_id IS ?", (tenant_id,))
        conn.commit()
        return int(cur.rowcount)
    finally:
        conn.close()


def purge_expired(days: int | None = None) -> int:
    """Retention (P3.2): delete rows older than ``days`` (default retention_days()).

    Returns the count deleted (0 when disabled). Raises on DB error, like
    erase_tenant — this is operator/cron-invoked, not on the request path.
    ISO-8601 UTC timestamps sort lexicographically, so a string compare is a
    correct chronological cutoff (same approach as count_turns' ``ts >=``).
    """
    path = _db_path()
    if path is None:
        return 0
    window = days if days is not None else retention_days()
    cutoff = (datetime.now(UTC) - timedelta(days=window)).isoformat()
    conn = _open(path)
    try:
        cur = conn.execute("DELETE FROM audit_log WHERE ts < ?", (cutoff,))
        conn.commit()
        return int(cur.rowcount)
    finally:
        conn.close()


def recent(*, limit: int = 50, tenant_id: str | None = None) -> list[dict[str, Any]]:
    """Return the most recent rows (newest first) for inspection. [] when disabled."""
    path = _db_path()
    if path is None:
        return []
    try:
        conn = _open(path)
        conn.row_factory = sqlite3.Row
        try:
            if tenant_id is not None:
                cur = conn.execute(
                    "SELECT * FROM audit_log WHERE tenant_id IS ? ORDER BY id DESC LIMIT ?",
                    (tenant_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_store.recent failed: %s", exc)
        return []
