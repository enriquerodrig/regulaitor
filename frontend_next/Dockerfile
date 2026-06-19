# syntax=docker/dockerfile:1
# RegulAItor frontend (Fase 5, HX) — Next.js 16 standalone, multi-stage.
# Self-hosted alongside the FastAPI `api` service (see ../docker-compose.yml).
# Debian (bookworm-slim) base: node:22-alpine + `npm ci` hits npm's
# "Exit handler never called!" bug; bookworm-slim installs reliably.

# --- deps: install all deps (incl. dev, needed to build) ---------------------
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# --- builder: produce the standalone server ----------------------------------
FROM node:22-bookworm-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- runner: minimal runtime, non-root --------------------------------------
FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# REGULAITOR_API_URL is provided at runtime (compose / .env); defaults to the
# in-compose backend if unset (see src/lib/api-server.ts).

# Standalone server + static assets + public/ (traced prod deps only). The
# node:22 image ships a non-root `node` user (uid 1000) — run as it.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node
EXPOSE 3000

# /login is public (no auth gate) — a cheap liveness probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
