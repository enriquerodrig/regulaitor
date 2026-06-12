# ADR 0040 — Next.js frontend (BFF + nonce-CSP, self-hosted) (Fase 5, HX)

- **Status:** Accepted
- **Date:** 2026-06-12 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0008 (H6 Streamlit MVP — the marketing demo this does NOT
  replace), 0009 (H7 FastAPI surface this consumes), 0039 (Fase 4 multi-tenancy —
  the per-tenant Bearer token this UI logs in with).

## Context

HX needs the "real product" UI: the triple surface (Pregunta / Analiza documento /
Estado) as a web app with login, sober and accessible, separate from the Streamlit
marketing demo. CLAUDE.md §15.3 lists a full Next.js frontend as HX2; §22.16 unblocks
it (Streamlit + evals + red team are closed).

The decisive constraint is the backend's reachability: a browser SPA needs the
FastAPI backend, which is **not** publicly deployed (the HF Space runs Streamlit
only). Pointing the UI at a public API would add hosting cost AND collide with the
founder's sovereignty thesis (no external LLM dependency in production), so the UI
is built to be **self-hosted next to the API** via docker-compose, not publicly
hosted.

## Decision

A Next.js 16 (App Router) frontend in `frontend_next/`, self-hosted alongside the
FastAPI `api` service.

### D1 — BFF + httpOnly cookie (not client-side token)
The Bearer token lives only in an `httpOnly + SameSite=Strict` cookie. Next route
handlers (`src/app/api/*`) read it server-side and forward `Authorization: Bearer`
to the FastAPI backend (`src/lib/api-server.ts`, `server-only`). The browser never
holds the raw token (XSS cannot exfiltrate it), and there is **no CORS** (server to
server). `Secure` adapts to the request scheme (https → set; plain-http LAN → not
set, so the cookie still works). Login is **optimistic** (no cheap authenticated
backend endpoint to validate against); any 401 clears the session and bounces to
`/login`.

### D2 — `proxy.ts` does auth-gate + per-request nonce CSP
Next 16 renamed Middleware → **Proxy**; one `src/proxy.ts` does the optimistic
auth-gate redirect **and** sets a per-request nonce CSP (`script-src` strict: self
+ nonce + strict-dynamic). The root layout is `force-dynamic` so the nonce applies
to every rendered page.

### D3 — Types generated from OpenAPI (zero drift)
`src/lib/api-types.ts` is generated from the FastAPI `/openapi.json`
(`openapi-typescript`, `npm run gen:types`). The Pydantic DTOs remain the single
source of truth; the UI types cannot structurally desync.

### D4 — Pure presentation (§6 invariant preserved)
The frontend renders `verdict` / `AuditResultDTO.validated` / findings **verbatim**
and never re-derives a verdict or re-validates a citation. The legal disclaimer
(§3) is persistent on every surface. §6 "no citation, no answer" stays entirely in
the backend (`citation/validator.py` + `agents/auditor.py` byte-unchanged).

### D5 — Self-hosted only (no public deploy)
Shipped as a 3rd docker-compose service (`frontend`, Next standalone, non-root)
talking to `api:8000` over the internal network. The public Space stays Streamlit.
A public deploy (API + Vercel) is out of scope for this phase.

### D6 — Stack
shadcn base-nova (Base UI) for accessible primitives (it works on Next 16 — no
stack deviation); native styled `<select>` for the two dropdowns (zero API risk);
hand-rolled presentation components for the domain views. Tailwind v4, TS strict,
vitest, UI in Spanish, WCAG 2.2 AA target.

## Consequences

- A real, accessible, multi-tenant-aware product UI that any client can self-host
  with the API in their own EU infra (the sovereignty story), at zero new hosting
  cost.
- §6 untouched (presentation-only); the backend remains the sole authority.
- A second toolchain (Node/npm) + CI lane enters the repo; the Python gate is
  unaffected.

## §22.22 disclosures

1. **Adversarial review found a real bug per-task tests missed:** the `/analyze`
   form defaulted `corpus="auto"`, which the document backend path rejects (415,
   with a misleading "unsupported file" message). The multi-agent review (0 crit /
   3 important / 15 minor confirmed) caught it; fixed (doc-mode corpus list excludes
   `auto`, defaults to a real norma). The other 2 important findings (nav/logout
   have no accessible name below `sm`; illogical heading order) and 11 minors were
   also fixed.
2. **`style-src 'unsafe-inline'` is a documented accepted weakening (the one
   deferred finding):** the corpus-chip accent colours use inline `style`
   attributes, which a CSP nonce does **not** cover (nonces whitelist `<style>` /
   `<script>` elements, not inline style attributes) — so adopting the framework's
   nonce-style recommendation would break the chips, not harden them. `script-src`
   stays strict; there is no `dangerouslySetInnerHTML` and all values are escaped,
   so there is no XSS path. A static class map (10 known colours) could eliminate
   it later; accepted as-is for now.
3. **Nonce CSP forces dynamic rendering** of every page (no static/CDN caching).
   Acceptable: the app is auth-gated and uncacheable anyway.
4. **Login is optimistic:** the cookie is set without validating the token (no cheap
   authenticated endpoint); a wrong token surfaces as a 401 on the first protected
   call, which clears the session. A future `/me` echo endpoint would let login
   validate eagerly and display the tenant name.
5. **Type generation needs the API's OpenAPI schema:** `gen:types` reads a
   committed `frontend_next/openapi.json` (dumped from the FastAPI app); regenerate
   it when the DTOs change.
6. **Multi-tenancy (Fase 4) is API-only and NOT live-demoed on the Space:** this UI
   is where login/tenancy becomes visible, but only under a self-hosted deploy;
   neither runs on the public Streamlit Space.

## Alternatives considered

- **Client-side fetch + token in `sessionStorage`** — rejected: weaker XSS posture
  than an httpOnly cookie, and would require CORS.
- **Public deploy (FastAPI on Render/Fly + Next on Vercel)** — rejected for this
  phase: new hosting cost + the production-LLM-key contradiction with the
  sovereignty thesis; the Space stays the Streamlit demo.
- **Hand-typed TS interfaces for the DTOs** — rejected: drift; OpenAPI generation
  makes structural desync impossible.
- **Plain Tailwind (no shadcn)** — rejected: base-nova works on Next 16 and gives
  accessible primitives; staying on the approved stack (CLAUDE.md §10.1).
