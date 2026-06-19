# ADR 0041 — Opt-in SQLite audit-trail persistence (Fase 6 hardening, HX)

- **Status:** Accepted
- **Date:** 2026-06-14 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0039 (Fase 4 multi-tenancy — the stateless contract this
  extends, and the per-tenant `tenant_id` the rows carry), 0012 (H11
  observability — the no-op-when-unconfigured + swallow-errors pattern reused).

## Context

RegulAItor is stateless (ADR-0039): nothing per-request is persisted. That is the
right default, but a **compliance** product has a specific need that statelessness
leaves open — **traceability for audit** (the project's problem #4): an auditable,
queryable record of every consultation. ADR-0039 explicitly deferred this as a
"net-new persistence layer".

This is the first HX hardening item: persist a minimal, privacy-safe record of
every `/ask` and `/analyze` turn, per tenant, and lay the foundation for per-tenant
usage/quotas — **without** weakening the stateless default or storing any sensitive
text.

## Decision

An **opt-in** SQLite audit trail (`observability/audit_store.py`).

### D1 — Opt-in, no-op by default
Persistence activates only when `REGULAITOR_AUDIT_DB` points at a writable path.
Unset (the default) → every function is a no-op and the system stays fully
ephemeral (ADR-0039 preserved byte-for-byte). This mirrors `langfuse_client`
(ADR-0012): unconfigured = inert, and every failure is swallowed with a WARNING
so auditing can never break a request.

### D2 — One append-only row per turn, wired at the logging layer
A single `audit_log` table. The wiring lives in `api/logging.py` — the one place
that already builds a structured per-turn record — so `log_api_chat_turn` and
`log_api_document_turn` each persist exactly one row. No route or pipeline change.

### D3 — §18.8 / SSDLC: hashes and metadata only
The raw query is **never** stored — only its SHA-256 (`query_sha256`). Document
text is never stored. Rows hold non-sensitive metadata: `case_id`, `tenant_id`,
`mode`, `corpus`, `language`, `verdict`, finding/citation/segment counts,
`latency_ms`, `cost_eur`. A unit test asserts the raw query bytes never appear in
the DB file. A fresh connection per call is used only on the thread that opened
it (never shared across threads → thread-safe); concurrent writers contend
briefly on the single SQLite file (absorbed by the default 5s busy-timeout, and
any residual error is swallowed — at most one audit row dropped, never a request).

### D4 — Quota foundation (not enforcement)
`count_turns(tenant_id, since=)` + `recent()` are provided for usage counting and
inspection. Quota **enforcement** (rejecting a tenant over budget) is a deliberate
follow-up — this ADR ships the persistence + counting layer only.

## Consequences

- Compliance-grade auditability + per-tenant usage counting, with **zero new
  infrastructure** when unconfigured and a single SQLite file when enabled.
- §6 untouched: `citation/validator.py` + `agents/auditor.py` byte-unchanged
  (this is an observability/egress layer above the pipeline).
- Backward-compat: unset env = the ADR-0039 stateless system; all prior tests pass.

## §22.22 disclosures

1. **Opt-in, not default-on:** production must set `REGULAITOR_AUDIT_DB`; unset
   means no audit trail. The stateless default is preserved deliberately (not an
   oversight) so an operator chooses persistence consciously.
2. **Counting, not enforcing:** quotas are persisted/countable but not enforced
   yet; the 429-over-quota path is a follow-up in auth/rate-limit.
3. **SQLite single-file:** fine for a single-instance self-host; multi-instance/HA
   would need Postgres (the ADR-0039 note carries — a swap is a future change).
4. **Per-call connection** (open/create-if-not-exists/insert/close): simple and
   thread-safe for the API's volume; not tuned for very high write throughput
   (batching/pooling would be a later optimisation).
5. **Document-input correlation deferred:** chat turns store `query_sha256`;
   document turns store `query_sha256 = NULL` for now. Correlating which document
   was analysed (via the already-computed `DocumentReport.document_hash`) is a
   clean follow-up — not added here to avoid schema churn.
6. **Unsalted query hash:** SHA-256 lets you detect identical repeated queries but
   is not reversible; if even hash-correlation across deploys is undesirable, a
   per-deploy salt could be added (follow-up).
7. **Unbounded growth:** `audit_log` is append-only with no retention/rotation/row
   cap. One small row per turn, but on a long-lived self-host the file grows
   without bound — retention/pruning is an operator follow-up.
8. **Operator-trusted DB path:** `REGULAITOR_AUDIT_DB` is taken verbatim and not
   sandboxed — an operator can point it anywhere the process can write. No user
   input flows into the path (not attacker-reachable); it is operator-trusted env
   config, consistent with the rest of the config surface, and not validated by
   design.
9. **`recent()` / `count_turns()` are not yet HTTP-exposed:** they exist for
   inspection/usage counting and have no route. Their `tenant_id=None` mode
   returns/counts across all tenants — before any of them gets an HTTP surface,
   the handler MUST force `tenant_id` from `request.state.tenant` so a tenant can
   never read another tenant's rows.

## Alternatives considered

- **Postgres** — rejected for v1 (single-instance self-host; SQLite is zero-infra;
  swap to Postgres if/when multi-instance, per ADR-0039).
- **Persist raw queries** — rejected (§18.8 PII risk); only the SHA-256 is stored.
- **Default-on persistence** — rejected: it would silently change the stateless
  contract (ADR-0039); opt-in is the safe default.
