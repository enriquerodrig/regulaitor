#!/usr/bin/env bash
set -euo pipefail

# v0.1.26 H16 deploy-prep: cold-start corpus build hook.
# On first container start, if the LanceDB index isn't present at LANCEDB_PATH
# (defaults to /data/indexes per Dockerfile ENV), run ingest + rag-build. This is
# idempotent: subsequent starts find the index file and skip the build. Documented
# SLA: ~15-20 min on first start (LanceDB build + BGE-M3 + reranker download);
# <5s warm. See docs/H16_DEPLOY.md §7.
INDEX_DIR="${LANCEDB_PATH:-/data/indexes}"
# LanceDB always creates the table dir as <DB>/<TABLE_NAME>.lance/; with
# TABLE_NAME="chunks" (src/regulaitor/rag/store.py) the table dir is chunks.lance.
# Using this marker works for BOTH the prod env path (LANCEDB_PATH=/data/indexes
# → /data/indexes/chunks.lance/) AND the dev fallback (corpus/indexes/regulaitor.lance
# → corpus/indexes/regulaitor.lance/chunks.lance/). Marker drift is pinned by
# tests/unit/rag/test_store_lancedb_path_env.py::test_entrypoint_marker_matches_store_table_name.
INDEX_MARKER="${INDEX_DIR}/chunks.lance"

cd /app

if [ ! -d "${INDEX_MARKER}" ]; then
  echo "[entrypoint] Cold-start: corpus index not found at ${INDEX_MARKER}; building (~15-20 min)..."
  # Deep-review I7 fix: fail-fast on cold-start build errors. Previous version
  # used `|| { echo ...; }` which swallowed the exit code → container started
  # with empty LanceDB + /health returned 503 with no upstream signal to
  # debug. Orchestrators (HF Spaces, docker-compose, k8s) now get a failed-
  # start event and the traceback stays visible.
  uv run python -m scripts.ingest --corpus all --lang all --use-local-only || {
    echo "[entrypoint] FATAL: ingest failed during cold-start; aborting container." >&2
    exit 1
  }
  # --force-rebuild required: the baked-in corpus/manifests/ have chunks
  # already listed (from the original build that produced the now-missing
  # LFS lance index), so rag_build's default skip-if-manifest-shows-chunks
  # logic would SKIP all 1569 articles and leave /data/indexes empty.
  # Force-rebuild ensures the manifest-vs-index inconsistency is resolved
  # by actually re-chunking + re-embedding into the empty LANCEDB_PATH.
  uv run python -m scripts.rag_build --corpus all --lang all --force-rebuild || {
    echo "[entrypoint] FATAL: rag-build failed during cold-start; aborting container." >&2
    exit 1
  }
  echo "[entrypoint] Cold-start build complete; proceeding to serve."
else
  echo "[entrypoint] Warm-start: existing corpus index found at ${INDEX_MARKER}."
fi

MODE="${APP_MODE:-api}"

case "$MODE" in
  api)
    exec uv run uvicorn regulaitor.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  streamlit)
    exec uv run streamlit run src/regulaitor/ui_streamlit/app.py \
      --server.port="${PORT:-7860}" \
      --server.address=0.0.0.0 \
      --server.headless=true
    ;;
  *)
    echo "ERROR: APP_MODE must be 'api' or 'streamlit', got '$MODE'" >&2
    exit 1
    ;;
esac
