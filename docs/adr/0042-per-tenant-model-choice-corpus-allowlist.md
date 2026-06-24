# ADR 0042 — Per-tenant model_choice + corpus allowlist (Fase 6B hardening, HX)

- **Status:** Accepted
- **Date:** 2026-06-14 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0039 (Fase 4 multi-tenancy — the `Tenant` model + the D5
  deferral this closes), 0013 (router modes — the `model_choice` this threads),
  0009 (H7 API errors — the 403 handler pattern reused).

## Context

ADR-0039 D5 deferred two per-tenant capabilities as "needs threading through the
orchestration": **per-tenant `model_choice`** (so a premium tenant can run on a
different model) and a **per-tenant corpus allowlist** (so a tenant is scoped to
the norms it pays for). This milestone implements both — the second half of the
Fase 6 hardening (the first was ADR-0041, the audit trail).

## Decision

### D1 — Two optional fields on `Tenant`, validated at load
`Tenant` gains `model_choice: str | None = None` and
`allowed_corpora: list[str] | None = None`. Both `None` (the default) means **no
restriction**, so existing tenants are byte-identical. Validation is **fail-closed
at load**: `model_choice` must be a valid router mode (checked against
`router._VALID_MODES`, lazily imported so the LLM router is not pulled at module
load); each `allowed_corpora` member must be a valid `CorpusSelector`; an empty
list is rejected (use `null` for "no restriction").

### D2 — `model_choice` threaded (chat)
`Tenant.model_choice` → `routes_ask` → `graph.run(model_choice=...)` →
`ChatState.model_choice` → `_analyst_node` → `AnalystAgent.analyze(model_choice=)`
→ `router.complete`. An explicit per-tenant value wins; `None` or an invalid value
falls back to the existing env seam (`REGULAITOR_ANALYST_MODEL_CHOICE`) and then to
`default`. The Auditor/Council judge models are untouched.

### D3 — Corpus allowlist enforced at the routes (403)
`/ask` (single corpus) and `/analyze` (list) reject a request whose corpus is not
in the tenant's `allowed_corpora` with a new `CorpusNotAllowed` → **403**
(`error_code: corpus_not_allowed`). The check runs before the pipeline, so a
disallowed corpus never reaches `run`/`run_document`.

### D4 — §6 untouched
`citation/validator.py` + `agents/auditor.py` byte-unchanged. The Analyst's model
is a *routing* choice, not a validation change; the allowlist is *authorization*,
not citation logic.

## Consequences

- Tenants can be **tiered** (different model per tenant) and **scoped** (corpus
  allowlist), with backward-compat (unset = current behaviour) and fail-closed
  config validation.
- Closes ADR-0039 D5.

## §22.22 disclosures

1. **`model_choice` is CHAT-ONLY:** `/analyze` keeps the `document_analyst`
   default; per-tenant *doc* model_choice is a follow-up (the doc graph +
   `document_analyst` role were not threaded, to keep this change bounded). The
   corpus allowlist **does** apply to `/analyze`.
2. **`"auto"` is literal in the allowlist** (not "allow all"): a tenant restricted
   to `["gdpr"]` cannot use the multi-corpus `auto` path unless `"auto"` is
   explicitly listed. **Operator caveat:** listing `"auto"` effectively *un-scopes*
   chat corpus restriction — the `auto` path (`run_auto`) searches across all
   corpora and the purity gate can resolve to any norma, so `"auto"` on an
   allowlist grants the full corpus, not a subset. `/analyze` is unaffected (it
   accepts only `Norma` members, never `"auto"`).
3. **No cost/quota coupling:** a tenant on an expensive model simply costs more;
   cost controls (quota enforcement) remain the audit-trail follow-up (ADR-0041
   D4). model_choice here is capability, not budget.
4. **Defensive double-validation of model_choice:** validated at `Tenant` load
   (fail-closed) AND re-checked in `analyze` (an unexpected value falls back to the
   env/default rather than crashing a turn) — belt-and-suspenders.
5. **`allowed_corpora = []` is rejected, `null` is "no restriction":** an empty
   list would mean "locked out of everything", an almost-certainly-unintended
   config — so it fails at load with a clear message.

## Alternatives considered

- **Per-request `model_choice`** — rejected: ADR-0039 D5 intent is per-tenant
  config; a per-request field would let any caller select an expensive model.
- **Env-only `model_choice` (the current seam)** — insufficient for multi-tenant
  (one env value applies to all tenants).
- **Enforce the allowlist inside `verify_token`** — rejected: the corpus is request
  data, not auth; the route is the right place, and `verify_token` stays auth-only.
