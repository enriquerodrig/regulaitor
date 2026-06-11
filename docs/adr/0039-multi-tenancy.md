# ADR 0039 — Config-based multi-tenancy (stateless) (Fase 4, HX)

- **Status:** Accepted
- **Date:** 2026-06-11 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0009 (H7 FastAPI — single-token auth + slowapi this evolves),
  0013 (router modes — the `model_choice` seam a future per-tenant follow-up will reuse).

## Context

HX needs to onboard multiple PYME client organisations ("tenants") before real
clients arrive: per-tenant auth, isolation, and rate limiting. An exploration of
the current state established the decisive fact:

**RegulAItor is STATELESS** — fully ephemeral per request. No database, no ORM; no
query / document / result / case is ever persisted. LanceDB holds only the
read-only regulatory corpus. `case_id` is a log correlation id, not a data key.
Every request: auth → compute → log → discard.

This reframes multi-tenancy: with no shared per-request state, **data isolation is
inherent** (each request is independent). Tenancy reduces to isolating
**auth + config + rate-limit + observability** — NOT row-level DB scoping. No
database is required.

## Decision

A **config-based, stateless** multi-tenant registry (`security/tenancy.py`).

### D1 — Tenant registry (no DB)
`Tenant` (frozen, `extra="forbid"`): `tenant_id`, `name`, `rate_limit_ask`,
`rate_limit_analyze`. Loaded once at startup (FastAPI lifespan) from, first match:
1. `REGULAITOR_TENANTS_JSON` — inline JSON array (a Space secret).
2. `REGULAITOR_TENANTS_FILE` — path to a JSON array.
3. `REGULAITOR_API_TOKEN` — **backward-compat**: a single "default" tenant, so
   existing single-token deploys keep working byte-for-byte.

The **token is the secret KEY** — it is never stored on the `Tenant` model nor
logged. Entropy guard: every token ≥16 chars. Duplicate tenant_ids / tokens and
extra fields are rejected at load (fail-fast).

### D2 — Tenant-aware auth
`verify_token` resolves the presented Bearer token to a `Tenant` via
`tenancy.resolve_tenant` (`hmac.compare_digest` against **every** registered token
— no early return, so timing does not leak which token matched), injects
`request.state.tenant` + a `token_hash`, and 401s on no match.

### D3 — Per-tenant rate limiting
The slowapi key function returns `tenant:{tenant_id}` (isolated buckets — one
tenant cannot exhaust another's quota). The per-tenant limit **value** uses
slowapi's key-aware callable (a limit callable declaring a `key` parameter is
invoked with `key_func(request)`); it resolves the tenant's configured limit,
falling back to `REGULAITOR_RATE_LIMIT_*` env / defaults.

### D4 — Per-tenant logging
The structured `/ask` + `/analyze` records carry `tenant_id` (null in legacy /
pre-auth state).

### D5 — Scope
API-only. The Streamlit UI stays single-user (one instance = one tenant); a
multi-tenant UI with login is Fase 5 (Next.js). `model_choice` per tenant and a
per-tenant corpus allowlist are **deferred** (user decision) — `model_choice`
needs threading through the orchestration; both are clean follow-ups.

## Consequences

- Multiple clients can be onboarded with isolated API keys, per-tenant rate limits,
  and tenant-tagged logs — with **zero new infrastructure** (no DB, no migrations).
- §6 untouched: `citation/validator.py` + `agents/auditor.py` byte-unchanged
  (tenancy is an auth/config layer above the pipeline).
- Backward-compat: single-`REGULAITOR_API_TOKEN` deploys are unchanged (default
  tenant); all prior integration/contract tests pass without modification.

## §22.22 disclosures

1. **Stateless ⇒ isolation is inherent, not enforced by storage:** there is no
   per-tenant data to leak because nothing is stored. If per-tenant audit trails /
   usage history / quotas become a requirement, that is a NET-NEW persistence layer
   (SQLite/Postgres) — explicitly out of this scope (user chose the no-DB option).
2. **`model_choice` + corpus-allowlist per tenant are config-less for now:** the
   `Tenant` model intentionally omits them (no dead/un-enforced config); they ship
   with their enforcement in the follow-up.
3. **Registry is static (load-at-startup):** adding a tenant is a config change +
   restart. Dynamic tenant management (add without redeploy) is the SQLite option,
   deferred.
4. **Token storage is operator-side:** the registry holds raw tokens in env/file
   config (like `.env`); rotation + secret hygiene are operator responsibilities
   (the same model as the existing single token).

## Alternatives considered

- **SQLite/Postgres persistence (tenants + audit + quotas)** — rejected for v1
  (the system is stateless; a DB is net-new infra for features not yet needed).
- **Minimal (auth + rate-limit only, no per-tenant config)** — rejected: the user
  wants per-tenant config (e.g. different rate limits per client).
- **JWT with tenant claims** — rejected: heavier (key management) than opaque
  Bearer tokens for a handful of pilot tenants; revisit at self-service scale.
