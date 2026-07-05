# RegulAItor — Secret Management & Rotation Runbook

> Roadmap P3.4. Actionable guide for the credentials RegulAItor holds. The founder's
> single stated pre-captación blocker is "rotate the keys before the first tenant" —
> this doc makes that concrete + establishes the ongoing hygiene. See also
> `docs/threat_model.md §2.6` (secrets + supply chain).

## 1. Principles

1. **Secrets never enter the repo.** `.env` is `.gitignored`; `gitleaks` gates CI
   (`ci.yml` Security job) and pre-commit. No key has ever been committed (verified).
2. **`.env` is DEV-ONLY**, with low-value dev keys. **Production uses the deploy
   platform's secret manager** — never a `.env` on the box:
   - HF Spaces → Space *Settings → Secrets*
   - Render → *Environment* / secret files
   - Fly.io → `fly secrets set …`
   - Self-hosted (OVH/Scaleway, roadmap P4) → the platform vault / a KMS-backed store.
3. **Least privilege + separate keys per environment** (dev / staging / prod), so
   rotating or revoking one never takes another down.
4. Keys are **never logged and never stored on a model/DTO** — only a SHA-256[:8]
   `token_hash` is used for rate-limit/log correlation (`api/auth.py`).

## 2. Key inventory + blast radius

| Secret | Purpose | If leaked |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sonnet (prod) + Haiku (judge) | spend; rotate at console.anthropic.com |
| `REGULAITOR_SELFHOST_API_KEY` (Mistral La Plateforme) | production Analyst (sovereign) | spend; rotate at console.mistral.ai |
| `OPENAI_API_KEY` | (optional) router fallback | spend; platform.openai.com |
| `GROQ_API_KEY` | (optional) council judge | spend; console.groq.com |
| `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | (optional) tracing | reads trace data; rotate in LangFuse project settings |
| `HF_TOKEN` | deploy to the HF Space | **can push to the PUBLIC Space** — highest urgency |
| `REGULAITOR_API_TOKEN` / tenant tokens | Bearer auth to the API | a tenant's access; rotate the registry + notify the tenant |

## 3. Rotation

**Cadence:** rotate all provider keys **every 90 days**, and **immediately** on any of:
suspected exposure, an offboarded operator, or before onboarding the first external
tenant (the hard checklist below).

**Per-key rotation (zero-downtime pattern):**
1. Create a NEW key at the provider console (keep the old one live).
2. Set the new value in the deploy secret manager (§1.2) and redeploy / restart.
3. Verify `GET /health` + one `POST /ask` succeed on the new key.
4. Revoke the OLD key at the provider.
5. Record the rotation date (an internal log, not the repo).

**Tenant tokens:** generate with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`, update
`REGULAITOR_TENANTS_JSON`/`_FILE`, restart, and notify the tenant. Tokens are the
registry KEY — the raw value is never stored on the `Tenant` model.

## 4. Pre-captación hard checklist (do BEFORE the first external tenant)

- [ ] Rotate ALL keys in §2 (they were used during development / pasted into tooling).
- [ ] Move production keys out of any `.env` into the deploy secret manager.
- [ ] Confirm `HF_TOKEN` is rotated (it can push to the public Space).
- [ ] `REGULAITOR_ENABLE_DOCS=0` in prod (stop advertising the schema — authz-02).
- [ ] Confirm the CI Security job (gitleaks + pip-audit) is green on `main`.

## 5. Leaked-key incident response

1. **Revoke the key at the provider immediately** (before anything else).
2. Rotate per §3 with a fresh key.
3. If it was `HF_TOKEN`: check the Space's commit history for unexpected pushes.
4. If it was an LLM key: check provider usage/billing for anomalous spend.
5. Run `gitleaks detect --no-git --source .` locally to confirm nothing landed in the
   tree, and review recent commits.

## 6. Automation guardrails already in place

- `gitleaks` — CI (`ci.yml`) + pre-commit, pinned v8.21.2.
- `pip-audit` + `bandit` — CI Security job (dependency + static analysis).
- **Dependabot** (`.github/dependabot.yml`, P3.4) — weekly CI-gated dependency-update PRs
  so CVEs surface as reviewable PRs instead of silently accumulating (the gap P1.5 hit).
- `.env` gitignored; keys never logged or persisted on a model.

**Not yet automated (carry-forward):** a managed secret store / KMS with automatic
rotation, and per-tenant token lifecycle tooling — proportionate only once there are
paying tenants (roadmap P5 / HX production hardening).
