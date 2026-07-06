# H16 Deployment Runbook

**Status:** Ready (post v0.1.26 deploy-prep).
**Scope:** Public-demo deploy of RegulAItor MVP via 1+ of: HF Spaces · Render · Fly.io · local Docker.
**Audience:** TFM defender + (future) anyone reproducing the project.

---

## §1 — Choose your platform

| Platform | Best for | Cost | Native? | Cold-start |
|---|---|---|---|---|
| **HF Spaces (Streamlit SDK)** | TFM demo (free, instant URL, public) | Free | ✅ | ~5 min first build (no Docker overhead) |
| **HF Spaces (Docker SDK)** | TFM demo + API endpoint exposed | Free | ✅ | ~15-20 min first build |
| **Render** | Foundation production-grade | Free tier (sleeps after 15 min idle) | Docker | ~20 min first build + ~30 s wake-from-sleep |
| **Fly.io** | Foundation production-grade + custom domain | Free tier (3 shared-cpu-1x VMs) | Docker | ~10 min first build |
| **Local Docker** | Dev / staging / pre-prod test | Free | Native (docker compose) | ~15-20 min first up |

**Recommendation for TFM defense:** HF Spaces Streamlit SDK (§3.1) for the demo URL + local Docker (§6) for reviewer reproducibility.

---

## §2 — Secrets you must inject (any platform)

| Env var | Purpose | Where to get |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sonnet 4.6 (production) + Haiku 4.5 (judge) | console.anthropic.com → API keys |
| `REGULAITOR_API_TOKEN` | Bearer auth for `/ask` + `/analyze` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `OPENAI_API_KEY` | (optional) Router fallback path | platform.openai.com |
| `GROQ_API_KEY` | (optional) Llama-3.3-70b for council judge | console.groq.com |
| `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` + `LANGFUSE_HOST` | (optional) Observability tracing | langfuse.com or self-hosted |
| `REGULAITOR_CORS_ORIGINS` | (browser deploy) e.g. `https://yourapp.example.com` | Set if exposing API to a web frontend |

**Never commit `.env` to git** (it's gitignored). For each platform §3-§6, the secrets injection is platform-specific (see each).

### §2.1 — Operator configuration (optional; pre-pilot hardening)

Not secrets — these tune behaviour and were added by the pre-pilot hardening pass.
All have safe defaults.

| Env var | Default | Purpose |
|---|---|---|
| `REGULAITOR_TENANTS_JSON` | (single-token) | Multi-tenant registry as inline JSON (see shape below). When unset, `REGULAITOR_API_TOKEN` resolves to one "default" tenant (backward-compat). |
| `REGULAITOR_TENANTS_FILE` | — | Path to the tenant-registry JSON (alternative to `_JSON`). |
| `REGULAITOR_AUDIT_DB` | (disabled) | Path to the opt-in SQLite audit trail. **MUST live on the persistent volume** (e.g. `/data/audit.db`) — a path on the image layer is wiped on every restart. Stores hashes + metadata only; the raw query is never persisted (§18.8). |
| `REGULAITOR_AUDIT_RETENTION_DAYS` | `365` | Retention window for the audit trail. Purge with `python -m scripts.dsr purge` (cron); GDPR access/erasure via the same CLI. See `docs/data_retention.md`. |
| `REGULAITOR_ENABLE_DOCS` | `1` (on) | Serves `/docs`, `/redoc`, `/openapi.json`. **Set `0` before a public pilot** so the API schema is not advertised to unauthenticated callers. |
| `REGULAITOR_MAX_SEGMENTS` | `500` | Hard cap on segments processed per `/analyze` document (DoS guard — each segment is a CPU-reranker call). Over the cap → `requires_human_review`. Raise only for genuinely long contracts. |
| `REGULAITOR_RATE_LIMIT_ASK` / `_ANALYZE` / `_AUDIT` | `30/minute` / `5/minute` / `30/minute` | Per-tenant rate limits (override per-tenant in the registry). |
| `REGULAITOR_RATELIMIT_STORAGE` | `memory://` | Rate-limit bucket backend. **`memory://` is per-worker** — a multi-worker / multi-instance deploy needs a shared store (e.g. `redis://host:6379`) for global limits. The single-worker self-hosted pilot is fine on the default. |
| `REGULAITOR_ENABLE_METRICS` | (off) | Set `1` to expose `GET /metrics` (Prometheus text: §6 verdict distribution → live block-rate + PII-query count). Unauth like `/health` — **restrict at the network layer** (scraper-only). Fail-secure: 404 when unset. See `observability/metrics.py` for the block-rate-collapse alert rule. |

**Per-tenant config shape** (one entry in `REGULAITOR_TENANTS_JSON`'s list):

```json
{"token": "<bearer>", "tenant_id": "acme", "name": "Acme S.L.",
 "allowed_corpora": ["ai_act", "gdpr"], "model_choice": "quality"}
```

`allowed_corpora` omitted = all corpora allowed; `model_choice` omitted = server default.

**Pre-pilot security checklist additions**: set `REGULAITOR_ENABLE_DOCS=0`, put
`REGULAITOR_AUDIT_DB` on the persistent volume, and rotate every key in §2 before
onboarding the first external tenant.

---

## §3 — HF Spaces

### §3.1 — Streamlit SDK variant (recommended for TFM)

1. Create a new Space at https://huggingface.co/new-space.
2. Choose **Streamlit SDK** + Python 3.11.
3. Connect to this GitHub repo OR upload via git push to the Space remote.
4. In the Space → **Settings → Repository secrets**, add each var from §2.
5. The Space auto-detects `src/regulaitor/ui_streamlit/app.py` and uses `.streamlit/config.toml` (port 7860).
6. First build: ~5 min (pip install + cold-start corpus rebuild ~15 min on first request).
7. Subsequent: ~5s cold + <1s warm.

### §3.2 — Docker SDK variant

1. Create Space → **Docker SDK**.
2. Add a `Dockerfile.huggingface` (HF expects port 7860 ENTRYPOINT):
   ```dockerfile
   FROM regulaitor:dev
   ENV APP_MODE=streamlit PORT=7860
   EXPOSE 7860
   ```
3. Push image to Docker Hub (or build in-Space using the project's `Dockerfile`).
4. Secrets same as §3.1.

### §3.3 — Persistent volume on HF + cold-start strategy

HF Spaces grants 16 GB persistent storage per Space. Mount path varies by plan:
- Free: `/data` writable; persists across restarts.
- Set `HF_HOME=/data/hf_cache` in Space secrets (BGE-M3 + reranker cache).

**LANCEDB_PATH — two valid strategies (pick ONE)**:

| Strategy | `LANCEDB_PATH` value | Cold-start | When |
|---|---|---|---|
| **Baked-in (recommended for TFM demo)** | `/app/corpus/indexes/regulaitor.lance` | ~5 min (image pull + warmup + BGE-M3 load) | Ship pre-built LanceDB in Docker image via Git LFS. v0.1.32 default. |
| **Build-on-first-run** | `/data/indexes` | ~15-30 min (often timeout on HF cpu-basic free tier) | Persistent volume; corpus re-builds on first cold-start, persists to `/data/indexes/chunks.lance/` for future restarts. |

The Dockerfile sets `LANCEDB_PATH=/data/indexes` as the ENV default (build-on-first-run). For the v0.1.32 H16 deploy, the HF Space env var **overrides** to `/app/corpus/indexes/regulaitor.lance` so the entrypoint detects the baked-in `chunks.lance/` and skips `rag_build`. **Use baked-in if you can ship the index via LFS**; otherwise the build-on-first-run path risks the 30-min HF Spaces hard limit.

---

## §4 — Render

1. Render → New → Web Service → Build from `Dockerfile`.
2. Choose Free plan (sleeps after 15 min idle).
3. Environment: add each var from §2.
4. Persistent disk: attach 10 GB at `/data`.
5. Healthcheck path: `/health`.
6. First build: ~20 min. Wake-from-sleep: ~30 s.

`render.yaml` (commit to repo for IaC):
```yaml
services:
  - type: web
    name: regulaitor-api
    runtime: docker
    dockerfilePath: ./Dockerfile
    plan: free
    healthCheckPath: /health
    envVars:
      - key: APP_MODE
        value: api
      - key: LANCEDB_PATH
        value: /data/indexes
      - key: HF_HOME
        value: /data/hf_cache
      - fromGroup: regulaitor-secrets
    disk:
      name: regulaitor-data
      mountPath: /data
      sizeGB: 10
```

---

## §5 — Fly.io

1. Install flyctl: `iwr https://fly.io/install.ps1 -useb | iex` (Windows).
2. `fly launch --no-deploy` (auto-generates `fly.toml` from Dockerfile).
3. Edit `fly.toml`:
   ```toml
   app = "regulaitor"
   primary_region = "mad"  # Madrid

   [build]
     dockerfile = "Dockerfile"

   [env]
     APP_MODE = "api"
     LANCEDB_PATH = "/data/indexes"
     HF_HOME = "/data/hf_cache"

   [[services]]
     internal_port = 8000
     protocol = "tcp"
     [[services.ports]]
       handlers = ["http"]
       port = 80
     [[services.ports]]
       handlers = ["tls", "http"]
       port = 443
     [services.http_checks]
       interval = "30s"
       method = "get"
       path = "/health"
       protocol = "http"

   [mounts]
     source = "regulaitor_data"
     destination = "/data"
   ```
4. Create volume: `fly volumes create regulaitor_data --size 10 --region mad`.
5. Set secrets: `fly secrets set ANTHROPIC_API_KEY=sk-... REGULAITOR_API_TOKEN=...`.
6. Deploy: `fly deploy`.

---

## §6 — Local Docker (dev / staging / reproducibility)

This project does NOT ship a `.env.example` (per user rule overriding CLAUDE.md §22.6). Create `.env` inline:

```bash
cat > .env <<'EOF'
ANTHROPIC_API_KEY=sk-ant-...
REGULAITOR_API_TOKEN=replace-with-token-urlsafe-32
# Optional:
# OPENAI_API_KEY=...
# GROQ_API_KEY=...
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
# LANGFUSE_HOST=...
# REGULAITOR_CORS_ORIGINS=https://yourapp.example.com
# LANCEDB_PATH=/data/indexes  # or /app/corpus/indexes/regulaitor.lance per §3.3
EOF

make docker-build
make docker-up
# API:       http://localhost:8000/health
# Streamlit: http://localhost:8501
```

Cold-start: 15-20 min on first up (entrypoint auto-runs `scripts.ingest --use-local-only` + `scripts.rag_build` + BGE-M3 + reranker download). See §7 for the exact phases.
Warm-start: <5s (volume `regulaitor-data` persists models + indexes; entrypoint detects existing `chunks.lance/` table dir and skips the build).

Tear down (keep data):
```bash
make docker-down
```

Tear down (delete corpus indexes — NUCLEAR):
```bash
make docker-clean
```

---

## §7 — Cold-start SLA + warm performance

| Phase | First time | Subsequent |
|---|---|---|
| Image build | 3-5 min | cached layers |
| Container startup | <5s | <5s |
| BGE-M3 download | 2-3 min (~2 GB to `/data/hf_cache`) | cached |
| Reranker download | 1-2 min (~600 MB) | cached |
| LanceDB corpus build | 10-15 min (4 corpora × ~250 chunks/corpus) | cached |
| `/health` first response | 15-20 min | <1s |
| `/ask` query (warm) | 15-60 s | varies by retrieval+LLM |

**How the cold-start corpus build is triggered** (v0.1.26): `docker-entrypoint.sh` checks for `${LANCEDB_PATH:-/data/indexes}/chunks.lance/` (LanceDB's actual table dir for table `chunks`, per `src/regulaitor/rag/store.py::TABLE_NAME`) at container start; if absent, it runs `scripts.ingest --use-local-only` + `scripts.rag_build` BEFORE exec'ing uvicorn/streamlit. This is idempotent: subsequent restarts find the existing table dir and skip the build (the v0.1.26 entrypoint marker uses the LanceDB-table-name suffix so it works under both the prod `LANCEDB_PATH=/data/indexes` and the dev fallback `corpus/indexes/regulaitor.lance`). The Dockerfile bakes `corpus/processed/` (parsed JSON inputs) + `scripts/` into the image, so the build needs no network beyond the BGE-M3 + reranker downloads to `${HF_HOME:-/data/hf_cache}` (use a persistent volume to cache these).

**Implication for HF Spaces / Render:** First user request will block for the full cold-start window (~15-20 min). The container does NOT serve `/health` 200 until uvicorn starts, which is AFTER the cold-start build completes. For platforms with HTTP-readiness timeouts (Render's default is 5 min), pre-warm the volume by running `docker run --rm -v regulaitor-data:/data regulaitor:dev /bin/bash -c "/usr/local/bin/docker-entrypoint.sh && exit 0"` locally OR use a longer health-check `start_period` (compose: 1200s; Render: configurable).

---

## §8 — Monitoring (optional)

- **LangFuse** (free SaaS): set `LANGFUSE_*` envs; traces appear in dashboard with case_id + latency p50/p95 + cost per case.
- **External watchdog**: GitHub Action cron pings `/health` every 15 min; alerts on failure to your email.
- **Streamlit access logs**: HF Spaces / Render / Fly.io all surface stdout in their dashboards.

---

## §9 — Rollback

If a deploy regresses behavior:

```bash
# Local: revert to prior tag
git checkout v0.1.25-auditor-partial-routing
make docker-build && make docker-up
```

```bash
# HF Spaces: redeploy from the prior commit via the Space's UI
```

```bash
# Render: redeploy from prior commit via dashboard
```

```bash
# Fly.io: roll back image
fly releases  # list
fly deploy --image <prior-image-id>
```

---

## §10 — Verification checklist (use before public announce)

- [ ] `/health` returns 200 with valid `case_id` echoed back
- [ ] `/ask` returns a citation-validated response for a known-good query (e.g., "¿Cuáles son las obligaciones del RGPD para PYMEs?")
- [ ] CORS headers present if `REGULAITOR_CORS_ORIGINS` is set
- [ ] Streamlit UI loads both tabs (Pregunta / Analiza documento) + disclaimer banner visible
- [ ] LangFuse dashboard shows the test query (if observability enabled)
- [ ] Cold-start SLA matches §7 expectations (no surprises)
- [ ] No `.env` accidentally pushed to platform (verify in platform UI)
- [ ] Rate limit triggers on >30 requests/min/token (per slowapi config)

---

## §11 — Carry-forwards from v0.1.25 close

- chat-016 all-blocked routing edge case (1/30 cohort) — Design D HX-deferred per CLAUDE.md §27.
- Citation_precision (-0.63 aspirational) — HIGH §6 risk; HX post-TFM only.
- Severity_match (-0.40 aspirational) — Analyst v1.6 calibration if user feedback shows it matters in production; HX otherwise.
- Cross-vendor judge migration (Haiku → GPT-4o-mini or Llama-3.3-70b) — HX per ADR-0021 D3.

These do NOT block H16 deploy.

---

## §12 — Sovereign profile (EU, zero US processor)

For an EU-sovereign deploy (founder constraints C1 self-hosted inference + C3
EU-sovereign), route the Analyst to an EU-hosted open model (Mistral) and omit
every US key. Full spike/design + gap analysis + cost regimes: `docs/sovereign_deploy.md`.

The env bundle (add to the `.env`; **never** create `.env.example`):

```bash
REGULAITOR_ANALYST_MODEL_CHOICE=self_hosted
REGULAITOR_SELFHOST_BASE_URL=https://api.mistral.ai/v1   # or your own vLLM endpoint (self-host GPU)
REGULAITOR_SELFHOST_API_KEY=<Mistral La Plateforme key>
REGULAITOR_SELFHOST_MODEL=mistral-small-latest
REGULAITOR_ANALYST_PROMPT_VERSION=v1.6                   # required with the open model (citation-format discipline)
REGULAITOR_AUDIT_DB=/data/audit.db                       # traceability = the compliance selling point
# OMIT ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY  → no US model can be invoked
```

Guarantees (CI-enforced): the `self_hosted` mode **never falls back to a US
model** (`test_self_hosted_does_not_fall_back_to_us_model`); §6 `citation/validator.py`
is byte-unchanged under any Analyst model (citation validation is deterministic).
Sovereignty proof for a partner: `/health` shows lancedb ok **without**
`anthropic_key`; the audit trail stores hashes not text (§18.8).

Council under the sovereign profile (P4.1): with a judge's provider key absent the
Council **skips** that judge (zero doomed calls, DEBUG log) instead of attempting +
swallowing it. A skipped judge degrades conservatively (the Auditor's mechanical
verdict stands; §6 unaffected). See `docs/sovereign_deploy.md` §4 G2.

---

**End of H16 Deployment Runbook.**
