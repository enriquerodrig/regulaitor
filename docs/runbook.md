# RegulAItor Operational Runbook

Audience: developer or operator running RegulAItor locally or in CI.
Scope: LangFuse observability (H11) + operational procedures for the three most
common alert conditions.

---

## 1. LangFuse Setup

LangFuse tracing is **entirely optional**. Without the three `LANGFUSE_*` env vars
the system behaves identically — the SDK is not even imported, tracing is a true
no-op, and the LangFuse dashboard stays empty. No code path changes, no latency
penalty, no errors. See section 4 for the no-op contract.

### Step-by-step

1. Create a free account at <https://cloud.langfuse.com>.
2. Create a new project (name it `regulaitor` or similar).
3. Open **Settings → API Keys** and create a new key pair.
4. Copy the **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`).
5. Add the three vars to your local `.env` (same file that holds `ANTHROPIC_API_KEY`):

   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-<your-public-key>
   LANGFUSE_SECRET_KEY=sk-lf-<your-secret-key>
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

6. Restart the pipeline (`make serve`, `make serve-api`, or your Python process).
   On the next query or redteam run, traces will appear in the LangFuse UI.

**No other steps required.** There is no migration, no schema change, and no
restart penalty if the vars are later removed.

---

## 2. What the Dashboard Shows

When enabled, LangFuse receives **metadata only** — raw query text, document
content, and citation strings never leave the process (redaction allowlist
enforced at `src/regulaitor/observability/langfuse_client.py`).

### Per-trace data (live, H11)

Each chat or document turn produces one LangFuse trace (`chat_turn` or
`document_turn`) with sub-spans for the pipeline stages:

| Span | Metadata emitted |
|------|-----------------|
| `retriever` | `corpus`, `language`, `n_chunks_returned`, `retriever_ms` |
| `analyst` | `tokens_in`, `tokens_out`, `cost_eur`, `retry_triggered` |
| `auditor` | `verdict`, `reason_code`, `n_citations_checked` |
| `sanitizer` (doc mode) | `hit` (bool), `pattern_name`, `blocked_category` |
| `injection` (doc mode) | `hit` (bool), `pattern_name` |

Root trace metadata: `case_id`, `corpus`, `language`, `verdict` / `document_verdict`.

From these spans you can read **per-query latency** (the clean product SLA —
see section 3), cost per turn, and verdict distribution directly in the
LangFuse trace list and the built-in dashboard charts.

### Custom scores (H11)

**Live now:** `block_rate` — emitted after each redteam run (full or smoke) when
LangFuse is enabled. The value is the fraction of attacks blocked in that run.

**Deferred to H15:** `citation_recall` and `verdict_match`. These numbers already
exist in `evals/reports/latest.md` and `docs/technical_decisions_log.md` §H10.
They are not wired to LangFuse in H11 because pushing historical batch numbers
to LangFuse adds no analytical value until H15 implements live calibration loops.
Do not expect these scores in the LangFuse dashboard until H15.

### H17 note

Dashboard screenshots for the academic thesis (memoria) will be captured at
H17, once the system has accumulated real production traces over the advanced
milestone track.

---

## 3. Latency Interpretation

**Two latency figures exist in this project. They measure different things and
must not be conflated.**

### Per-query latency (product SLA) — read from LangFuse

The per-span latency shown in LangFuse is the real, per-query latency a user
experiences: retriever (~1–3 s) + Analyst LLM call (~10–40 s) + Auditor (ms).
**Typical end-to-end: 15–60 s.** This is the number to cite when discussing
product performance.

CLAUDE.md §17 #7 target: p95 ≤ 12 s (MVP), ≤ 8 s (advanced). The current
real-query range (~15–60 s) **exceeds the 12 s target**. This is a known,
documented gap. Latency optimisation (streaming, `max_tokens` reduction,
parallel retriever, multi-LLM router with a fast model) is deferred to H12/H15.
Do not claim the target is met.

### Batch eval latency (`latency_p95_ms` ≈ 572 s) — NOT the product SLA

The `latency_p95_ms` figure in `evals/reports/latest.md` (~572 s) is a
**batch-under-rate-limit artifact**: 40 sequential gold-set cases running
against the Anthropic API with tenacity retry backoff in a single process.
It reflects queue contention and exponential back-off, not how fast a single
query runs for a user. **Never cite this number as the product SLA.**

---

## 4. Operational Procedures

### (a) `block_rate` drops below 0.90

Gate §16.2 #4 requires `block_rate ≥ 0.90` on the redteam smoke set.

1. Run the smoke set immediately to confirm the drop:

   ```bash
   make redteam-smoke
   ```

   This runs only the deterministic doc-mode attacks (no LLM, $0, ~30 s).
   Report is written to `redteam/reports/latest.md`.

2. Check recent commits to `src/regulaitor/security/` (sanitizer categories,
   injection patterns, allowlist). A regression there is the most common cause.

3. Check recent commits to `src/regulaitor/agents/prompts/` — a prompt change
   that softens the Auditor verdict criteria can lower block rate on E2E attacks.

4. If the drop is only on E2E attacks (not smoke), run the full suite:

   ```bash
   make redteam
   ```

   Full run: 50 attacks, ~$2.35 Anthropic credit. Results in
   `redteam/reports/latest.md`.

5. Do not merge the offending commit until `block_rate ≥ 0.90` is restored.

### (b) Latency p95 rises (per LangFuse span data)

When LangFuse is enabled, per-span latencies are visible in the trace list.
If the analyst or retriever span latency rises significantly:

1. Check the [Anthropic status page](https://status.anthropic.com) — elevated
   API latency is frequently external.

2. Check the retriever model cache: `BGE-M3` and `bge-reranker-v2-m3` are
   loaded from `~/.cache/huggingface/`. If the cache was evicted or the model
   moved to CPU, first-query latency will be high.

3. Check recent prompt changes under `src/regulaitor/agents/prompts/`. A prompt
   that causes longer completions (more tokens out) increases analyst latency.
   Prompts are versioned (`<agent>/<role>.vN.M.md`) — diff the most recent
   version bump.

4. Check the `retry_triggered` rate in LangFuse analyst spans. A non-zero rate
   means the Analyst is re-invoking the LLM on citation failures (H4 retry
   mechanism). A high rate multiplies cost and latency.

### (c) Cost spikes

Unexpected credit consumption typically comes from one of three sources:

1. **Analyst retry loop** — the `retry_triggered` metadata key in LangFuse
   analyst spans shows whether the H4 citation-failure retry fired. High retry
   rates mean the Analyst is calling the LLM 2× per turn. Investigate by
   checking citation_recall in the latest eval report; a sharp drop in recall
   often coincides with retry spikes.

2. **Unexpected eval or redteam run** — `make eval` costs ~$2.50–$3.50 and
   `make redteam` costs ~$2.35. Confirm no automated CI job triggered these
   unintentionally. The CI `ci.yml` workflow only runs `make redteam-smoke`
   (deterministic, $0); full runs are not automated.

3. **Redteam per-attack timeout / hung run** — a silent Anthropic API hang was
   encountered in H9 (cost ~$1.50 wasted in an incomplete run). H11 addresses
   this with per-attack daemon-thread timeouts. Two env vars control the limits:

   | Env var | Default | Applies to |
   |---------|---------|-----------|
   | `REGULAITOR_REDTEAM_TIMEOUT_CHAT` | `300` s | chat-mode attacks |
   | `REGULAITOR_REDTEAM_TIMEOUT_DOC` | `900` s | document-mode E2E attacks |

   A timed-out attack is recorded as outcome `timeout` with `blocked=False`,
   correctly dragging `block_rate` down (safe direction). The abandoned daemon
   thread does not block process exit. If you see many `timeout` outcomes in
   `redteam/reports/latest.md`, the API may be degraded — check Anthropic status
   before re-running. Lower the timeout vars only if normal attacks are reliably
   faster than the defaults.

---

## 5. Reproducibility

### Canonical `make` sequence

From a fresh clone (CLAUDE.md §20):

```bash
make setup       # install deps via uv + pre-commit hooks
make lint        # ruff + black --check + mypy
make test        # pytest
make ingest      # parse PDF corpora into manifests + processed/
make rag-build   # chunk + embed + populate LanceDB (~3 GB model download on first run)
make serve       # Streamlit MVP UI (http://localhost:8501)
make serve-api   # FastAPI on http://localhost:8000 (requires REGULAITOR_API_TOKEN in .env)
make eval        # full evaluation (~$2.50 Anthropic credit; populates judge cache)
make redteam     # full red team (50 attacks, ~$2.35 Anthropic credit)
```

`make docker` and `make deploy` are placeholders (H16).

### Windows note

`make` is not bundled with Git for Windows. Either install GNU Make
(`choco install make` or `scoop install make`) or run the underlying
`uv run ...` commands directly — each Makefile target is one line.
CI runs on Ubuntu (make always available). The gate §16.2 #1
reproducibility check is verified on Linux per push.

See the README Quickstart for the full Windows guidance.

### Secret scanning

Secret scanning is enforced in CI via the `Security` job in
`.github/workflows/ci.yml` (gitleaks v8.21.2 on Linux).

The local pre-commit gitleaks hook cannot run on the Windows dev box
(the hook is Go-based; no Go toolchain is installed). Local commits on
Windows skip **only** the gitleaks hook via the `SKIP=gitleaks` env
prefix — all other pre-commit hooks run (end-of-file-fixer,
trailing-whitespace, ruff, black, detect-private-key, etc.). This is a
deliberate, user-approved arrangement. Never use `--no-verify`.

```powershell
# Windows commit pattern (skip only gitleaks):
$env:SKIP = "gitleaks"; git commit -m "your message"
```

On Linux/macOS (and in CI) gitleaks runs unconditionally as a pre-commit
hook and as a CI step. Any secret found blocks the merge.
