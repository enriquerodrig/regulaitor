# syntax=docker/dockerfile:1.7

# ============================================================
# Stage 1: builder — resolve dependencies with uv
# ============================================================
# Note (v0.1.26, §22.22 carry-forward from v0.1.22 ADR-0029):
#   This Dockerfile has been tested on Linux hosts and works correctly.
#   On Windows Docker Desktop, you may encounter SSL certificate verification
#   errors when pulling packages (CRYPT_E_NO_REVOCATION_CHECK / UnknownIssuer).
#   Workaround: build on a Linux host, or use Docker on WSL2 with native Linux kernel.
#   Root cause: Windows Docker Desktop's truststore integration with PyPI / GHCR.
#
FROM python:3.11-slim-bookworm AS builder

# Install uv
RUN pip install --no-cache-dir uv==0.4.18

WORKDIR /app

# Copy lock + manifest first for layer caching
COPY pyproject.toml uv.lock ./

# Install deps into .venv (uv default location)
# --frozen: don't update uv.lock; --no-install-project: deps only, not the package itself yet
RUN uv sync --frozen --no-install-project --no-dev

# Now copy source + install project
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# ============================================================
# Stage 2: runtime — minimal image with .venv copied over
# ============================================================
FROM python:3.11-slim-bookworm AS runtime

# Non-root user for security
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# System deps for PDF processing + HF model downloads + SSL verification
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy .venv + source from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser corpus/manifests/ ./corpus/manifests/
COPY --chown=appuser:appuser corpus/processed/ ./corpus/processed/
# H16 deploy: ship pre-built LanceDB index in image (~76 MB) for HF Spaces
# Docker SDK cold-start reduction. Eliminates the entrypoint's `scripts.rag_build`
# step (10-15 min CPU on first request). Operator must override LANCEDB_PATH
# to point at this baked-in location for the runtime to use it; otherwise the
# default LANCEDB_PATH=/data/indexes wins and the entrypoint rebuilds.
# Set in HF Space env: LANCEDB_PATH=/app/corpus/indexes/regulaitor.lance.
COPY --chown=appuser:appuser corpus/indexes/regulaitor.lance/ ./corpus/indexes/regulaitor.lance/

# uv must be in PATH for entrypoint (consolidated PATH set in next ENV block)
RUN pip install --no-cache-dir uv==0.4.18

# HF model cache location (persistent volume mount target in compose/HF Spaces)
ENV HF_HOME=/data/hf_cache \
    LANCEDB_PATH=/data/indexes \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /data/hf_cache /data/indexes && chown -R appuser:appuser /data

USER appuser

# Default to API mode; override with -e APP_MODE=streamlit
# H16 HF Spaces deploy expects port 7860 + APP_MODE=streamlit; override
# both via Space env vars (Settings → Variables and secrets):
#   APP_MODE=streamlit
#   PORT=7860
#   LANCEDB_PATH=/app/corpus/indexes/regulaitor.lance  (use baked-in v0.1.30 index)
#   ANTHROPIC_API_KEY=<your key>
ENV APP_MODE=api \
    PORT=8000

EXPOSE 8000 7860

# start-period generous to cover cold-start corpus build (~15-20 min) when
# /data/indexes is empty; warm restarts find the index and start <5s.
# PORT fallback to 8000 in case ENV is overridden to empty at runtime.
HEALTHCHECK --interval=30s --timeout=10s --start-period=1200s --retries=3 \
    CMD curl --fail "http://localhost:${PORT:-8000}/health" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
